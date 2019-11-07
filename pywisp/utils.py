# -*- coding: utf-8 -*-
import copy as cp
import logging
import os
import struct
from bisect import bisect_left

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QRegExp, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator, QIcon, QDoubleValidator, QKeySequence
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout, QFormLayout, \
    QLayout, QComboBox, QPushButton, QWidget, QSlider, QMenu, QWidgetAction, QShortcut
from pyqtgraph import mkPen
from pyqtgraph.dockarea import Dock

__all__ = ["getResource", "packArrayToFrame"]


def getResource(resName, resType="icons"):
    """
    Build absolute path to specified resource within the package
    :param resName: name of the ressource
    :param resType: sub directory
    :return: path to resource
    """
    own_path = os.path.dirname(__file__)
    resource_path = os.path.abspath(os.path.join(own_path, "resources", resType))
    return os.path.join(resource_path, resName)


def getFormatedStructString(dataLenFloat, dataLenInt, lenFloat):
    """
    Returns a format string for the struct package by given float and integer length and
    count of floats.

    :param dataLenFloat: length of float datatype
    :param dataLenInt: length of integer datatype
    :param lenFloat: length of float data
    :return:
    """
    if dataLenFloat == 4:
        floatStr = 'f'
    elif dataLenFloat == 8:
        floatStr = 'd'
    else:
        floatStr = 'f'

    if dataLenInt == 1:
        intStr = 'B'
    elif dataLenInt == 2:
        intStr = 'H'
    elif dataLenInt == 4:
        intStr = 'I'
    else:
        intStr = ''

    fmtStr = '>{}{}{}'.format(intStr, lenFloat, floatStr)

    return fmtStr


def packArrayToFrame(id, data, frameLen, dataLenFloat, dataLenInt):
    """
    Packs data to an array of dataPoints with given identifier.

    :param id: identifier of frame
    :param data: data of frame
    :param frameLen: maximal data size of frame
    :param dataLenFloat: length of float datatype
    :param dataLenInt: length of integer datatype
    :return: array of dataPoints (id + payload)
    """
    completeData = len(data) * dataLenFloat + 1 * dataLenInt
    N = np.ceil(completeData / frameLen)
    frameLenFloat = frameLen // dataLenFloat
    dataPoints = []
    for i in range(int(N)):
        if i > 0:
            outList = [float(data[i * frameLenFloat + j - 1]) for j in range(frameLenFloat) if
                       i * frameLenFloat + j - 1 < len(data)]
            fmtStr = getFormatedStructString(dataLenFloat, 0, len(outList))
            payload = struct.pack(fmtStr, *outList)
        else:
            outList = [len(data)]
            outList += [float(data[i * frameLenFloat + j]) for j in range(frameLenFloat - 1)]
            fmtStr = getFormatedStructString(dataLenFloat, dataLenInt, len(outList) - 1)
            payload = struct.pack(fmtStr, *outList)
        dataPoints += [{'id': id,
                        'msg': payload}]
    return dataPoints


class PlainTextLogger(logging.Handler):
    """
    Logging handler, that formats log data for line display.
    """

    def __init__(self, settings, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        self.name = "PlainTextLogger"
        self.settings = settings

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S")
        self.setFormatter(formatter)

        self.cb = None

    def setTargetCb(self, cb):
        self.cb = cb

    def emit(self, record):
        msg = self.format(record)
        if self.cb:
            if self.cb:
                self.settings.beginGroup('log_colors')
                clr = QColor(self.settings.value(record.levelname,
                                                 "#000000"))
                self.settings.endGroup()
                self.cb.setTextColor(clr)

                self.cb.append(msg)
        else:
            logging.getLogger().error("No callback configured!")


class DataPointBuffer(object):
    """
    Buffer object to store the values of the data points
    """

    def __init__(self, time=None, values=None):
        if time is None:
            self.time = []
        else:
            self.time = time
        if values is None:
            self.values = []
        else:
            self.values = values

    def addValue(self, time, value):
        """
        Adds a new value to the data point buffer
        :param time: time(stamp) of the corresponding value (x axis)
        :param value: the new value for the data point (y axis)
        :return:
        """
        self.time.append(time)
        self.values.append(value)

    def clearBuffer(self):
        """
        Clears all the buffers of the data point
        """
        del self.values[:]
        del self.time[:]


class PlotChart(object):
    """
    Object containing the plot widgets and the associated plot curves
    """

    def __init__(self, title, settings, interpolationPoints, movingWindowEnable, movingWindowWidth):
        self.title = title
        self.dataPoints = dict()
        self.plotWidget = None
        self.plotCurves = []
        self.interpolationPoints = interpolationPoints
        self.settings = settings
        self.movingWindowEnable = movingWindowEnable
        self.movingWindowWidth = movingWindowWidth

    def addPlotCurve(self, name, data):
        """
        Adds a curve to the plot widget
        Args:
            dataPoint(DataPointBuffer): Data point which contains the data be added
        """
        self.dataPoints[name] = data

        self.settings.beginGroup('plot_colors')
        cKeys = self.settings.childKeys()
        colorIdxItem = len(self.plotCurves) % len(cKeys)
        colorItem = QColor(self.settings.value(cKeys[colorIdxItem]))
        self.settings.endGroup()

        self.plotCurves.append(self.plotWidget.plot(name=name, pen=mkPen(colorItem, width=2)))

    def setInterpolationPoints(self, interpolationPoints):
        self.interpolationPoints = int(interpolationPoints)

    def setEnableMovingWindow(self, movingWindowEnable):
        self.movingWindowEnable = movingWindowEnable

    def setMovingWindowWidth(self, movingWindowWidth):
        self.movingWindowWidth = int(movingWindowWidth)

    def getMovingWindowWidth(self):
        return self.movingWindowWidth

    def getInterpolataionPoints(self):
        return self.interpolationPoints

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            startPlotRange = 0
            for indx, curve in enumerate(self.plotCurves):
                if self.movingWindowEnable:
                    timeLen = len(self.dataPoints[curve.name()].time)
                    if timeLen > 0:
                        startPlotRange = bisect_left(self.dataPoints[curve.name()].time,
                                                     self.dataPoints[curve.name()].time[-1]
                                                     - self.movingWindowWidth)
                    if startPlotRange < 0 or startPlotRange > timeLen:
                        startPlotRange = 0
                datax = self.dataPoints[curve.name()].time[startPlotRange:]
                datay = self.dataPoints[curve.name()].values[startPlotRange:]
                if datax:
                    if self.interpolationPoints == 0 or len(datax) < self.interpolationPoints:
                        curve.setData(datax, datay)
                    else:
                        interpx = np.linspace(datax[0], datax[-1], self.interpolationPoints)
                        interpy = np.interp(interpx, datax, datay)
                        curve.setData(interpx, interpy)

    def clear(self):
        """
        Clears the data point and curve lists and the plot items
        """
        if self.plotWidget:
            self.plotWidget.getPlotItem().clear()
            self.dataPoints.clear()
            del self.plotCurves[:]


class Exporter(object):
    """
    Class exports data points from GUI to different formats (csv, png) as pandas dataframe.
    """

    def __init__(self, **kwargs):
        dataPoints = kwargs.get('dataPoints', None)

        if dataPoints is None:
            raise Exception("Given data points are None!")

        # build pandas data frame
        self.df = None
        for key, value in dataPoints.items():
            if self.df is None:
                self.df = pd.DataFrame(index=value.time, data={key: value.values})
            else:
                newDf = pd.DataFrame(index=value.time, data={key: value.values})
                self.df = self.df.join(newDf, how='outer')

        self.df.index.name = 'time'

    def exportPng(self, fileName):
        """
        Exports the data point dataframe as png with matplotlib.
        :param fileName: name of file with extension
        """
        fig = plt.figure(figsize=(10, 6))
        gs = gridspec.GridSpec(1, 1, hspace=0.1)
        axes = plt.Subplot(fig, gs[0])

        for col in self.df.columns:
            self.df[col].plot(ax=axes, label=col)

        axes.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
                    ncol=4, mode="expand", borderaxespad=0., framealpha=0.5)

        axes.grid(True)
        if self.df.index.name == 'time':
            axes.set_xlabel(r"Time (s)")

        fig.add_subplot(axes)

        fig.savefig(fileName, dpi=300)

    def exportCsv(self, fileName, sep=','):
        """
        Exports the data point dataframe as csv
        :param fileName: name of file with extension
        :param sep: separator for csv (default: ,)
        """
        self.df.to_csv(fileName, sep=sep)


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
        self.valueOff = str(kwargs.get('valueOff', 0.0))
        self.minSlider = str(kwargs.get('minSlider', 0))
        self.maxSlider = str(kwargs.get('maxSlider', 1))
        self.stepSlider = str(kwargs.get('stepSlider', 1))
        self.shortcut = str(kwargs.get('shortcut', ""))
        self.shortcutPlus = str(kwargs.get('shortcutPlus', ""))
        self.shortcutMinus = str(kwargs.get('shortcutMinus', ""))

        self.curModule = kwargs.get('module', None)
        self.curParameter = kwargs.get('parameter', None)

        self.editWidget = editWidget

        self.minSliderText = None
        self.maxSliderText = None
        self.stepSliderText = None
        self.valueOffText = None
        self.valueOnText = None
        self.valueText = None
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
        exp = kwargs.get('exp', None)
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

        if self.typeList.currentText() == "PushButton":
            self.valueText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value"), self.valueText)
            self.valueText.setValidator(QDoubleValidator())
            self.valueText.mousePressEvent = lambda event: self.valueText.selectAll()
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy2 = QLabel("")
            dummy2.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy2)
            dummy3 = QLabel("")
            dummy3.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy3)
        elif self.typeList.currentText() == "Switch":
            self.valueOnText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value On"), self.valueOnText)
            self.valueOnText.setValidator(QDoubleValidator())
            self.valueOnText.mousePressEvent = lambda event: self.valueOnText.selectAll()
            self.valueOffText = QLineEdit(self.valueOff)
            self.settingsWidgetLayout.addRow(QLabel("Value Off"), self.valueOffText)
            self.valueOffText.mousePressEvent = lambda event: self.valueOffText.selectAll()
            self.valueOffText.setValidator(QDoubleValidator())
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
            self.maxSliderText.setValidator(QDoubleValidator())
            self.maxSliderText.mousePressEvent = lambda event: self.maxSliderText.selectAll()
            self.minSliderText = QLineEdit(str(self.minSlider))
            self.settingsWidgetLayout.addRow(QLabel("Min"), self.minSliderText)
            self.minSliderText.setValidator(QDoubleValidator())
            self.minSliderText.mousePressEvent = lambda event: self.minSliderText.selectAll()
            self.stepSliderText = QLineEdit(str(self.stepSlider))
            self.settingsWidgetLayout.addRow(QLabel("Step Size"), self.stepSliderText)
            self.stepSliderText.setValidator(QDoubleValidator())
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

        for p in self.modules[module]:
            self.paramList.addItem(p)

    def _getData(self):
        msg = dict()
        msg['name'] = self.nameText.text()
        msg['widgetType'] = self.typeList.currentText()
        msg['module'] = self.moduleList.currentText()
        msg['parameter'] = self.paramList.currentText()

        if self.typeList.currentText() == "PushButton":
            msg['valueOn'] = self.valueText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
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

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec_()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            if msg['parameter'] in exp[msg['module']]:
                msg['startValue'] = exp[msg['module']][msg['parameter']]
            else:
                msg['startValue'] = 0

        return msg, result == QDialog.Accepted


class FreeLayout(QLayout):
    """
    An empty layout for widgets with no position and placement management
    """

    def __init__(self):
        super(FreeLayout, self).__init__()
        self.list = []

    def count(self):
        return len(self.list)

    def sizeHint(self):
        return QSize()

    def itemAt(self, p_int):
        return

    def addItem(self, QLayoutItem):
        return

    def addWidget(self, widget):
        if not isinstance(widget, QLabel):
            self.list.append(widget)
        super(FreeLayout, self).addWidget(widget)

    def removeWidget(self, widget):
        if widget in self.list:
            if widget.label:
                widget.label.setParent(None)
            self.list.remove(widget)
        widget.setParent(None)

    def clearAll(self):
        for i in self.list:
            if i.label:
                i.label.setParent(None)
            i.setParent(None)
        self.list = []


class MovableWidget(object):
    def __init__(self, name, label=None, **kwargs):
        self.widgetName = name
        self.label = label
        self.module = cp.copy(kwargs.get('module', None))
        self.parameter = cp.copy(kwargs.get('parameter', None))
        self._mousePressPos = None
        self._mouseMovePos = None

        self.contextMenu = QMenu()
        self.removeAction = self.contextMenu.addAction("Remove")
        self.editAction = self.contextMenu.addAction("Edit")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._mousePressPos = event.globalPos()
            self._mouseMovePos = event.globalPos()

        self.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.RightButton:
            # adjust offset from clicked point to origin of widget
            currPos = self.mapToGlobal(self.pos())
            globalPos = event.globalPos()
            diff = globalPos - self._mouseMovePos
            newPos = self.mapFromGlobal(currPos + diff)
            if self.parent().rect().contains(newPos):
                self.move(newPos)
                if self.label:
                    newPos.setY(newPos.y() + 30)
                    newPos.setX(newPos.x() + 80)
                    self.label.move(newPos)
                self._mouseMovePos = globalPos

        self.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            if self._mousePressPos is not None:
                moved = event.globalPos() - self._mousePressPos
                if moved.manhattanLength() > 0:
                    event.ignore()
                    return
                self.mouseReleaseEvent(event)
                self.contextMenu.exec_(self.mapToGlobal(event.pos()))
        else:
            self.mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        pass

    def getData(self):
        pass

    def updateData(self):
        pass


class MovablePushButton(QPushButton, MovableWidget):
    def __init__(self, name, valueOn, shortcutKey, **kwargs):
        MovableWidget.__init__(self, name, **kwargs)
        QPushButton.__init__(self, name=name)
        self.valueOn = valueOn

        self.shortcut = QShortcut(self)
        self.shortcut.setKey(shortcutKey)
        self.shortcut.setAutoRepeat(False)
        self.shortcut.activated.connect(lambda: self.animateClick())

        self.updateData()

    def getData(self):
        data = dict()

        data['widgetType'] = 'PushButton'
        data['name'] = self.widgetName
        data['valueOn'] = self.valueOn
        data['module'] = self.module
        data['parameter'] = self.parameter
        data['shortcut'] = self.shortcut.key().toString()

        return data

    def updateData(self):
        self.setText(self.widgetName + '\n' + self.valueOn)


class DoubleSlider(QSlider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        super().setMinimum(0)
        super().setMaximum(1)

        self._minValue = 0.0
        self._maxValue = 1.0

        self._stepSize = 1
        self._invStepSize = 1

    @property
    def value(self):
        curValue = float(super().value())
        return curValue * self._stepSize + self._minValue

    def setValue(self, value):
        super().setValue(int((value - self._minValue) / self._stepSize))

    def setMinimum(self, value):
        if value > self._maxValue:
            raise ValueError("Minimum limit cannot be higher than maximum")

        self._minValue = value
        super().setMinimum(0)
        super().setMaximum(int((self._maxValue - self._minValue) / self._stepSize))

    def setMaximum(self, value):
        if value < self._minValue:
            raise ValueError("Minimum limit cannot be higher than maximum")

        self._maxValue = value
        super().setMinimum(0)
        super().setMaximum(int((self._maxValue - self._minValue) / self._stepSize))

    def setTickInterval(self, p_int):
        self._stepSize = p_int

        super().setMinimum(0)
        super().setMaximum(int((self._maxValue - self._minValue) / self._stepSize))

        super().setTickInterval(1)

    def minimum(self):
        return self._minValue

    def maximum(self):
        return self._maxValue


class MovableSlider(DoubleSlider, MovableWidget):
    def __init__(self, name, minSlider, maxSlider, stepSlider, label, shortcutPlusKey, shortcutMinusKey, startValue
                 , **kwargs):
        MovableWidget.__init__(self, name, label, **kwargs)
        DoubleSlider.__init__(self, Qt.Horizontal, name=name)
        self.minSlider = minSlider
        self.maxSlider = maxSlider
        self.stepSlider = stepSlider
        self.label = label

        self.shortcutPlus = QShortcut(self)
        self.shortcutPlus.setKey(shortcutPlusKey)
        self.shortcutPlus.activated.connect(lambda: self.setValue(self.value + float(self.stepSlider)))
        self.shortcutMinus = QShortcut(self)
        self.shortcutMinus.setKey(shortcutMinusKey)
        self.shortcutMinus.activated.connect(lambda: self.setValue(self.value - float(self.stepSlider)))

        self.startValue = startValue
        self.setTracking(False)

        self.updateData()

    def getData(self):
        data = dict()

        data['widgetType'] = 'Slider'
        data['name'] = self.widgetName
        data['minSlider'] = self.minSlider
        data['maxSlider'] = self.maxSlider
        data['stepSlider'] = self.stepSlider
        data['module'] = self.module
        data['parameter'] = self.parameter
        data['shortcutPlus'] = self.shortcutPlus.key().toString()
        data['shortcutMinus'] = self.shortcutMinus.key().toString()

        return data

    def updateData(self):
        self.setValue(float(self.startValue))
        self.label.setText(self.widgetName + ': ' + str(self.startValue))
        self.setMinimum(float(self.minSlider))
        self.setMaximum(float(self.maxSlider))
        self.setTickInterval(float(self.stepSlider))
        self.setPageStep(float(self.stepSlider))
        self.setSingleStep(float(self.stepSlider))


class MovableSwitch(QPushButton, MovableWidget):
    def __init__(self, name, valueOn, valueOff, shortcutKey, **kwargs):
        MovableWidget.__init__(self, name, **kwargs)
        QPushButton.__init__(self, name=name)
        self.valueOn = valueOn
        self.valueOff = valueOff

        self.shortcut = QShortcut(self)
        self.shortcut.setKey(shortcutKey)
        self.shortcut.setAutoRepeat(False)
        self.shortcut.activated.connect(lambda: self.animateClick())

        self.setCheckable(True)

        self.updateData()

    def getData(self):
        data = dict()

        data['widgetType'] = 'Switch'
        data['name'] = self.widgetName
        data['valueOn'] = self.valueOn
        data['valueOff'] = self.valueOff
        data['module'] = self.module
        data['parameter'] = self.parameter
        data['shortcut'] = self.shortcut.key().toString()

        return data

    def updateData(self):
        self.setChecked(False)
        self.setText(self.widgetName + '\n' + self.valueOn)


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


class PinnedDock(Dock):
    def __init__(self, *args):
        super(PinnedDock, self).__init__(*args)
        self.label.mouseDoubleClickEvent = lambda event: event.ignore()


class ContextLineEditAction(QWidgetAction):
    dataEmit = pyqtSignal(str)

    def __init__(self, **kwargs):
        parent = kwargs.get("parent", None)
        super(QWidgetAction, self).__init__(parent)

        self.minValue = kwargs.get("min", 1)
        self.maxValue = kwargs.get("max", 1000)
        self.currentValue = kwargs.get("current", 0)
        self.unit = kwargs.get("unit", "")
        self.title = kwargs.get("title", "pywisp")

        mainLayout = QHBoxLayout()
        titleLabel = QLabel(parent)
        titleLabel.setText(self.title)
        mainLayout.addWidget(titleLabel)

        self.data = QLineEdit()
        self.data.setText(str(self.currentValue))
        self.data.setValidator(QIntValidator(self.minValue, self.maxValue, self))

        mainLayout.addWidget(self.data)

        if not self.unit == "":
            unitLabel = QLabel()
            unitLabel.setText(self.unit)
            mainLayout.addWidget(unitLabel)

        mainWidget = QWidget()
        mainWidget.setLayout(mainLayout)
        self.setDefaultWidget(mainWidget)

        self.data.editingFinished.connect(self.onChange)

    def onChange(self):
        self.dataEmit.emit(self.data.text())
