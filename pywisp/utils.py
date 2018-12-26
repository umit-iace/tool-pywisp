# -*- coding: utf-8 -*-
import logging
import numpy as np
import os
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout
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
    Logging handler hat formats log data for line display
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
    def __init__(self, name):
        self.name = name
        self.values = []
        self.time = []

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
        self.dataPoints = []
        self.plotWidget = None
        self.plotCurves = []
        self.interpolationPoints = 100
        self.settings = settings

    def addPlotCurve(self, dataPoint):
        """
        Adds a curve to the plot widget
        Args:
            dataPoint(DataPointBuffer): Data point which contains the data be added
        """
        self.dataPoints.append(dataPoint)

        self.settings.beginGroup('plot_colors')
        cKeys = self.settings.childKeys()
        colorIdxItem = len(self.plotCurves) % len(cKeys)
        colorItem = QColor(self.settings.value(cKeys[colorIdxItem]))
        self.settings.endGroup()

        self.plotCurves.append(self.plotWidget.plot(name=dataPoint.name, pen=mkPen(colorItem, width=2)))

    def setInterpolationPoints(self, interpolationPoints):
        self.interpolationPoints = int(interpolationPoints)

    def updatePlot(self):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        if self.plotWidget:
            for indx, curve in enumerate(self.plotCurves):
                datax = self.dataPoints[indx].time
                datay = self.dataPoints[indx].values
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
            del self.dataPoints[:]
            del self.plotCurves[:]


class CSVExporter(object):
    def __init__(self, dataPoints):
        self.dataPoints = dataPoints
        self.sep = ','

    def export(self, fileName):

        fd = open(fileName, 'w')
        data = []
        header = []

        for dataPoint in self.dataPoints:
            if dataPoint.time:
                header.append('Zeit')
                header.append(dataPoint.name)
                data.append(dataPoint.time)
                data.append(dataPoint.values)

        numColumns = len(header)
        if data:
            numRows = len(max(data, key=len))
        else:
            fd.close()
            return

        fd.write(self.sep.join(header) + '\n')

        for i in range(numRows):
            for j in range(numColumns):
                if i < len(data[j]):
                    fd.write(str(data[j][i]))
                else:
                    fd.write(str(np.nan))

                if j < numColumns:
                    fd.write(self.sep)

            fd.write('\n')
        fd.close()


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

        # nice widget for editing the date
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

        self.ipValue = kwargs.get("ip", 0)
        self.portValue = kwargs.get("prt", 0)

        ipRange = "(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])"  # Part of the regular expression
        # regular expression
        ipRegex = QRegExp("^" + ipRange + "\\." + ipRange + "\\." + ipRange + "\\." + ipRange + "$")
        ipValidator = QRegExpValidator(ipRegex, self)

        mainLayout = QVBoxLayout(self)

        self.ipData = QLineEdit(self)
        self.ipData.setText(str(self.ipValue))
        self.ipData.setValidator(ipValidator)

        mainLayout.addWidget(self.ipData)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

    def _getData(self):
        return self.ipData.text()

    @staticmethod
    def getData(**kwargs):
        dialog = DataTcpIpDialog(**kwargs)
        result = dialog.exec_()
        ipData = dialog._getData()

        return ipData, result == QDialog.Accepted
