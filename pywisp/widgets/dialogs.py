# -*- coding: utf-8 -*-
"""
Dialogs for settings and the configuration of remote widgets.
"""
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QIcon, QIntValidator, QKeySequence, QRegularExpressionValidator
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLayout, \
    QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..utils import getResource

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
    Creates a dialog to add and edit remote widgets of different types
    """

    def __init__(self, editWidget=False, **kwargs):
        parent = kwargs.get('parent', None)
        super(RemoteWidgetEdit, self).__init__(parent)
        self.widgetType = kwargs.get('widgetType', 'PushButton')
        self.name = kwargs.get('name', 'New')
        self.valueOn = str(kwargs.get('valueOn', 0.0))
        self.valueReset = str(kwargs.get('valueReset', ''))
        self.valueOff = str(kwargs.get('valueOff', 0.0))
        self.minSlider = str(kwargs.get('minSlider', 0))
        self.maxSlider = str(kwargs.get('maxSlider', 1))
        self.stepSlider = str(kwargs.get('stepSlider', 1))
        self.shortcut = str(kwargs.get('shortcut', ""))
        self.shortcutPlus = str(kwargs.get('shortcutPlus', ""))
        self.shortcutMinus = str(kwargs.get('shortcutMinus', ""))
        self.shortcutGp = kwargs.get('shortcut-Gp', None)
        self.invertSlider = kwargs.get('invertSlider', False)
        self.targets = [dict(t) for t in kwargs.get('targets', None) or []]

        self.curModule = kwargs.get('Module', None)
        self.curParameter = kwargs.get('Parameter', None)

        self.editWidget = editWidget

        self.minSliderText = None
        self.maxSliderText = None
        self.stepSliderText = None
        self.valueOffText = None
        self.valueOnText = None
        self.valueText = None
        self.valueResetText = None
        self.shortcutField = None
        self.shortcutFieldPlus = None
        self.shortcutFieldMinus = None
        self.targetLayout = None
        self.targetRows = []

        mainLayout = QFormLayout()

        self.nameText = QLineEdit(self.name)
        mainLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(["PushButton", "Switch", "Slider", "MultiButton"])
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

    def typeListChanged(self):
        while self.settingsWidgetLayout.rowCount():
            self.settingsWidgetLayout.removeRow(0)
        self.targetRows = []

        # a multi button has its own module and parameter for every target
        isMulti = self.typeList.currentText() == "MultiButton"
        self.mainLayout.setRowVisible(self.moduleList, not isMulti)
        self.mainLayout.setRowVisible(self.paramList, not isMulti)

        height = QLineEdit().sizeHint().height()
        doubleValidator = QRegularExpressionValidator(QRegularExpression("[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?"), self)

        if self.typeList.currentText() == "PushButton":
            self.valueText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value"), self.valueText)
            self.valueText.setValidator(doubleValidator)
            self.valueText.mousePressEvent = lambda event: self.valueText.selectAll()
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
            self.valueResetText = QLineEdit(self.valueReset)
            self.settingsWidgetLayout.addRow(QLabel("Reset Value"), self.valueResetText)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy2 = QLabel("")
            dummy2.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy2)
        elif self.typeList.currentText() == "Switch":
            self.valueOnText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value On"), self.valueOnText)
            self.valueOnText.setValidator(doubleValidator)
            self.valueOnText.mousePressEvent = lambda event: self.valueOnText.selectAll()
            self.valueOffText = QLineEdit(self.valueOff)
            self.settingsWidgetLayout.addRow(QLabel("Value Off"), self.valueOffText)
            self.valueOffText.mousePressEvent = lambda event: self.valueOffText.selectAll()
            self.valueOffText.setValidator(doubleValidator)
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy2 = QLabel("")
            dummy2.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy2)
        elif self.typeList.currentText() == "Slider":
            self.maxSliderText = QLineEdit(str(self.maxSlider))
            self.settingsWidgetLayout.addRow(QLabel("Max"), self.maxSliderText)
            self.maxSliderText.setValidator(doubleValidator)
            self.maxSliderText.mousePressEvent = lambda event: self.maxSliderText.selectAll()
            self.minSliderText = QLineEdit(str(self.minSlider))
            self.settingsWidgetLayout.addRow(QLabel("Min"), self.minSliderText)
            self.minSliderText.setValidator(doubleValidator)
            self.minSliderText.mousePressEvent = lambda event: self.minSliderText.selectAll()
            self.stepSliderText = QLineEdit(str(self.stepSlider))
            self.settingsWidgetLayout.addRow(QLabel("Step Size"), self.stepSliderText)
            self.stepSliderText.setValidator(doubleValidator)
            self.stepSliderText.mousePressEvent = lambda event: self.stepSliderText.selectAll()
            self.shortcutFieldPlus = ShortcutCreator()
            self.shortcutFieldPlus.setText(self.shortcutPlus)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Plus:"), self.shortcutFieldPlus)
            self.shortcutFieldMinus = ShortcutCreator()
            self.shortcutFieldMinus.setText(self.shortcutMinus)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Minus:"), self.shortcutFieldMinus)
        elif self.typeList.currentText() == "MultiButton":
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
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

    def addTargetRow(self, Module=None, Parameter=None, value=0.0):
        """
        Adds a row with module, parameter and value to the targets of a multi button
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
        valueText.setValidator(QRegularExpressionValidator(
            QRegularExpression("[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?"), self))
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
        msg['Module'] = self.moduleList.currentText()
        msg['Parameter'] = self.paramList.currentText()
        msg['shortcut-Gp'] = self.shortcutGp

        if self.typeList.currentText() == "PushButton":
            msg['valueOn'] = self.valueText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
            msg['valueReset'] = self.valueResetText.text()
        elif self.typeList.currentText() == "Switch":
            msg['valueOn'] = self.valueOnText.text()
            msg['valueOff'] = self.valueOffText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
        elif self.typeList.currentText() == "Slider":
            msg['minSlider'] = self.minSliderText.text()
            msg['maxSlider'] = self.maxSliderText.text()
            msg['stepSlider'] = self.stepSliderText.text()
            msg['shortcutPlus'] = self.shortcutFieldPlus.getKeySequence()
            msg['shortcutMinus'] = self.shortcutFieldMinus.getKeySequence()
            msg['invertSlider'] = self.invertSlider
        elif self.typeList.currentText() == "MultiButton":
            del msg['Module'], msg['Parameter']
            msg['shortcut'] = self.shortcutField.getKeySequence()
            msg['targets'] = [{'Module': moduleList.currentText(),
                               'Parameter': paramList.currentText(),
                               'value': valueText.text()}
                              for _, moduleList, paramList, valueText in self.targetRows]

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            if exp and msg['Parameter'] in exp.get(msg['Module'], {}):
                msg['startValue'] = exp[msg['Module']][msg['Parameter']]
            else:
                msg['startValue'] = 0

        return msg, result == QDialog.DialogCode.Accepted


class ShortcutCreator(QLineEdit):
    def __init__(self, parent=None):
        super(ShortcutCreator, self).__init__(parent)
        self.keySequence = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control or \
                event.key() == Qt.Key.Key_Alt or \
                event.key() == Qt.Key.Key_AltGr or \
                event.key() == Qt.Key.Key_Escape or \
                event.key() == Qt.Key.Key_Shift or \
                event.key() == Qt.Key.Key_CapsLock or \
                event.key() == Qt.Key.Key_Space or \
                event.key() == Qt.Key.Key_Tab:
            self.setText('')
        else:
            self.keySequence = QKeySequence(event.key()).toString()
            self.setText(self.keySequence)

    def getKeySequence(self):
        return self.keySequence

    def setText(self, text):
        self.keySequence = text
        super(ShortcutCreator, self).setText(text)
