# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict

import pytest
import yaml

from pywisp.config import dumpExperiments, validateExperiments


class Mod:
    publicSettings = OrderedDict([("gain", 1.0), ("offset", 0.0)])


class Visu:
    pass


MODULES = {"Mod": Mod}
VISUALIZERS = {"Visu": Visu}


@pytest.fixture
def validate(caplog):
    caplog.set_level(logging.WARNING)

    def run(experiments):
        valid = validateExperiments(experiments, MODULES, VISUALIZERS)
        return valid, [r.getMessage() for r in caplog.records]
    return run


def test_valid_experiment_passes_silently(validate):
    exp = {"Name": "A", "Mod": {"gain": 2.0}, "Visu": {"Visu": None},
           "Config": {"TimerTime": 40, "MovingWindowSize": 10, "MovingWindowEnable": True},
           "Remote": {"W": {"widgetType": "PushButton", "Module": "Mod", "Parameter": "gain", "valueOn": "1"}}}
    valid, messages = validate([exp])
    assert valid == [exp]
    assert messages == []
    # optional widget keys get their defaults
    assert exp["Remote"]["W"]["shortcut"] == ""


def test_aliases_are_renamed(validate):
    exp = {"Name": "A", "Config": {"MovingWindowWidth": 5, "Heartbeat": 100}}
    valid, messages = validate([exp])
    assert exp["Config"] == {"MovingWindowSize": 5, "HeartbeatTime": 100}
    assert len(messages) == 2


def test_unknown_and_invalid_config(validate):
    exp = {"Name": "A", "Config": {"MovingWindowSise": 5, "TimerTime": "fast"}}
    valid, messages = validate([exp])
    assert valid == [exp]
    assert exp["Config"] == {"MovingWindowSise": 5}
    assert any("unknown key 'MovingWindowSise'" in m for m in messages)
    assert any("'TimerTime' must be" in m for m in messages)


def test_unknown_module_skips_experiment(validate):
    valid, messages = validate([{"Name": "A", "Modd": {}}, {"Name": "B", "Mod": None}])
    assert [e["Name"] for e in valid] == ["B"]
    assert any("'Modd'" in m for m in messages)


def test_missing_name_skips_experiment(validate):
    valid, _ = validate([{"Mod": None}, "nonsense"])
    assert valid == []


def test_unknown_setting_warns(validate):
    valid, messages = validate([{"Name": "A", "Mod": {"gian": 1}}])
    assert len(valid) == 1
    assert any("no setting 'gian'" in m for m in messages)


def test_broken_widgets_are_dropped(validate):
    exp = {"Name": "A", "Mod": None, "Remote": {
        "badType": {"widgetType": "Knob", "Module": "Mod", "Parameter": "gain"},
        "badParam": {"widgetType": "Switch", "Module": "Mod", "Parameter": "x", "valueOn": 1, "valueOff": 0},
        "missing": {"widgetType": "Slider", "Module": "Mod", "Parameter": "gain", "minSlider": 0},
        "extra": {"widgetType": "PushButton", "Module": "Mod", "Parameter": "gain", "valueOn": 1, "colour": "red"},
    }}
    valid, messages = validate([exp])
    assert list(exp["Remote"]) == ["extra"]
    assert any("unknown key(s) ['colour']" in m for m in messages)


def test_empty_sections_are_fine(validate):
    valid, messages = validate([{"Name": "A", "Remote": None, "Config": None, "Visu": None}])
    assert len(valid) == 1
    assert messages == []


def test_unknown_visualizer_warns(validate):
    _, messages = validate([{"Name": "A", "Visu": ["Visu", "Other"]}])
    assert messages == ["Experiment 'A': Visu: 'Other' is not a registered visualizer"]


def widget(**extra):
    return dict({"widgetType": "PushButton", "Module": "Mod", "Parameter": "gain", "valueOn": "1"}, **extra)


@pytest.mark.parametrize("position, valid", [
    ([10, 20], True), ((0, 5.5), True), ([10], False), ("10, 20", False), ([-1, 0], False), ([True, 1], False),
])
def test_widget_position(validate, position, valid):
    exp = {"Name": "A", "Mod": {}, "Remote": {"W": widget(position=position)}}
    _, messages = validate([exp])
    assert ("position" in exp["Remote"]["W"]) == valid
    assert any("invalid position" in m for m in messages) != valid


def test_dump_round_trip(validate):
    exp = {"Name": "A", "Mod": {"gain": 2.0}, "Config": {"TimerTime": 40},
           "Remote": {"W": widget(position=[10.0, 20], shortcut="P")}}
    validate([exp])
    # the gui stores the name in the widget config
    exp["Remote"]["W"]["name"] = "W"

    text = dumpExperiments([exp])
    loaded = yaml.safe_load(text)
    assert loaded == [{"Name": "A", "Mod": {"gain": 2.0}, "Config": {"TimerTime": 40},
                       "Remote": {"W": dict(widget(position=[10, 20], shortcut="P"))}}]
    # empty optional entries are omitted, the original is not changed
    assert "shortcut-Gp" not in text and "valueReset" not in text
    assert exp["Remote"]["W"]["name"] == "W"

    valid, messages = validate(loaded)
    assert valid and not messages


def test_dump_keeps_invalid_experiments():
    experiments = [{"Name": "A", "Unknown": {}}, "garbage", {"Mod": {}}]
    assert yaml.safe_load(dumpExperiments(experiments)) == experiments


def multiButton(targets):
    return {"widgetType": "MultiButton", "targets": targets, "shortcut": "Esc"}


def test_multi_button(validate):
    targets = [{"Module": "Mod", "Parameter": "gain", "value": 0}, {"Module": "Mod", "Parameter": "offset", "value": 0}]
    exp = {"Name": "A", "Mod": {}, "Remote": {
        "Stop": multiButton(targets),
        "empty": multiButton([]),
        "badTarget": multiButton([{"Module": "Mod", "Parameter": "gain"}]),
        "badParam": multiButton([targets[0], {"Module": "Mod", "Parameter": "x", "value": 0}]),
    }}
    valid, messages = validate([exp])
    assert list(exp["Remote"]) == ["Stop"]
    assert any("non-empty list" in m for m in messages)
    assert any("target 1 must be a mapping" in m for m in messages)
    assert any("target 2: module 'Mod' has no setting 'x'" in m for m in messages)

    loaded = yaml.safe_load(dumpExperiments(valid))
    assert loaded[0]["Remote"]["Stop"] == multiButton(targets)
