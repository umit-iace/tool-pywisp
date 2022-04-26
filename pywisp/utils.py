# -*- coding: utf-8 -*-
import logging
import os
import struct
from bisect import bisect_left
import subprocess
from pathlib import Path
import importlib.util

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QRegExp, QSize, pyqtSignal, QRect
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator, QIcon, QDoubleValidator, QKeySequence, QFont, QPen, \
    QPainter, QTextCursor
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout, QFormLayout, \
    QLayout, QComboBox, QPushButton, QWidget, QSlider, QMenu, QWidgetAction, QShortcut, QStyledItemDelegate, QStyle
from pyqtgraph import mkPen
from pyqtgraph.dockarea import Dock

__all__ = ["createDir", "getResource", "packArrayToFrame", "CppBinding"]

def coroutine(func):
    """ wrapper for starting coroutine upon creation """
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return start

def pipe(coros):
    """ start a pipe of coroutines """
    def flatten(lst):
        """ flatten an arbitrarily nested list """
        ret = []
        if isinstance(lst, list):
            for item in lst:
                if isinstance(item, list):
                    ret.extend(flatten(item))
                else:
                    ret.append(item)
            return ret
        else:
            return lst
    coros = flatten(coros)

    ret = coros[-1]()
    for coro in reversed(coros[:-1]):
        ret = coro(ret)
    return ret

def createDir(dirName):
    """
    Checks if directory exists and create the directory if not.
    :param dirName: directory name
    :return: path of directory
    """
    path = os.getcwd() + os.path.sep + dirName
    if not os.path.exists(path) or not os.path.isdir(path):
        os.mkdir(path)
    return path


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
            outList += [float(data[i * frameLenFloat + j]) for j in range(frameLenFloat - 1) if
                       i * frameLenFloat + j < len(data)]
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
                self.cb.moveCursor(QTextCursor.End)
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
                # check if data is multidimensional
                if self.dataPoints[curve.name()].values:
                    if isinstance(self.dataPoints[curve.name()].values[-1], (list, np.ndarray)):
                        continue
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
        self.valueReset = str(kwargs.get('valueReset', ''))
        self.valueOff = str(kwargs.get('valueOff', 0.0))
        self.minSlider = str(kwargs.get('minSlider', 0))
        self.maxSlider = str(kwargs.get('maxSlider', 1))
        self.stepSlider = str(kwargs.get('stepSlider', 1))
        self.shortcut = str(kwargs.get('shortcut', ""))
        self.shortcutPlus = str(kwargs.get('shortcutPlus', ""))
        self.shortcutMinus = str(kwargs.get('shortcutMinus', ""))

        self.curModule = kwargs.get('Module', None)
        self.curParameter = kwargs.get('Parameter', None)

        self.editWidget = editWidget

        self.minSliderText = None
        self.maxSliderText = None
        self.stepSliderText = None
        self.valueOffText = None
        self.valueOnText = None
        self.valueText = None
        self.valueResetText =None
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

        for p in self.modules[module]:
            self.paramList.addItem(p)

    def _getData(self):
        msg = dict()
        msg['name'] = self.nameText.text()
        msg['widgetType'] = self.typeList.currentText()
        msg['Module'] = self.moduleList.currentText()
        msg['Parameter'] = self.paramList.currentText()

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

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec_()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            if msg['Parameter'] in exp[msg['Module']]:
                msg['startValue'] = exp[msg['Module']][msg['Parameter']]
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
    def __init__(self, name, label=None):
        self.widgetName = name
        self.label = label
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
    def __init__(self, name, valueOn, valueReset, shortcutKey, **kwargs):
        MovableWidget.__init__(self, name)
        QPushButton.__init__(self, name=name)
        self.valueOn = valueOn
        self.valueReset = valueReset

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

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
        data['valueReset'] = self.valueReset
        data['Module'] = self.module
        data['Parameter'] = self.parameter
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

    @property
    def value(self):
        curValue = float(super().value())
        return self.calcValue(curValue)

    def calcValue(self, value):
        return round((value * self._stepSize) + self._minValue, 6)

    def setValue(self, value):
        super().setValue(int(round((value - self._minValue) / self._stepSize, 8)))

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
        MovableWidget.__init__(self, name, label)
        DoubleSlider.__init__(self, Qt.Horizontal, name=name)

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

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

    def updateGamePad(self, gamepad):
        self.gamepad = gamepad
        if gamepad is not None:
            self.gamepad.absX.connect(lambda: self.setValue(self.value + float(self.stepSlider)))
            self.gamepad.btnN.connect(lambda: self.setValue(self.value - float(self.stepSlider)))

    def getData(self):
        data = dict()

        data['widgetType'] = 'Slider'
        data['name'] = self.widgetName
        data['minSlider'] = self.minSlider
        data['maxSlider'] = self.maxSlider
        data['stepSlider'] = self.stepSlider
        data['Module'] = self.module
        data['Parameter'] = self.parameter
        data['shortcutPlus'] = self.shortcutPlus.key().toString()
        data['shortcutMinus'] = self.shortcutMinus.key().toString()

        return data

    def updateData(self):
        self.setMinimum(float(self.minSlider))
        self.setMaximum(float(self.maxSlider))
        self.setTickInterval(float(self.stepSlider))
        self.setPageStep(1)
        self.setSingleStep(1)
        self.setValue(float(self.startValue))
        self.label.setText(self.widgetName + ': ' + str(self.startValue))


class MovableSwitch(QPushButton, MovableWidget):
    def __init__(self, name, valueOn, valueOff, shortcutKey, **kwargs):
        MovableWidget.__init__(self, name)
        QPushButton.__init__(self, name=name)

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

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
        data['Module'] = self.module
        data['Parameter'] = self.parameter
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


def isNan(value):
    if value == 6.95165821120223e-310:
        return True
    else:
        return False


def isInf(value):
    if value == 6.94996061456946e-310:
        return True
    else:
        return False


class TreeWidgetStyledItemDelegate(QStyledItemDelegate):
    """
        For overriding behavior of selection and hovering in QTreeView and QTreeWidget

        When you set background color (QtGui.QColor()) to QTreeWidgetItem you also must set this color like:
            item.setData(0, QtCore.Qt.BackgroundRole, QtGui.QColor())
    """

    def paint(self, painter, option, index):
        def draw_my(option, painter, brush, text, icon):
            if brush is None:
                brush = QColor(255, 255, 255,
                               0)  # This is original background color. I just set alpha to 0 which means it is transparent

            x, y = (option.rect.x(), option.rect.y())
            h = option.rect.height()
            painter.save()

            painter.setFont(option.font)
            if icon:
                icon = icon.pixmap(h, h)
                painter.drawPixmap(QRect(x, y, h, h), icon)
                painter.drawText(option.rect.adjusted(h, 0, 0, 0), Qt.AlignLeft, text)
            else:
                painter.drawText(option.rect, Qt.AlignLeft, text)

            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.setPen(QPen(Qt.NoPen))
            painter.fillRect(option.rect, brush)
            painter.setBackgroundMode(Qt.OpaqueMode)
            painter.setBackground(brush)
            painter.drawRect(option.rect)
            painter.restore()

        # Also should be activated in StyleSheet
        #                             Selected
        if (option.state & QStyle.State_Selected):
            option.font.setWeight(QFont.Bold)

            brush = index.data(Qt.BackgroundRole)
            text = index.data(Qt.DisplayRole)
            icon = index.data(Qt.DecorationRole)

            draw_my(option=option, painter=painter, brush=brush, text=text, icon=icon)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)


class BindingException(Exception):
    """
    Exception to be raised if the cpp binding raises.
    """
    pass


class CppBinding:
    buildDir = "_build"
    libDir = "_lib"
    cmakeLists = "CMakeLists.txt"

    def __init__(self,
                 moduleName=None,
                 modulePath=None,
                 bindingClassName=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        # adapt to os-specific extensions
        if os.name == 'nt':
            self.sfx = '.pyd'
        else:
            self.sfx = '.so'

        if moduleName is None:
            self._logger.error("Instantiation of binding class without"
                               " moduleName is not allowed!")
            raise BindingException("Instantiation of binding class without"
                                   " moduleName is not allowed!")
        self.moduleName = moduleName

        if modulePath is None:
            self._logger.error("Instantiation of binding class without"
                               " modulePath is not allowed!")
            raise BindingException("Instantiation of binding class without"
                                   " modulePath is not allowed!")

        self.modulePath = Path(modulePath)
        self.moduleStem = self.modulePath / self.moduleName
        self.moduleIncPath = self.moduleStem.with_suffix(".h")
        self.moduleSrcPath = self.moduleStem.with_suffix(".cpp")
        self.cmakeListsPath = self.modulePath / self.cmakeLists
        self.moduleBuildPath = self.modulePath / self.buildDir
        self.moduleLibPath = self.modulePath / self.libDir

        if bindingClassName is None:
            self._logger.error("Instantiation of binding class without"
                               " bindingClassName is not allowed!")
            raise BindingException("Instantiation of binding class without"
                                   " bindingClassName is not allowed!")
        self.bindingClassName = bindingClassName

        if self.createBindingConfig():
            self.buildBinding()
            self.installBinding()

    def createBindingConfig(self):
        # check if folder exists
        if not self.modulePath.is_dir():
            self._logger.error("Module directory '{}' could not be found."
                               "".format(self.modulePath))
            return False

        if not self.moduleSrcPath.is_file():
            self._logger.error("CPP binding '{}' could not be found in the "
                               "given module path '{}'."
                               "".format(self.moduleSrcPath,
                                         self.modulePath))
            return False

        if not self.moduleIncPath.is_file():
            self._logger.error("Header file '{}' could not be found in the "
                               "given module path '{}'."
                               "".format(self.moduleIncPath,
                                         self.modulePath))
            return False

        if not self.cmakeListsPath.is_file():
            self._logger.warning("CMakeLists.txt not found in module path.")
            self._logger.info("Generating new CMake config.")
            self.createCmakeLists()

        configChanged = self.updateBindingConfig()
        if configChanged:
            self.buildConfig()

        return True

    def createCmakeLists(self):
        """
        Create the stub of a `CMakeLists.txt` .

        Returns:

        """
        cMakeLists = "cmake_minimum_required(VERSION 3.4)\n"
        cMakeLists += "project(Bindings)\n\n"

        cMakeLists += "set( CMAKE_CXX_STANDARD 11 )\n\n"
        cMakeLists += "find_package(PythonLibs REQUIRED)\n\n"

        cMakeLists += "set( CMAKE_RUNTIME_OUTPUT_DIRECTORY . )\n"
        cMakeLists += "set( CMAKE_LIBRARY_OUTPUT_DIRECTORY . )\n"
        cMakeLists += "set( CMAKE_ARCHIVE_OUTPUT_DIRECTORY . )\n\n"

        cMakeLists += "foreach( OUTPUTCONFIG ${CMAKE_CONFIGURATION_TYPES} )\n"
        cMakeLists += "\tstring( TOUPPER ${OUTPUTCONFIG} OUTPUTCONFIG )\n"
        cMakeLists += "\tset( CMAKE_RUNTIME_OUTPUT_DIRECTORY_${OUTPUTCONFIG} . )\n"
        cMakeLists += "\tset( CMAKE_LIBRARY_OUTPUT_DIRECTORY_${OUTPUTCONFIG} . )\n"
        cMakeLists += "\tset( CMAKE_ARCHIVE_OUTPUT_DIRECTORY_${OUTPUTCONFIG} . )\n"
        cMakeLists += "endforeach( OUTPUTCONFIG CMAKE_CONFIGURATION_TYPES )\n\n"

        cMakeLists += "include_directories(${PYTHON_INCLUDE_DIRS})\n"

        with open(self.cmakeListsPath, "w") as f:
            f.write(cMakeLists)

    def updateBindingConfig(self):
        """
        Add the module config to the cmake lists.

        Returns:
            bool: True if build config has been changed and cmake has to be
            rerun.
        """
        configLine = "add_library({} SHARED {} {})\n".format(
            self.moduleName,
            self.moduleSrcPath.as_posix(),
            self.bindingClassName + '.cpp'
        )
        configLine += "set_target_properties({} PROPERTIES PREFIX \"\" OUTPUT_NAME \"{}\" SUFFIX \"{}\")\n".format(
            self.moduleName,
            self.moduleName,
            self.sfx
        )
        configLine += "target_link_libraries({} ${{PYTHON_LIBRARIES}})\n".format(
            self.moduleName
        )
        configLine += "install(FILES {}/{} DESTINATION {})".format(
            self.buildDir,
            self.moduleName + self.sfx,
            self.moduleLibPath.as_posix()
        )
        with open(self.cmakeListsPath, "r") as f:
            if configLine in f.read():
                return False

        self._logger.info("Appending build info for '{}'".format(self.moduleName))
        with open(self.cmakeListsPath, "a") as f:
            f.write("\n")
            f.write(configLine)

        return True

    def buildConfig(self):
        if os.name == 'nt':
            cmd = ['cmake', '-A', 'x64', '-S', '.', '-B', self.buildDir]
        else:
            cmd = ['cmake',  '-S', '.', '-B', self.buildDir]
        result = subprocess.run(cmd, cwd=self.modulePath)

        if result.returncode != 0:
            self._logger.error("Generation of binding config failed.")
            raise BindingException("Generation of binding config failed.")

    def buildBinding(self):
        # build
        if os.name == 'nt':
            cmd = ['cmake', '--build', self.buildDir, '--config', 'Release', '--target', 'INSTALL']
        else:
            cmd = ['cmake', '--build', self.buildDir]
        result = subprocess.run(cmd, cwd=self.modulePath)

        if result.returncode != 0:
            self._logger.error("Build failed!")
            raise BindingException("Build failed!")

    def installBinding(self):
        # generate config
        if os.name == 'nt':
            return
        else:
            cmd = ['cmake', '--install', self.buildDir]
        result = subprocess.run(cmd, cwd=self.modulePath)

        if result.returncode != 0:
            self._logger.error("Installation of bindings failed.")
            raise BindingException("Installation of bindings failed.")

    def getClassFromModule(self):
        try:
            spec = importlib.util.spec_from_file_location(self.moduleName,
                                                          (self.moduleLibPath / self.moduleName).with_suffix(self.sfx))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except ImportError as e:
            self._logger.error("Cannot load module: {}".format(e))
            raise e
