# -*- coding: utf-8 -*-
import copy
import pickle

import numpy as np
import pytest

from pywisp.utils import DataPointBuffer


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
