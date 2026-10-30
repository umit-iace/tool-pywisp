# -*- coding: utf-8 -*-
"""
The content of the data dock: the data points of the experiment, the plots made of them and
their docks, and the export of data points.
"""
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, \
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from pyqtgraph.dockarea import Dock

from ..buffer import DataPointBuffer
from ..export import Exporter
from .common import TreeWidgetStyledItemDelegate
from .plotchart import PlotChart

__all__ = ["PlotManager"]

# the selection of the plot tree is drawn by TreeWidgetStyledItemDelegate
TREE_STYLE_SHEET = """
    QTreeView {
        selection-background-color: transparent;
    }
    QTreeView::item:selected { }
    QTreeView::item:hover { }
    QTreeView::item:hover:selected { }
"""


class PlotManager(QWidget):
    """
    Lists the data points of the experiment and the plots made of them. Every plot is shown
    in a dock of the dock area, it shows the data of the current measurement.
    """
    #: coordinates of the mouse in a plot
    coords = pyqtSignal(str)
    #: the last plot dock has been closed
    allPlotsClosed = pyqtSignal()
    #: an export has ended, `True` if successful
    exportDone = pyqtSignal(bool)

    def __init__(self, area, anchorDock, settings, currentMeasurement, dataPointNames, plotConfig, parent=None):
        """
        :param area: dock area the plot docks are added to
        :param anchorDock: the first plot dock is placed below this dock
        :param settings: :class:`pywisp.settings.Settings` with the plot colors
        :param currentMeasurement: function returning the measurement shown in the gui or `None`
        :param dataPointNames: function returning the names of the data points of the experiment
        :param plotConfig: function returning the config of new plots
        """
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.area = area
        self.anchorDock = anchorDock
        self._settings = settings
        self._currentMeasurement = currentMeasurement
        self._dataPointNames = dataPointNames
        self._plotConfig = plotConfig
        # the docks of the area that are not plots, their names cannot be used for plots
        self.nonPlottingDocks = list(self.area.findAll()[1].keys())
        self.plotCharts = {}
        self.exporter = None

        layout = QHBoxLayout()

        self.dataPointListWidget = QListWidget()
        self.dataPointListWidget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.dataPointListWidget)

        buttonsWidget = QWidget()
        buttonsLayout = QVBoxLayout()
        buttonsLayout.addStretch()
        buttonsLayout.setSpacing(5)
        self.dataPointRightButton = QPushButton(chr(0x226b), self)
        self.dataPointRightButton.setToolTip(
            "Add the selected data set from the left to the selected plot "
            "on the right.")
        self.dataPointRightButton.clicked.connect(self.addDataPointToTree)
        dataPointLabel = QLabel('DataPoint', self)
        dataPointLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttonsLayout.addWidget(dataPointLabel)
        buttonsLayout.addWidget(self.dataPointRightButton)
        self.dataPointLeftButton = QPushButton(chr(0x03A7), self)
        self.dataPointLeftButton.setToolTip(
            "Remove the selected data set from the plot on the right."
        )
        self.dataPointLeftButton.clicked.connect(self.removeDataPointFromTree)
        buttonsLayout.addWidget(self.dataPointLeftButton)
        self.dataPointExportButton = QPushButton(chr(0x25BC), self)
        self.dataPointExportButton.setToolTip(
            "Export the selected data set from the left to a csv or png file."
        )
        self.dataPointExportButton.clicked.connect(self.exportDataPointFromTree)
        buttonsLayout.addWidget(self.dataPointExportButton)
        self.dataPointPlotAddButton = QPushButton("+", self)
        self.dataPointPlotAddButton.setToolTip(
            "Create a new plot window."
        )
        self.dataPointPlotAddButton.clicked.connect(lambda: self.addPlotTreeItem())
        plotLabel = QLabel('Plots', self)
        plotLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttonsLayout.addWidget(plotLabel)
        buttonsLayout.addWidget(self.dataPointPlotAddButton)
        self.dataPointPlotRemoveButton = QPushButton("-", self)
        self.dataPointPlotRemoveButton.setToolTip(
            "Delete the selected plot window."
        )
        self.dataPointPlotRemoveButton.clicked.connect(self.removeSelectedPlotTreeItems)
        buttonsLayout.addWidget(self.dataPointPlotRemoveButton)
        buttonsWidget.setLayout(buttonsLayout)
        layout.addWidget(buttonsWidget)

        self.dataPointTreeWidget = QTreeWidget()
        self.dataPointTreeWidget.setItemDelegate(TreeWidgetStyledItemDelegate(self.dataPointTreeWidget))
        self.dataPointTreeWidget.setStyleSheet(TREE_STYLE_SHEET)
        self.dataPointTreeWidget.setHeaderLabels(["PlotTitle", "DataPoint"])
        self.dataPointTreeWidget.itemDoubleClicked.connect(self.plotVectorClicked)
        self.dataPointTreeWidget.setExpandsOnDoubleClick(False)
        layout.addWidget(self.dataPointTreeWidget)

        self.setLayout(layout)

    def updateDataPoints(self, dataPointNames):
        """
        Clears and adds all given data point names to list widget
        :param dataPointNames: list of data point names
        """
        if dataPointNames:
            self.dataPointListWidget.clear()
            self.dataPointListWidget.addItems(dataPointNames)

    def showData(self, dataPointBuffers):
        """ shows the given data in all plots, e.g. of another measurement """
        for i in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.updatePlot(self.dataPointTreeWidget.topLevelItem(i), dataPointBuffers)

    def updateCharts(self, dataPointBuffers):
        """ adds new data to all plots """
        for chart in self.plotCharts.values():
            chart.updateCurves(dataPointBuffers)

    def closeAllPlots(self):
        """ closes all plot docks """
        self.plotCharts.clear()
        for dock in self.findAllPlotDocks():
            dock.close()

    def waitForExport(self):
        if self.exporter is not None:
            self._logger.warning("Export in progress, waiting!")
            self.exporter.wait()

    def currentBuffers(self):
        """ the buffers of the shown measurement, empty buffers if there is none """
        measurement = self._currentMeasurement()
        if measurement is None:
            return {name: DataPointBuffer() for name in self._dataPointNames()}
        return measurement.dataPointBuffers

    def addPlotTreeItem(self, default=False):
        existingNames = {self.dataPointTreeWidget.topLevelItem(index).text(0)
                         for index in range(self.dataPointTreeWidget.topLevelItemCount())}
        index = 0
        while f"plot_{index:03d}" in existingNames:
            index += 1
        text = f"plot_{index:03d}"
        if not default:
            name, ok = QInputDialog.getText(self,
                                            "Select a plot title",
                                            "Name of the new plot:",
                                            text=text)
            if not (ok and name):
                return
        else:
            name = text

        similarItems = self.dataPointTreeWidget.findItems(name, Qt.MatchFlag.MatchExactly)
        if similarItems:
            self._logger.error(f"Name '{name}' exists.")
            return

        topLevelItem = QTreeWidgetItem()
        topLevelItem.setText(0, name)
        self.dataPointTreeWidget.addTopLevelItem(topLevelItem)
        topLevelItem.setExpanded(True)

        for index in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.dataPointTreeWidget.topLevelItem(index).setSelected(False)
            for childIndex in range(self.dataPointTreeWidget.topLevelItem(index).childCount()):
                self.dataPointTreeWidget.topLevelItem(index).child(childIndex).setSelected(False)
        topLevelItem.setSelected(True)

    def removeSelectedPlotTreeItems(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
            self._logger.error("Cannot delete plot: No plot selected.")
            return

        for item in items:
            self.removePlotTreeItem(item)

    def removePlotTreeItem(self, item):
        # get the  top item
        while item.parent():
            item = item.parent()

        text = "The labeled plot '" + item.text(0) + "' will be deleted!"
        buttonReply = QMessageBox.warning(self, "Plot delete", text,
                                          QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if buttonReply == QMessageBox.StandardButton.Ok:
            openDocks = [dock.title() for dock in self.findAllPlotDocks()]
            if item.text(0) in openDocks:
                self.area.docks[item.text(0)].close()

            self.dataPointTreeWidget.takeTopLevelItem(self.dataPointTreeWidget.indexOfTopLevelItem(item))

    def addDataPointToTree(self):
        if not self.dataPointListWidget.selectedIndexes():
            self._logger.error("Cannot add datapoint: No datapoint selected.")
            return

        toplevelItems = self.dataPointTreeWidget.selectedItems()
        if not toplevelItems:
            if self.dataPointTreeWidget.topLevelItemCount() < 2:
                if self.dataPointTreeWidget.topLevelItemCount() < 1:
                    self.addPlotTreeItem(default=True)
                toplevelItem = self.dataPointTreeWidget.topLevelItem(0)
            else:
                self._logger.error("Cannot add dataset: No dataset selected.")
                return
        else:
            toplevelItem = toplevelItems[0]

        while toplevelItem.parent():
            toplevelItem = toplevelItem.parent()

        topLevelItemList = []
        for i in range(toplevelItem.childCount()):
            topLevelItemList.append(toplevelItem.child(i).text(1))

        for dataPoint in self.dataPointListWidget.selectedItems():
            if dataPoint.text() not in topLevelItemList:
                child = QTreeWidgetItem()
                child.setText(1, dataPoint.text())
                toplevelItem.addChild(child)

        for i in range(toplevelItem.childCount()):
            toplevelItem.child(i).setBackground(0, self._settings.color(i))

        self.updatePlotChart(toplevelItem)

    def exportDataPointFromTree(self):
        if self.exporter is not None:
            self._logger.error("There is already an export job running")
            return

        if not self.dataPointListWidget.selectedIndexes():
            self._logger.error("Can't export data set: no data set selected.")
            return

        measurement = self._currentMeasurement()
        if measurement is None:
            self._logger.error("Nothing to export!")
            return
        dataPointBuffers = measurement.dataPointBuffers

        expLabels = [item.text()
                     for item in self.dataPointListWidget.selectedItems()]
        self._logger.info(f"Measurements selected for export are: {expLabels}")
        dataPoints = {lbl: dataPointBuffers[lbl] for lbl in expLabels}

        # snapshots share the memory, but are not affected by data that is still being added
        expData = {lbl: buf.snapshot() for lbl, buf in dataPoints.items()}
        self.exporter = Exporter(dataPoints=expData)
        self.exporter.done.connect(self._onExportDone)
        self.exporter.runExport()

    def _onExportDone(self, success):
        self.exporter = None
        self.exportDone.emit(success)

    def removeDataPointFromTree(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
            self._logger.error("Cannot delete dataset: No dataset selected.")
            return

        toplevelItem = items[0]
        while toplevelItem.parent():
            toplevelItem = toplevelItem.parent()

        toplevelItem.takeChild(toplevelItem.indexOfChild(self.dataPointTreeWidget.selectedItems()[0]))

        for i in range(toplevelItem.childCount()):
            toplevelItem.child(i).setBackground(0, self._settings.color(i))

        self.updatePlotChart(toplevelItem)

    def _reservedTitle(self, title):
        if title in self.nonPlottingDocks:
            self._logger.error(f"Title '{title}' not allowed for a plot window since "
                               "it would shadow one of the reserved names")
            return True
        return False

    def updatePlotChart(self, item):
        title = item.text(0)

        measurement = self._currentMeasurement()
        if measurement is None:
            self._logger.warning("No Measurement to plot!")
            return
        dataPointBuffers = measurement.dataPointBuffers

        # check if a top level item has been clicked
        if not item.parent():
            if self._reservedTitle(title):
                return

            # check if plot has already been opened
            openDocks = [dock.title() for dock in self.findAllPlotDocks()]
            if title in openDocks:
                chart = self.plotCharts[title]

                # check if all items are present as curves
                reqLabels = []
                for idx in range(item.childCount()):
                    curveLabel = item.child(idx).text(1)
                    reqLabels.append(curveLabel)
                    if curveLabel not in chart.plotCurves.keys():
                        chart.addCurve(curveLabel, dataPointBuffers[curveLabel])

                # clear all curves that are no longer required by items
                for lbl in [lbl for lbl in chart.plotCurves.keys() if lbl not in reqLabels]:
                    chart.removeCurve(lbl)

    def plotVectorClicked(self, item):
        # ignore non-top level items
        if item.parent():
            return

        title = item.text(0)
        if self._reservedTitle(title):
            return

        # check if plot has already been opened
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        if title in openDocks:
            dock = self.area.docks.get(title)
            if dock is not None:
                dock.raiseDock()
        else:
            self.plotDataVector(item)

    def updatePlot(self, item, dataPointBuffers):
        title = item.text(0)
        if title in self.plotCharts:
            self.plotCharts[title].cache.clear()
            self.plotCharts[title].updateCurves(dataPointBuffers)

    def plotDataVector(self, item):
        title = str(item.text(0))
        if title in self.plotCharts.keys():
            self._logger.error(f"Plot chart name '{title}' is already taken.")
            return

        # create chart
        chart = PlotChart(title, self._plotConfig())
        chart.coords.connect(self.coords)
        self.plotCharts[title] = chart

        # add curves
        dataPointBuffers = self.currentBuffers()
        for idx in range(item.childCount()):
            for key, value in dataPointBuffers.items():
                if key == item.child(idx).text(1):
                    chart.addCurve(key, value)

        # create dock container and add it to dock area
        dock = Dock(title, closable=True)
        dock.addWidget(chart)
        dock.sigClosed.connect(self.closedDock)

        plotWidgets = self.findAllPlotDocks()
        if plotWidgets:
            self.area.addDock(dock, "above", plotWidgets[0])
        else:
            self.area.addDock(dock, "bottom", self.anchorDock)

    def closedDock(self):
        """
        Gets called when a dock was closed, if it was a plot dock remove the corresponding PlotChart object
        form the list
        """
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        for lbl in [lbl for lbl in self.plotCharts.keys() if lbl not in openDocks]:
            self.plotCharts.pop(lbl, None)

        if len(openDocks) == 0:
            self.allPlotsClosed.emit()

    def findAllPlotDocks(self):
        """
        Finds all docks with plots inside
        :return: list of docks with plots
        """
        return [dock for title, dock in self.area.findAll()[1].items() if title not in self.nonPlottingDocks]
