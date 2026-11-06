# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

from PyQt6.QtCore import QObject

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

    An instance of the module is created when an experiment using it is applied and
    is kept until another experiment is applied, so it can store state in attributes.
    :attr:`publicSettings` and :attr:`dataPoints` are read from the class and have to be
    class attributes.

    All modules send and receive via the connection selected in the gui, see
    :meth:`pywisp.registry.registerConnection`.

    Attributes:
        settings (OrderedDict): Current values of the :attr:`publicSettings`. They are set
            to the values of the experiment when it is applied and updated to the values
            passed to :meth:`getStartParams`, :meth:`getParams` and :meth:`getStopParams`
            right before these are called. So :meth:`handleFrame` sees the values that have
            been sent to the test rig last.
        connection (str): Name of the active connection class, e.g. to pack the frames differently
            per connection. It is set when the module is created and updated when another connection
            is selected, `None` outside of the gui.
    """
    # module classes warned about their own `connection` attribute
    _connectionWarned = set()

    def __init__(self):
        QObject.__init__(self, None)
        self._logger = logging.getLogger(self.__class__.__name__)
        cls = type(self)
        if hasattr(cls, 'connection') and cls not in ExperimentModule._connectionWarned:
            ExperimentModule._connectionWarned.add(cls)
            self._logger.warning(f"{cls.__name__}.connection is deprecated and ignored, the module uses the "
                                 f"connection selected in the gui, remove the attribute")
        self.settings = OrderedDict(self.publicSettings)
        self.connection = None

    @property
    @abstractmethod
    def publicSettings(self) -> OrderedDict:
        """
        Public settings of the module that are shown in the GUI, mapping their names to the
        default values. All entries stated in this dictionary will be available as changeable
        settings for the module. Their current values are passed to the parameter methods
        as list in the order of this dictionary and are available by name via :attr:`settings`.
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

    dataPointElements: dict[str, list[str]] = {}
    """
    Optional names of the elements of array data points, mapping a name from :attr:`dataPoints`
    to the names of its elements, e.g. ``{'state': ['pos', 'phi1', 'phi2']}``. They are shown, plotted
    and exported prefixed with the data point, ``state.pos`` etc. Elements without a name are called
    ``state.<k>`` (k counted from 1). An invalid or duplicate name is logged and replaced by the default one.
    Names given as a string instead of a list, or a data point named by more than one module,
    make applying the experiment fail.
    """

    def handleFrame(self, frame: Frame) -> dict:
        """
        Handle frames from test rig so they can be shown in the GUI.

        This function must return a dictionary with the following keys:

        * Time (float): Timestamp of the measurement.
        * DataPoints (dict): Dictionary of measurements where the keys are the labels and the values hold the
          actual data. A value is a number or a 1d array (e.g. ``{'state': np.array(data[1:])}``), whose
          elements are shown and plotted as ``state.<name>`` with the names of :attr:`dataPointElements` or
          ``state.1`` ... ``state.n``, the buffer ``state`` holds the arrays as rows.

        Return `None` if the frame is not meant for this module, which is also what the
        default implementation does.

        Note:
            To unpack the frame use the :mod:`struct` module.
        """
        return None

    def getStartParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test rig when starting an experiment
        See :meth:`getParams` for details. Sends nothing by default.
        """
        return []

    def getStopParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test rig when stopping an experiment
        See :meth:`getParams` for details. Sends nothing by default.
        """
        return []

    def getParams(self, *args) -> list[dict]:
        """
        Data to be sent to the test everytime a setting is changed in the GUI

        This function must return a list of data frames to be sent, where each frame is given
        by a dictionary with the following keys:

            * id (int): Frame ID to help the test rig sort out what the frame contains.
              This must be unique for the whole application, or you will be in trouble.
            * msg (bytes): The actual payload.

        Sends nothing by default.

        Note:
            To construct the payload use the :mod:`struct` module.
        """
        return []

