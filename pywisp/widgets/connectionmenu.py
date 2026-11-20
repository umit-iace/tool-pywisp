# -*- coding: utf-8 -*-
"""
The Connections menu: selection of the active connection and the settings dialog of the connections.
"""
import serial.tools.list_ports
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QActionGroup

from ..connection import SerialConnection
from .dialogs import ConnectionSettingsDialog


class ConnectionMenu(QObject):
    """
    Adds the selection of the active connection (radio buttons, a serial connection gets a submenu with the
    available devices) and the entry of the settings dialog to the given menu.
    Both are only enabled while disconnected.

    :param manager: :class:`pywisp.connectionManager.ConnectionManager`
    :param menu: menu to fill
    :param parentWidget: parent of the dialog
    """

    def __init__(self, manager, menu, parentWidget=None):
        super().__init__(menu)
        self.manager = manager
        #: radio buttons selecting the active connection
        self.connectionActions = QActionGroup(menu)
        self.connectionActions.setExclusive(True)
        serialCnt = 0
        for name, cls in manager.connections.items():
            if issubclass(cls, SerialConnection):
                deviceMenu = menu.addMenu(name)
                deviceMenu.aboutToShow.connect(lambda name=name, deviceMenu=deviceMenu:
                                               self._fillDeviceMenu(name, deviceMenu))
                act = deviceMenu.menuAction()
                if cls.settings['port'] == '':
                    manager.setDefaultComPort(cls.settings, serialCnt)
                serialCnt += 1
            else:
                # owned by the menu
                act = menu.addAction(name)
            act.setData(name)
            act.setCheckable(True)
            act.setChecked(name == manager.activeConnection)
            self.connectionActions.addAction(act)
            act.triggered.connect(lambda _, name=name: self._onActionTriggered(name))
        manager.activeConnectionChanged.connect(self._checkActiveAction)
        menu.addSeparator()

        #: opens the settings dialog of the connections
        self.actSettings = menu.addAction("Settings")
        self.actSettings.triggered.connect(lambda: self.editSettings(parentWidget))
        manager.stateChanged.connect(self._lockMenu)

    def _lockMenu(self, state):
        self.connectionActions.setEnabled(state == self.manager.DISCONNECTED)
        self.actSettings.setEnabled(state == self.manager.DISCONNECTED)

    def _onActionTriggered(self, name):
        # a refused selection checks the active connection again
        self.manager.setActiveConnection(name)
        self._checkActiveAction(self.manager.activeConnection)

    def _checkActiveAction(self, name):
        for act in self.connectionActions.actions():
            act.setChecked(act.data() == name)

    def _fillDeviceMenu(self, name, deviceMenu):
        """ lists the available serial devices, selecting one sets the port and activates the connection """
        settings = self.manager.connections[name].settings

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
        dialog = ConnectionSettingsDialog(self.manager.connections, self.manager.activeConnection,
                                          parent=parentWidget)
        if dialog.exec() == ConnectionSettingsDialog.DialogCode.Accepted:
            dialog.apply()
