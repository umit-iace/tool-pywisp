# -*- coding: utf-8 -*-
import struct
from collections import OrderedDict
from unittest import mock

import pytest
from PyQt5.QtWidgets import QMenu

import pywisp as pw
from pywisp.widgets.remote import MovablePushButton, MovableSlider, MovableSwitch, MovableWidget

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
    gui.experimentDclicked(gui.experimentList.item(1))
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
    slider._onGamePad(-0.5)
    assert slider.value == 0
    slider._onGamePad(0.0)
    assert slider.value == 5
    slider._onGamePad(0.5)
    assert slider.value == 10


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
    stored = gui.measurements[-1]['dataPointBuffers']['x']
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
