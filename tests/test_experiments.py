import logging
import struct
from collections import OrderedDict

import pytest
from PyQt6.QtWidgets import QTreeView

import pywisp as pw
from pywisp.experiments import ExperimentInteractor, checkFrame
from pywisp.min import Frame


class Counter(pw.ExperimentModule):
    """ keeps state between calls, which needs an instance """
    dataPoints = ['n']
    publicSettings = OrderedDict([('step', 1)])
    connection = 'Conn'

    def __init__(self):
        super().__init__()
        self.count = 0
        self.started = 0

    def getStartParams(self, data):
        self.started += 1
        return [{'id': 20, 'msg': b'start'}]

    def getParams(self, data):
        return [{'id': 21, 'msg': struct.pack('<B', int(data[0]))}]

    def handleFrame(self, frame):
        if frame.id != 30:
            return None
        self.count += 1
        return {'Time': self.count, 'DataPoints': {'n': self.count}}


class Legacy(pw.ExperimentModule):
    """ written for the former class based calls, like the examples """
    dataPoints = ['v']
    publicSettings = OrderedDict([('gain', 2)])
    connection = 'Conn'
    ids = [31, 22]
    _logger = logging.getLogger("Legacy")

    def __init__(self):
        pw.ExperimentModule.__init__(self)

    # no getStartParams / getStopParams, these used to be optional

    def getParams(self, data):
        return {'id': self.ids[1], 'msg': struct.pack('<B', data[0])}

    def handleFrame(self, frame):
        if frame.id == self.ids[0]:
            return {'Time': 1, 'DataPoints': {Legacy.dataPoints[0]: frame.payload[0]}}
        return None


class Echo(pw.ExperimentModule):
    """ reports its settings with every frame """
    dataPoints = ['gain', 'offset']
    publicSettings = OrderedDict([('gain', 1.0), ('offset', 0.0)])
    connection = 'Conn'

    def __init__(self):
        # does not call the base class, which used to be harmless
        self.received = []

    def getParams(self, data):
        self.received.append(data)
        return []

    def handleFrame(self, frame):
        return {'Time': 0, 'DataPoints': dict(self.settings)}


class Rogue(pw.ExperimentModule):
    """ sends frames given by the test """
    dataPoints = []
    publicSettings = OrderedDict([('x', 0)])
    connection = 'Conn'
    startFrames = []
    frames = []

    def getStartParams(self, data):
        return self.startFrames

    def getParams(self, data):
        return self.frames


class Broken(pw.ExperimentModule):
    dataPoints = []
    publicSettings = OrderedDict()
    connection = 'Conn'

    def __init__(self):
        raise RuntimeError("hardware missing")


class Incomplete(pw.ExperimentModule):
    """ lacks the mandatory connection attribute """
    dataPoints = []
    publicSettings = OrderedDict()


@pytest.fixture
def interactor(qtbot, cleanRegistry):
    for mod in (Counter, Legacy, Echo, Rogue, Broken, Incomplete):
        pw.registerExperimentModule(mod)
    view = QTreeView()
    qtbot.addWidget(view)
    exp = ExperimentInteractor(view)
    exp.sent = []
    exp.sendData.connect(exp.sent.append)
    return exp


def ids(interactor):
    return [d['id'] for d in interactor.sent]


def frames(interactor):
    return [(d['id'], d['msg']) for d in interactor.sent]


def test_state_is_kept_in_the_instance(interactor):
    assert interactor.setExperiment({'Name': 'a', 'Counter': {'step': 3}})
    interactor.runExperiment()
    assert ids(interactor) == [20, 21, 1]

    for _ in range(3):
        result = interactor.handleFrame(Frame(30, b''), 'Conn')
    assert result == {'Time': 3, 'DataPoints': {'n': 3}}

    # the instance lives on for further runs of the same experiment
    interactor.stopExperiment()
    interactor.runExperiment()
    assert interactor.handleFrame(Frame(30, b''), 'Conn')['Time'] == 4
    assert interactor._getInstance('Counter').started == 2


def test_applying_an_experiment_creates_new_instances(interactor):
    interactor.setExperiment({'Name': 'a', 'Counter': {}})
    first = interactor._getInstance('Counter')
    interactor.handleFrame(Frame(30, b''), 'Conn')

    interactor.setExperiment({'Name': 'b', 'Counter': {}})
    second = interactor._getInstance('Counter')
    assert second is not first
    assert interactor.handleFrame(Frame(30, b''), 'Conn')['Time'] == 1


def test_frames_only_reach_modules_of_the_connection(interactor):
    interactor.setExperiment({'Name': 'a', 'Counter': {}})
    assert interactor.handleFrame(Frame(30, b''), 'Other') is None
    assert interactor._getInstance('Counter').count == 0


def test_legacy_module(interactor):
    assert interactor.setExperiment({'Name': 'a', 'Legacy': {'gain': 5}})
    interactor.runExperiment()
    assert frames(interactor) == [(22, b'\x05'), (1, b'\x01')]
    assert interactor.handleFrame(Frame(31, b'\x07'), 'Conn') == {'Time': 1, 'DataPoints': {'v': 7}}

    interactor.sent.clear()
    interactor.stopExperiment()
    assert frames(interactor) == [(1, b'\x00')]


def test_failing_constructor(interactor, caplog):
    assert not interactor.setExperiment({'Name': 'a', 'Broken': {}})
    assert "Cannot create experiment module 'Broken'" in caplog.text
    assert "hardware missing" in caplog.text


def test_missing_mandatory_attribute(interactor, caplog):
    assert not interactor.setExperiment({'Name': 'a', 'Incomplete': {}})
    assert "connection" in caplog.text


def test_defaults_of_the_base_class():
    class Minimal(pw.ExperimentModule):
        dataPoints = []
        publicSettings = OrderedDict()
        connection = 'Conn'

    mod = Minimal()
    assert mod.getStartParams([]) == []
    assert mod.getParams([]) == []
    assert mod.getStopParams([]) == []
    assert mod.handleFrame(Frame(5, b'')) is None


def test_settings_of_a_new_instance():
    mod = Counter()
    assert mod.settings == {'step': 1}
    # a copy, changing it must not touch the class defaults
    mod.settings['step'] = 5
    assert Counter.publicSettings['step'] == 1


def test_settings_follow_the_experiment(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    mod = interactor._getInstance('Echo')
    assert mod.settings == {'gain': 2.0, 'offset': 0.0}
    assert interactor.handleFrame(Frame(41, b''), 'Conn')['DataPoints'] == {'gain': 2.0, 'offset': 0.0}


def test_settings_are_updated_when_sent(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    mod = interactor._getInstance('Echo')
    interactor.runExperiment()

    # editing a value in the gui does not reach the module before it is sent
    interactor.editExperiment({'Echo': {'offset': 0.5}})
    assert mod.settings['offset'] == 0.0

    interactor.sendChangedParameterExperiment()
    assert mod.settings == {'gain': 2.0, 'offset': 0.5}
    assert mod.received[-1] == [2.0, 0.5]
    # the module gets its own copy
    mod.settings['gain'] = 99
    assert interactor.getExperiment()['Echo']['gain'] == 2.0


@pytest.mark.parametrize("frame, problem", [
    ({'id': 5, 'msg': b'x'}, None),
    ({'id': 0, 'msg': bytearray(b'x')}, None),
    ({'id': 1, 'msg': b'x'}, "reserved"),
    ({'id': 256, 'msg': b'x'}, "[0, 255]"),
    ({'id': '5', 'msg': b'x'}, "integer"),
    ({'id': True, 'msg': b'x'}, "integer"),
    ({'id': 5, 'msg': 'x'}, "bytes"),
    ({'id': 5}, "bytes"),
    ([5, b'x'], "dicts"),
])
def test_check_frame(frame, problem):
    result = checkFrame(frame)
    if problem is None:
        assert result is None
    else:
        assert problem in result


def test_control_frames_of_the_experiment(interactor):
    interactor.setExperiment({'Name': 'a', 'Counter': {}})
    interactor.runExperiment()
    assert frames(interactor)[-1] == (1, bytes([pw.Control.START]))
    interactor.stopExperiment()
    assert frames(interactor)[-1] == (1, bytes([pw.Control.STOP]))


def test_reserved_id_aborts_start(interactor, monkeypatch, caplog):
    monkeypatch.setattr(Rogue, 'startFrames', [{'id': 1, 'msg': bytes([0])}])
    interactor.setExperiment({'Name': 'a', 'Rogue': {}})
    interactor.runExperiment()
    # nothing reaches the rig, especially no start command
    assert interactor.sent == []
    assert not interactor.runningExperiment
    assert "reserved for the experiment control" in caplog.text


def test_invalid_frames_are_dropped_while_running(interactor, monkeypatch, caplog):
    interactor.setExperiment({'Name': 'a', 'Rogue': {}})
    interactor.runExperiment()
    interactor.sent.clear()

    monkeypatch.setattr(Rogue, 'frames', [{'id': 1, 'msg': b'\x00'}, {'id': 7, 'msg': b'ok'}, {'id': 300, 'msg': b''}])
    interactor.sendParameterExperiment()
    assert frames(interactor) == [(7, b'ok')]
    assert caplog.text.count("dropping it") == 2
    assert interactor.runningExperiment
