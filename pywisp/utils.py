# -*- coding: utf-8 -*-
import copy as cp
import logging
import os
from bisect import bisect_left

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QRegExp, QSize, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator, QIcon, QDoubleValidator, QKeySequence, QPainter
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout, QFormLayout, \
    QLayout, QComboBox, QPushButton, QWidget, QSlider, QMenu, QWidgetAction, QShortcut, QTabWidget
from pyqtgraph import mkPen
from pyqtgraph.dockarea import Dock

__all__ = ["get_resource"]


def get_resource(resName, resType="icons"):
    """
    Build absolute path to specified resource within the package
    :param resName: name of the ressource
    :param resType: sub directory
    :return: path to resource
    """
    own_path = os.path.dirname(__file__)
    resource_path = os.path.abspath(os.path.join(own_path, "resources", resType))
    return os.path.join(resource_path, resName)


class PlainTextLogger(logging.Handler):
    """
    Logging handler that formats log data for line display
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

    def set_target_cb(self, cb):
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

    def __init__(self, title, settings):
        self.title = title
        self.dataPoints = dict()
        self.plotWidget = None
        self.plotCurves = []
        self.interpolationPoints = 100
        self.settings = settings
        self.movingWindowEnable = False
        self.movingWindowWidth = 60

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

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            startPlotRange = 0
            if self.movingWindowEnable and self.plotCurves is not None:
                timeLen = len(self.dataPoints[self.plotCurves[0].name()].time)
                if timeLen > 0:
                    startPlotRange = bisect_left(self.dataPoints[self.plotCurves[0].name()].time,
                                                 self.dataPoints[self.plotCurves[0].name()].time[-1]
                                                 - self.movingWindowWidth)
                if startPlotRange < 0 or startPlotRange > timeLen:
                    startPlotRange = 0
            for indx, curve in enumerate(self.plotCurves):
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

        resPath = get_resource("icon.svg")
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

        resPath = get_resource("icon.svg")
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
        self.rangeXMax = str(kwargs.get('rangeXMax', 1))
        self.rangeXMin = str(kwargs.get('rangeXMin', -1))
        self.precisionX = str(kwargs.get('precisionX', 0))
        self.shortcutXPlus = str(kwargs.get('shortcutXPlus', ""))
        self.shortcutXMinus = str(kwargs.get('shortcutXMinus', ""))
        self.rangeYMax = str(kwargs.get('rangeYMax', 1))
        self.rangeYMin = str(kwargs.get('rangeYMin', -1))
        self.precisionY = str(kwargs.get('precisionY', 0))
        self.shortcutYPlus = str(kwargs.get('shortcutYPlus', ""))
        self.shortcutYMinus = str(kwargs.get('shortcutYMinus', ""))

        self.curModule = kwargs.get('module', None)
        self.curParameter = kwargs.get('parameter', None)

        self.curModuleX = kwargs.get('moduleX', None)
        self.curParameterX = kwargs.get('parameterX', None)
        self.curModuleY = kwargs.get('moduleY', None)
        self.curParameterY = kwargs.get('parameterY', None)

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
        self.rangeXMaxText = None
        self.rangeXMinText = None
        self.precisionXText = None
        self.shortcutFieldXPlus = None
        self.shortcutFieldXMinus = None
        self.rangeYMaxText = None
        self.rangeYMinText = None
        self.precisionYText = None
        self.shortcutFieldYPlus = None
        self.shortcutFieldYMinus = None

        mainwidget = QWidget()
        mainLayout = QFormLayout()
        mainwidget.setLayout(mainLayout)

        windowLayout = QVBoxLayout()

        windowLayout.addWidget(mainwidget)
        self.setLayout(windowLayout)

        self.nameText = QLineEdit(self.name)
        self.nameText.setMinimumWidth(200)
        mainLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(["PushButton", "Switch", "Slider", "Joystick"])
        self.typeList.setCurrentText(self.widgetType)
        self.typeList.currentIndexChanged.connect(lambda: self.typeListChanged(kwargs.get('exp', None)))
        self.typeList.setEnabled(not self.editWidget)
        mainLayout.addRow(QLabel("Widget type"), self.typeList)

        self.tabWidget = QTabWidget()
        self.tabWidget.setUsesScrollButtons(False)
        mainLayout.addRow(self.tabWidget)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        windowLayout.addWidget(buttons)

        self.typeListChanged(kwargs.get('exp', None))

        self.setWindowTitle("Add Remote Widget ...")
        resPath = get_resource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)
        self.setFixedSize(self.sizeHint())

    def typeListChanged(self, exp):
        height = QLineEdit().sizeHint().height()

        if self.typeList.currentText() == "PushButton":
            self.settingsWidget = QWidget()
            self.settingsWidgetLayout = QFormLayout()
            self.settingsWidget.setLayout(self.settingsWidgetLayout)
            self.tabWidget.clear()
            self.tabWidget.addTab(self.settingsWidget, "Settings")

            self.moduleList = QComboBox()
            self.paramList = QComboBox()
            self.modules = dict()
            for key, value in exp.items():
                self.modules[key] = [k for k, v in value.items()]

                self.moduleList.addItem(key)
            self.moduleList.currentIndexChanged.connect(lambda: self.moduleChanged(self.moduleList, self.paramList, self.modules))
            if self.curModule is None:
                self.moduleList.setCurrentIndex(0)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            else:
                self.moduleList.setCurrentText(self.curModule)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            if self.curParameter is not None:
                self.paramList.setCurrentText(self.curParameter)
            self.settingsWidgetLayout.addRow(QLabel("Modules"), self.moduleList)
            self.settingsWidgetLayout.addRow(QLabel("Parameter"), self.paramList)

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
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
        elif self.typeList.currentText() == "Switch":
            self.settingsWidget = QWidget()
            self.settingsWidgetLayout = QFormLayout()
            self.settingsWidget.setLayout(self.settingsWidgetLayout)
            self.tabWidget.clear()
            self.tabWidget.addTab(self.settingsWidget, "Settings")

            self.moduleList = QComboBox()
            self.paramList = QComboBox()
            self.modules = dict()
            for key, value in exp.items():
                self.modules[key] = [k for k, v in value.items()]

                self.moduleList.addItem(key)
            self.moduleList.currentIndexChanged.connect(lambda: self.moduleChanged(self.moduleList, self.paramList, self.modules))
            if self.curModule is None:
                self.moduleList.setCurrentIndex(0)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            else:
                self.moduleList.setCurrentText(self.curModule)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            if self.curParameter is not None:
                self.paramList.setCurrentText(self.curParameter)
            self.settingsWidgetLayout.addRow(QLabel("Modules"), self.moduleList)
            self.settingsWidgetLayout.addRow(QLabel("Parameter"), self.paramList)

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
            self.settingsWidgetLayout.addRow(QLabel("Shortcut"), self.shortcutField)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
        elif self.typeList.currentText() == "Slider":
            self.settingsWidget = QWidget()
            self.settingsWidgetLayout = QFormLayout()
            self.settingsWidget.setLayout(self.settingsWidgetLayout)
            self.tabWidget.clear()
            self.tabWidget.addTab(self.settingsWidget, "Settings")

            self.moduleList = QComboBox()
            self.paramList = QComboBox()
            self.modules = dict()
            for key, value in exp.items():
                self.modules[key] = [k for k, v in value.items()]

                self.moduleList.addItem(key)
            self.moduleList.currentIndexChanged.connect(lambda: self.moduleChanged(self.moduleList, self.paramList, self.modules))
            if self.curModule is None:
                self.moduleList.setCurrentIndex(0)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            else:
                self.moduleList.setCurrentText(self.curModule)
                self.moduleChanged(self.moduleList, self.paramList, self.modules)
            if self.curParameter is not None:
                self.paramList.setCurrentText(self.curParameter)
            self.settingsWidgetLayout.addRow(QLabel("Modules"), self.moduleList)
            self.settingsWidgetLayout.addRow(QLabel("Parameter"), self.paramList)

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
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Plus"), self.shortcutFieldPlus)
            self.shortcutFieldMinus = ShortcutCreator()
            self.shortcutFieldMinus.setText(self.shortcutMinus)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Minus"), self.shortcutFieldMinus)
        elif self.typeList.currentText() == "Joystick":

            self.settingsWidgetX = QWidget()
            self.settingsWidgetLayoutX = QFormLayout()
            self.settingsWidgetX.setLayout(self.settingsWidgetLayoutX)
            self.tabWidget.clear()
            self.tabWidget.addTab(self.settingsWidgetX, "Settings X-Axis")

            self.moduleListX = QComboBox()
            self.paramListX = QComboBox()
            self.modulesX = dict()
            for key, value in exp.items():
                self.modulesX[key] = [k for k, v in value.items()]

                self.moduleListX.addItem(key)
            self.moduleListX.currentIndexChanged.connect(lambda: self.moduleChanged(self.moduleListX, self.paramListX, self.modulesX))
            if self.curModuleX is None:
                self.moduleListX.setCurrentIndex(0)
                self.moduleChanged(self.moduleListX, self.paramListX, self.modulesX)
            else:
                self.moduleListX.setCurrentText(self.curModuleX)
                self.moduleChanged(self.moduleListX, self.paramListX, self.modulesX)
            if self.curParameterX is not None:
                self.paramListX.setCurrentText(self.curParameterX)
            self.settingsWidgetLayoutX.addRow(QLabel("Modules"), self.moduleListX)
            self.settingsWidgetLayoutX.addRow(QLabel("Parameter"), self.paramListX)

            self.rangeXMaxText = QLineEdit(self.rangeXMax)
            self.settingsWidgetLayoutX.addRow(QLabel("Range Max"), self.rangeXMaxText)
            self.rangeXMaxText.setValidator(QDoubleValidator())
            self.rangeXMaxText.mousePressEvent = lambda event: self.rangeXMaxText.selectAll()
            self.rangeXMinText = QLineEdit(self.rangeXMin)
            self.settingsWidgetLayoutX.addRow(QLabel("Range Min"), self.rangeXMinText)
            self.rangeXMinText.mousePressEvent = lambda event: self.rangeXMinText.selectAll()
            self.rangeXMinText.setValidator(QDoubleValidator())
            self.precisionXText = QLineEdit(self.precisionX)
            self.settingsWidgetLayoutX.addRow(QLabel("Precision"), self.precisionXText)
            self.precisionXText.mousePressEvent = lambda event: self.precisionXText.selectAll()
            self.precisionXText.setValidator(QIntValidator(0, 5))
            self.shortcutFieldXPlus = ShortcutCreator()
            self.shortcutFieldXPlus.setText(self.shortcutXPlus)
            self.settingsWidgetLayoutX.addRow(QLabel("Shortcut Plus"), self.shortcutFieldXPlus)
            self.shortcutFieldXMinus = ShortcutCreator()
            self.shortcutFieldXMinus.setText(self.shortcutXMinus)
            self.settingsWidgetLayoutX.addRow(QLabel("Shortcut Minus"), self.shortcutFieldXMinus)

            self.settingsWidgetY = QWidget()
            self.settingsWidgetLayoutY = QFormLayout()
            self.settingsWidgetY.setLayout(self.settingsWidgetLayoutY)
            self.tabWidget.addTab(self.settingsWidgetY, "Settings Y-Axis")

            self.moduleListY = QComboBox()
            self.paramListY = QComboBox()
            self.modulesY = dict()
            for key, value in exp.items():
                self.modulesY[key] = [k for k, v in value.items()]

                self.moduleListY.addItem(key)
            self.moduleListY.currentIndexChanged.connect(lambda: self.moduleChanged(self.moduleListY, self.paramListY, self.modulesY))
            if self.curModuleY is None:
                self.moduleListY.setCurrentIndex(0)
                self.moduleChanged(self.moduleListY, self.paramListY, self.modulesY)
            else:
                self.moduleListY.setCurrentText(self.curModuleY)
                self.moduleChanged(self.moduleListY, self.paramListY, self.modulesY)
            if self.curParameterY is not None:
                self.paramListY.setCurrentText(self.curParameterY)
            self.settingsWidgetLayoutY.addRow(QLabel("Modules"), self.moduleListY)
            self.settingsWidgetLayoutY.addRow(QLabel("Parameter"), self.paramListY)

            self.rangeYMaxText = QLineEdit(self.rangeYMax)
            self.settingsWidgetLayoutY.addRow(QLabel("Range Max"), self.rangeYMaxText)
            self.rangeYMaxText.setValidator(QDoubleValidator())
            self.rangeYMaxText.mousePressEvent = lambda event: self.rangeYMaxText.selectAll()
            self.rangeYMinText = QLineEdit(self.rangeYMin)
            self.settingsWidgetLayoutY.addRow(QLabel("Range Min"), self.rangeYMinText)
            self.rangeYMinText.mousePressEvent = lambda event: self.rangeYMinText.selectAll()
            self.rangeYMinText.setValidator(QDoubleValidator())
            self.precisionYText = QLineEdit(self.precisionY)
            self.settingsWidgetLayoutY.addRow(QLabel("Precision"), self.precisionYText)
            self.precisionYText.mousePressEvent = lambda event: self.precisionYText.selectAll()
            self.precisionYText.setValidator(QIntValidator(0, 5))
            self.shortcutFieldYPlus = ShortcutCreator()
            self.shortcutFieldYPlus.setText(self.shortcutYPlus)
            self.settingsWidgetLayoutY.addRow(QLabel("Shortcut Plus"), self.shortcutFieldYPlus)
            self.shortcutFieldYMinus = ShortcutCreator()
            self.shortcutFieldYMinus.setText(self.shortcutYMinus)
            self.settingsWidgetLayoutY.addRow(QLabel("Shortcut Minus"), self.shortcutFieldYMinus)

    def moduleChanged(self, moduleList, paramList, modules):
        paramList.clear()
        module = moduleList.currentText()

        for p in modules[module]:
            paramList.addItem(p)

    def _getData(self):
        msg = dict()
        msg['name'] = self.nameText.text()
        msg['widgetType'] = self.typeList.currentText()

        if self.typeList.currentText() == "PushButton":
            msg['module'] = self.moduleList.currentText()
            msg['parameter'] = self.paramList.currentText()
            msg['valueOn'] = self.valueText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
        elif self.typeList.currentText() == "Switch":
            msg['module'] = self.moduleList.currentText()
            msg['parameter'] = self.paramList.currentText()
            msg['valueOn'] = self.valueOnText.text()
            msg['valueOff'] = self.valueOffText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
        elif self.typeList.currentText() == "Slider":
            msg['module'] = self.moduleList.currentText()
            msg['parameter'] = self.paramList.currentText()
            msg['minSlider'] = self.minSliderText.text()
            msg['maxSlider'] = self.maxSliderText.text()
            msg['stepSlider'] = self.stepSliderText.text()
            msg['shortcutPlus'] = self.shortcutFieldPlus.getKeySequence()
            msg['shortcutMinus'] = self.shortcutFieldMinus.getKeySequence()
        elif self.typeList.currentText() == "Joystick":
            msg['moduleX'] = self.moduleListX.currentText()
            msg['parameterX'] = self.paramListX.currentText()
            msg['moduleY'] = self.moduleListY.currentText()
            msg['parameterY'] = self.paramListY.currentText()
            msg['rangeXMax'] = self.rangeXMaxText.text()
            msg['rangeXMin'] = self.rangeXMinText.text()
            msg['rangeYMax'] = self.rangeYMaxText.text()
            msg['rangeYMin'] = self.rangeYMinText.text()
            msg['precisionX'] = self.precisionXText.text()
            msg['precisionY'] = self.precisionYText.text()
            msg['shortcutXPlus'] = self.shortcutFieldXPlus.getKeySequence()
            msg['shortcutXMinus'] = self.shortcutFieldXMinus.getKeySequence()
            msg['shortcutYPlus'] = self.shortcutFieldYPlus.getKeySequence()
            msg['shortcutYMinus'] = self.shortcutFieldYMinus.getKeySequence()

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec_()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            msg['startValue'] = exp[msg['module']][msg['parameter']]

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
        if self._mousePressPos is not None:
            moved = event.globalPos() - self._mousePressPos
            if moved.manhattanLength() > 0:
                event.ignore()
                return

            self.mouseReleaseEvent(event)
            self.contextMenu.exec_(self.mapToGlobal(event.pos()))

    def contextMenuEvent(self, event):
        pass

    def getData(self):
        pass

    def updateData(self):
        pass


class MovablePushButton(QPushButton, MovableWidget):
    def __init__(self, name, valueOn, shortcutKey, **kwargs):
        QPushButton.__init__(self, name=name)
        MovableWidget.__init__(self, name, **kwargs)
        self.valueOn = valueOn

        self.module = cp.copy(kwargs.get('module', None))
        self.parameter = cp.copy(kwargs.get('parameter', None))

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


class MovableSlider(QSlider, MovableWidget):
    def __init__(self, name, minSlider, maxSlider, stepSlider, label, shortcutPlusKey, shortcutMinusKey, startValue
                 , **kwargs):
        QSlider.__init__(self, Qt.Horizontal, name=name)
        MovableWidget.__init__(self, name, label, **kwargs)
        self.minSlider = minSlider
        self.maxSlider = maxSlider
        self.stepSlider = stepSlider
        self.label = label

        self.module = cp.copy(kwargs.get('module', None))
        self.parameter = cp.copy(kwargs.get('parameter', None))

        self.shortcutPlus = QShortcut(self)
        self.shortcutPlus.setKey(shortcutPlusKey)
        self.shortcutPlus.activated.connect(lambda: self.setValue(self.value() + int(self.stepSlider)))
        self.shortcutMinus = QShortcut(self)
        self.shortcutMinus.setKey(shortcutMinusKey)
        self.shortcutMinus.activated.connect(lambda: self.setValue(self.value() - int(self.stepSlider)))

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
        self.setValue(int(self.startValue))
        self.label.setText(self.widgetName + ': ' + str(self.startValue))
        self.setMinimum(int(self.minSlider))
        self.setMaximum(int(self.maxSlider))
        self.setTickInterval(int(self.stepSlider))
        self.setPageStep(int(self.stepSlider))
        self.setSingleStep(int(self.stepSlider))


class MovableSwitch(QPushButton, MovableWidget):
    def __init__(self, name, valueOn, valueOff, shortcutKey, **kwargs):
        QPushButton.__init__(self, name=name)
        MovableWidget.__init__(self, name, **kwargs)
        self.valueOn = valueOn
        self.valueOff = valueOff

        self.module = cp.copy(kwargs.get('module', None))
        self.parameter = cp.copy(kwargs.get('parameter', None))

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


class MovableJoystick(QWidget, MovableWidget):
    valuesChanged = pyqtSignal()
    def __init__(self, name, rangeXMax, rangeXMin, rangeYMax, rangeYMin, shortcutXPlusKey, shortcutXMinusKey,
                 shortcutYPlusKey, shortcutYMinusKey, precisionX, precisionY, **kwargs):
        QWidget.__init__(self, name=name)
        MovableWidget.__init__(self, name, **kwargs)
        self.currentX = 100
        self.currentY = 100
        self.centerX = 100
        self.centerY = 100

        self.precisionX = int(precisionX)
        self.precisionY = int(precisionY)

        self.rangeXMin = float(rangeXMin)
        self.rangeXMax = float(rangeXMax)
        self.rangeYMin = float(rangeYMin)
        self.rangeYMax = float(rangeYMax)

        self.valueX = (self.rangeXMax-self.rangeXMin)/2+self.rangeXMin
        self.valueY = -((self.rangeYMax-self.rangeYMin)/2+self.rangeYMin)

        self.moduleX = cp.copy(kwargs.get('moduleX', None))
        self.parameterX = cp.copy(kwargs.get('parameterX', None))
        self.moduleY = cp.copy(kwargs.get('moduleY', None))
        self.parameterY = cp.copy(kwargs.get('parameterY', None))

        self.shortcutXPlus = QShortcut(self)
        self.shortcutXPlus.setKey(shortcutXPlusKey)
        self.shortcutXPlus.activated.connect(lambda: self.moveCenter(self.currentX+5, self.currentY))
        self.shortcutXMinus = QShortcut(self)
        self.shortcutXMinus.setKey(shortcutXMinusKey)
        self.shortcutXMinus.activated.connect(lambda: self.moveCenter(self.currentX-5, self.currentY))

        self.shortcutYPlus = QShortcut(self)
        self.shortcutYPlus.setKey(shortcutYPlusKey)
        self.shortcutYPlus.activated.connect(lambda: self.moveCenter(self.currentX, self.currentY-5))
        self.shortcutYMinus = QShortcut(self)
        self.shortcutYMinus.setKey(shortcutYMinusKey)
        self.shortcutYMinus.activated.connect(lambda: self.moveCenter(self.currentX, self.currentY+5))

        self.updateData()

    def paintEvent(self, event):
        paint = QPainter()
        paint.begin(self)
        paint.setRenderHint(QPainter.Antialiasing)
        paint.setBrush(Qt.lightGray)
        paint.drawRect(event.rect())
        radius = 20
        actualCenter = QPoint(self.currentX, self.currentY)
        center = QPoint(self.centerX, self.centerY)
        paint.setBrush(Qt.black)
        paint.drawEllipse(actualCenter, radius, radius)
        paint.drawText(1, 15, self.widgetName)
        paint.drawText(1, 195, "["+str(self.valueX)+","+str(self.valueY)+"]")
        paint.setBrush(Qt.red)
        paint.drawEllipse(center, 5, 5)
        paint.end()

    def moveCenter(self, x, y):
        self.rangeXMin = float(self.rangeXMin)
        self.rangeXMax = float(self.rangeXMax)
        self.rangeYMin = float(self.rangeYMin)
        self.rangeYMax = float(self.rangeYMax)
        self.precisionX = int(self.precisionX)
        self.precisionY = int(self.precisionY)

        if x > 2*self.centerX:
            x = 2*self.centerX
        if x < 0:
            x = 0
        if y > 2*self.centerY:
            y = 2*self.centerY
        if y < 0:
            y = 0

        self.currentX = x
        self.currentY = y
        self.valueX = np.around(x/(self.centerX*2) * (self.rangeXMax-self.rangeXMin)+self.rangeXMin, self.precisionX)
        self.valueY = -np.around(y/(self.centerY*2) * (self.rangeYMax-self.rangeYMin)+self.rangeYMin, self.precisionY)

        self.repaint()
        self.valuesChanged.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mousePressPos = event.pos()
        elif event.button() == Qt.RightButton:
            self._mousePressPos = event.globalPos()
            self._mouseMovePos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            newPos = event.pos()
            if self.rect().contains(newPos):
                self.moveCenter(newPos.x(), newPos.y())
        elif event.buttons() == Qt.RightButton:
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

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moveCenter(self.centerX, self.centerY)
        if self._mousePressPos is not None:
            moved = event.globalPos() - self._mousePressPos
            if moved.manhattanLength() > 0:
                event.ignore()
                return
            self.contextMenu.exec_(self.mapToGlobal(event.pos()))

    def getData(self):
        data = dict()

        data['widgetType'] = 'Joystick'
        data['name'] = self.widgetName
        data['moduleX'] = self.moduleX
        data['parameterX'] = self.parameterX
        data['moduleY'] = self.moduleY
        data['parameterY'] = self.parameterY
        data['rangeXMin'] = self.rangeXMin
        data['rangeYMin'] = self.rangeYMin
        data['rangeXMax'] = self.rangeXMax
        data['rangeYMax'] = self.rangeYMax
        data['precisionX'] = self.precisionX
        data['precisionY'] = self.precisionY
        data['shortcutXPlus'] = self.shortcutXPlus.key().toString()
        data['shortcutYPlus'] = self.shortcutYPlus.key().toString()
        data['shortcutXMinus'] = self.shortcutXMinus.key().toString()
        data['shortcutYMinus'] = self.shortcutYMinus.key().toString()

        return data

    def updateData(self):
        self.moveCenter(self.centerX, self.centerY)


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
