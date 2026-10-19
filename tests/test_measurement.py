from pywisp.measurement import Measurement


def test_running_measurement():
    exp = {'Name': 'First', 'Dummy': {'gain': 2.0}}
    meas = Measurement(3, exp, ['x', 'y'])
    assert meas.running
    assert meas.name == 'First'
    assert meas.label() == "3: First ~current~"
    assert set(meas.dataPointBuffers) == {'x', 'y'}
    # the settings are a copy, later changes of the experiment do not leak in
    exp['Dummy']['gain'] = 5.0
    assert meas.experiment['Dummy']['gain'] == 2.0


def test_finish():
    meas = Measurement(1, {'Name': 'A'}, [])
    meas.finish()
    stopTime = meas.stopTime
    assert not meas.running
    assert meas.label() == "1: A"
    meas.finish()
    assert meas.stopTime == stopTime
