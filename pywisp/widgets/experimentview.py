# -*- coding: utf-8 -*-
"""
Tree view of the settings of the applied experiment, see :class:`pywisp.experiments.ExperimentInteractor`.

The view only displays the state of the interactor, edits of the user are written back with
:meth:`pywisp.experiments.ExperimentInteractor.setParameter`.
"""
import ast
import logging

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QItemDelegate, QTreeView

__all__ = ["ExperimentModel", "PropertyItem", "PropertyDelegate", "ExperimentView"]


class ExperimentModel(QStandardItemModel):
    """
    Model to provide item model that includes an additional name attribute.

    It only displays the settings of the :class:`pywisp.experiments.ExperimentInteractor`, values edited
    by the user are reported with :attr:`settingEdited`.
    """
    #: module, setting and new value of a setting edited in the view
    settingEdited = pyqtSignal(str, str, object)

    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)
        self._name = None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        ok = super().setData(index, value, role)
        if role == Qt.ItemDataRole.EditRole and index.column() == 1 and index.parent().isValid():
            module = self.itemFromIndex(index.parent()).data(PropertyItem.RawDataRole)
            key = self.itemFromIndex(index.siblingAtColumn(0)).data(PropertyItem.RawDataRole)
            # the item keeps its old value if the text cannot be parsed
            self.settingEdited.emit(module, key, self.itemFromIndex(index).data(PropertyItem.RawDataRole))
        return ok

    def setName(self, name):
        self._name = name

    def getName(self):
        return self._name

    def flags(self, index):
        if index.column() == 1:
            return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled
        else:
            return Qt.ItemFlag.ItemIsEnabled


class PropertyItem(QStandardItem):
    RawDataRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, data):
        QStandardItem.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._text = self._getText(data)

    def type(self):
        return QStandardItem.ItemType.UserType

    def _getText(self, data):
        return str(data)

    def setData(self, Any, role=None, *args, **kwargs):
        if role == Qt.ItemDataRole.EditRole:
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

    def data(self, role=None, *args, **kwargs):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text
        elif role == Qt.ItemDataRole.EditRole:
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
    """
    Shows the settings of an :class:`pywisp.experiments.ExperimentInteractor`, see :meth:`setInteractor`,
    with the rig values in the column 'Rig'.
    """
    #: background of a rig value that equals the value (`True`) or not (`False`)
    RIG_COLORS = {True: QColor(92, 184, 92, 110), False: QColor(217, 83, 79, 110)}

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegateForColumn(1, PropertyDelegate(self))
        self._interactor = None
        self.targetModel = ExperimentModel(self)
        self.targetModel.settingEdited.connect(self._onSettingEdited)
        # value and rig items of the model by (module, setting)
        self._settingItems = {}
        self._rigItems = {}
        self.setModel(self.targetModel)

    def sizeHint(self):
        return QSize(300, 150)

    def minimumSizeHint(self):
        return self.sizeHint()

    def setInteractor(self, interactor):
        """ shows the settings of the interactor and follows its changes """
        self._interactor = interactor
        interactor.experimentChanged.connect(self._rebuild)
        interactor.settingChanged.connect(self._onSettingChanged)
        interactor.rigSettingsChanged.connect(self._updateRigItems)
        self._rebuild()

    def _rebuild(self):
        model = self.targetModel
        self._settingItems = {}
        self._rigItems = {}
        model.clear()
        model.setHorizontalHeaderLabels(['Property', 'Value', 'Rig'])
        exp = self._interactor.getExperiment()
        model.setName(exp.pop('Name'))
        for moduleName, settings in exp.items():
            moduleItem = PropertyItem(moduleName)
            model.appendRow([moduleItem, None])
            for key, val in settings.items():
                valueItem, rigItem = PropertyItem(val), QStandardItem()
                moduleItem.appendRow([PropertyItem(key), valueItem, rigItem])
                self._settingItems[(moduleName, key)] = valueItem
                self._rigItems[(moduleName, key)] = rigItem
        self._updateRigItems()

    def _onSettingEdited(self, module, parameter, value):
        """ writes a value the user has edited back to the interactor """
        self._interactor.setParameter(module, parameter, value)

    def _onSettingChanged(self, module, parameter, value):
        item = self._settingItems.get((module, parameter))
        if item is None:
            return
        item.setData(value, role=PropertyItem.RawDataRole)
        self.targetModel.dataChanged.emit(item.index(), item.index())
        self._updateRigItem(module, parameter)

    def _updateRigItems(self):
        for module, key in self._rigItems:
            self._updateRigItem(module, key)

    def _updateRigItem(self, module, key):
        item = self._rigItems.get((module, key))
        if item is None:
            return
        tracking = self._interactor.trackingRig
        rig = (self._interactor.rigSettings or {}).get(module, {})
        known = tracking and key in rig
        item.setText(str(rig[key]) if known else "")
        brush = None
        if tracking:
            brush = QBrush(self.RIG_COLORS[known and rig[key] == self._interactor.getParameter(module, key)])
        item.setData(brush, Qt.ItemDataRole.BackgroundRole)
