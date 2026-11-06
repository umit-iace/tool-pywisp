# -*- coding: utf-8 -*-
import copy
import pickle

import numpy as np
import pytest

from pywisp.buffer import DataPointBuffer


def test_grows_beyond_initial_capacity():
    buf = DataPointBuffer()
    n = DataPointBuffer._initialCapacity * 3 + 7
    for i in range(n):
        buf.addValue(i, 2 * i)
    assert len(buf) == n
    np.testing.assert_array_equal(buf.time, np.arange(n))
    np.testing.assert_array_equal(buf.values, 2 * np.arange(n))


def test_list_like_truthiness():
    buf = DataPointBuffer()
    assert not buf.values
    buf.addValue(0, 0.0)
    buf.addValue(1, 5.0)
    # this is how the visualizers in the examples use the buffers
    assert buf.values
    assert buf.values[-1] == 5.0


def test_views_are_read_only():
    buf = DataPointBuffer([0, 1], [2, 3])
    with pytest.raises(ValueError):
        buf.values[0] = 1


def test_snapshot_is_not_affected_by_new_data():
    buf = DataPointBuffer()
    buf.extend([0, 1], [10, 11])
    snap = buf.snapshot()
    buf.addValue(2, 12)
    assert list(snap.values) == [10, 11]
    assert list(buf.values) == [10, 11, 12]


def test_clear_does_not_touch_old_views():
    buf = DataPointBuffer([0, 1], [10, 11])
    view = buf.values
    buf.clearBuffer()
    buf.addValue(5, 99)
    assert list(view) == [10, 11]
    assert list(buf.values) == [99]


def test_invalid_value_leaves_buffer_untouched():
    buf = DataPointBuffer()
    with pytest.raises((TypeError, ValueError)):
        buf.addValue(0, "abc")
    assert len(buf) == 0


def test_pickle_and_deepcopy():
    buf = DataPointBuffer([0, 1, 2], [3, 4, 5])
    for clone in (pickle.loads(pickle.dumps(buf)), copy.deepcopy(buf)):
        assert list(clone.time) == [0, 1, 2]
        assert list(clone.values) == [3, 4, 5]
        clone.addValue(3, 6)
        assert len(buf) == 3


def test_legacy_pickle_state():
    buf = DataPointBuffer.__new__(DataPointBuffer)
    buf.__setstate__({'time': [0, 1], 'values': [2, 3]})
    assert list(buf.values) == [2, 3]


def test_array_values():
    buf = DataPointBuffer()
    buf.addValue(0.0, np.array([1.0, 2.0, 3.0]))
    buf.addValue(1.0, [4.0, 5.0, 6.0])
    assert buf.columns == 3 and len(buf) == 2
    assert buf.values.shape == (2, 3) and list(buf.values[-1]) == [4.0, 5.0, 6.0]
    element = buf.column(1)
    assert list(element.time) == [0.0, 1.0] and list(element.values) == [2.0, 5.0] and len(element) == 2

    # element views follow the parent when it reallocates
    n = DataPointBuffer._initialCapacity + 5
    for i in range(n):
        buf.addValue(2.0 + i, [i, i, i])
    assert len(element.values) == n + 2 and element.values[-1] == n - 1
    assert not element.values.flags.writeable


def test_array_values_grow_and_shrink():
    buf = DataPointBuffer()
    buf.addValue(0.0, [1.0, 2.0])
    old = buf.column(1).snapshot()
    buf.addValue(1.0, [3.0, 4.0, 5.0])
    buf.addValue(2.0, [6.0])
    np.testing.assert_array_equal(buf.values, [[1, 2, np.nan], [3, 4, 5], [6, np.nan, np.nan]])
    # the snapshot is independent of the new data and the reallocation
    assert list(old.time) == [0.0] and list(old.values) == [2.0]


def test_mixed_values_are_rejected():
    arrays = DataPointBuffer()
    arrays.addValue(0.0, [1.0, 2.0])
    numbers = DataPointBuffer([0.0], [1.0])
    for buf, value in ((arrays, 3.0), (arrays, np.zeros((2, 2))), (numbers, [1.0, 2.0]), (arrays, [1.0, 'a'])):
        with pytest.raises(ValueError):
            buf.addValue(1.0, value)
        assert len(buf) == 1
    assert arrays.columns == 2 and numbers.columns is None


def test_array_pickle():
    buf = DataPointBuffer()
    buf.addValue(0.0, [1.0, 2.0])
    buffers = {'state': buf, 'state.2': buf.column(1)}
    clone = pickle.loads(pickle.dumps(buffers))
    assert clone['state.2'].parent is clone['state']
    clone['state'].addValue(1.0, [3.0, 4.0])
    assert list(clone['state.2'].values) == [2.0, 4.0] and len(buf) == 1
