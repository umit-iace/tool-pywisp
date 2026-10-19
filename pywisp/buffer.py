# -*- coding: utf-8 -*-
"""
Storage of the values received for the data points.
"""
import numpy as np

__all__ = ["BufferView", "DataPointBuffer"]


class BufferView(np.ndarray):
    """
    Read only numpy view on the data of a :class:`DataPointBuffer`.

    In contrast to a plain array its truth value behaves like the one of a list,
    so ``if buffer.values:`` keeps working.
    """

    def __bool__(self):
        if self.ndim == 0:
            return bool(self.item())
        return self.size > 0


class DataPointBuffer(object):
    """
    Buffer object to store the values of the data points.

    The data is kept in numpy arrays that grow in chunks, :attr:`time` and :attr:`values`
    return views on the filled part.
    """
    _initialCapacity = 1024

    def __init__(self, time=None, values=None):
        time = np.asarray([] if time is None else time, dtype=float)
        values = np.asarray([] if values is None else values, dtype=float)
        if time.shape != values.shape:
            raise ValueError("time and values must have the same length")
        self._setData(time, values)

    def _setData(self, time, values):
        self._size = len(time)
        capacity = max(self._initialCapacity, self._size)
        self._time = np.empty(capacity)
        self._values = np.empty(capacity)
        self._time[:self._size] = time
        self._values[:self._size] = values

    def _view(self, arr):
        view = arr[:self._size].view(BufferView)
        view.flags.writeable = False
        return view

    @property
    def time(self):
        """ time stamps of the values (x axis) """
        return self._view(self._time)

    @property
    def values(self):
        """ values of the data point (y axis) """
        return self._view(self._values)

    def __len__(self):
        return self._size

    def _reserve(self, size):
        capacity = len(self._time)
        if size <= capacity:
            return
        # grow geometrically to keep appending amortized O(1)
        capacity = max(size, 2 * capacity)
        for name in ('_time', '_values'):
            old = getattr(self, name)
            new = np.empty(capacity)
            new[:self._size] = old[:self._size]
            setattr(self, name, new)

    def addValue(self, time, value):
        """
        Adds a new value to the data point buffer
        :param time: time(stamp) of the corresponding value (x axis)
        :param value: the new value for the data point (y axis)
        :return:
        """
        self._reserve(self._size + 1)
        # write the value first, so a failing conversion leaves the buffer untouched
        self._values[self._size] = value
        self._time[self._size] = time
        self._size += 1

    def extend(self, time, values):
        """
        Adds several values to the data point buffer
        :param time: time stamps of the values
        :param values: the new values
        """
        time = np.asarray(time, dtype=float)
        values = np.asarray(values, dtype=float)
        if time.shape != values.shape:
            raise ValueError("time and values must have the same length")
        n = len(time)
        self._reserve(self._size + n)
        self._time[self._size:self._size + n] = time
        self._values[self._size:self._size + n] = values
        self._size += n

    def snapshot(self):
        """
        Returns a buffer containing the current data without copying it.
        Data added later on to this buffer does not show up in the snapshot.
        """
        snap = DataPointBuffer.__new__(DataPointBuffer)
        snap._size = self._size
        snap._time = self._time[:self._size]
        snap._values = self._values[:self._size]
        return snap

    def clearBuffer(self):
        """
        Clears all the buffers of the data point
        """
        # allocate new memory, views handed out before must not see new data
        self._setData(np.empty(0), np.empty(0))

    def __getstate__(self):
        return {'time': self.time.view(np.ndarray).copy(), 'values': self.values.view(np.ndarray).copy()}

    def __setstate__(self, state):
        # also handles pickles of the former list based implementation
        self._setData(np.asarray(state['time'], dtype=float), np.asarray(state['values'], dtype=float))
