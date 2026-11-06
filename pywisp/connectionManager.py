# -*- coding: utf-8 -*-
"""
Management of the connection to the rig: selecting one of the registered connections,
establishing and closing it, sending data, the heartbeat and the menu with the connection settings.
"""
import logging
import time

import serial.tools.list_ports
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QActionGroup

from .connection import Connection, SerialConnection
from .min import STATUS_FRAME_ID, Control, RigStatus, controlFrame, frameCrc, syncFrame
from .registry import getRegisteredConnections
from .settings import Settings
from .widgets.dialogs import ConnectionSettingsDialog

__all__ = ["ConnectionManager"]


class ConnectionManager(QObject):
    """
    Holds the registered connections, one of them is active and used to talk to the rig.

    The active connection is selected with :meth:`setActiveConnection` while disconnected, the
    selection is stored in the settings. :meth:`connect` establishes it in the background,
    :meth:`disconnect` closes it.

    Rigs that send status frames (tool-libs `Experiment::enableStatus`) are watched: the manager
    reports whether the rig responds and checks that it received all parameters of a start.
    Rigs without status frames are not checked.
    """
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'

    #: key of the active connection in the settings
    SETTINGS_KEY = 'connection/active'

    #: the new state, one of :attr:`DISCONNECTED`, :attr:`CONNECTING` and :attr:`CONNECTED`
    stateChanged = pyqtSignal(str)
    #: name of the newly selected connection
    activeConnectionChanged = pyqtSignal(str)
    #: frames received by the active connection
    framesReceived = pyqtSignal(object)
    #: an established connection has been closed by itself, e.g. by the rig
    connectionLost = pyqtSignal()
    #: the status of the rig changed or it stopped responding
    rigStatusChanged = pyqtSignal()
    #: the rig confirmed the start with the parameters that were sent
    startConfirmed = pyqtSignal()
    #: the rig did not confirm the start or received other parameters, with the reason
    startFailed = pyqtSignal(str)
    #: the rig confirmed the parameters sent during the run with the given sync id
    syncConfirmed = pyqtSignal(int)
    #: the rig did not confirm the parameters of the given sync id or received others, with the reason
    syncFailed = pyqtSignal(int, str)

    #: [s] a rig that sent status frames before and then none for this long does not respond
    statusTimeout = 1.0
    #: [ms] time a rig has to confirm a start
    startTimeout = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        #: registered connection classes by name
        self.connections = dict(getRegisteredConnections())
        for name in self.connections:
            self._logger.info(f"Found Connection: {name}")
        if not self.connections:
            self._logger.error("No Connections found!")
        self._settings = Settings()
        saved = self._settings.value(self.SETTINGS_KEY)
        #: name of the connection used for the rig, `None` if none is registered
        self.activeConnection = saved if saved in self.connections else next(iter(self.connections), None)
        #: instance of the active connection while connecting or connected
        self.connection = None
        self.state = self.DISCONNECTED

        self.heartbeatTimer = QTimer(self)
        self.heartbeatTimer.timeout.connect(self.heartbeat)
        # time of the last heartbeat, finds stalls of the gui that look like a lost connection
        self._lastHeartbeat = None

        #: last status of the rig if it sends one: (RigStatus, receive time), else `None`
        self.rigStatus = None
        # the rig has been reported as not responding
        self._staleReported = False
        self._statusTimer = QTimer(self)
        self._statusTimer.timeout.connect(self._checkStatusAge)
        self._statusTimer.start(250)
        # pending start check: (startSeq before, expected count, crc)
        self._expectedStart = None
        self._startTimer = QTimer(self)
        self._startTimer.setSingleShot(True)
        self._startTimer.timeout.connect(self._onStartTimeout)
        # pending sync checks by sync id: (expected count, crc, deadline)
        self._pendingSyncs = {}
        self._syncId = 0

    @property
    def isConnected(self):
        return self.state == self.CONNECTED

    def _setState(self, state):
        if state != self.state:
            self.state = state
            self.stateChanged.emit(state)

    def setActiveConnection(self, name):
        """
        Selects the connection used for the rig, only possible while disconnected.

        :param name: name of a registered connection
        :return: `True` if `name` is the active connection now
        """
        if name == self.activeConnection:
            return True
        if name not in self.connections:
            self._logger.error(f"Unknown connection '{name}'!")
            return False
        if self.state != self.DISCONNECTED:
            self._logger.warning("Disconnect before selecting another connection!")
            return False
        self.activeConnection = name
        self._settings.setValue(self.SETTINGS_KEY, name)
        self._logger.info(f"Connection {name} selected")
        self.activeConnectionChanged.emit(name)
        return True

    def connect(self):
        """
        Establishes the active connection in the background, :attr:`stateChanged` reports the result.
        """
        if self.activeConnection is None:
            self._logger.error("No connections registered!")
            return
        if self.state != self.DISCONNECTED:
            return

        self._setState(self.CONNECTING)
        try:
            conn = self.connections[self.activeConnection]()
        except Exception:
            self.disconnect()
            raise
        conn.receivedFrames.connect(self._onFrames)
        conn.finished.connect(self._onFinished)
        conn.opened.connect(lambda ok, conn=conn: self._onOpened(conn, ok))
        self.connection = conn
        conn.openAsync()

    def _onOpened(self, conn, ok):
        """ result of establishing the given connection """
        if conn is not self.connection or self.state != self.CONNECTING:
            return
        name = self.activeConnection
        if not ok:
            self._logger.warning(f"No connection for {name} established! Check your settings!")
            self.disconnect()
            return
        self._logger.info(f"Connection for {name} established!")
        self._setState(self.CONNECTED)
        # udp rigs only know where to send their status after they received something
        self.heartbeat()

    def _onFinished(self):
        """ the connection has been closed, by the manager or by itself """
        if self.state == self.CONNECTED:
            self.connectionLost.emit()
            self.disconnect()

    def disconnect(self):
        """ closes the connection, also if it is still being established """
        self.heartbeatTimer.stop()
        self.cancelStartCheck()
        self.cancelSyncChecks()
        self.rigStatus = None
        self._staleReported = False
        # the state is changed first, so a connection closing itself is not reported as lost
        self._setState(self.DISCONNECTED)
        conn, self.connection = self.connection, None
        if conn is not None:
            conn.close()

    def shutdown(self, timeout=5000):
        """
        Closes the connection and waits for one that is still being established,
        e.g. before the application quits.

        :return: `True` if it has ended
        """
        self.disconnect()
        # connections that are still being established end with their connect timeout
        if not Connection.waitForAborted(timeout):
            self._logger.warning("Aborted connections did not end in time")
            return False
        return True

    def write(self, data):
        """
        Sends the given data to the rig.
        :param data: dict with the keys 'id' and 'msg'
        """
        if self.connection is not None:
            self.connection.writeData(data)

    def heartbeat(self):
        now = time.monotonic()
        if self.heartbeatTimer.isActive() and self._lastHeartbeat is not None:
            gap = now - self._lastHeartbeat
            if gap > max(0.3, 3e-3 * self.heartbeatTimer.interval()):
                self._logger.warning(f"heartbeat delayed by {gap * 1e3:.0f} ms, the gui was blocked")
        self._lastHeartbeat = now
        self.write(controlFrame(Control.HEARTBEAT))

    # status of the rig

    def _onFrames(self, frames):
        """ takes the status frames out, passes the others on """
        data = []
        for frame in frames:
            if frame.id != STATUS_FRAME_ID:
                data.append(frame)
                continue
            status = RigStatus.fromPayload(frame.payload)
            if status is None:
                self._logger.warning(f"unknown status frame {bytes(frame.payload).hex()}")
                continue
            self._onStatus(status)
        if data:
            self.framesReceived.emit(data)

    def _onStatus(self, status):
        last = self.rigStatus
        if last is not None and status.uptime < last[0].uptime:
            self._logger.warning("the rig has been restarted")
        self.rigStatus = (status, time.monotonic())
        # the uptime changes with every frame, only report what is shown
        if (last is None or self._staleReported
                or (last[0].running, last[0].flags) != (status.running, status.flags)):
            self._staleReported = False
            self.rigStatusChanged.emit()
        self._checkStart(status)
        self._checkSync(status)

    def _isStale(self, received):
        return time.monotonic() - received > self.statusTimeout

    def _checkStatusAge(self):
        if self.rigStatus is not None and self._isStale(self.rigStatus[1]) and not self._staleReported:
            self._staleReported = True
            self.rigStatusChanged.emit()
        now = time.monotonic()
        for syncId, (_, _, deadline) in list(self._pendingSyncs.items()):
            if now > deadline:
                del self._pendingSyncs[syncId]
                self.syncFailed.emit(syncId, f"no confirmation of the parameters within {self.startTimeout} ms")

    def isResponding(self):
        """
        :return: `True` if the rig sends status frames, `False` if it stopped,
            `None` if it never sent one (no status support)
        """
        if self.rigStatus is None:
            return None
        return not self._isStale(self.rigStatus[1])

    def statusFlagNames(self):
        """ names of the status bits of the rig, from the `statusFlags` list of the active connection class """
        return list(getattr(self.connections.get(self.activeConnection), 'statusFlags', []))

    # check of the start

    def _rigCrc(self, frames):
        """ (number, CRC32) of the frames as the rig receives them over the active connection,
        see :meth:`pywisp.connection.Connection.rigFrame` and :func:`pywisp.min.frameCrc` """
        if self.connection is not None:
            frames = [f for f in map(self.connection.rigFrame, frames) if f is not None]
        return frameCrc(frames)

    def expectStart(self, expected):
        """
        Checks the next start of the rig if it sends status frames.

        :param expected: the frames sent before the start command
        :return: `True` if the rig is checked, :attr:`startConfirmed` or :attr:`startFailed` follow
        """
        self.cancelStartCheck()
        if self.rigStatus is None or self._isStale(self.rigStatus[1]):
            return False
        self._expectedStart = (self.rigStatus[0].startSeq, *self._rigCrc(expected))
        self._startTimer.start(self.startTimeout)
        return True

    def cancelStartCheck(self):
        self._expectedStart = None
        self._startTimer.stop()

    def _checkStart(self, status):
        if self._expectedStart is None:
            return
        seqBefore, count, crc = self._expectedStart
        if status.startSeq == seqBefore or not status.running:
            return
        self.cancelStartCheck()
        if (status.startCount, status.startCrc) != (count, crc):
            self.startFailed.emit(f"the rig received {status.startCount} frames with "
                                  f"CRC {status.startCrc:08x} instead of {count} frames with CRC {crc:08x}")
            return
        self.startConfirmed.emit()

    def _onStartTimeout(self):
        self._expectedStart = None
        self.startFailed.emit(f"no confirmation of the start within {self.startTimeout} ms")

    # check of parameters sent during the run

    def sync(self, expected):
        """
        Sends a sync command after parameters sent during the run, a rig that supports it confirms
        what it received since the last control frame.

        :param expected: the frames sent since the last control frame
        :return: the sync id, :attr:`syncConfirmed` or :attr:`syncFailed` follow with it,
            `None` if the rig does not support sync commands (nothing is sent then)
        """
        if self.rigStatus is None or self.rigStatus[0].syncId is None or self._isStale(self.rigStatus[1]):
            return None
        # ids 1..255, the rig reports 0 before the first sync
        self._syncId = self._syncId % 255 + 1
        self._pendingSyncs[self._syncId] = (*self._rigCrc(expected), time.monotonic() + self.startTimeout / 1000)
        self.write(syncFrame(self._syncId))
        return self._syncId

    def cancelSyncChecks(self):
        self._pendingSyncs.clear()

    def _checkSync(self, status):
        entry = self._pendingSyncs.pop(status.syncId, None)
        if entry is None:
            return
        count, crc, _ = entry
        if (status.syncCount, status.syncCrc) != (count, crc):
            self.syncFailed.emit(status.syncId, f"the rig received {status.syncCount} frames with CRC "
                                                f"{status.syncCrc:08x} instead of {count} frames with CRC {crc:08x}")
            return
        self.syncConfirmed.emit(status.syncId)

    def startHeartbeat(self, interval):
        """ sends a heartbeat every `interval` ms, 0 disables it """
        if interval:
            self._lastHeartbeat = None
            self.heartbeatTimer.start(int(interval))

    def stopHeartbeat(self):
        self.heartbeatTimer.stop()

    # menu with the selection and the settings of the connections

    def fillMenu(self, menu, parentWidget=None):
        """
        Adds the selection of the active connection (radio buttons, a serial connection gets a submenu with the
        available devices) and the entry of the settings dialog to the given menu.
        Both are only enabled while disconnected.
        :param parentWidget: parent of the dialog
        """
        #: radio buttons selecting the active connection
        self.connectionActions = QActionGroup(menu)
        self.connectionActions.setExclusive(True)
        serialCnt = 0
        for name, cls in self.connections.items():
            if issubclass(cls, SerialConnection):
                deviceMenu = menu.addMenu(name)
                deviceMenu.aboutToShow.connect(lambda name=name, deviceMenu=deviceMenu:
                                               self._fillDeviceMenu(name, deviceMenu))
                act = deviceMenu.menuAction()
                if cls.settings['port'] == '':
                    self.setDefaultComPort(cls.settings, serialCnt)
                serialCnt += 1
            else:
                # owned by the menu
                act = menu.addAction(name)
            act.setData(name)
            act.setCheckable(True)
            act.setChecked(name == self.activeConnection)
            self.connectionActions.addAction(act)
            act.triggered.connect(lambda _, name=name: self._onActionTriggered(name))
        self.activeConnectionChanged.connect(self._checkActiveAction)
        menu.addSeparator()

        #: opens the settings dialog of the connections
        self.actSettings = menu.addAction("Settings")
        self.actSettings.triggered.connect(lambda: self.editSettings(parentWidget))
        self.stateChanged.connect(self._lockMenu)

    def _lockMenu(self, state):
        self.connectionActions.setEnabled(state == self.DISCONNECTED)
        self.actSettings.setEnabled(state == self.DISCONNECTED)

    def _onActionTriggered(self, name):
        # a refused selection checks the active connection again
        self.setActiveConnection(name)
        self._checkActiveAction(self.activeConnection)

    def _checkActiveAction(self, name):
        for act in self.connectionActions.actions():
            act.setChecked(act.data() == name)

    def _fillDeviceMenu(self, name, deviceMenu):
        """ lists the available serial devices, selecting one sets the port and activates the connection """
        settings = self.connections[name].settings

        def select(port):
            settings['port'] = port
            self._onActionTriggered(name)

        deviceMenu.clear()
        for p in serial.tools.list_ports.comports():
            # owned by the menu, so clear() deletes it
            act = deviceMenu.addAction(p.device)
            act.setCheckable(True)
            act.setChecked(p.device == settings['port'])
            act.triggered.connect(lambda _, port=p.device: select(port))
        if deviceMenu.isEmpty():
            deviceMenu.addAction("No devices found").setEnabled(False)

    def editSettings(self, parentWidget=None):
        """ edits the settings of the connections with a dialog, does not change the active connection """
        dialog = ConnectionSettingsDialog(self.connections, self.activeConnection, parent=parentWidget)
        if dialog.exec() == ConnectionSettingsDialog.DialogCode.Accepted:
            dialog.apply()

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
