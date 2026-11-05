import numpy as np
import pytest

from pywisp.measurement import Measurement, addDataPointValue, elementName


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


def test_array_data_point():
    buffers = Measurement(1, {'Name': 'A'}, ['x', 'state']).dataPointBuffers
    assert not addDataPointValue(buffers, 'x', 1.0, 5.0)
    assert addDataPointValue(buffers, 'state', 1.0, np.array([1.0, 2.0]))
    assert not addDataPointValue(buffers, 'state', 2.0, [3.0, 4.0])
    assert list(buffers) == ['x', 'state', 'state.1', 'state.2']
    assert list(buffers['x'].values) == [5.0]
    assert list(buffers['state'].values[-1]) == [3.0, 4.0]
    assert list(buffers['state.1'].time) == [1.0, 2.0] and list(buffers['state.1'].values) == [1.0, 3.0]
    assert list(buffers['state.2'].values) == [2.0, 4.0]

    # a longer array adds elements, earlier values are missing
    assert addDataPointValue(buffers, 'state', 3.0, (5.0, 6.0, 7.0))
    assert list(buffers['state.3'].time) == [1.0, 2.0, 3.0] and buffers['state.3'].values[-1] == 7.0
    assert np.isnan(buffers['state.3'].values[0])


@pytest.mark.parametrize('names, expected', [
    (None, ['state.1', 'state.2', 'state.3', 'state.4', 'state.5']),
    ([], ['state.1', 'state.2', 'state.3', 'state.4', 'state.5']),
    (['phi', 'theta'], ['phi', 'theta', 'state.3', 'state.4', 'state.5']),
    (['a', 'b', 'c', 'd', 'e'], ['a', 'b', 'c', 'd', 'e']),
    (['a', 'b', 'c', 'd', 'e', 'unused'], ['a', 'b', 'c', 'd', 'e']),
])
def test_element_name(names, expected):
    assert [elementName('state', i, names) for i in range(5)] == expected


def test_named_array_elements():
    buffers = Measurement(1, {'Name': 'A'}, ['state']).dataPointBuffers
    assert addDataPointValue(buffers, 'state', 1.0, [1.0, 2.0], ['phi'])
    assert addDataPointValue(buffers, 'state', 2.0, [3.0, 4.0, 5.0], ['phi'])
    assert list(buffers) == ['state', 'phi', 'state.2', 'state.3']
    assert buffers['phi'].parent is buffers['state'] and list(buffers['phi'].values) == [1.0, 3.0]
    assert list(buffers['state.2'].values) == [2.0, 4.0]


def test_invalid_data_point_values():
    buffers = Measurement(1, {'Name': 'A'}, ['state']).dataPointBuffers
    with pytest.raises(KeyError):
        addDataPointValue(buffers, 'unknown', 0.0, 1.0)
    with pytest.raises(ValueError):
        addDataPointValue(buffers, 'state', 0.0, np.zeros((2, 2)))
    # a bad element adds nothing
    with pytest.raises(ValueError):
        addDataPointValue(buffers, 'state', 0.0, [1.0, 'a'])
    assert list(buffers) == ['state'] and len(buffers['state']) == 0
