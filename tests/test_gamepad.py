import pytest

import pywisp.gamepad as gp
from pywisp.widgets.remote import MovablePushButton, MovableSlider, MovableSwitch


class FakeController:
    """ stands in for an SDL game controller """
    name = "Fake Pad"

    def __init__(self):
        self.buttons = set()
        self.axes = {}
        self.isAttached = True
        self.closed = False

    def update(self):
        pass

    def attached(self):
        return self.isAttached

    def axis(self, name):
        return self.axes.get(name, 0)

    def button(self, name):
        return name in self.buttons

    def close(self):
        self.closed = True


@pytest.fixture
def ctrl():
    return FakeController()


@pytest.fixture
def pad(ctrl, qtbot):
    return gp.Gamepad(ctrl, dict(gp.DEFAULT_MAPPING))


def recorder(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def test_mapping_covers_all_signals():
    assert set(gp.DEFAULT_MAPPING) == set(gp.AXES) | set(gp.BUTTONS)
    for abbrev in gp.AXES:
        assert hasattr(gp.Gamepad, 'abs' + abbrev)
    for abbrev in gp.BUTTONS:
        assert hasattr(gp.Gamepad, 'btn' + abbrev)


def test_button_emits_once_per_press(pad, ctrl):
    calls = recorder(pad.btnN)
    ctrl.buttons.add('y')
    pad.poll(0)
    pad.poll(0.001)
    assert len(calls) == 1
    ctrl.buttons.clear()
    pad.poll(0.002)
    ctrl.buttons.add('y')
    pad.poll(0.003)
    assert len(calls) == 2


def test_trigger_as_button(pad, ctrl):
    calls = recorder(pad.btnTHL)
    ctrl.axes['lefttrigger'] = gp.TRIGGER_THRESHOLD
    pad.poll(0)
    assert not calls
    ctrl.axes['lefttrigger'] = 32767
    pad.poll(0.001)
    assert len(calls) == 1


@pytest.mark.parametrize("raw, expected", [(-32768, -0.5), (0, 0.0), (32767, 0.5)])
def test_axis_scaling(pad, ctrl, raw, expected):
    calls = recorder(pad.absX)
    ctrl.axes['leftx'] = raw
    pad.poll(0)
    assert calls == [(pytest.approx(expected, abs=1e-3),)]


@pytest.mark.parametrize("button, abbrev, value", [
    ('dpup', 'HY', -0.5), ('dpdown', 'HY', 0.5), ('dpleft', 'HX', -0.5), ('dpright', 'HX', 0.5),
])
def test_dpad_as_axis(pad, ctrl, button, abbrev, value):
    ctrl.buttons.add(button)
    assert pad.readAxis(abbrev) == value


def test_axes_are_emitted_periodically(pad):
    calls = recorder(pad.absY)
    for t in (0.0, 0.05, 0.1, 0.15, 0.2):
        pad.poll(t)
    assert len(calls) == 3


def test_disconnect_ends_polling(pad, ctrl, caplog):
    ctrl.isAttached = False
    pad.run()
    assert not pad.runFlag
    assert ctrl.closed
    assert "disconnected" in caplog.text


def test_stop(pad, ctrl):
    pad.start()
    pad.stop()
    assert pad.isFinished()
    assert ctrl.closed


class TestMapping:
    def test_custom_mapping(self, tmp_path, ctrl, qtbot):
        # conftest already changes into tmp_path
        (tmp_path / 'gamepad.yaml').write_text("N: a\nX: rightx\n")
        pad = gp.Gamepad(ctrl)
        assert pad.mapping['N'] == 'a' and pad.mapping['X'] == 'rightx'
        assert pad.mapping['S'] == 'a'

        calls = recorder(pad.btnN)
        ctrl.buttons.add('a')
        pad.poll(0)
        assert calls

    def test_invalid_entries(self, tmp_path, caplog):
        (tmp_path / 'gamepad.yaml').write_text("Q: a\nN: nonsense\nS: b\n")
        mapping = gp.loadMapping()
        assert mapping['N'] == 'y' and mapping['S'] == 'b'
        assert "unknown abbreviation 'Q'" in caplog.text
        assert "unknown input 'nonsense'" in caplog.text

    def test_broken_file(self, tmp_path, caplog):
        (tmp_path / 'gamepad.yaml').write_text("- just\n- a list\n")
        assert gp.loadMapping() == gp.DEFAULT_MAPPING
        assert "Cannot read" in caplog.text

    def test_old_config_files(self, tmp_path, caplog):
        (tmp_path / 'gpLinux.yaml').write_text("faceButtons:\n  N: Key-BTN_SOUTH\n")
        assert gp.loadMapping() == gp.DEFAULT_MAPPING
        assert "gpLinux.yaml is no longer supported" in caplog.text


class TestRemoteWidgets:
    @pytest.mark.parametrize("cls, args", [
        (MovablePushButton, dict(valueOn='1', valueReset='0', shortcutKey='')),
        (MovableSwitch, dict(valueOn='1', valueOff='0', shortcutKey='')),
    ])
    def test_button(self, pad, ctrl, qtbot, cls, args):
        widget = cls('w', shortcutKeyGp='S', **args)
        qtbot.addWidget(widget)
        widget.updateGamepad(pad)
        clicks = recorder(widget.clicked)
        ctrl.buttons.add('a')
        pad.poll(0)
        assert len(clicks) == 1

        # disconnecting stops the forwarding
        widget.updateGamepad(None)
        ctrl.buttons.clear()
        pad.poll(0.001)
        ctrl.buttons.add('a')
        pad.poll(0.002)
        assert len(clicks) == 1

    def test_slider(self, pad, ctrl, qtbot):
        from PyQt5.QtWidgets import QLabel
        label = QLabel()
        slider = MovableSlider('s', minSlider='0', maxSlider='10', invertSlider=False, stepSlider='1',
                               label=label, shortcutPlusKey='', shortcutMinusKey='', shortcutKeyGp='X',
                               startValue='5')
        qtbot.addWidget(slider)
        qtbot.addWidget(label)
        slider.updateGamepad(pad)
        ctrl.axes['leftx'] = 32767
        pad.poll(0)
        assert slider.value == 10

    def test_wrong_input_kind(self, pad, qtbot, caplog):
        # a button cannot be driven by an axis
        widget = MovablePushButton('w', '1', '0', '', shortcutKeyGp='X')
        qtbot.addWidget(widget)
        widget.updateGamepad(pad)
        assert "absolute" in caplog.text
        assert widget._gamepadConnection is None

    def test_unknown_input(self, pad, qtbot, caplog):
        widget = MovablePushButton('w', '1', '0', '', shortcutKeyGp='Q')
        qtbot.addWidget(widget)
        widget.updateGamepad(pad)
        assert "not a valid gamepad button" in caplog.text


class TestSdl:
    def test_list_and_open(self, sdl, virtualPad, qtbot):
        pads = gp.getAllGamepads()
        assert gp.GamepadInfo(virtualPad.id, 'Virtual Controller') in pads

        pad = gp.openGamepad(virtualPad.id)
        assert pad.controller.name == 'Virtual Controller'
        with qtbot.waitSignal(pad.btnN, timeout=2000):
            virtualPad.press(sdl.SDL_CONTROLLER_BUTTON_Y)
        pad.stop()

    def test_unplugged_while_running(self, sdl, virtualPad, qtbot):
        pad = gp.openGamepad(virtualPad.id)
        with qtbot.waitSignal(pad.finished, timeout=2000):
            virtualPad.unplug()
        assert not pad.runFlag

    def test_open_unknown(self, sdl, caplog):
        assert gp.openGamepad(-12345) is None
        assert "no longer connected" in caplog.text

    def test_sdl_missing(self, monkeypatch):
        monkeypatch.setattr(gp, '_sdl', False)
        assert gp.getAllGamepads() == []
        assert gp.openGamepad(0) is None
