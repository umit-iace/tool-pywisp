# -*- coding: utf-8 -*-
import ast
import logging
from collections import OrderedDict

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QItemDelegate, QTreeView

from .registry import *


class ExperimentException(Exception):
    pass


class ExperimentModel(QStandardItemModel):
    """
    Model to provide item model that includes an additional name attribute
    """
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
    sendData = pyqtSignal(object)

    def __init__(self, targetView, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.targetView = targetView
        self.dataPoints = None
        self.runningExperiment = False
        # create model
        self.targetModel = ExperimentModel(self)
        self.targetModel.itemChanged.connect(self.itemChanged)

    def _addSettings(self, index):
        """
        Sets the settings from an experiment module.
        :param index: the given experiment module index
        """
        parent = index.model().itemFromIndex(index)
        moduleName = parent.data(role=PropertyItem.RawDataRole)

        settings = self._readSettings(moduleName)
        for key, val in settings.items():
            setting_name = PropertyItem(key)
            setting_value = PropertyItem(val)
            parent.appendRow([setting_name, setting_value])

    def _readSettings(self, moduleName):
        """
        Reads the public settings from an experiment module.
        :param moduleName: the given experiment module name
        :return: settings of module or raise an exception if module is unknown
        """
        for module in getRegisteredExperimentModules():
            if module[1] == moduleName:
                return module[0].publicSettings

        raise ExperimentException("_readSettings(): No module called {} found!".format(moduleName))

    def _readDataPoints(self, index):
        """
        Reads the data points from an experiment module.
        :param index: the given experiment module index
        :return: data points of module or raise an exception if module is unknown
        """
        parent = index.model().itemFromIndex(index)
        moduleName = parent.data(role=PropertyItem.RawDataRole)

        for module in getRegisteredExperimentModules():
            if module[1] == moduleName:
                return module[0].dataPoints

        raise ExperimentException("_readDataPoints(): No module called {} found!".format(moduleName))

    def itemChanged(self, item):
        """
        Updates settings of an experiment module.
        :param item: the given experiment module
        """
        if item.parent():
            return

        idx = item.index()
        moduleItem = idx.model().item(idx.row())

        # delete all old settings
        moduleItem.removeRows(0, moduleItem.rowCount())

        # insert new settings
        self._addSettings(moduleItem.index())

    def getSettings(self, item):
        """
        Returns a dict with all settings of the item of an experiment.
        :param item: experiment module
        :return: settings
        """
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
        :param exp: the given experiment
        :return: `True` if successful, `False` if errors occurred.
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
        :param exp: the provided experiment
        :return: `True` if successful, `False` if errors occurred.
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
        """
        Returns all data points of the experiment.
        :return: data points
        """
        return self.dataPoints

    def handleFrame(self, frame, connection):
        """
        Returns the corresponding data points of a frame of the test rig.
        :param frame: data from the test rig
        :param connection: connection of the frame
        :return: data points or None if nothing found
        """
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)

            parent = index.model().itemFromIndex(index)
            moduleName = parent.data(role=PropertyItem.RawDataRole)

            for module in getRegisteredExperimentModules():
                if module[1] == moduleName and module[0].connection == connection.__name__:
                    dataPoints = module[0].handleFrame(frame)
                    if dataPoints is not None:
                        return dataPoints

        return None

    def runExperiment(self):
        """
        Sends all start parameters of all modules that are registered in the target model to start an experiment and
        adds and frame with id 1 and payload 1 as general start command.
        """
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
                        startParams['connection'] = module[0].connection
                        data.append(startParams)

                    settings = self.getSettings(parent)
                    vals = []
                    for key, val in settings.items():
                        if val is not None:
                            vals.append(val)
                    params = module[0].getParams(self, vals)
                    if params and not None:
                        params['connection'] = module[0].connection
                        data.append(params)
                    break

        # start experiment
        payload = bytes([1])

        data.append({'id': 1,
                     'msg': payload})
        for _data in data:
            self.sendData.emit(_data)

    def sendParameterExperiment(self):
        """
        Sends all parameters of all modules that are registered in the target model to an experiment.
        """
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
                        params['connection'] = module[0].connection
                        data.append(params)
                    break

        for _data in data:
            self.sendData.emit(_data)

    def stopExperiment(self):
        """
        Sends all stop parameters of all modules that are registered in the target model to stop an experiment and
        adds and frame with id 1 and payload 0 as general stop command.
        """
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
                        stopParams['connection'] = module[0].connection
                        data.append(stopParams)
                    break

        # stop experiment
        payload = bytes([0])

        data.append({'id': 1,
                     'msg': payload})
        for _data in data:
            self.sendData.emit(_data)

        self.expFinished.emit()

    def getExperiment(self):
        """
        Returns an dict for the current experiment with all settings of it.
        :return: experiment
        """
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
