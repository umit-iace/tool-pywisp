# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod

from PyQt5.QtCore import QObject

pyqtWrapperType = type(QObject)

__all__ = ["ExperimentModule"]


class ExperimentModuleMeta(ABCMeta, pyqtWrapperType):
    pass


class ExperimentModule(QObject, metaclass=ExperimentModuleMeta):
    """
    Smallest unit of the framework.
    This class provides necessary functions like start, stop and general
    parameter handling and holds all settings that can be accessed by the
    user.
    The :py:attr:`publicSettings` are rendered by the GUI. All entries
    stated in this dictionary will be available as changeable settings for the
    module. On initialization, a possibly modified (in terms of its values) version of
    this dict will be passed back to this class and is thenceforward available
    via the :py:attr:`settings` property.
    The :py:attr:`dataPoints` are accessible by the GUI for plotting.
    The :py:attr:`connection` determines the connection interface.
    """
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

    @property
    @abstractmethod
    def connection(self):
        pass

    @staticmethod
    @abstractmethod
    def handleFrame(frame):
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

