# -*- coding: utf-8 -*-
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

