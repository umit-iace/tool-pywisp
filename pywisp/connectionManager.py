# -*- coding: utf-8 -*-
"""
Management of the connections to the rig: establishing and closing them, sending data,
the heartbeat and the menu with the connection settings.
"""
import logging
import time

import serial.tools.list_ports
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .connection import Connection, SerialConnection, SocketConnection
from .min import CONTROL_FRAME_ID, STATUS_FRAME_ID, Control, RigStatus, controlFrame, syncFrame
from .registry import getRegisteredConnections
from .widgets.dialogs import DataTcpIpDialog

__all__ = ["ConnectionManager"]


class ConnectionManager(QObject):
    """
    Holds an instance of every registered connection while connected.

    All connections are established in the background, the manager is connected once all of
    them are open. If one of them fails or drops, all of them are closed.

    Rigs that send status frames (tool-libs `Experiment::enableStatus`) are watched: the manager
    reports whether they respond and checks that they received all parameters of a start.
    Rigs without status frames are not checked.
    """
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'

    #: the new state, one of :attr:`DISCONNECTED`, :attr:`CONNECTING` and :attr:`CONNECTED`
    stateChanged = pyqtSignal(str)
    #: frames received by the connection with the given name
    framesReceived = pyqtSignal(object, str)
    #: an established connection has been closed by itself, e.g. by the rig
    connectionLost = pyqtSignal()
    #: the status of the rig of the given connection changed or it stopped responding
    rigStatusChanged = pyqtSignal(str)
    #: all rigs confirmed the start with the parameters that were sent
    startConfirmed = pyqtSignal()
    #: a rig did not confirm the start or received other parameters, with the reason
    startFailed = pyqtSignal(str)
    #: all rigs confirmed the parameters sent during the run with the given sync id
    syncConfirmed = pyqtSignal(int)
    #: a rig did not confirm the parameters of the given sync id or received others, with the reason
    syncFailed = pyqtSignal(int, str)

    #: [s] a rig that sent status frames before and then none for this long does not respond
    statusTimeout = 1.0
    #: [ms] time a rig has to confirm a start
    startTimeout = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        # registered connections by name, the instance is stored as 'inst' while connected
        self.connections = {name: {'cls': cls} for name, cls in getRegisteredConnections().items()}
        for name in self.connections:
            self._logger.info(f"Found Connection: {name}")
        if not self.connections:
            self._logger.error("No Connections found!")
        self.state = self.DISCONNECTED
        # names of the connections that are still being established
        self._pendingConnections = set()

        self.heartbeatTimer = QTimer(self)
        self.heartbeatTimer.timeout.connect(self.heartbeat)

        # last status of the rigs that send one, by connection name: (RigStatus, receive time)
        self.rigStatus = {}
        # rigs reported as not responding
        self._staleReported = set()
        self._statusTimer = QTimer(self)
        self._statusTimer.timeout.connect(self._checkStatusAge)
        self._statusTimer.start(250)
        # pending start check, by connection name: (startSeq before, expected count, crc)
        self._expectedStart = {}
        self._startTimer = QTimer(self)
        self._startTimer.setSingleShot(True)
        self._startTimer.timeout.connect(self._onStartTimeout)
        # pending sync checks by sync id: ({connection name: (expected count, crc)}, deadline)
        self._pendingSyncs = {}
        self._syncId = 0

    @property
    def isConnected(self):
        return self.state == self.CONNECTED

    def _setState(self, state):
        if state != self.state:
            self.state = state
            self.stateChanged.emit(state)

    def connectAll(self):
        """
        Establishes all connections in the background, :attr:`stateChanged` reports the result.
        """
        if not self.connections:
            self._logger.error("No connections registered!")
            return
        if self.state != self.DISCONNECTED:
            return

        self._pendingConnections = set(self.connections)
        self._setState(self.CONNECTING)
        for name, conn in self.connections.items():
            try:
                connInstance = conn['cls']()
            except Exception:
                self.disconnectAll()
                raise
            # bind name as default argument, otherwise all lambdas would see the last name
            connInstance.receivedFrames.connect(lambda frames, name=name: self._onFrames(frames, name))
            connInstance.finished.connect(self._onFinished)
            connInstance.opened.connect(lambda ok, name=name: self._onOpened(name, ok))
            conn['inst'] = connInstance
            connInstance.openAsync()

    def _onOpened(self, name, ok):
        """ result of establishing the connection with the given name """
        if name not in self._pendingConnections:
            return
        if not ok:
            self._logger.warning(f"No connection for {name} established! Check your settings!")
            # do not leave the other connections half open
            self.disconnectAll()
            return
        self._logger.info(f"Connection for {name} established!")
        self._pendingConnections.discard(name)
        if not self._pendingConnections:
            self._setState(self.CONNECTED)

    def _onFinished(self):
        """ a connection has been closed, by the manager or by itself """
        if self.state == self.CONNECTED:
            self.connectionLost.emit()
            self.disconnectAll()

    def disconnectAll(self):
        """ closes all connections, also those that are still being established """
        self._pendingConnections.clear()
        self.heartbeatTimer.stop()
        self.cancelStartCheck()
        self.cancelSyncChecks()
        self.rigStatus.clear()
        self._staleReported.clear()
        # the state is changed first, so connections closing themselves are not reported as lost
        self._setState(self.DISCONNECTED)
        for conn in self.connections.values():
            inst = conn.pop('inst', None)
            if inst is not None:
                inst.close()

    def shutdown(self, timeout=5000):
        """
        Closes all connections and waits for those that are still being established,
        e.g. before the application quits.

        :return: `True` if all of them have ended
        """
        self.disconnectAll()
        # connections that are still being established end with their connect timeout
        if not Connection.waitForAborted(timeout):
            self._logger.warning("Aborted connections did not end in time")
            return False
        return True

    def write(self, data):
        """
        Sends the given data to its connection, control frames go to all connections.
        :param data: dict with the keys 'id', 'msg' and 'connection'
        """
        if data['id'] == CONTROL_FRAME_ID:
            # control frames go to all rigs
            targets = list(self.connections.values())
        else:
            conn = self.connections.get(data['connection'])
            if conn is None:
                self._logger.error(f"Unknown connection '{data['connection']}'!")
                return
            targets = [conn]

        for conn in targets:
            if 'inst' in conn:
                conn['inst'].writeData(data)

    def heartbeat(self):
        self.write(controlFrame(Control.HEARTBEAT))

    # status of the rigs

    def _onFrames(self, frames, name):
        """ takes the status frames out, passes the others on """
        data = []
        for frame in frames:
            if frame.id != STATUS_FRAME_ID:
                data.append(frame)
                continue
            status = RigStatus.fromPayload(frame.payload)
            if status is None:
                self._logger.warning(f"{name}: unknown status frame {bytes(frame.payload).hex()}")
                continue
            self._onStatus(name, status)
        if data:
            self.framesReceived.emit(data, name)

    def _onStatus(self, name, status):
        last = self.rigStatus.get(name)
        if last is not None and status.uptime < last[0].uptime:
            self._logger.warning(f"{name}: the rig has been restarted")
        self.rigStatus[name] = (status, time.monotonic())
        # the uptime changes with every frame, only report what is shown
        if (last is None or name in self._staleReported
                or (last[0].running, last[0].flags) != (status.running, status.flags)):
            self._staleReported.discard(name)
            self.rigStatusChanged.emit(name)
        self._checkStart(name, status)
        self._checkSync(name, status)

    def _isStale(self, received):
        return time.monotonic() - received > self.statusTimeout

    def _checkStatusAge(self):
        for name, (_, received) in self.rigStatus.items():
            if self._isStale(received) and name not in self._staleReported:
                self._staleReported.add(name)
                self.rigStatusChanged.emit(name)
        now = time.monotonic()
        for syncId, (names, deadline) in list(self._pendingSyncs.items()):
            if now > deadline:
                del self._pendingSyncs[syncId]
                self.syncFailed.emit(syncId, f"{', '.join(names)}: no confirmation of the parameters "
                                             f"within {self.startTimeout} ms")

    def isResponding(self, name):
        """
        :return: `True` if the rig sends status frames, `False` if it stopped,
            `None` if it never sent one (no status support)
        """
        entry = self.rigStatus.get(name)
        if entry is None:
            return None
        return not self._isStale(entry[1])

    def statusFlagNames(self, name):
        """ names of the status bits of the rig, from the `statusFlags` list of the connection class """
        return list(getattr(self.connections[name]['cls'], 'statusFlags', []))

    # check of the start

    def expectStart(self, expected):
        """
        Checks the next start of the rigs that send status frames.

        :param expected: (number, CRC32) of the frames sent before the start command by
            connection name, see :func:`pywisp.min.frameCrc`
        :return: `True` if a rig is checked, :attr:`startConfirmed` or :attr:`startFailed` follow
        """
        self.cancelStartCheck()
        for name, (status, received) in self.rigStatus.items():
            if self._isStale(received):
                continue
            # the start command goes to all rigs, also to those without parameters
            count, crc = expected.get(name, (0, 0))
            self._expectedStart[name] = (status.startSeq, count, crc)
        if not self._expectedStart:
            return False
        self._startTimer.start(self.startTimeout)
        return True

    def cancelStartCheck(self):
        self._expectedStart.clear()
        self._startTimer.stop()

    def _checkStart(self, name, status):
        if name not in self._expectedStart:
            return
        seqBefore, count, crc = self._expectedStart[name]
        if status.startSeq == seqBefore or not status.running:
            return
        del self._expectedStart[name]
        if (status.startCount, status.startCrc) != (count, crc):
            self.cancelStartCheck()
            self.startFailed.emit(f"{name}: the rig received {status.startCount} frames with "
                                  f"CRC {status.startCrc:08x} instead of {count} frames with CRC {crc:08x}")
            return
        if not self._expectedStart:
            self._startTimer.stop()
            self.startConfirmed.emit()

    # check of parameters sent during the run

    def sync(self, expected):
        """
        Sends a sync command after parameters sent during the run, the rigs that support it confirm
        what they received since the last control frame.

        :param expected: (number, CRC32) of the frames sent since the last control frame by
            connection name, see :func:`pywisp.min.frameCrc`
        :return: the sync id, :attr:`syncConfirmed` or :attr:`syncFailed` follow with it,
            `None` if no rig supports sync commands (nothing is sent then)
        """
        names = {}
        for name, (status, received) in self.rigStatus.items():
            if status.syncId is None or self._isStale(received):
                continue
            # the sync command goes to all rigs, also to those without parameters
            names[name] = expected.get(name, (0, 0))
        if not names:
            return None
        # ids 1..255, the rig reports 0 before the first sync
        self._syncId = self._syncId % 255 + 1
        self._pendingSyncs[self._syncId] = (names, time.monotonic() + self.startTimeout / 1000)
        self.write(syncFrame(self._syncId))
        return self._syncId

    def cancelSyncChecks(self):
        self._pendingSyncs.clear()

    def _checkSync(self, name, status):
        entry = self._pendingSyncs.get(status.syncId)
        if entry is None or name not in entry[0]:
            return
        count, crc = entry[0].pop(name)
        if (status.syncCount, status.syncCrc) != (count, crc):
            del self._pendingSyncs[status.syncId]
            self.syncFailed.emit(status.syncId, f"{name}: the rig received {status.syncCount} frames with CRC "
                                                f"{status.syncCrc:08x} instead of {count} frames with CRC {crc:08x}")
            return
        if not entry[0]:
            del self._pendingSyncs[status.syncId]
            self.syncConfirmed.emit(status.syncId)

    def _onStartTimeout(self):
        names = ', '.join(self._expectedStart)
        self._expectedStart.clear()
        self.startFailed.emit(f"{names}: no confirmation of the start within {self.startTimeout} ms")

    def startHeartbeat(self, interval):
        """ sends a heartbeat every `interval` ms, 0 disables it """
        if interval:
            self.heartbeatTimer.start(int(interval))

    def stopHeartbeat(self):
        self.heartbeatTimer.stop()

    # menu with the settings of the connections

    def fillMenu(self, menu, parentWidget=None):
        """
        Adds the settings of all connections to the given menu.
        :param parentWidget: parent of the dialogs
        """
        serialCnt = 0
        for name, conn in self.connections.items():
            cls = conn['cls']
            if issubclass(cls, SerialConnection):
                serialMenu = menu.addMenu(name)
                self._fillSerialMenu(serialMenu, cls.settings)
                if cls.settings['port'] == '':
                    self.setDefaultComPort(cls.settings, serialCnt)
                serialCnt += 1
            elif issubclass(cls, SocketConnection):
                actTcp = menu.addAction(name)
                actTcp.triggered.connect(lambda _, settings=cls.settings: self.editSocketSettings(settings, parentWidget))
            else:
                self._logger.warning("Cannot handle the connection type!")
            menu.addSeparator()

    def editSocketSettings(self, settings, parentWidget=None):
        """ edit ip and port with a dialog """
        ip, port, ok = DataTcpIpDialog.getData(parent=parentWidget, ip=settings['ip'], port=settings['port'])
        if ok:
            settings['ip'] = ip
            settings['port'] = port

    def _fillSerialMenu(self, serialMenu, settings):
        # port
        portMenu = serialMenu.addMenu("Port")
        portMenu.aboutToShow.connect(lambda: self.getComPorts(settings, portMenu))

        # baud
        baudMenu = serialMenu.addMenu("Baud")
        baudMenu.aboutToShow.connect(lambda: self.getBauds(settings, baudMenu))

        return serialMenu

    def getBauds(self, settings, connMenu):
        """
        Sets the baud rate in serial connection menu
        :param settings: serial connection settings
        :param connMenu: serial connection menu
        """

        def setBaud(baud):
            def fn():
                settings['baud'] = baud

            return fn

        baud = int(settings['baud'])
        connMenu.clear()
        for _baud in SerialConnection.supportedBaudrates:
            # owned by the menu, so clear() deletes it
            baudAction = connMenu.addAction(str(_baud))
            baudAction.setCheckable(True)
            baudAction.setChecked(_baud == baud)
            baudAction.triggered.connect(setBaud(_baud))

    def setDefaultComPort(self, settings, cnt):
        """
        Sets the default port in given connection settings if an Arduino can found. If more than one Arduino can found,
        the counter describes the connection number.
        :param settings: serial connection settings
        :param cnt: counter for serial connection
        """
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]

            if len(arduinoPorts) > cnt:
                settings['port'] = arduinoPorts[cnt]
            else:
                self._logger.warning("Can't set comport for Arduino automatically! Set the port manually!")
        else:
            self._logger.warning("No ComPorts for Arduino available, connect a device!")

    def getComPorts(self, settings, connMenu):
        """
        Fills the port menu of a serial connection with the available ports
        :param settings: serial connection settings
        :param connMenu: port menu
        """

        def setPort(port):
            def fn():
                settings['port'] = port

            return fn

        port = settings['port']
        connMenu.clear()
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            if port == '':
                arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]
                if len(arduinoPorts) != 0:
                    port = arduinoPorts[0]
                    settings['port'] = port
            for p in comPorts:
                # owned by the menu, so clear() deletes it
                portAction = connMenu.addAction(p.device)
                portAction.setCheckable(True)
                portAction.setChecked(p.device == port)
                portAction.triggered.connect(setPort(p.device))
        else:
            noAction = connMenu.addAction("(None)")
            noAction.setEnabled(False)
