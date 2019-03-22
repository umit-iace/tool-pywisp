# -*- coding: utf-8 -*-
import logging
import os

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QRegExp, QSize
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator, QDoubleValidator
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout, QFormLayout, \
    QLayout, QComboBox, QPushButton, QWidget
from pyqtgraph import mkPen

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

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            for indx, curve in enumerate(self.plotCurves):
                datax = self.dataPoints[curve.name()].time
                datay = self.dataPoints[curve.name()].values
                if datax:
                    if len(datax) < self.interpolationPoints:
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
        parent = kwargs.get('parent', None)
        super(DataIntDialog, self).__init__(parent)

        self.minValue = kwargs.get("min", 1)
        self.maxValue = kwargs.get("max", 1000)
        self.currentValue = kwargs.get("current", 0)

        mainLayout = QVBoxLayout(self)
        labelLayout = QHBoxLayout()

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

        mainLayout.addWidget(self.data)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

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
    def __init__(self, gui, edit=False, name='New', widgetType="PushButton", param=None, valueOn=None, valueOff=None, minSlider=0,
                 maxSlider=255, stepSlider=1, visible=True):
        super(QDialog, self).__init__(None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.widgetType = widgetType
        self.valueOn = valueOn
        self.valueOff = valueOff
        self.parameter = param
        self.name = name
        self.minSlider = minSlider
        self.maxSlider = maxSlider
        self.stepSlider = stepSlider
        self.gui = gui
        self.ok = False

        self.stepSliderText = None
        self.minSliderText = None
        self.maxSliderText = None
        self.valueOffText = None
        self.valueOnText = None
        self.valueText = None

        self.formLayout = QFormLayout()

        self.nameText = QLineEdit(name)
        self.formLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(["PushButton", "Switch", "Slider"])
        self.typeList.setCurrentText(widgetType)
        self.typeList.currentIndexChanged.connect(self.typeListchanged)
        self.typeList.setEnabled(not edit)
        self.formLayout.addRow(QLabel("Widget type"), self.typeList)

        self.paramList = QComboBox()
        for top in self.gui.exp.getExperiment():
            if not top == 'Name':
                for key in self.gui.exp.getExperiment()[top]:
                    self.paramList.addItem(key)
        if self.paramList.findText(self.parameter):
            self.paramList.setCurrentIndex(self.paramList.findText(self.parameter))
        self.formLayout.addRow(QLabel("Parameter of '{}'".format(self.gui.exp.getExperiment()['Name'])), self.paramList)

        self.settingsWidget = QWidget()
        self.settingsWidgetLayout = QFormLayout()
        self.settingsWidget.setLayout(self.settingsWidgetLayout)
        self.formLayout.addRow(self.settingsWidget)

        self.typeListchanged()

        self.formLayout.addRow(QLabel(' '))
        self.formLayout.addRow(QLabel(' '))

        self.btnOk = QPushButton("Ok", self)
        self.btnOk.clicked.connect(self.button_press)
        self.btnCancel = QPushButton("Cancel", self)
        self.btnCancel.clicked.connect(self.button_press)

        self.formLayout.addRow(self.btnOk, self.btnCancel)

        self.setLayout(self.formLayout)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle("Add Remote Widget ...")
        self.setWindowIcon(self.gui.icon)
        if visible:
            self.exec()

    def typeListchanged(self):
        for i in reversed(range(self.settingsWidgetLayout.count())):
            self.settingsWidgetLayout.itemAt(i).widget().deleteLater()

        if self.typeList.currentText() == "PushButton":
            self.valueText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value"), self.valueText)
            self.valueText.setValidator(QDoubleValidator())
            self.valueText.mousePressEvent = lambda event: self.valueText.selectAll()
        elif self.typeList.currentText() == "Switch":
            self.valueOnText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value for On"), self.valueOnText)
            self.valueOnText.setValidator(QDoubleValidator())
            self.valueOnText.mousePressEvent = lambda event: self.valueOnText.selectAll()
            self.valueOffText = QLineEdit(self.valueOff)
            self.settingsWidgetLayout.addRow(QLabel("Value for Off"), self.valueOffText)
            self.valueOffText.mousePressEvent = lambda event: self.valueOffText.selectAll()
            self.valueOffText.setValidator(QDoubleValidator())
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
            self.settingsWidgetLayout.addRow(QLabel("Stepsize"), self.stepSliderText)
            self.stepSliderText.setValidator(QDoubleValidator())
            self.stepSliderText.mousePressEvent = lambda event: self.stepSliderText.selectAll()

    def button_press(self):
        if self.sender() == self.btnOk:
            self.parameter = self.paramList.currentText()
            if not self.parameter:
                return
            self.name = self.nameText.text()
            if self.name == '':
                return

            if self.typeList.currentText() == "PushButton":
                self.valueOn = self.valueText.text()
                if self.valueOn == "":
                    return
            elif self.typeList.currentText() == "Switch":
                self.valueOn = self.valueOnText.text()
                self.valueOff = self.valueOffText.text()
                if self.valueOn == "" or self.valueOff == "":
                    return
            elif self.typeList.currentText() == "Slider":
                self.maxSlider = int(float(self.maxSliderText.text()))
                self.minSlider = int(float(self.minSliderText.text()))
                self.stepSlider = int(float(self.stepSliderText.text()))
                if self.maxSlider == "" or self.minSlider == "" or self.stepSlider == "":
                    return
            self.widgetType = self.typeList.currentText()
            self.ok = True
        self.close()


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

    def clearAll(self):
        while self.count() > 0:
            self.removeWidget(self.list[0])

    def removeWidget(self, widget):
        self.list.remove(widget)
        if widget.widgetType == "Slider":
            widget.label.deleteLater()
        widget.deleteLater()
