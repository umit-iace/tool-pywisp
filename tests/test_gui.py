# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict
from unittest import mock

import logging
import os
import stat
import textwrap
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QFileDialog

import pywisp as pw
from pywisp.measurement import elementName
from pywisp.widgets.remote import MovableMultiButton, MovablePushButton, MovableSlider, MovableSwitch, MovableWidget
from test_status import statusFrame

SREG = """
- Name: First
  Dummy:
    gain: 2.0
  Remote:
    Gain:
      widgetType: Slider
      Module: Dummy
      Parameter: gain
      minSlider: 0
      maxSlider: 10
      stepSlider: 0.5
      shortcutPlus: ''
      shortcutMinus: ''
    Go:
      widgetType: PushButton
      Module: Dummy
      Parameter: gain
      valueOn: '1'
      shortcut: ''
      shortcut-Gp: S
      position: [150, 60]
- Name: Second
  Dummy:
  Remote:
"""


class DummyConnection(pw.UdpConnection):
    settings = {"ip": "127.0.0.1", "port": 45999}

    def __init__(self):
        super().__init__(**self.settings)


class DummySerial(pw.SerialConnection):
    settings = {"port": "", "baud": 115200}

    def __init__(self):
        super().__init__(**self.settings)


class Dummy(pw.ExperimentModule):
    dataPoints = ["x"]
    publicSettings = OrderedDict([("gain", 1.0)])

    def getParams(self, data):
        return [{'id': 10, 'msg': struct.pack('<d', float(data[0]))}]

    def handleFrame(self, frame):
        t, x = struct.unpack('<Ld', frame.payload)
        return {'Time': t, 'DataPoints': {'x': x}}


@pytest.fixture
def gui(qtbot, cleanRegistry, tmp_path):
    pw.registerConnection(DummyConnection)
    pw.registerConnection(DummySerial)
    pw.registerExperimentModule(Dummy)
    (tmp_path / "default.sreg").write_text(SREG)
    form = pw.MainGui()
    qtbot.addWidget(form)
    return form


def test_experiments_are_loaded(gui):
    assert [gui.experimentList.item(i).text() for i in range(gui.experimentList.count())] == ["First", "Second"]
    assert {type(w) for w in gui.remotePanel.widgets} == {MovableSlider, MovablePushButton}


def test_empty_remote_section(gui):
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    assert gui.remotePanel.widgets == []


def ports(*devices):
    return [SimpleNamespace(device=d, description="USB Serial") for d in devices]


def test_menu_refresh_does_not_leak_actions(gui, monkeypatch):
    from PyQt6.QtGui import QAction
    monkeypatch.setattr(pw.gui, 'getAllGamepads', lambda: [])
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: ports("/dev/ttyUSB0", "/dev/ttyACM0"))
    deviceMenu = serialMenu(gui)

    def refresh():
        deviceMenu.aboutToShow.emit()
        gui.detectGamepads()
        return len(gui.findChildren(QAction))

    first = refresh()
    assert refresh() == refresh() == first
    assert len(deviceMenu.actions()) == 2


def test_missing_config(qtbot, cleanRegistry):
    form = pw.MainGui()
    qtbot.addWidget(form)
    assert form.experimentList.count() == 0
    # must not raise even though nothing was loaded
    form.stopExperiment()


def test_show_coordinates_setting(gui):
    gui.actShowCoords.setChecked(False)
    assert gui._settings.value("view/show_coordinates", type=bool) is False
    gui.actShowCoords.setChecked(True)
    assert gui._settings.value("view/show_coordinates", type=bool) is True


@pytest.fixture
def themeGui(gui):
    """ the theme is global for the application, the other tests expect the system theme """
    yield gui
    gui.setTheme('System')


def test_theme_toggle_is_right_of_visualizers(gui):
    actions = gui.toolbarExp.actions()
    assert actions[-1] is gui.actToggleTheme
    assert actions[-2].isSeparator()
    assert gui.toolbarExp.widgetForAction(actions[-3]) is gui.visComboBox


def test_theme_toggle(themeGui):
    from PyQt6.QtGui import QPalette
    gui = themeGui
    style = QApplication.style().name()

    def window():
        return QApplication.palette().color(QPalette.ColorRole.Window).lightness()

    assert gui._settings.value("theme/name") == 'System'
    gui.actToggleTheme.trigger()
    assert gui._settings.value("theme/name") == 'Dark'
    assert window() < 100
    assert gui.actToggleTheme.toolTip() == "Switch to light mode"
    # also the content of the docks, it is below a style sheet
    assert gui.logBox.palette().color(QPalette.ColorRole.Base) == QApplication.palette().color(QPalette.ColorRole.Base)

    # the toggle returns to the last theme of the other kind
    gui.setTheme('Solarized Light')
    gui.actToggleTheme.trigger()
    assert gui._settings.value("theme/name") == 'Dark'
    gui.actToggleTheme.trigger()
    assert gui._settings.value("theme/name") == 'Solarized Light'
    assert [a.text() for a in gui._themeActions.actions() if a.isChecked()] == ['Solarized Light']

    gui.setTheme('System')
    assert QApplication.style().name() == style


def test_unknown_theme_falls_back_to_system(themeGui):
    themeGui.setTheme('removed theme')
    assert themeGui._settings.value("theme/name") == 'System'


def test_theme_is_restored_after_restart(themeGui, qtbot):
    from PyQt6.QtGui import QPalette
    themeGui.setTheme('Solarized Light')
    themeGui.actToggleTheme.trigger()
    themeGui.close()
    themeGui._settings.sync()

    gui = pw.MainGui()
    qtbot.addWidget(gui)
    assert gui._settings.value("theme/name") == 'Dark'
    assert [a.text() for a in gui._themeActions.actions() if a.isChecked()] == ['Dark']
    assert QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 100
    assert gui.actToggleTheme.toolTip() == "Switch to light mode"
    # the toggle still knows the last light theme
    gui.actToggleTheme.trigger()
    assert gui._settings.value("theme/name") == 'Solarized Light'


def test_log_colors_of_older_settings_are_ignored(gui):
    gui._settings.setValue("log_colors/INFO", "#101010")
    assert not gui._settings.color('INFO', 'log').isValid()
    assert gui._settings.color('ERROR', 'log').isValid()


def test_movable_widgets_use_mixin_handlers():
    for cls in (MovablePushButton, MovableSwitch, MovableSlider):
        assert cls.mousePressEvent is MovableWidget.mousePressEvent
        assert cls.mouseReleaseEvent is MovableWidget.mouseReleaseEvent


def connectRig(gui, qtbot):
    """ connect like the user does and wait for the result of the background connection """
    gui.connectRig()
    qtbot.waitUntil(lambda: gui.connectionManager.state != gui.connectionManager.CONNECTING, timeout=5000)


def test_frames_of_the_active_connection_reach_the_gui(gui, qtbot):
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        connectRig(gui, qtbot)
    try:
        assert gui.isConnected
        assert isinstance(gui.connectionManager.connection, DummyConnection)
        with mock.patch.object(gui, "updateData") as updateData:
            gui.connectionManager.connection.receivedFrames.emit([pw.Frame(15, b"")])
        updateData.assert_called_once()
        assert [f.id for f in updateData.call_args.args[0]] == [15]
    finally:
        gui.disconnectRig()
    assert not gui.isConnected
    assert gui.connectionManager.connection is None


def test_connect_resets_the_frame_count_of_the_rig(gui, qtbot):
    """ connect frames would be counted by the rig and break the first start check, sync 0 resets the count """
    session = {'id': 62, 'msg': bytes([1, 1])}
    with mock.patch.object(DummyConnection, "_connect", return_value=True), \
            mock.patch.object(DummyConnection, "connectFrames", [session]), \
            mock.patch.object(DummyConnection, "writeData") as writeData:
        connectRig(gui, qtbot)
        try:
            assert [c.args[0] for c in writeData.call_args_list] == [session, pw.syncFrame(0)]
        finally:
            gui.disconnectRig()


def connectionMenuActions(gui):
    return [a for a in gui.connMenu.actions() if a.isCheckable()]


def test_connection_selection(gui):
    manager = gui.connectionManager
    # the first registered connection is the default
    assert manager.activeConnection == "DummyConnection"
    actions = connectionMenuActions(gui)
    assert [a.text() for a in actions] == ["DummyConnection", "DummySerial"]
    assert [a.isChecked() for a in actions] == [True, False]
    assert manager.connectionActions.isExclusive()
    combo = gui.connComboBox
    assert [combo.itemText(i) for i in range(combo.count())] == ["DummyConnection", "DummySerial"]
    assert combo.currentText() == "DummyConnection"
    # the combobox sits left of the connect button
    assert gui.toolbarExp.widgetForAction(gui.toolbarExp.actions()[0]) is combo

    # radio button selects, combobox follows
    actions[1].trigger()
    assert manager.activeConnection == "DummySerial"
    assert combo.currentText() == "DummySerial"
    assert [a.isChecked() for a in actions] == [False, True]
    assert gui.exp.connection == "DummySerial"

    # combobox selects, radio buttons follow
    combo.setCurrentText("DummyConnection")
    assert manager.activeConnection == "DummyConnection"
    assert [a.isChecked() for a in actions] == [True, False]
    assert gui.exp.connection == "DummyConnection"

    # unknown names are refused
    assert not manager.setActiveConnection("Unknown")
    assert manager.activeConnection == "DummyConnection"


def serialMenu(gui):
    return next(a.menu() for a in gui.connMenu.actions() if a.text() == "DummySerial")


def test_connection_menu_structure(gui):
    actions = gui.connMenu.actions()
    assert [a.text() for a in actions] == ["DummyConnection", "DummySerial", "", "Settings"]
    assert actions[0].menu() is None and actions[1].menu() is not None
    assert actions[2].isSeparator()
    assert actions[3] is gui.connectionManager.actSettings and not actions[3].isCheckable()
    # the serial entry with its submenu is a radio button like the others
    assert actions[1] in gui.connectionManager.connectionActions.actions()


def test_connection_group_is_delimited_in_the_toolbar(gui):
    """ combobox, connect/disconnect | start/stop | """
    actions = gui.toolbarExp.actions()
    assert [gui.toolbarExp.widgetForAction(a) for a in actions[:2]] == [gui.connComboBox, gui.connButton]
    assert actions[2].isSeparator()
    assert gui.toolbarExp.widgetForAction(actions[3]) is gui.expButton
    assert actions[4].isSeparator()


def test_toolbar_buttons_show_the_enabled_action(gui):
    gui.actConnect.setEnabled(True)
    gui.actDisconnect.setEnabled(False)
    assert gui.connButton.defaultAction() is gui.actConnect
    gui.actDisconnect.setEnabled(True)
    assert gui.connButton.defaultAction() is gui.actDisconnect
    gui.actDisconnect.setEnabled(False)
    assert gui.connButton.defaultAction() is gui.actConnect

    gui.actStopExperiment.setEnabled(False)
    assert gui.expButton.defaultAction() is gui.actStartExperiment
    gui.actStopExperiment.setEnabled(True)
    assert gui.expButton.defaultAction() is gui.actStopExperiment
    gui.actStopExperiment.setEnabled(False)
    assert gui.expButton.defaultAction() is gui.actStartExperiment


def test_toolbar_buttons_keep_their_width(gui):
    """ the toolbar must not shift when a button swaps its action """
    for btn, a, b in gui._toggleButtons:
        width = btn.width()
        a.setEnabled(True)
        b.setEnabled(not b.isEnabled())
        assert btn.width() == width == btn.minimumWidth() == btn.maximumWidth()
        # a second action would give the button a menu arrow
        assert btn.actions() == [btn.defaultAction()]


def test_serial_device_menu(gui, monkeypatch):
    manager = gui.connectionManager
    monkeypatch.setitem(DummySerial.settings, "port", "/dev/ttyACM0")
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: ports("/dev/ttyUSB0", "/dev/ttyACM0"))
    menu = serialMenu(gui)
    menu.aboutToShow.emit()
    devices = menu.actions()
    assert [a.text() for a in devices] == ["/dev/ttyUSB0", "/dev/ttyACM0"]
    assert [a.isChecked() for a in devices] == [False, True]

    # selecting a device sets the port and activates the connection
    devices[0].trigger()
    assert DummySerial.settings["port"] == "/dev/ttyUSB0"
    assert manager.activeConnection == "DummySerial"
    assert gui.connComboBox.currentText() == "DummySerial"
    assert [a.isChecked() for a in connectionMenuActions(gui)] == [False, True]
    menu.aboutToShow.emit()
    assert [a.isChecked() for a in menu.actions()] == [True, False]

    # refreshed when shown
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: [])
    menu.aboutToShow.emit()
    assert [(a.text(), a.isEnabled()) for a in menu.actions()] == [("No devices found", False)]


def test_settings_dialog_from_menu(gui, monkeypatch):
    from pywisp.widgets.dialogs import ConnectionSettingsDialog
    shown = []

    def exec(dialog):
        shown.append(dialog.connList.currentText())
        dialog.connList.setCurrentText("DummyConnection")
        dialog._fields["DummyConnection"][1].setText("46000")
        return ConnectionSettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(ConnectionSettingsDialog, "exec", exec)
    monkeypatch.setitem(DummyConnection.settings, "port", 45999)
    gui.connComboBox.setCurrentText("DummySerial")
    gui.connectionManager.actSettings.trigger()
    # the active connection is shown first and stays active
    assert shown == ["DummySerial"]
    assert DummyConnection.settings["port"] == 46000
    assert gui.connectionManager.activeConnection == "DummySerial"


def test_settings_dialog_cancel_discards(gui, monkeypatch):
    from pywisp.widgets.dialogs import ConnectionSettingsDialog

    def exec(dialog):
        dialog._fields["DummySerial"][1].setCurrentText("9600")
        return ConnectionSettingsDialog.DialogCode.Rejected

    monkeypatch.setattr(ConnectionSettingsDialog, "exec", exec)
    gui.connectionManager.actSettings.trigger()
    assert DummySerial.settings["baud"] == 115200


def test_connection_selection_is_persistent(gui, qtbot):
    gui.connComboBox.setCurrentText("DummySerial")
    gui.connectionManager._settings.sync()
    form = pw.MainGui()
    qtbot.addWidget(form)
    assert form.connectionManager.activeConnection == "DummySerial"
    assert form.connComboBox.currentText() == "DummySerial"
    assert [a.isChecked() for a in connectionMenuActions(form)] == [False, True]


def test_unregistered_saved_connection_falls_back_to_the_first(qtbot, cleanRegistry):
    from pywisp.settings import Settings
    Settings().setValue("connection/active", "Gone")
    pw.registerConnection(DummyConnection)
    form = pw.MainGui()
    qtbot.addWidget(form)
    assert form.connectionManager.activeConnection == "DummyConnection"


def test_selection_is_disabled_while_connected(gui, qtbot):
    manager = gui.connectionManager
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        connectRig(gui, qtbot)
    try:
        assert gui.isConnected
        assert not gui.connComboBox.isEnabled()
        assert not manager.connectionActions.isEnabled()
        assert not manager.actSettings.isEnabled()
        # the serial entry with the device menu is locked too
        assert not serialMenu(gui).menuAction().isEnabled()
        assert not manager.setActiveConnection("DummySerial")
        # a refused selection is reverted in the menu and the combobox
        connectionMenuActions(gui)[1].trigger()
        gui.connComboBox.setCurrentText("DummySerial")
        assert manager.activeConnection == "DummyConnection"
        assert gui.connComboBox.currentText() == "DummyConnection"
        assert [a.isChecked() for a in connectionMenuActions(gui)] == [True, False]
    finally:
        gui.disconnectRig()
    assert gui.connComboBox.isEnabled() and manager.connectionActions.isEnabled() and manager.actSettings.isEnabled()


def test_only_the_active_connection_is_opened(gui, qtbot):
    gui.connComboBox.setCurrentText("DummySerial")
    with mock.patch.object(DummyConnection, "_connect", return_value=True) as udp, \
            mock.patch.object(DummySerial, "_connect", return_value=False) as serial:
        connectRig(gui, qtbot)
        qtbot.waitUntil(lambda: not pw.Connection._aborting, timeout=5000)
    serial.assert_called_once()
    udp.assert_not_called()


def test_modules_get_the_active_connection(gui):
    gui.experimentDoubleClicked(gui.experimentList.item(0))
    mod = gui.exp._getInstance('Dummy')
    assert mod.connection == "DummyConnection"
    gui.connComboBox.setCurrentText("DummySerial")
    assert mod.connection == "DummySerial"


def test_connection_traffic_light(gui, qtbot):
    """ green while connected, yellow if the rig does not respond or misses status bits """
    import struct
    assert gui.connectionLedState == 'red'
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        connectRig(gui, qtbot)
    try:
        # a rig without status frames is not checked
        assert gui.connectionLedState == 'green'

        def status(flags):
            payload = struct.pack('<BBBBHIIBHI', 1, 0, flags, 0, 0, 0, 1000, 0, 0, 0)
            gui.connectionManager._onFrames([pw.Frame(pw.STATUS_FRAME_ID, payload)])

        with mock.patch.object(DummyConnection, "statusFlags", ['ODrive', 'Motor'], create=True):
            status(0b11)
            assert gui.connectionLedState == 'green'
            assert gui.statusbarLabel.text() == "DummyConnection: IDLE"
            status(0b01)
            assert gui.connectionLedState == 'yellow'
            assert "missing Motor" in gui.connectionLed.toolTip()
            status(0b11)
            assert gui.connectionLedState == 'green'
            gui._setCommError("Start not confirmed")
            assert gui.connectionLedState == 'yellow'
            assert "Start not confirmed" in gui.connectionLed.toolTip()
    finally:
        gui.disconnectRig()
    assert gui.connectionLedState == 'red'


def test_failed_connection(gui, qtbot):
    gui.connComboBox.setCurrentText("DummySerial")
    with mock.patch.object(DummySerial, "_connect", return_value=False):
        connectRig(gui, qtbot)
        qtbot.waitUntil(lambda: not pw.Connection._aborting, timeout=5000)
    assert not gui.isConnected
    assert gui.actConnect.isEnabled() and gui.connComboBox.isEnabled()
    assert gui.connectionManager.connection is None


def test_connecting_does_not_block_the_gui(gui, qtbot):
    """ the gui stays responsive while the rig does not answer, and connecting can be aborted """
    import threading
    release = threading.Event()

    def slowConnect(self):
        release.wait(5)
        return True

    with mock.patch.object(DummyConnection, "_connect", slowConnect):
        gui.connectRig()
        assert gui.connectionLedState == 'red'
        assert gui.connectionLed.toolTip() == "Connecting ..."
        assert not gui.isConnected and not gui.actConnect.isEnabled()
        # abort while the connection is still being established
        gui.disconnectRig()
        assert gui.actConnect.isEnabled()
        release.set()
        qtbot.waitUntil(lambda: not pw.Connection._aborting, timeout=5000)
    assert not gui.isConnected
    assert gui.connectionLedState == 'red'
    assert gui.connectionLed.toolTip() == "Not connected"


def test_close_waits_for_aborted_connections(gui, qtbot):
    """ closing the window while connecting must not destroy the running reader thread """
    import threading
    release = threading.Event()

    def slowConnect(self):
        release.wait(5)
        return True

    with mock.patch.object(DummyConnection, "_connect", slowConnect):
        gui.connectRig()
        threading.Timer(0.2, release.set).start()
        gui.close()
    assert not pw.Connection._aborting
    assert not gui.isConnected


def test_gamepad_slider_mapping(gui):
    slider = next(w for w in gui.remotePanel.widgets if isinstance(w, MovableSlider))
    slider._onGamepad(-0.5)
    assert slider.value == 0
    slider._onGamepad(0.0)
    assert slider.value == 5
    slider._onGamepad(0.5)
    assert slider.value == 10


def test_gamepad_menu_without_gamepads(gui, monkeypatch):
    monkeypatch.setattr(pw.gui, 'getAllGamepads', lambda: [])
    gui.detectGamepads()
    actions = gui.gamepadMenu.actions()
    assert [a.text() for a in actions] == ["No gamepad found"]
    assert not actions[0].isEnabled()


def test_gamepad_drives_remote_widgets(gui, qtbot, sdl, virtualPad):
    gui.detectGamepads()
    action = next(a for a in gui.gamepadMenu.actions() if a.text() == 'Virtual Controller')
    action.trigger()
    assert gui.gamepad is not None
    gui.detectGamepads()
    assert next(a for a in gui.gamepadMenu.actions() if a.text() == 'Virtual Controller').isChecked()

    button = next(w for w in gui.remotePanel.widgets if isinstance(w, MovablePushButton))
    with qtbot.waitSignal(button.clicked, timeout=2000):
        virtualPad.press(sdl.SDL_CONTROLLER_BUTTON_A)

    # unplugging releases the gamepad
    virtualPad.unplug()
    qtbot.waitUntil(lambda: gui.gamepad is None, timeout=2000)
    assert button._gamepadConnection is None


def test_gamepad_ignores_widgets_of_other_experiments(gui, qtbot, sdl, virtualPad):
    gui.detectGamepads()
    next(a for a in gui.gamepadMenu.actions() if a.text() == 'Virtual Controller').trigger()
    button = remoteWidget(gui, MovablePushButton)
    assert button._gamepadConnection is not None

    # the patched slot is used, otherwise the check below would prove nothing
    with mock.patch.object(gui.remotePanel, 'widgetActivated') as send:
        virtualPad.press(sdl.SDL_CONTROLLER_BUTTON_A)
        qtbot.waitUntil(lambda: send.called, timeout=2000)
    virtualPad.press(sdl.SDL_CONTROLLER_BUTTON_A, 0)
    qtbot.wait(50)

    # the second experiment has no remote widgets
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    assert gui.remotePanel.widgets == []
    with mock.patch.object(gui.remotePanel, 'widgetActivated') as send:
        virtualPad.press(sdl.SDL_CONTROLLER_BUTTON_A)
        qtbot.wait(200)
    send.assert_not_called()


def frame(t, x):
    return pw.Frame(15, struct.pack('<Ld', t, x))


def startExperiment(gui):
    gui.actStopExperiment.setEnabled(True)
    gui.startExperiment()


def test_data_path_handles_batches(gui):
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0), frame(2000, 2.0)])
    buf = gui._currentDataPointBuffers['x']
    assert list(buf.time) == [1.0, 2.0]
    assert list(buf.values) == [1.0, 2.0]
    gui.stopExperiment()
    # the finished run keeps its data and is no longer modified
    stored = gui.measurements[-1].dataPointBuffers['x']
    gui.updateData([frame(3000, 3.0)])
    assert len(stored) == 2


def test_failing_module_does_not_crash(gui, monkeypatch, caplog):
    def broken(self, frame):
        raise RuntimeError("boom")
    monkeypatch.setattr(Dummy, "handleFrame", broken)
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0)] * 50)
    errors = [r for r in caplog.records if "failed to handle frame" in r.getMessage()]
    assert len(errors) == 1
    gui.stopExperiment()
    assert any("failed to handle 50 frame(s)" in r.getMessage() for r in caplog.records)


def test_failing_params_abort_start(gui, monkeypatch):
    def broken(self, data):
        raise RuntimeError("boom")
    monkeypatch.setattr(Dummy, "getParams", broken)
    startExperiment(gui)
    assert not gui.exp.runningExperiment


def test_failing_visualizer_is_disabled(gui, caplog):
    class BrokenVisualizer:
        def update(self, dataPoints):
            raise RuntimeError("boom")
    gui.visualizer = BrokenVisualizer()
    gui.updateDataPlots()
    assert gui.visualizer is None
    assert any("has been disabled" in r.getMessage() for r in caplog.records)


def test_moving_window_size_is_used(gui):
    from pywisp.widgets.plotchart import PlotChart
    assert PlotChart("t", {"MovingWindowSize": 7}).movingWindowWidth == 7
    assert PlotChart("t", {"MovingWindowWidth": 8}).movingWindowWidth == 8


def test_plot_color_order(gui):
    from pywisp.settings import Settings, _default
    st = Settings()
    expected = [v for _, v in _default["plot_colors"]]
    assert [st.color(i).name() for i in range(len(expected))] == expected


def remoteWidget(gui, cls):
    return next(w for w in gui.remotePanel.widgets if isinstance(w, cls))


def rightDrag(widget, delta):
    """ move a remote widget like the user does, by dragging it with the right mouse button """
    start = QPoint(5, 5)

    def send(kind, pos, buttons):
        event = QMouseEvent(kind, QPointF(pos), QPointF(widget.mapToGlobal(pos)), Qt.MouseButton.RightButton,
                            buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, event)

    send(QEvent.Type.MouseButtonPress, start, Qt.MouseButton.RightButton)
    send(QEvent.Type.MouseMove, start + delta, Qt.MouseButton.RightButton)
    send(QEvent.Type.MouseButtonRelease, start + delta, Qt.MouseButton.NoButton)


def savedExperiments(path):
    with open(path) as f:
        return yaml.safe_load(f)


def test_remote_positions_are_loaded(gui):
    assert remoteWidget(gui, MovablePushButton).position() == [150, 60]
    slider = remoteWidget(gui, MovableSlider)
    # without a position the widgets are placed in two columns
    assert slider.position() == [0, 0]
    assert slider.label.pos() == QPoint(80, 30)


def test_moving_a_widget_updates_the_experiment(gui):
    button = remoteWidget(gui, MovablePushButton)
    rightDrag(button, QPoint(30, 20))
    assert button.position() == [180, 80]
    assert gui._experiments[0]['Remote']['Go']['position'] == [180, 80]

    # editing the widget keeps its position
    config = dict(button.getData(), valueOn='2')
    with mock.patch.object(pw.widgets.remotepanel.RemoteWidgetEdit, 'getData', return_value=(config, True)):
        gui.remotePanel.configWidget(button)
    assert gui._experiments[0]['Remote']['Go']['position'] == [180, 80]


def test_save_experiments(gui, tmp_path):
    configFile = tmp_path / "default.sreg"
    original = configFile.read_text()
    os.chmod(configFile, 0o640)

    rightDrag(remoteWidget(gui, MovablePushButton), QPoint(10, 0))
    gui.remotePanel.removeWidget(remoteWidget(gui, MovableSlider))
    assert gui.saveExperiments()

    saved = savedExperiments(configFile)
    assert [e['Name'] for e in saved] == ['First', 'Second']
    assert saved[0]['Dummy'] == {'gain': 2.0}
    assert saved[0]['Remote'] == {'Go': {'widgetType': 'PushButton', 'Module': 'Dummy', 'Parameter': 'gain',
                                         'valueOn': '1', 'shortcut-Gp': 'S', 'position': [160, 60]}}
    # the hand written file is kept once, the file mode stays
    assert (tmp_path / "default.sreg.bak").read_text() == original
    assert stat.S_IMODE(configFile.stat().st_mode) == 0o640

    # a second save does not replace the backup
    assert gui.saveExperiments()
    assert (tmp_path / "default.sreg.bak").read_text() == original

    # the saved file loads with the same widgets
    form = pw.MainGui()
    try:
        assert [w.widgetName for w in form.remotePanel.widgets] == ['Go']
        assert form.remotePanel.widgets[0].position() == [160, 60]
    finally:
        form.close()


def test_save_stores_unmoved_widget_positions(gui, tmp_path):
    assert gui.saveExperiments()
    assert savedExperiments(tmp_path / "default.sreg")[0]['Remote']['Gain']['position'] == [0, 0]


def test_save_keeps_skipped_experiments(qtbot, cleanRegistry, tmp_path):
    pw.registerConnection(DummyConnection)
    pw.registerExperimentModule(Dummy)
    (tmp_path / "default.sreg").write_text(textwrap.dedent("""
        - Name: Valid
          Dummy:
        - Name: Broken
          NotRegistered:
            x: 1
    """))
    form = pw.MainGui()
    qtbot.addWidget(form)
    assert form.experimentList.count() == 1
    assert form.saveExperiments()
    saved = savedExperiments(tmp_path / "default.sreg")
    assert [e['Name'] for e in saved] == ['Valid', 'Broken']
    assert saved[1]['NotRegistered'] == {'x': 1}


def test_save_experiments_as(gui, tmp_path, monkeypatch):
    target = tmp_path / "other"
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    assert gui.saveExperimentsAs()
    assert savedExperiments(tmp_path / "other.sreg")[1]['Name'] == 'Second'
    assert gui._configFile == str(tmp_path / "other.sreg")
    # nothing to back up for a new file
    assert not (tmp_path / "other.sreg.bak").exists()

    # aborting the dialog saves nothing
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    assert not gui.saveExperimentsAs()


def test_save_failure_keeps_file(gui, tmp_path, caplog):
    configFile = tmp_path / "default.sreg"
    original = configFile.read_text()
    with mock.patch.object(pw.gui, 'dumpExperiments', side_effect=yaml.YAMLError("broken")):
        assert not gui.saveExperiments()
    assert "Cannot save experiments" in caplog.text
    assert configFile.read_text() == original
    assert not gui.saveExperiments(str(tmp_path / "missing" / "x.sreg"))
    assert [p.name for p in tmp_path.iterdir() if p.suffix == '.sreg'] == ['default.sreg']


def test_copy_remote_source(gui):
    gui.copyRemoteSource()
    text = QApplication.clipboard().text()
    assert text.startswith("  Remote:\n    Gain:\n")
    remote = yaml.safe_load(textwrap.dedent(text))['Remote']
    assert set(remote) == {'Gain', 'Go'}
    assert 'name' not in remote['Go']
    assert remote['Go']['position'] == [150, 60]


def test_frames_go_to_the_active_connection(gui):
    inst = mock.Mock()
    gui.connectionManager.connection = inst
    gui.connectionManager.heartbeat()
    gui.connectionManager.write({'id': 10, 'msg': b'x'})
    assert [c.args[0] for c in inst.writeData.call_args_list] == [{'id': 1, 'msg': b'\x02'}, {'id': 10, 'msg': b'x'}]
    gui.connectionManager.connection = None


def test_measurement_list(gui):
    startExperiment(gui)
    item = gui.lastMeasList.item(0)
    measurement = item.data(Qt.ItemDataRole.UserRole)
    assert measurement is gui.measurements[0] and measurement.running
    assert item.text() == "1: First ~current~"
    assert gui._currentDataPointBuffers is measurement.dataPointBuffers

    gui.stopExperiment()
    assert not measurement.running
    assert item.text() == "1: First"

    startExperiment(gui)
    assert gui.lastMeasList.item(1).text() == "2: First ~current~"
    gui.stopExperiment()


def test_running_measurement_does_not_depend_on_the_text(gui):
    startExperiment(gui)
    gui.lastMeasList.item(0).setText("renamed")
    with mock.patch.object(gui.exp, 'sendParameterExperiment') as send:
        gui.sendParameter()
    send.assert_called_once()
    gui.stopExperiment()
    # the measurement is finished although its text has changed
    assert not gui.measurements[0].running
    assert gui.lastMeasList.item(0).text() == "1: First"


def test_parameters_only_go_to_the_shown_running_experiment(gui, caplog):
    startExperiment(gui)
    gui.stopExperiment()
    startExperiment(gui)
    # show the first, finished measurement while the second one runs
    gui._currentLastMeasItem = gui.lastMeasList.item(0)
    with mock.patch.object(gui.exp, 'sendChangedParameterExperiment') as send:
        gui.sendChangedParameter()
    send.assert_not_called()
    assert "doesn't match current running Experiment 'First'" in caplog.text
    gui.stopExperiment()

    with mock.patch.object(gui.exp, 'sendParameterExperiment') as send:
        gui.sendParameter()
    send.assert_not_called()
    assert "No experiment is running" in caplog.text


def test_load_last_measurement(gui):
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0)])
    gui.stopExperiment()

    # switch to the second experiment, then restore the measurement of the first one
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    gui.loadLastMeas(gui.lastMeasList.item(0))
    assert gui.exp.getExperiment()['Name'] == 'First'
    assert gui._currentMeasurement() is gui.measurements[0]
    assert list(gui.plotManager.currentBuffers()['x'].values) == [1.0]


def test_multi_button_sets_all_targets(gui):
    config = {'name': 'Stop', 'widgetType': 'MultiButton', 'shortcut': '',
              'targets': [{'Module': 'Dummy', 'Parameter': 'gain', 'value': '0'}]}
    gui.remotePanel.addWidget(config)
    button = remoteWidget(gui, MovableMultiButton)
    slider = remoteWidget(gui, MovableSlider)
    assert slider.value == 2.0

    with mock.patch.object(gui, 'sendChangedParameter') as send:
        gui.actSendParameter.setEnabled(True)
        button.click()
    assert gui.exp.getExperiment()['Dummy']['gain'] == '0'
    # the sliders of the parameter follow and everything is sent at once
    assert slider.value == 0
    send.assert_called_once()
    assert button.getData()['targets'] == config['targets']


def test_log_from_worker_thread(gui, qtbot):
    """ records of other threads are appended to the log box in the gui thread """
    import threading
    appended = []
    origAppend = gui.logBox.append
    gui.logBox.append = lambda msg: (appended.append(threading.current_thread()), origAppend(msg))

    worker = threading.Thread(target=lambda: logging.getLogger("Worker").warning("from the worker"))
    worker.start()
    worker.join()
    qtbot.waitUntil(lambda: "from the worker" in gui.logBox.toPlainText(), timeout=2000)
    assert appended == [threading.main_thread()]


@pytest.fixture
def customWidget():
    """ a widget type registered by an application, it sends twice the configured value """
    from pywisp.widgets.remote import REMOTE_WIDGETS

    class Doubler(MovablePushButton):
        widgetType = 'Doubler'

        def updates(self):
            return [(self.module, self.parameter, 2 * float(self.valueOn))]

    pw.registerRemoteWidget(Doubler)
    yield Doubler
    del REMOTE_WIDGETS['Doubler']


def test_custom_widget_type(gui, customWidget):
    exp = {'Name': 'Custom', 'Dummy': {'gain': 1.0},
           'Remote': {'Twice': {'widgetType': 'Doubler', 'Module': 'Dummy', 'Parameter': 'gain', 'valueOn': '3'}}}
    valid = pw.config.validateExperiments([exp], {'Dummy': Dummy}, {})
    assert valid and 'Twice' in valid[0]['Remote']

    gui.remotePanel.addWidget(dict(valid[0]['Remote']['Twice'], name='Twice'))
    widget = remoteWidget(gui, customWidget)
    widget.click()
    assert gui.exp.getExperiment()['Dummy']['gain'] == 6.0


def test_switch_sends_both_values(gui):
    gui.remotePanel.addWidget({'name': 'Sw', 'widgetType': 'Switch', 'Module': 'Dummy', 'Parameter': 'gain',
                         'valueOn': '5', 'valueOff': '0', 'shortcut': ''})
    switch = remoteWidget(gui, MovableSwitch)
    slider = remoteWidget(gui, MovableSlider)
    switch.click()
    assert gui.exp.getExperiment()['Dummy']['gain'] == '5'
    assert switch.text() == 'Sw\n0'
    assert slider.value == 5
    switch.click()
    assert gui.exp.getExperiment()['Dummy']['gain'] == '0'
    assert switch.text() == 'Sw\n5'


def test_push_button_reset_value(gui):
    button = remoteWidget(gui, MovablePushButton)
    button.valueReset = '0.5'
    with mock.patch.object(gui.exp, 'updateSendParameter') as updateSend:
        button.click()
    # the value is sent, afterwards the reset value is set without sending it
    assert gui.exp.getExperiment()['Dummy']['gain'] == '0.5'
    updateSend.assert_called_once_with('Dummy', 'gain', '0.5')


def test_plot_manager_shows_measurement(gui, qtbot):
    pm = gui.plotManager
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0), frame(2000, 2.0)])
    tree = pm.dataPointNameTree
    assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ['x']

    # without a plot, a default plot is created for the selected data point
    tree.topLevelItem(0).setSelected(True)
    pm.addDataPointToTree()
    plot = pm.dataPointTreeWidget.topLevelItem(0)
    assert plot.text(0) == 'plot_000' and plot.child(0).text(1) == 'x'

    pm.plotVectorClicked(plot)
    assert [d.title() for d in pm.findAllPlotDocks()] == ['plot_000']
    gui.updateDataPlots()
    x, y = pm.plotCharts['plot_000'].plotCurves['x'].getData()
    assert list(x) == [1.0, 2.0] and list(y) == [1.0, 2.0]
    gui.stopExperiment()

    # reserved names of the gui docks cannot be used for plots
    pm.addPlotTreeItem(default=True)
    pm.dataPointTreeWidget.topLevelItem(1).setText(0, 'Log')
    pm.plotVectorClicked(pm.dataPointTreeWidget.topLevelItem(1))
    assert [d.title() for d in pm.findAllPlotDocks()] == ['plot_000']

    with qtbot.waitSignal(pm.allPlotsClosed, timeout=2000):
        pm.closeAllPlots()
    assert pm.plotCharts == {} and pm.findAllPlotDocks() == []


@pytest.mark.parametrize('names', [None, ['pos', 'phi']])
def test_array_data_points(gui, monkeypatch, names):
    pm = gui.plotManager
    # without names the elements are called state.1 ..., given names come first
    e1, e2, e3 = (elementName('state', i, names) for i in range(3))
    monkeypatch.setattr(gui.exp, 'getDataPoints', lambda: ['x', 'state'])
    monkeypatch.setattr(gui.exp, 'getDataPointElements', lambda: {'state': names} if names else {})
    monkeypatch.setattr(gui.exp, 'handleFrame',
                        lambda f: {'Time': f[0], 'DataPoints': {'state': np.array(f[1:])}})
    startExperiment(gui)
    gui.updateData([(1000, 1.0, 10.0), (2000, 2.0, 20.0)])
    tree = pm.dataPointNameTree

    def children(item):
        return [item.child(i).text(0) for i in range(item.childCount())]

    assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ['x', 'state']
    assert children(tree.topLevelItem(0)) == []
    assert children(tree.topLevelItem(1)) == [e1, e2]

    # a longer array adds elements, expansion and selection are kept
    tree.topLevelItem(1).setExpanded(True)
    tree.topLevelItem(1).child(1).setSelected(True)
    gui.updateData([(3000, 3.0, 30.0, 300.0)])
    state = tree.topLevelItem(1)
    assert children(state) == [e1, e2, e3]
    assert state.isExpanded() and [item.text(0) for item in tree.selectedItems()] == [e2]

    # a single element is plotted over time
    pm.addDataPointToTree()
    plot = pm.dataPointTreeWidget.topLevelItem(0)
    assert plot.childCount() == 1 and plot.child(0).text(1) == e2
    pm.plotVectorClicked(plot)
    gui.updateDataPlots()
    x, y = pm.plotCharts['plot_000'].plotCurves[e2].getData()
    assert list(x) == [1.0, 2.0, 3.0] and list(y) == [10.0, 20.0, 30.0]

    # the parent stands for all of its elements
    tree.clearSelection()
    state.setSelected(True)
    pm.addDataPointToTree()
    assert set(pm.plotCharts['plot_000'].plotCurves) == {e1, e2, e3}
    x, y = pm.plotCharts['plot_000'].plotCurves[e3].getData()
    # earlier frames did not contain this element
    assert list(x) == [1.0, 2.0, 3.0] and np.isnan(y[:2]).all() and y[2] == 300.0
    gui.stopExperiment()

    # a new run shows the elements once they arrive, the old measurement keeps its elements
    startExperiment(gui)
    assert children(tree.topLevelItem(1)) == []
    gui.stopExperiment()
    gui.loadLastMeas(gui.lastMeasList.item(0))
    assert children(tree.topLevelItem(1)) == [e1, e2, e3]


def test_plot_manager_export_ends(gui, qtbot, tmp_path, monkeypatch):
    from pywisp.widgets.fileselector import FileSelector
    pm = gui.plotManager
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0)])
    gui.stopExperiment()
    monkeypatch.setattr(FileSelector, 'getSaveFileName', lambda self: str(tmp_path / "x.csv"))
    pm.dataPointNameTree.topLevelItem(0).setSelected(True)
    with qtbot.waitSignal(pm.exportDone, timeout=60000) as blocker:
        pm.exportDataPointFromTree()
    assert blocker.args == [True]
    assert pm.exporter is None
    assert gui.statusbarLabel.text() == "Export successful."
    assert (tmp_path / "x.csv").exists()


def test_connection_manager_reports_lost_connections(gui, qtbot):
    manager = gui.connectionManager
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        connectRig(gui, qtbot)
    assert manager.state == manager.CONNECTED and gui.actDisconnect.isEnabled()

    startExperiment(gui)
    inst = manager.connection
    with qtbot.waitSignal(manager.connectionLost, timeout=2000):
        # e.g. the rig has closed the connection
        inst.close()
    assert manager.state == manager.DISCONNECTED
    assert not gui.actStopExperiment.isEnabled() and gui.actConnect.isEnabled()
    assert gui.connectionLedState == 'red'
    assert gui.connectionLed.toolTip() == "Not connected"
    assert manager.connection is None


START = pw.controlFrame(pw.Control.START)


def rigStatus(gui, **kwargs):
    """ a status frame of the rig, see tests/test_status.py """
    gui.connectionManager._onFrames([statusFrame(**kwargs)])


def rigCell(gui):
    """ text and background color of the rig value of the setting gain """
    model = gui.exp.targetModel
    index = model.index(0, 2, model.index(0, 0))
    brush = model.data(index, Qt.ItemDataRole.BackgroundRole)
    return model.data(index), brush.color() if brush is not None else None


@pytest.fixture
def sent(gui):
    """ the frames sent by the experiment """
    frames = []
    gui.exp.sendData.connect(frames.append)
    return frames


def startConfirmed(gui, sent):
    """ start with a rig supporting syncs, which confirms the parameters and the start """
    rigStatus(gui, sync=(0, 0, 0))
    startExperiment(gui)
    rigStatus(gui, sync=(gui._startSyncId, *pw.frameCrc(sent)))
    rigStatus(gui, running=True, seq=1, sync=(gui.connectionManager._syncId, 0, 0))
    assert gui._startConfirmed


def test_start_waits_for_the_sync(gui, sent):
    green = pw.ExperimentInteractor.RIG_COLORS[True]
    red = pw.ExperimentInteractor.RIG_COLORS[False]
    rigStatus(gui, sync=(0, 0, 0))
    assert rigCell(gui) == ("", red)
    startExperiment(gui)
    assert sent == [{'id': 10, 'msg': struct.pack('<d', 2.0)}]
    assert gui._startSyncId is not None and gui.measurements == []
    assert gui.actStopExperiment.isEnabled()

    rigStatus(gui, sync=(gui._startSyncId, *pw.frameCrc(sent)))
    assert sent[-1] == START
    assert gui.exp.runningExperiment and gui._runningMeasurement is gui.measurements[-1]
    assert gui.measurements[-1].parameters == {'Dummy.gain': [(0.0, 2.0)]}
    assert gui.exp.rigSettings == {'Dummy': {'gain': 2.0}}
    assert rigCell(gui) == ("2.0", green)
    # the sync reset the counter of the rig, it reports no frames with the start
    rigStatus(gui, running=True, seq=1, sync=(gui.connectionManager._syncId, 0, 0))
    assert gui._startConfirmed
    gui.stopExperiment()


@pytest.mark.parametrize("confirm", [True, False])
def test_start_without_confirmed_parameters(gui, sent, qtbot, confirm):
    rigStatus(gui, sync=(0, 0, 0))
    gui.connectionManager.startTimeout = 100
    with mock.patch("pywisp.gui.QMessageBox.warning") as warning:
        startExperiment(gui)
        if confirm:
            # other parameters arrived
            rigStatus(gui, sync=(gui._startSyncId, 1, 0x123))
        else:
            qtbot.waitUntil(lambda: warning.called, timeout=2000)
    warning.assert_called_once()
    assert "not confirmed" in warning.call_args.args[2]
    assert START not in sent
    assert gui.measurements == [] and not gui.exp.runningExperiment
    assert not gui.actStopExperiment.isEnabled()
    assert "not confirmed" in gui._commError


def test_rig_without_sync_starts_with_a_warning(gui, sent, caplog):
    rigStatus(gui)
    startExperiment(gui)
    assert sent[-1] == START
    assert "no sync support" in caplog.text
    # the sent values are logged, but not shown as confirmed
    assert gui.measurements[-1].parameters == {'Dummy.gain': [(0.0, 2.0)]}
    assert rigCell(gui) == ("", None)
    gui.stopExperiment()


def test_changed_parameters_are_logged_once_confirmed(gui, sent):
    green = pw.ExperimentInteractor.RIG_COLORS[True]
    red = pw.ExperimentInteractor.RIG_COLORS[False]
    startConfirmed(gui, sent)
    gui.updateData([frame(1500, 1.0)])
    gui.exp.setParameter('Dummy', 'gain', 3.0)
    assert rigCell(gui) == ("2.0", red)
    count = len(sent)
    gui.sendChangedParameter()
    syncId = gui.connectionManager._syncId
    # not confirmed yet
    assert gui.measurements[-1].parameters == {'Dummy.gain': [(0.0, 2.0)]}
    rigStatus(gui, running=True, seq=1, sync=(syncId, *pw.frameCrc(sent[count:])))
    assert gui.measurements[-1].parameters == {'Dummy.gain': [(0.0, 2.0), (1.5, 3.0)]}
    assert rigCell(gui) == ("3.0", green)
    gui.stopExperiment()


def test_rig_values_are_cleared(gui, sent, qtbot):
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        connectRig(gui, qtbot)
    startConfirmed(gui, sent)
    gui.stopExperiment()
    # a restart of the rig loses the parameters
    rigStatus(gui, uptime=10, sync=(0, 0, 0))
    assert gui.exp.rigSettings is None
    gui.exp.confirmSettings({'Dummy': {'gain': 2.0}})
    gui.disconnectRig()
    assert gui.exp.rigSettings is None
    assert rigCell(gui) == ("", None)


def test_start_retry_keeps_one_measurement(gui, sent):
    rigStatus(gui, sync=(0, 0, 0))
    startExperiment(gui)
    rigStatus(gui, sync=(gui._startSyncId, *pw.frameCrc(sent)))
    assert len(gui.measurements) == 1
    # the rig reports other frames with the start, the start is tried again with a new sync
    rigStatus(gui, running=True, seq=1, count=3, crc=0x123, sync=(gui.connectionManager._syncId, 0, 0))
    assert gui._startRetried and gui._startSyncId is not None
    count = len(sent)
    rigStatus(gui, seq=1, sync=(gui._startSyncId, *pw.frameCrc(sent[count - 1:])))
    assert sent[-1] == START
    assert len(gui.measurements) == 1 and gui.lastMeasList.count() == 1
    assert gui._runningMeasurement is gui.measurements[0] and gui.measurements[0].running
    gui.stopExperiment()
