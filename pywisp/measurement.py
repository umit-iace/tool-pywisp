# -*- coding: utf-8 -*-
"""
Measurements recorded by running an experiment.
"""
import copy
import time

from .buffer import DataPointBuffer

__all__ = ["Measurement", "addDataPointValue"]


def addDataPointValue(buffers, name, time, value):
    """
    Adds the value of the data point `name` to its buffer in `buffers`.

    A buffer receiving 1d arrays (e.g. numpy arrays or lists) stores them as rows, its
    elements are added to `buffers` as :class:`pywisp.buffer.ElementBuffer` `name.1` ... `name.n`.

    :return: `True` if new element buffers have been added
    :raises KeyError: if `name` has no buffer
    :raises TypeError, ValueError: if the value is neither a number nor a 1d array of numbers
    """
    buf = buffers[name]
    buf.addValue(time, value)
    created = False
    for idx in range(buf.columns or 0):
        key = f"{name}.{idx + 1}"
        if key not in buffers:
            buffers[key] = buf.column(idx)
            created = True
    return created


class Measurement:
    """
    Data and settings of one run of an experiment.

    :param number: running number of the measurement, shown in the gui
    :param experiment: settings of the experiment as returned by
        :meth:`pywisp.experiments.ExperimentInteractor.getExperiment`, a copy is stored
    :param dataPointNames: names of the data points to record
    """

    def __init__(self, number, experiment, dataPointNames):
        self.number = number
        self.experiment = copy.deepcopy(experiment)
        self.dataPointBuffers = {name: DataPointBuffer() for name in dataPointNames}
        self.startTime = time.time()
        self.stopTime = None

    @property
    def name(self):
        return self.experiment.get('Name', '')

    @property
    def running(self):
        return self.stopTime is None

    def finish(self):
        """ marks the measurement as finished, calling it again has no effect """
        if self.running:
            self.stopTime = time.time()

    def label(self):
        """ text shown in the list of measurements """
        text = f"{self.number}: {self.name}"
        return text + " ~current~" if self.running else text
