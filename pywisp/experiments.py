# -*- coding: utf-8 -*-
from collections import OrderedDict

import ast
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QItemDelegate, QTreeView

from . import experimentModules
from .registry import *


class ExperimentException(Exception):
    pass


class ExperimentModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)
        self._name = None

    def setName(self, name):
        self._name = name

    def getName(self):
        return self._name

    def flags(self, index):
        if index.column() == 1:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsEnabled


class ExperimentStateChange(object):
    """
    Object that is emitted when Experiment changes its state.

    Keyword Args:
        type: Keyword describing the state change, can be one of the following

            * `init` Initialisation
            * `start` : Start of Experiment
            * `abort` : Abortion of Experiment

        data: Data that is emitted on state change.
        info: Further information.

    """

    def __init__(self, **kwargs):
        assert "type" in kwargs.keys()
        for key, val in kwargs.items():
            setattr(self, key, val)


class PropertyItem(QStandardItem):
    RawDataRole = Qt.UserRole + 1

    def __init__(self, data):
        QStandardItem.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._text = self._getText(data)
        self.isUsed = False

    def type(self):
        return QStandardItem.UserType

    def _getText(self, data):
        return str(data)

    def setData(self, Any, role=None, *args, **kwargs):
        if role == Qt.EditRole:
            try:
                self._data = ast.literal_eval(Any)
            except (SyntaxError, ValueError) as e:
                self._logger.exception(e)
                return
            self._text = str(self._data)

        elif role == self.RawDataRole:
            self._data = Any
            self._text = self._getText(Any)

        else:
            raise NotImplementedError

        self.emitDataChanged()

    def data(self, role=None, *args, **kwargs):
        if role == Qt.DisplayRole:
            return self._text
        elif role == Qt.EditRole:
            if isinstance(self._data, str):
                return "'" + self._text + "'"
            else:
                return self._text
        elif role == self.RawDataRole:
            return self._data

        else:
            return super().data(role, *args, **kwargs)


class PropertyDelegate(QItemDelegate):
    """
    A delegate that manages all property settings.
    For now it uses a combobox for experimentModules and a standard
    delegate for the rest.
    """

    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        if index.parent().isValid():
            return QItemDelegate.createEditor(self, parent, option, index)
        else:
            # no parent -> top of hierarchy
            return None

    def setEditorData(self, editor, index):
        QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        QItemDelegate.setModelData(self, editor, model, index)


class ExperimentView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegateForColumn(1, PropertyDelegate(self))

    def sizeHint(self):
        return QSize(300, 150)

    def minimumSizeHint(self):
        return self.sizeHint()


class ExperimentInteractor(QObject):
    """
    Class that interacts between the gui which controls the programs execution
    and the Experiment
    """
    expFinished = pyqtSignal()

    def __init__(self, inputQueue, targetView, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.inputQueue = inputQueue
        self.targetView = targetView
        self.dataPoints = None
        self.runningExperiment = False
        # create model
        self.targetModel = ExperimentModel(self)
        self.targetModel.itemChanged.connect(self.itemChanged)

    def _addSettings(self, index):
        parent = index.model().itemFromIndex(index)
        moduleName = parent.data(role=PropertyItem.RawDataRole)

        settings = self._readSettings(moduleName)
        for key, val in settings.items():
            setting_name = PropertyItem(key)
            setting_value = PropertyItem(val)
            parent.appendRow([setting_name, setting_value])

    def _readSettings(self, moduleName):
        """
        Read the public settings from an experiment module
        """
        for module in getRegisteredExperimentModules():
            if module[1] == moduleName:
                return module[0].publicSettings

        raise ExperimentException("_readSettings(): No module called {} found!".format(moduleName))

    def _readDataPoints(self, index):
        """
        Read the data points from an experiment module
        """
        parent = index.model().itemFromIndex(index)
        moduleName = parent.data(role=PropertyItem.RawDataRole)

        for module in getRegisteredExperimentModules():
            if module[1] == moduleName:
                return module[0].dataPoints

        raise ExperimentException("_readDataPoints(): No module called {} found!".format(moduleName))

    def itemChanged(self, item):
        if item.parent():
            return

        idx = item.index()
        moduleItem = idx.model().item(idx.row())

        # delete all old settings
        moduleItem.removeRows(0, moduleItem.rowCount())

        # insert new settings
        self._addSettings(moduleItem.index())

        return

    def getSettings(self, item):

        settings = OrderedDict()
        for row in range(item.rowCount()):
            propertyName = self.targetModel.data(item.child(row, 0).index(),
                                                 role=PropertyItem.RawDataRole)
            propertyVal = self.targetModel.data(item.child(row, 1).index(),
                                                role=PropertyItem.RawDataRole)
            settings.update({propertyName: propertyVal})

        return settings

    def setExperiment(self, exp):
        """
        Load the given experiment settings into the target model.
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        if exp is None:
            return
        if isinstance(exp, list):
            self._logger.error("setExperiment(): only scalar input allowed!")
            return False

        return self._applyExperiment(exp)

    def _applyExperiment(self, exp):
        """
        Set all module settings to those provided in the experiment.
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        self.dataPoints = []
        self.targetModel.clear()
        # insert header
        self.targetModel.setHorizontalHeaderLabels(['Property', 'Value'])
        # insert main items
        for key, value in exp.items():
            if key == 'Name':
                self.targetModel.setName(value)
                continue

            name = PropertyItem(key)
            value = None
            newItems = [name, value]
            self.targetModel.appendRow(newItems)

        # insert default settings
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)
            try:
                self._addSettings(index)
                self.dataPoints += self._readDataPoints(index)
            except ExperimentException as e:
                self._logger.error(e)
                return False

        for moduleName, moduleValue in exp.items():
            if moduleName == 'Name':
                continue

            if not moduleValue:
                continue

            for valKey, valVal in moduleValue.items():
                modules = self.targetModel.findItems(moduleName)[0]

                for row in range(modules.rowCount()):
                    if self.targetModel.data(modules.child(row, 0).index()) == valKey:
                        valueIdx = self.targetModel.index(row, 1, self.targetModel.indexFromItem(modules))
                        self.targetModel.setData(valueIdx, valVal, role=PropertyItem.RawDataRole)
                        break
                else:
                    self._logger.warning("_applyExperiment(): Setting: '{0}' not "
                                       "available for Module: '{1}'".format(
                        valKey, moduleName))

        self.targetView.setModel(self.targetModel)

        return True

    def getDataPoints(self):
        return self.dataPoints

    def handleFrame(self, frame):
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName:
                    dataPoints = module[0].handleFrame(frame)
                    if dataPoints is not None:
                        return dataPoints

        return None

    def runExperiment(self):
        data = []
        self.runningExperiment = True
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName:
                    startParams = module[0].getStartParams(self)
                    if startParams is not None:
                        data.append(startParams)

                    settings = self.getSettings(parent)
                    vals = []
                    for key, val in settings.items():
                        if val is not None:
                            vals.append(val)
                    params = module[0].getParams(self, vals)
                    if params and not None:
                        data.append(params)

                    break

        # start experiment
        payload = bytes([1])

        data.append({'id': 1,
                     'msg': payload})
        for _data in data:
            self.inputQueue.put(_data)

    def sendParameterExperiment(self):
        data = []
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName:
                    settings = self.getSettings(parent)
                    vals = []
                    for key, val in settings.items():
                        if val is not None:
                            vals.append(val)
                    params = module[0].getParams(self, vals)
                    if params and not None:
                        data.append(params)

                    break

        for _data in data:
            self.inputQueue.put(_data)

    def stopExperiment(self):
        data = []

        if not self.runningExperiment:
            return

        self.runningExperiment = False
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName:
                    stopParams = module[0].getStopParams(self)
                    if stopParams is not None:
                        data.append(stopParams)

                    break

        # stop experiment
        payload = bytes([0])

        data.append({'id': 1,
                     'msg': payload})
        for _data in data:
            self.inputQueue.put(_data)

        self.expFinished.emit()

    def getExperiment(self):
        exp = {'Name': self.targetModel.getName()}

        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName:
                    exp[moduleName] = self.getSettings(parent)

                    break

        return exp
