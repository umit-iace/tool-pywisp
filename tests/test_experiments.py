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
    startFrames = []
    frames = []

    def getStartParams(self, data):
        return self.startFrames

    def getParams(self, data):
        return self.frames


class Broken(pw.ExperimentModule):
    dataPoints = []
    publicSettings = OrderedDict()

    def __init__(self):
        raise RuntimeError("hardware missing")


@pytest.fixture
def interactor(qtbot, cleanRegistry):
    for mod in (Counter, Legacy, Echo, Rogue, Broken):
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


def start(interactor):
    """ sends the parameters and the start command like the gui after a confirmed sync """
    expected = interactor.prepareExperiment()
    if expected is not None:
        interactor.runExperiment()
    return expected


def test_state_is_kept_in_the_instance(interactor):
    assert interactor.setExperiment({'Name': 'a', 'Counter': {'step': 3}})
    start(interactor)
    assert ids(interactor) == [20, 21, 1]

    for _ in range(3):
        result = interactor.handleFrame(Frame(30, b''))
    assert result == {'Time': 3, 'DataPoints': {'n': 3}}

    # the instance lives on for further runs of the same experiment
    interactor.stopExperiment()
    start(interactor)
    assert interactor.handleFrame(Frame(30, b''))['Time'] == 4
    assert interactor._getInstance('Counter').started == 2


def test_applying_an_experiment_creates_new_instances(interactor):
    interactor.setExperiment({'Name': 'a', 'Counter': {}})
    first = interactor._getInstance('Counter')
    interactor.handleFrame(Frame(30, b''))

    interactor.setExperiment({'Name': 'b', 'Counter': {}})
    second = interactor._getInstance('Counter')
    assert second is not first
    assert interactor.handleFrame(Frame(30, b''))['Time'] == 1


def test_modules_know_the_active_connection(interactor):
    interactor.setConnection('Udp')
    interactor.setExperiment({'Name': 'a', 'Counter': {}, 'Echo': {}})
    counter, echo = interactor._getInstance('Counter'), interactor._getInstance('Echo')
    assert counter.connection == echo.connection == 'Udp'
    interactor.setConnection('Tcp')
    assert counter.connection == echo.connection == 'Tcp'
    # new instances get the current one
    interactor.setExperiment({'Name': 'b', 'Counter': {}})
    assert interactor._getInstance('Counter').connection == 'Tcp'


def test_old_connection_attribute_is_deprecated(interactor, caplog, monkeypatch):
    monkeypatch.setattr(pw.ExperimentModule, '_connectionWarned', set())
    interactor.setConnection('Udp')
    with caplog.at_level(logging.WARNING):
        interactor.setExperiment({'Name': 'a', 'Legacy': {}})
        interactor.setExperiment({'Name': 'b', 'Legacy': {}})
    assert caplog.text.count("Legacy.connection is deprecated") == 1
    # the class attribute is overwritten by the active connection
    assert interactor._getInstance('Legacy').connection == 'Udp'
    assert Legacy.connection == 'Conn'


def test_legacy_module(interactor):
    assert interactor.setExperiment({'Name': 'a', 'Legacy': {'gain': 5}})
    start(interactor)
    assert frames(interactor) == [(22, b'\x05'), (1, b'\x01')]
    assert interactor.handleFrame(Frame(31, b'\x07')) == {'Time': 1, 'DataPoints': {'v': 7}}

    interactor.sent.clear()
    interactor.stopExperiment()
    assert frames(interactor) == [(1, b'\x00')]


def test_failing_constructor(interactor, caplog):
    assert not interactor.setExperiment({'Name': 'a', 'Broken': {}})
    assert "Cannot create experiment module 'Broken'" in caplog.text
    assert "hardware missing" in caplog.text


def test_defaults_of_the_base_class():
    class Minimal(pw.ExperimentModule):
        dataPoints = []
        publicSettings = OrderedDict()
    
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


def test_element_names(interactor, caplog):
    class Arrays(pw.ExperimentModule):
        dataPoints = ['state', 'u']
        dataPointElements = {'state': ['pos', 'gain', 'pos', 3, '3', '2', '7'], 'missing': ['a']}
        publicSettings = OrderedDict()
    
    pw.registerExperimentModule(Arrays)
    assert interactor.setExperiment({'Name': 'a', 'Arrays': {}, 'Echo': {}})
    # the names are prefixed with the data point, so 'gain' does not clash with the data point of Echo,
    # duplicates, non-strings and default names of other elements fall back to the default name
    assert interactor.getDataPointElements() == {'state': ['pos', 'gain', '3', '4', '5', '6', '7']}
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 5
    assert "'missing' is not a data point" in errors[-1]
    assert "'pos' for element 3 of 'state', using 'state.3'" in errors[0]


@pytest.mark.parametrize("elements, problem", [
    ({'state': 'pos'}, "must be a list"),
    ({'shared': ['a']}, "more than one module"),
])
def test_invalid_element_declarations_fail(interactor, caplog, elements, problem):
    class First(pw.ExperimentModule):
        dataPoints = ['state', 'shared']
        dataPointElements = {'shared': ['b']}
        publicSettings = OrderedDict()
    
    class Second(First):
        dataPoints = []
        dataPointElements = elements

    pw.registerExperimentModule(First)
    pw.registerExperimentModule(Second)
    assert not interactor.setExperiment({'Name': 'a', 'First': {}, 'Second': {}})
    assert problem in caplog.text


def test_settings_follow_the_experiment(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    mod = interactor._getInstance('Echo')
    assert mod.settings == {'gain': 2.0, 'offset': 0.0}
    assert interactor.handleFrame(Frame(41, b''))['DataPoints'] == {'gain': 2.0, 'offset': 0.0}


def test_settings_are_updated_when_sent(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    mod = interactor._getInstance('Echo')
    start(interactor)

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
    ({'id': 10, 'msg': b'x'}, None),
    ({'id': 0, 'msg': bytearray(b'x')}, None),
    ({'id': 1, 'msg': b'x'}, "reserved"),
    ({'id': 2, 'msg': b'x'}, "reserved"),
    ({'id': 5, 'msg': b'x'}, "reserved"),
    ({'id': 6, 'msg': b'x'}, None),
    ({'id': 256, 'msg': b'x'}, "[0, 255]"),
    ({'id': '5', 'msg': b'x'}, "integer"),
    ({'id': True, 'msg': b'x'}, "integer"),
    ({'id': 10, 'msg': 'x'}, "bytes"),
    ({'id': 10}, "bytes"),
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
    start(interactor)
    assert frames(interactor)[-1] == (1, bytes([pw.Control.START]))
    interactor.stopExperiment()
    assert frames(interactor)[-1] == (1, bytes([pw.Control.STOP]))


def test_reserved_id_aborts_start(interactor, monkeypatch, caplog):
    monkeypatch.setattr(Rogue, 'startFrames', [{'id': 1, 'msg': bytes([0])}])
    interactor.setExperiment({'Name': 'a', 'Rogue': {}})
    start(interactor)
    # nothing reaches the rig, especially no start command
    assert interactor.sent == []
    assert not interactor.runningExperiment
    assert "reserved for the system frames" in caplog.text


def test_invalid_frames_are_dropped_while_running(interactor, monkeypatch, caplog):
    interactor.setExperiment({'Name': 'a', 'Rogue': {}})
    start(interactor)
    interactor.sent.clear()

    monkeypatch.setattr(Rogue, 'frames', [{'id': 1, 'msg': b'\x00'}, {'id': 7, 'msg': b'ok'}, {'id': 300, 'msg': b''}])
    interactor.sendParameterExperiment()
    assert frames(interactor) == [(7, b'ok')]
    assert caplog.text.count("dropping it") == 2
    assert interactor.runningExperiment


def test_settings_are_the_data_object(interactor):
    """ the model only displays the settings, edits in the view and set parameters reach them """
    from PyQt6.QtCore import Qt
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    model = interactor.targetModel
    moduleIndex = model.index(0, 0)
    offsetIndex = model.index(1, 1, moduleIndex)

    # editing like the delegate does
    model.setData(offsetIndex, "0.25", Qt.ItemDataRole.EditRole)
    assert interactor.getExperiment()['Echo'] == {'gain': 2.0, 'offset': 0.25}
    # text that cannot be parsed keeps the old value
    model.setData(offsetIndex, "nonsense(", Qt.ItemDataRole.EditRole)
    assert interactor.getExperiment()['Echo']['offset'] == 0.25

    assert interactor.setParameter('Echo', 'gain', 3.0)
    assert model.data(model.index(0, 1, moduleIndex)) == '3.0'
    assert interactor.getExperiment()['Echo']['gain'] == 3.0
    assert not interactor.setParameter('Echo', 'missing', 1)
    assert not interactor.setParameter('Missing', 'gain', 1)

    # the experiment returned is a copy
    interactor.getExperiment()['Echo']['gain'] = 99
    assert interactor.getExperiment()['Echo']['gain'] == 3.0


def test_prepare_sends_parameters_and_run_the_start(interactor):
    interactor.setExperiment({'Name': 'a', 'Counter': {'step': 3}})
    expected = interactor.prepareExperiment()
    assert ids(interactor) == [20, 21]
    assert [f['id'] for f in expected] == [20, 21]
    assert interactor.lastSent == {'Counter': {'step': 3}}
    assert not interactor.runningExperiment
    interactor.runExperiment()
    assert ids(interactor) == [20, 21, 1]
    assert interactor.runningExperiment


def test_last_sent_holds_the_sent_settings(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}, 'Counter': {}})
    start(interactor)
    interactor.setParameter('Counter', 'step', 2)
    assert [f['id'] for f in interactor.sendChangedParameterExperiment()] == [21]
    assert interactor.lastSent == {'Counter': {'step': 2}}
    assert interactor.sendChangedParameterExperiment() is None
    assert interactor.lastSent == {}
    interactor.sendParameterExperiment()
    # Echo sends no frames, nothing to confirm, its settings count as on the rig
    assert set(interactor.lastSent) == {'Counter', 'Echo'}


def test_confirm_settings_reports_changes(interactor):
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    assert interactor.rigSettings is None
    changes = interactor.confirmSettings({'Echo': {'gain': 2.0, 'offset': 0.0}})
    assert changes == [('Echo', 'gain', 2.0), ('Echo', 'offset', 0.0)]
    assert interactor.confirmSettings({'Echo': {'gain': 3.0, 'offset': 0.0}}) == [('Echo', 'gain', 3.0)]
    assert interactor.rigSettings == {'Echo': {'gain': 3.0, 'offset': 0.0}}
    interactor.clearRigSettings()
    assert interactor.rigSettings is None


def rigCell(interactor, row):
    """ text and background color of the rig value in a row of the first module """
    from PyQt6.QtCore import Qt
    model = interactor.targetModel
    index = model.index(row, 2, model.index(0, 0))
    brush = model.data(index, Qt.ItemDataRole.BackgroundRole)
    return model.data(index), brush.color() if brush is not None else None


def test_rig_column(interactor):
    from PyQt6.QtCore import Qt
    green, red = ExperimentInteractor.RIG_COLORS[True], ExperimentInteractor.RIG_COLORS[False]
    interactor.setExperiment({'Name': 'a', 'Echo': {'gain': 2.0}})
    model = interactor.targetModel
    assert model.headerData(2, Qt.Orientation.Horizontal) == 'Rig'
    gainIndex = model.index(0, 2, model.index(0, 0))
    assert not model.flags(gainIndex) & Qt.ItemFlag.ItemIsEditable

    # no tracking, no colors
    interactor.confirmSettings({'Echo': {'gain': 2.0, 'offset': 0.0}})
    assert rigCell(interactor, 0) == ("", None)

    interactor.trackRig(True)
    assert rigCell(interactor, 0) == ("2.0", green)
    # an edit not sent yet
    interactor.setParameter('Echo', 'gain', 4.0)
    assert rigCell(interactor, 0) == ("2.0", red)
    model.setData(model.index(1, 1, model.index(0, 0)), "0.5", Qt.ItemDataRole.EditRole)
    assert rigCell(interactor, 1) == ("0.0", red)
    interactor.confirmSettings({'Echo': {'gain': 4.0, 'offset': 0.5}})
    assert rigCell(interactor, 0) == ("4.0", green)
    assert rigCell(interactor, 1) == ("0.5", green)

    # unknown rig values are not confirmed
    interactor.clearRigSettings()
    assert rigCell(interactor, 0) == ("", red)
    # the rig values survive applying an experiment
    interactor.confirmSettings({'Echo': {'gain': 4.0, 'offset': 0.5}})
    interactor.setExperiment({'Name': 'b', 'Echo': {'gain': 4.0}})
    assert rigCell(interactor, 0) == ("4.0", green)
    assert rigCell(interactor, 1) == ("0.5", red)
    interactor.trackRig(False)
    assert rigCell(interactor, 0) == ("", None)


def test_failing_modules_are_not_in_last_sent(interactor, monkeypatch):
    interactor.setExperiment({'Name': 'a', 'Counter': {}, 'Rogue': {}})
    monkeypatch.setattr(Rogue, 'frames', [{'id': 7, 'msg': b'ok'}])
    start(interactor)
    assert set(interactor.lastSent) == {'Counter', 'Rogue'}

    def broken(self, data):
        raise RuntimeError("boom")
    monkeypatch.setattr(Counter, 'getParams', broken)
    # one of the frames is dropped
    monkeypatch.setattr(Rogue, 'frames', [{'id': 1, 'msg': b'\x00'}, {'id': 7, 'msg': b'ok'}])
    interactor.sendParameterExperiment()
    assert interactor.lastSent == {}
    interactor.setParameter('Counter', 'step', 5)
    interactor.setParameter('Rogue', 'x', 5)
    interactor.sendChangedParameterExperiment()
    assert interactor.lastSent == {}
    # so they are never taken for confirmed values
    assert interactor.confirmSettings(interactor.lastSent) == []
