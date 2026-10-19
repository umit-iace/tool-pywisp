# -*- coding: utf-8 -*-
"""
Measurements recorded by running an experiment.
"""
import copy
import time

from .buffer import DataPointBuffer

__all__ = ["Measurement"]


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
