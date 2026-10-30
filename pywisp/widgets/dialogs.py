# -*- coding: utf-8 -*-
"""
Dialogs for settings and the configuration of remote widgets.
"""
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QIcon, QIntValidator, QKeySequence, QRegularExpressionValidator
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLayout, \
    QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..utils import getResource
from .remote import REMOTE_WIDGETS

__all__ = ["DataIntDialog", "DataTcpIpDialog", "RemoteWidgetEdit", "ShortcutCreator"]


class DataIntDialog(QDialog):
    """
    Qt Dialog handler for integer settings with a min and max value
    """

    def __init__(self, **kwargs):
        parent = kwargs.get("parent", None)
        super(DataIntDialog, self).__init__(parent)

        self.minValue = kwargs.get("min", 1)
        self.maxValue = kwargs.get("max", 1000)
        self.currentValue = kwargs.get("current", 0)
        self.unit = kwargs.get("unit", "")
        self.title = kwargs.get("title", "pywisp")

        self.setWindowTitle(self.title)

        mainLayout = QVBoxLayout(self)
        labelLayout = QHBoxLayout()
        inputLayout = QHBoxLayout()

        minLabel = QLabel(self)
        minLabel.setText(f"min. value: {self.minValue}")
        labelLayout.addWidget(minLabel)
        maxLabel = QLabel(self)
        maxLabel.setText(f"max. value: {self.maxValue}")
        labelLayout.addWidget(maxLabel)
        mainLayout.addLayout(labelLayout)

        self.data = QLineEdit(self)
        self.data.setText(str(self.currentValue))

        self.data.setValidator(QIntValidator(self.minValue, self.maxValue, self))

        inputLayout.addWidget(self.data)

        if not self.unit == "":
            unitLabel = QLabel(self)
            unitLabel.setText(self.unit)
            inputLayout.addWidget(unitLabel)

        mainLayout.addLayout(inputLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)

    def _getData(self):
        return self.data.text()

    @staticmethod
    def getData(**kwargs):
        dialog = DataIntDialog(**kwargs)
        result = dialog.exec()
        data = dialog._getData()

        return data, result == QDialog.DialogCode.Accepted

class DataTcpIpDialog(QDialog):
    """
    Qt Dialog handler for tcp settings
    """

    def __init__(self, **kwargs):
        parent = kwargs.get('parent', None)
        super(DataTcpIpDialog, self).__init__(parent)

        self.ipValue = kwargs.get("ip", '127.0.0.1')
        self.portValue = kwargs.get("port", 0)

        ipRange = "(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])"  # Part of the regular expression
        # regular expression
        ipRegex = QRegularExpression("^" + ipRange + "\\." + ipRange + "\\." + ipRange + "\\." + ipRange + "$")
        ipValidator = QRegularExpressionValidator(ipRegex, self)

        mainLayout = QVBoxLayout(self)

        self.ipData = QLineEdit(self)
        self.ipData.setText(str(self.ipValue))
        self.ipData.setValidator(ipValidator)

        self.portData = QLineEdit(self)
        self.portData.setText(str(self.portValue))
        self.portData.setValidator(QIntValidator(0, 65535, self))

        horizontalLayout = QHBoxLayout()

        horizontalLayout.addWidget(self.ipData)
        horizontalLayout.addWidget(self.portData)
        mainLayout.addLayout(horizontalLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)

    def _getData(self):
        return self.ipData.text(), self.portData.text()

    @staticmethod
    def getData(**kwargs):
        dialog = DataTcpIpDialog(**kwargs)
        result = dialog.exec()
        ipData, portData = dialog._getData()

        return ipData, portData, result == QDialog.DialogCode.Accepted


class RemoteWidgetEdit(QDialog):
    """
    Creates a dialog to add and edit remote widgets of different types.

    The settings of a widget type are added by the `editor` of its class in :data:`REMOTE_WIDGETS`
    using the `add...` methods of the dialog.
    """
    # floating point numbers
    numberRegex = "[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?"

    def __init__(self, editWidget=False, **kwargs):
        parent = kwargs.get('parent', None)
        super(RemoteWidgetEdit, self).__init__(parent)
        # config of the widget the fields are filled with
        self.initial = kwargs
        self.widgetType = kwargs.get('widgetType', 'PushButton')
        self.name = kwargs.get('name', 'New')
        self.shortcutGp = kwargs.get('shortcut-Gp', None)
        self.targets = [dict(t) for t in kwargs.get('targets', None) or []]

        self.curModule = kwargs.get('Module', None)
        self.curParameter = kwargs.get('Parameter', None)

        self.editWidget = editWidget

        self.targetLayout = None
        self.targetRows = []
        # reads the settings of the selected widget type, set by its editor
        self._readSettings = dict

        mainLayout = QFormLayout()

        self.nameText = QLineEdit(self.name)
        mainLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(list(REMOTE_WIDGETS))
        self.typeList.setCurrentText(self.widgetType)
        self.typeList.currentIndexChanged.connect(self.typeListChanged)
        self.typeList.setEnabled(not self.editWidget)
        mainLayout.addRow(QLabel("Widget type"), self.typeList)

        self.moduleList = QComboBox()
        self.paramList = QComboBox()
        self.modules = dict()
        exp = kwargs.get('exp', None) or {}
        for key, value in exp.items():
            self.modules[key] = [k for k, v in value.items()]

            self.moduleList.addItem(key)

        self.moduleList.currentIndexChanged.connect(self.moduleChanged)
        if self.curModule is None:
            self.moduleList.setCurrentIndex(0)
            self.moduleChanged()
        else:
            self.moduleList.setCurrentText(self.curModule)
            self.moduleChanged()

        if self.curParameter is not None:
            self.paramList.setCurrentText(self.curParameter)

        mainLayout.addRow(QLabel("Modules:"), self.moduleList)
        mainLayout.addRow(QLabel("Parameter:"), self.paramList)
        self.mainLayout = mainLayout

        self.settingsWidget = QWidget()
        self.settingsWidgetLayout = QFormLayout()
        self.settingsWidget.setLayout(self.settingsWidgetLayout)
        mainLayout.addRow(self.settingsWidget)

        self.typeListChanged()

        self.setLayout(mainLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        self.setWindowTitle("Add Remote Widget ...")
        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)
        # the size follows the settings of the selected widget type
        mainLayout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def widgetClass(self):
        """ class of the selected widget type """
        return REMOTE_WIDGETS[self.typeList.currentText()]

    def typeListChanged(self):
        while self.settingsWidgetLayout.rowCount():
            self.settingsWidgetLayout.removeRow(0)
        self.targetRows = []

        cls = self.widgetClass()
        # widgets with targets have their own module and parameter for every target
        self.mainLayout.setRowVisible(self.moduleList, not cls.hasTargets)
        self.mainLayout.setRowVisible(self.paramList, not cls.hasTargets)
        self._readSettings = cls.editor(self)

    def addValueField(self, attr, label, key, default):
        """ adds a field for a number, stored as attribute `attr` and filled with the setting `key` """
        field = self.addTextField(attr, label, key, default)
        field.setValidator(QRegularExpressionValidator(QRegularExpression(self.numberRegex), self))
        field.mousePressEvent = lambda event: field.selectAll()
        return field

    def addTextField(self, attr, label, key, default):
        """ adds a text field, stored as attribute `attr` and filled with the setting `key` """
        field = QLineEdit(str(self.initial.get(key, default)))
        self.settingsWidgetLayout.addRow(QLabel(label), field)
        setattr(self, attr, field)
        return field

    def addShortcutField(self, attr, label, key):
        """ adds a field recording a shortcut, stored as attribute `attr` and filled with the setting `key` """
        field = ShortcutCreator()
        field.setText(str(self.initial.get(key, "")))
        self.settingsWidgetLayout.addRow(QLabel(label), field)
        setattr(self, attr, field)
        return field

    def addTargetList(self):
        """ adds the list of targets, each with module, parameter and value, see :meth:`readTargets` """
        targetWidget = QWidget()
        self.targetLayout = QVBoxLayout()
        self.targetLayout.setContentsMargins(0, 0, 0, 0)
        targetWidget.setLayout(self.targetLayout)
        self.settingsWidgetLayout.addRow(QLabel("Targets:"), targetWidget)
        for target in self.targets or [{}]:
            self.addTargetRow(**target)
        addButton = QPushButton("Add target")
        addButton.clicked.connect(lambda: self.addTargetRow())
        self.settingsWidgetLayout.addRow(None, addButton)

    def readTargets(self):
        return [{'Module': moduleList.currentText(),
                 'Parameter': paramList.currentText(),
                 'value': valueText.text()}
                for _, moduleList, paramList, valueText in self.targetRows]

    def addTargetRow(self, Module=None, Parameter=None, value=0.0):
        """
        Adds a row with module, parameter and value to the targets
        """
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        row.setLayout(layout)

        moduleList = QComboBox()
        moduleList.addItems(list(self.modules))
        paramList = QComboBox()

        def moduleChanged():
            paramList.clear()
            paramList.addItems(self.modules.get(moduleList.currentText(), []))

        moduleList.currentIndexChanged.connect(moduleChanged)
        if Module is not None:
            moduleList.setCurrentText(Module)
        moduleChanged()
        if Parameter is not None:
            paramList.setCurrentText(Parameter)

        valueText = QLineEdit(str(value))
        valueText.setValidator(QRegularExpressionValidator(QRegularExpression(self.numberRegex), self))
        valueText.setFixedWidth(80)
        removeButton = QPushButton("-")
        removeButton.setFixedWidth(30)

        layout.addWidget(moduleList)
        layout.addWidget(paramList)
        layout.addWidget(valueText)
        layout.addWidget(removeButton)

        entry = (row, moduleList, paramList, valueText)
        removeButton.clicked.connect(lambda: self.removeTargetRow(entry))
        self.targetRows.append(entry)
        self.targetLayout.addWidget(row)

    def removeTargetRow(self, entry):
        self.targetRows.remove(entry)
        self.targetLayout.removeWidget(entry[0])
        entry[0].deleteLater()

    def moduleChanged(self):
        self.paramList.clear()
        module = self.moduleList.currentText()

        for p in self.modules.get(module, []):
            self.paramList.addItem(p)

    def _getData(self):
        msg = dict()
        msg['name'] = self.nameText.text()
        msg['widgetType'] = self.typeList.currentText()
        if not self.widgetClass().hasTargets:
            msg['Module'] = self.moduleList.currentText()
            msg['Parameter'] = self.paramList.currentText()
        msg['shortcut-Gp'] = self.shortcutGp
        msg.update(self._readSettings())
        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec()
        msg = dialog._getData()
        dialog.widgetClass().completeConfig(msg, exp)

        return msg, result == QDialog.DialogCode.Accepted


class ShortcutCreator(QLineEdit):
    """
    Line edit that records the key pressed in it as shortcut. Backspace and Delete clear the shortcut.

    Escape and Space are recorded as well, e.g. Escape for an emergency stop, so Escape does not
    close the dialog while this field has the focus.
    """
    # keys that are no shortcut on their own
    modifierKeys = (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_AltGr, Qt.Key.Key_Shift, Qt.Key.Key_Meta,
                    Qt.Key.Key_CapsLock)
    clearKeys = (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)

    def __init__(self, parent=None):
        super(ShortcutCreator, self).__init__(parent)
        self.keySequence = None
        self.setPlaceholderText("press a key, Backspace clears")

    def keyPressEvent(self, event):
        key = event.key()
        if key in self.modifierKeys or key in self.clearKeys:
            self.setText('')
        else:
            self.keySequence = QKeySequence(key).toString()
            self.setText(self.keySequence)

    def getKeySequence(self):
        return self.keySequence

    def setText(self, text):
        self.keySequence = text
        super(ShortcutCreator, self).setText(text)
