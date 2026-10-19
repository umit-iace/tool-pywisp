from types import SimpleNamespace

import pytest
import yaml

import pywisp.gamepad as gp
from pywisp.utils import getResource
from pywisp.widgets.remote import MovablePushButton, MovableSwitch


def event(evType, code, state=0):
    return SimpleNamespace(ev_type=evType, code=code, state=state)


class FakeDevice:
    """ stands in for a gamepad of the inputs library """
    name = "Fake Pad"

    def __init__(self, batches=()):
        self.batches = list(batches)

    def _do_iter(self):
        if not self.batches:
            raise OSError("device unplugged")
        return self.batches.pop(0)


def devices(*pads):
    return SimpleNamespace(gamepads=list(pads))


@pytest.fixture(params=[False, True], ids=['linux', 'windows'])
def platform(request, monkeypatch):
    monkeypatch.setattr(gp, 'WIN', request.param)
    return request.param


@pytest.fixture
def pad(qtbot):
    return gp.Gamepad(devices(FakeDevice()), 0)


def recorder(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


@pytest.mark.parametrize("fileName", ['gpPS4-LinuxDefault.yaml', 'gpPS4-WinDefault.yaml'])
def test_default_configs_match_signals(fileName):
    """ every abbreviation in the shipped configs needs a signal """
    with open(getResource(fileName, '')) as f:
        config = yaml.safe_load(f)
    for group in config.values():
        for abbrev, key in group.items():
            prefix = 'abs' if key.startswith('Absolute') else 'btn'
            assert hasattr(gp.Gamepad, prefix + abbrev), f"{fileName}: no signal for {abbrev}"


def test_abbrevs_from_default_config(platform, qtbot):
    pad = gp.Gamepad(devices(FakeDevice()), 0)
    abbrevs = pad.getAbbrevs()
    assert abbrevs['Absolute-ABS_X'] == 'X'
    assert set(pad.absState) == {'HX', 'HY', 'X', 'Y', 'Z', 'RZ'}
    assert set(pad.btnState) == {'N', 'E', 'S', 'W', 'THL', 'THR', 'TL', 'TR', 'Select', 'Start'}


def test_custom_config_in_working_directory(tmp_path, monkeypatch, qtbot):
    # conftest already changes into tmp_path
    monkeypatch.setattr(gp, 'WIN', False)
    (tmp_path / 'gpLinux.yaml').write_text("faceButtons:\n  N: Key-BTN_SOUTH\n")
    pad = gp.Gamepad(devices(FakeDevice()), 0)
    assert pad.getAbbrevs() == {'Key-BTN_SOUTH': 'N'}


def test_button_press_emits_once(pad):
    calls = recorder(pad.btnN)
    pad.processEvent(event('Key', 'BTN_TRIGGER', 1))
    pad.processEvent(event('Key', 'BTN_TRIGGER', 0))
    assert len(calls) == 1
    assert pad.btnState['N'] == 0 and pad.oldBtnState['N'] == 1


def test_ignored_and_unknown_events(pad, caplog):
    calls = recorder(pad.btnN)
    pad.processEvent(event('Sync', 'SYN_REPORT'))
    pad.processEvent(event('Misc', 'MSC_SCAN'))
    assert not caplog.text
    pad.processEvent(event('Key', 'BTN_UNKNOWN', 1))
    assert "BTN_UNKNOWN" in caplog.text
    assert not calls


@pytest.mark.parametrize("win, raw, expected", [
    (False, 0, -0.5), (False, 128, 0.0), (False, 255, 0.496),
    (True, -32768, -0.5), (True, 0, 0.0), (True, 32767, 0.5),
])
def test_axis_scaling(monkeypatch, qtbot, win, raw, expected):
    monkeypatch.setattr(gp, 'WIN', win)
    pad = gp.Gamepad(devices(FakeDevice()), 0)
    calls = recorder(pad.absX)
    pad.processEvent(event('Absolute', 'ABS_X', raw))
    # axis values are only sent periodically
    assert not calls
    pad.outputAbsEvent()
    assert calls == [(pytest.approx(expected, abs=1e-3),)]


def test_run_processes_events_until_unplugged(monkeypatch, qtbot):
    monkeypatch.setattr(gp, 'WIN', False)
    device = FakeDevice([[event('Key', 'BTN_THUMB', 1)], None, [event('Absolute', 'ABS_Y', 0)]])
    pad = gp.Gamepad(devices(device), 0)
    buttons, axes = recorder(pad.btnE), recorder(pad.absY)
    pad.run()
    assert not pad.runFlag
    assert len(buttons) == 1
    assert axes and axes[0] == (-0.5,)


def test_get_gamepad_by_index(monkeypatch, qtbot):
    monkeypatch.setattr(gp, 'WIN', False)
    assert gp.getGamepadByIndex(None, 0) is None
    assert gp.getGamepadByIndex(devices(), 0) is None
    assert gp.getGamepadByIndex(devices(None), 0) is None

    pad = gp.getGamepadByIndex(devices(FakeDevice()), 0)
    assert isinstance(pad, gp.Gamepad)
    # the fake device is unplugged right away, which ends the thread
    assert pad.wait(5000)
    assert not pad.runFlag


def test_stop(monkeypatch, qtbot):
    monkeypatch.setattr(gp, 'WIN', False)
    device = FakeDevice()
    device._do_iter = lambda: None
    pad = gp.getGamepadByIndex(devices(device), 0)
    pad.stop()
    assert pad.isFinished()


def test_get_all_gamepads(monkeypatch):
    found = devices(FakeDevice())
    monkeypatch.setattr(gp, 'rescan_devices', lambda: found)
    assert gp.getAllGamepads() is found
    monkeypatch.setattr(gp, 'rescan_devices', lambda: devices())
    assert gp.getAllGamepads() is None


@pytest.mark.parametrize("cls, args", [
    (MovablePushButton, dict(valueOn='1', valueReset='0', shortcutKey='')),
    (MovableSwitch, dict(valueOn='1', valueOff='0', shortcutKey='')),
])
def test_button_drives_remote_widget(pad, qtbot, cls, args):
    widget = cls('w', shortcutKeyGp='N', **args)
    qtbot.addWidget(widget)
    widget.updateGamepad(pad)
    clicks = recorder(widget.clicked)
    pad.processEvent(event('Key', 'BTN_TRIGGER', 1))
    assert len(clicks) == 1

    # disconnecting stops the forwarding
    widget.updateGamepad(None)
    pad.processEvent(event('Key', 'BTN_TRIGGER', 1))
    assert len(clicks) == 1


def test_remote_widget_rejects_wrong_input_kind(pad, qtbot, caplog):
    # a button cannot be driven by an axis
    widget = MovablePushButton('w', '1', '0', '', shortcutKeyGp='X')
    qtbot.addWidget(widget)
    widget.updateGamepad(pad)
    assert "absolute" in caplog.text
    assert widget._gamepadConnection is None
