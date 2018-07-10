import logging
from abc import ABCMeta, abstractmethod

from PyQt5.QtCore import QObject

pyqtWrapperType = type(QObject)


class ExperimentModuleMeta(ABCMeta, pyqtWrapperType):
    pass


class ExperimentModule(QObject, metaclass=ExperimentModuleMeta):
    def __init__(self):
        QObject.__init__(self, None)
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def publicSettings(self):
        pass

    @property
    @abstractmethod
    def dataPoints(self):
        pass

    @abstractmethod
    def getStartParams(self):
        pass

    @abstractmethod
    def getStopParams(self):
        pass

    @abstractmethod
    def getParams(self, *kwargs):
        pass


class TestBench(ExperimentModule):
    """
    Base class for the used test bench
    """

    def __init__(self):
        ExperimentModule.__init__(self)


class Controller(ExperimentModule):
    """
    Base class for controllers.
    Args:
        settings (dict): Dictionary holding the config options for this module.
    """
    dataPoints = []

    def __init__(self):
        ExperimentModule.__init__(self)


class Trajectory(ExperimentModule):
    """
    Base class for all trajectory generators
    Args:
        settings (dict): Dictionary holding the config options for this module.
    """
    dataPoints = ['Referenz']

    def __init__(self):
        ExperimentModule.__init__(self)
