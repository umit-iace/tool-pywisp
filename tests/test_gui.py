# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict
from unittest import mock

import os
import stat
import textwrap

import pytest
import yaml
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu

import pywisp as pw
from pywisp.widgets.remote import MovableMultiButton, MovablePushButton, MovableSlider, MovableSwitch, MovableWidget

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
    connection = DummyConnection.__name__

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
    assert {type(w) for w in gui.remoteWidgetLayout.list} == {MovableSlider, MovablePushButton}


def test_empty_remote_section(gui):
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    assert gui.remoteWidgetLayout.list == []


def test_baud_menu(gui):
    menu = QMenu()
    gui.getBauds(DummySerial.settings, menu)
    checked = [a.text() for a in menu.actions() if a.isChecked()]
    assert checked == ["115200"]


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


def test_movable_widgets_use_mixin_handlers():
    for cls in (MovablePushButton, MovableSwitch, MovableSlider):
        assert cls.mousePressEvent is MovableWidget.mousePressEvent
        assert cls.mouseReleaseEvent is MovableWidget.mouseReleaseEvent


def test_connection_names_are_bound_correctly(gui):
    gui.connections = {"DummyConnection": {"cls": DummyConnection}}
    with mock.patch.object(DummyConnection, "_connect", return_value=True):
        gui.connect()
    try:
        assert gui.isConnected
        with mock.patch.object(gui, "updateData") as updateData:
            gui.connections["DummyConnection"]["inst"].receivedFrames.emit([pw.Frame(15, b"")])
        updateData.assert_called_once()
        assert updateData.call_args.args[1] == "DummyConnection"
    finally:
        gui.disconnect()
    assert not gui.isConnected
    assert "inst" not in gui.connections["DummyConnection"]


def test_failed_connection_closes_others(gui):
    with mock.patch.object(DummyConnection, "_connect", return_value=True), \
            mock.patch.object(DummySerial, "_connect", return_value=False):
        gui.connect()
    assert not gui.isConnected
    assert all("inst" not in c for c in gui.connections.values())


def test_gamepad_slider_mapping(gui):
    slider = next(w for w in gui.remoteWidgetLayout.list if isinstance(w, MovableSlider))
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

    button = next(w for w in gui.remoteWidgetLayout.list if isinstance(w, MovablePushButton))
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

    # the second experiment has no remote widgets
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    assert gui.remoteWidgetLayout.list == []
    with mock.patch.object(gui, 'remotePushButtonSendParameter') as send:
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
    gui.updateData([frame(1000, 1.0), frame(2000, 2.0)], "DummyConnection")
    buf = gui._currentDataPointBuffers['x']
    assert list(buf.time) == [1.0, 2.0]
    assert list(buf.values) == [1.0, 2.0]
    gui.stopExperiment()
    # the finished run keeps its data and is no longer modified
    stored = gui.measurements[-1].dataPointBuffers['x']
    gui.updateData([frame(3000, 3.0)], "DummyConnection")
    assert len(stored) == 2


def test_failing_module_does_not_crash(gui, monkeypatch, caplog):
    def broken(self, frame):
        raise RuntimeError("boom")
    monkeypatch.setattr(Dummy, "handleFrame", broken)
    startExperiment(gui)
    gui.updateData([frame(1000, 1.0)] * 50, "DummyConnection")
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
    return next(w for w in gui.remoteWidgetLayout.list if isinstance(w, cls))


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
    with mock.patch.object(pw.gui.RemoteWidgetEdit, 'getData', return_value=(config, True)):
        gui.remoteConfigWidget(button)
    assert gui._experiments[0]['Remote']['Go']['position'] == [180, 80]


def test_save_experiments(gui, tmp_path):
    configFile = tmp_path / "default.sreg"
    original = configFile.read_text()
    os.chmod(configFile, 0o640)

    rightDrag(remoteWidget(gui, MovablePushButton), QPoint(10, 0))
    gui.remoteRemoveWidget(remoteWidget(gui, MovableSlider))
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
        assert [w.widgetName for w in form.remoteWidgetLayout.list] == ['Go']
        assert form.remoteWidgetLayout.list[0].position() == [160, 60]
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


def test_heartbeat_goes_to_all_connections(gui):
    sent = {}
    for name in gui.connections:
        inst = mock.Mock()
        inst.writeData.side_effect = lambda data, name=name: sent.setdefault(name, []).append(data)
        gui.connections[name]['inst'] = inst
    gui.heartbeat()
    assert sent == {name: [{'id': 1, 'msg': b'\x02'}] for name in gui.connections}


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
    gui.updateData([frame(1000, 1.0)], "DummyConnection")
    gui.stopExperiment()

    # switch to the second experiment, then restore the measurement of the first one
    gui.experimentDoubleClicked(gui.experimentList.item(1))
    gui.loadLastMeas(gui.lastMeasList.item(0))
    assert gui.exp.getExperiment()['Name'] == 'First'
    assert gui._currentMeasurement() is gui.measurements[0]
    assert list(gui.getCurrentDataPoints()['x'].values) == [1.0]


def test_multi_button_sets_all_targets(gui):
    config = {'name': 'Stop', 'widgetType': 'MultiButton', 'shortcut': '',
              'targets': [{'Module': 'Dummy', 'Parameter': 'gain', 'value': '0'}]}
    gui.remoteAddWidget(config)
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
