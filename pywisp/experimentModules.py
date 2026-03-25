# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

from PyQt5.QtCore import QObject

from .min import Frame

pyqtWrapperType = type(QObject)

__all__ = ["ExperimentModule"]


class ExperimentModuleMeta(ABCMeta, pyqtWrapperType):
    pass


class ExperimentModuleException(Exception):
    """
    Special exception used internally be pywisp to deal with errors arising from
    packing and parsing data for and from the rig.
    """
    pass


class ExperimentModule(QObject, metaclass=ExperimentModuleMeta):
    """
    Base unit to build an experiment.

    This class provides necessary functions like start, stop and general
    parameter handling and holds all settings that can be accessed by the
    user.
    """
    def __init__(self):
        QObject.__init__(self, None)
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def publicSettings(self) -> OrderedDict:
        """
        Public settings of the module that are shown in the GUI.
        All entries
        stated in this dictionary will be available as changeable settings for the
        module. On initialization, a possibly modified (in terms of its values) version of
        this dict will be passed back to this class and is thenceforward available
        via the :py:attr:`settings` property.
        """
        pass

    @property
    @abstractmethod
    def dataPoints(self) -> list[str]:
        """
        List of labels for all data points that can be received from this module.
        These are used to label the measurements in the GUI for plotting.
        """
        pass

    @property
    @abstractmethod
    def connection(self) -> str:
        """
        Name of the connection class to be used.
        """
        pass

    @abstractmethod
    def handleFrame(self, frame: Frame) -> dict:
        """
        Handle frames from test rig so they can be shown in the GUI.

        This function must return a dictionary with the following keys:

        * Time (float): Timestamp of the measurement.
        * DataPoints (dict): Dictionary of measurements where the keys are the labels and the values hold the
          actual data.

        Note:
            To unpack the frame use the :mod:`struct` module.
        """
        pass

    @abstractmethod
    def getStartParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test rig when starting an experiment
        See :meth:`getParams` for details.
        """
        pass

    @abstractmethod
    def getStopParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test rig when stopping an experiment
        See :meth:`getParams` for details.
        """
        pass

    @abstractmethod
    def getParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test everytime a setting is changed in the GUI

        This function must return a list of data frames to be sent, where each frame is given
        by a dictionary with the following keys:

            * id (int): Frame ID to help the test rig sort out what the frame contains.
              This must be unique for the whole application, or you will be in trouble.
            * msg (bytes): The actual payload.

        Note:
            To construct the payload use the :mod:`struct` module.
        """
        pass

