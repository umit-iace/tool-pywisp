# -*- coding: utf-8 -*-
from collections import OrderedDict

import ast
from PyQt5.QtCore import Qt, pyqtSlot, QModelIndex, QSize, pyqtSignal
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QItemDelegate, QComboBox, QTreeView

from . import experimentModules
from .registry import *


class ExperimentModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)

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

    def type(self):
        return QStandardItem.UserType

    def _getText(self, data):
        return str(data)

    def setData(self, Any, role=None, *args, **kwargs):
        if role == Qt.EditRole:
            try:
                self._data = ast.literal_eval(Any)
            except (SyntaxError, ValueError) as e:
                # print(e)
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
        self.comboDel = ComboDelegate()

    def createEditor(self, parent, option, index):
        if index.parent().isValid():
            return QItemDelegate.createEditor(self, parent, option, index)
        else:
            # no parent -> top of hierarchy
            return self.comboDel.createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            self.comboDel.setEditorData(editor, index)
        else:
            QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            self.comboDel.setModelData(editor, model, index)
        else:
            QItemDelegate.setModelData(self, editor, model, index)


class ComboDelegate(QItemDelegate):
    """
    A delegate that adds a combobox to cells that lists
    all available types of Subclasses of ExperimentModule
    """

    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.extractEntries(index))
        editor.currentIndexChanged.connect(self.currentIndexChanged)
        return editor

    def setEditorData(self, editor, index):
        name = index.model().itemFromIndex(index).text()
        editor.blockSignals(True)
        editor.setCurrentIndex(editor.findText(name))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(
            index,
            editor.currentText() if editor.currentText() != "None" else None,
            role=PropertyItem.RawDataRole)

    @pyqtSlot(int)
    def currentIndexChanged(self, idx):
        self.commitData.emit(self.sender())

    @staticmethod
    def extractEntries(index):
        """
        extract all possible choices for the selected Experiment Module
        """
        entries = ["None"]
        idx = index.model().index(index.row(), 0, QModelIndex())
        simModuleName = str(index.model().itemFromIndex(idx).text())
        simModule = getattr(experimentModules, simModuleName)
        subModules = getRegisteredExperimentModules(simModule)
        for subModule in subModules:
            entries.append(subModule[1])

        return entries


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

    def __init__(self, moduleList, inputQueue, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.setupList = moduleList
        self.inputQueue = inputQueue
        self._setup_model()

    def _setup_model(self):
        # create model
        self.targetModel = ExperimentModel(self)
        self.targetModel.itemChanged.connect(self.itemChanged)

        # insert header
        self.targetModel.setHorizontalHeaderLabels(['Property', 'Value'])

        # insert items
        self._setupModelItems()

    def _setupModelItems(self):
        """
        fill model with items corresponding to all predefined SimulationModules
        """
        # insert main items
        for simModule in self.setupList:
            name = PropertyItem(simModule)
            value = PropertyItem(None)
            newItems = [name, value]
            self.targetModel.appendRow(newItems)

        # insert settings
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)
            self._addSettings(index)

    def _addSettings(self, index):
        parent = index.model().itemFromIndex(index)
        child = index.model().item(index.row(), 1)
        moduleName = parent.data(role=PropertyItem.RawDataRole)
        subModuleName = child.data(role=PropertyItem.RawDataRole)
        if subModuleName is None:
            return

        settings = self._readSettings(moduleName, subModuleName)
        for key, val in settings.items():
            setting_name = PropertyItem(key)
            setting_value = PropertyItem(val)
            parent.appendRow([setting_name, setting_value])

    def _readSettings(self, moduleName, subModuleName):
        """
        Read the public settings from a experiment module
        """
        moduleCls = getattr(experimentModules, moduleName)
        subModuleCls = getExperimentModuleClassByName(moduleCls,
                                                      subModuleName)
        return subModuleCls.publicSettings

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

    def getSettings(self, model, module_name):
        item = model.findItems(module_name).pop(0)

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

    def restoreExperiment(self, exp):
        """
        Restore the given generated experiment settings into the target model.

        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        if exp is None:
            return
        if isinstance(exp, list):
            self._logger.error("restoreExperiment(): only scalar input allowed!")
            return False

        return self._apply_regime(exp, True)

    def _applyExperiment(self, exp, ignore_is_public):
        """
        Set all module settings to those provided in the experiment.
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        self.targetModel.removeRows(0, self.targetModel.rowCount())

        # load module defaults
        self._setupModelItems()

        # overwrite all settings with the provided ones
        for moduleName, value in exp.items():
            if moduleName == "Name":
                continue

            # sanity check
            moduleCls = getattr(experimentModules, moduleName, None)
            if moduleCls is None:
                self._logger.error("_applyExperiment(): No module called {0}"
                                   "".format(moduleName))
                return False

            items = self.targetModel.findItems(moduleName)
            if not len(items):
                self._logger.error("_applyExperiment(): No item in List called {0}"
                                   "".format(moduleName))
                return False

            moduleItem = items.pop(0)
            moduleType = value["type"]

            # sanity check
            subModuleCls = getExperimentModuleClassByName(moduleCls,
                                                          moduleType)

            if not subModuleCls:
                self._logger.error("_applyExperiment(): No sub-module called {0}"
                                   "".format(moduleType))
                return False

            moduleIndex = moduleItem.index()
            moduleTypeIndex = moduleIndex.model().index(moduleIndex.row(),
                                                        1)
            moduleIndex.model().setData(moduleTypeIndex,
                                        moduleType,
                                        role=PropertyItem.RawDataRole)
            # due to signal connections, default settings are loaded
            # automatically in the back

            # overwrite specific settings
            for key, val in value.items():
                if key == "type":
                    continue

                for row in range(moduleItem.rowCount()):
                    if self.targetModel.data(
                            moduleItem.child(row, 0).index()) == key:
                        value_idx = self.targetModel.index(row, 1, moduleIndex)
                        self.targetModel.setData(value_idx,
                                                 val,
                                                 role=PropertyItem.RawDataRole)
                        break
                    else:
                        if not ignore_is_public:
                            self._logger.error("_applyExperiment(): Setting: '{0}' not "
                                               "available for Module: '{1}'".format(
                                key, moduleType))
                            return False

        return True

    def getDataPoints(self):
        dataPoints = []
        for expModule in self.setupList:
            moduleCls = getattr(experimentModules, expModule)
            regExpModules = getRegisteredExperimentModules(moduleCls)
            # only first module used
            dataPoints += regExpModules[0][0].dataPoints

        return dataPoints

    def runExperiment(self):
        data = []
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)
            parent = index.model().itemFromIndex(index)
            child = index.model().item(index.row(), 1)
            moduleName = parent.data(role=PropertyItem.RawDataRole)
            subModuleName = child.data(role=PropertyItem.RawDataRole)

            if subModuleName is None:
                continue

            moduleClass = getattr(experimentModules, moduleName, None)
            subModuleClass = getExperimentModuleClassByName(moduleClass, subModuleName)
            startParams = subModuleClass.getStartParams(self)
            if startParams is not None:
                data += startParams

            settings = self.getSettings(self.targetModel, moduleName)
            vals = []
            for key, val in settings.items():
                if val is not None:
                    vals.append(val)
            params = subModuleClass.getParams(self, vals)
            if params is not None:
                data += params

        # start experiment
        data.append('exp------1\n')
        for _data in data:
            self.inputQueue.put(_data)

    def stopExperiment(self):
        data = []

        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)
            parent = index.model().itemFromIndex(index)
            child = index.model().item(index.row(), 1)
            moduleName = parent.data(role=PropertyItem.RawDataRole)
            subModuleName = child.data(role=PropertyItem.RawDataRole)

            if subModuleName is None:
                continue

            moduleClass = getattr(experimentModules, moduleName, None)
            subModuleClass = getExperimentModuleClassByName(moduleClass, subModuleName)
            stopParams = subModuleClass.getStopParams(self)
            if stopParams is not None:
                data += stopParams

        data.append('exp------0\n')
        for _data in data:
            self.inputQueue.put(_data)

        self.expFinished.emit()
