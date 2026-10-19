# -*- coding: utf-8 -*-
"""
Dialogs for settings and the configuration of remote widgets.
"""
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QIcon, QIntValidator, QKeySequence, QRegExpValidator
from PyQt5.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, \
    QVBoxLayout, QWidget

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
        minLabel.setText("min. value: {}".format(self.minValue))
        labelLayout.addWidget(minLabel)
        maxLabel = QLabel(self)
        maxLabel.setText("max. value: {}".format(self.maxValue))
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
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
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
        result = dialog.exec_()
        data = dialog._getData()

        return data, result == QDialog.Accepted

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
        ipRegex = QRegExp("^" + ipRange + "\\." + ipRange + "\\." + ipRange + "\\." + ipRange + "$")
        ipValidator = QRegExpValidator(ipRegex, self)

        mainLayout = QVBoxLayout(self)

        self.ipData = QLineEdit(self)
        self.ipData.setText(str(self.ipValue))
        self.ipData.setValidator(ipValidator)

        self.portData = QLineEdit(self)
        self.portData.setText(str(self.portValue))
        self.portData.setValidator(QIntValidator(0, 65535, self))

        horizonalLayout = QHBoxLayout()

        horizonalLayout.addWidget(self.ipData)
        horizonalLayout.addWidget(self.portData)
        mainLayout.addLayout(horizonalLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
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
        result = dialog.exec_()
        ipData, portData = dialog._getData()

        return ipData, portData, result == QDialog.Accepted


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

        mainLayout = QFormLayout()

        self.nameText = QLineEdit(self.name)
        mainLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(["PushButton", "Switch", "Slider"])
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

        self.settingsWidget = QWidget()
        self.settingsWidgetLayout = QFormLayout()
        self.settingsWidget.setLayout(self.settingsWidgetLayout)
        mainLayout.addRow(self.settingsWidget)

        self.typeListChanged()

        self.setLayout(mainLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        self.setWindowTitle("Add Remote Widget ...")
        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)
        self.setFixedSize(self.sizeHint())

    def typeListChanged(self):
        for i in reversed(range(self.settingsWidgetLayout.count())):
            self.settingsWidgetLayout.itemAt(i).widget().deleteLater()

        height = QLineEdit().sizeHint().height()
        doubleValidator = QRegExpValidator(QRegExp("[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?"), self)

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

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec_()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            if exp and msg['Parameter'] in exp.get(msg['Module'], {}):
                msg['startValue'] = exp[msg['Module']][msg['Parameter']]
            else:
                msg['startValue'] = 0

        return msg, result == QDialog.Accepted


class ShortcutCreator(QLineEdit):
    def __init__(self, parent=None):
        super(ShortcutCreator, self).__init__(parent)
        self.KeySequence = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control or \
                event.key() == Qt.Key_Alt or \
                event.key() == Qt.Key_AltGr or \
                event.key() == Qt.Key_Escape or \
                event.key() == Qt.Key_Shift or \
                event.key() == Qt.Key_CapsLock or \
                event.key() == Qt.Key_Space or \
                event.key() == Qt.Key_Tab:
            self.setText('')
        else:
            self.KeySequence = QKeySequence(event.key()).toString()
            self.setText(self.KeySequence)

    def getKeySequence(self):
        return self.KeySequence

    def setText(self, p_str):
        self.KeySequence = p_str
        super(ShortcutCreator, self).setText(p_str)
