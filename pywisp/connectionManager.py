# -*- coding: utf-8 -*-
"""
Management of the connections to the rig: establishing and closing them, sending data,
the heartbeat and the menu with the connection settings.
"""
import logging

import serial.tools.list_ports
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .connection import Connection, SerialConnection, SocketConnection
from .min import CONTROL_FRAME_ID, Control, controlFrame
from .registry import getRegisteredConnections
from .widgets.dialogs import DataTcpIpDialog

__all__ = ["ConnectionManager"]


class ConnectionManager(QObject):
    """
    Holds an instance of every registered connection while connected.

    All connections are established in the background, the manager is connected once all of
    them are open. If one of them fails or drops, all of them are closed.
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
            connInstance.receivedFrames.connect(lambda frames, name=name: self.framesReceived.emit(frames, name))
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
