# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict

import pytest

from pywisp.config import validateExperiments


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
