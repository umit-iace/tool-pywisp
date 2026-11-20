# -*- coding: utf-8 -*-
"""
The plots of the plot area and the data point tree that fills them, and the export of data points.
"""
import logging

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QActionGroup, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QCheckBox, QColorDialog, QDockWidget, QHBoxLayout, QInputDialog, QMenu, QSpinBox, \
    QTabBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..buffer import DataPointBuffer, ElementBuffer
from ..export import Exporter
from .common import TreeWidgetStyledItemDelegate
from .dialogs import ExportDialog
from .plotchart import PlotChart

__all__ = ["PlotManager"]

# the selection of the tree is drawn by TreeWidgetStyledItemDelegate
TREE_STYLE_SHEET = """
    QTreeView {
        selection-background-color: transparent;
    }
    QTreeView::item:selected { }
    QTreeView::item:hover { }
    QTreeView::item:hover:selected { }
"""

#: title of the tab that adds a plot
ADD_TAB = "+"
#: smallest width of a plot tab, more tabs than fit are scrolled
TAB_MIN_WIDTH = "6em"

#: interpolation between the points of a curve, the value is the pyqtgraph step mode
INTERPOLATIONS = {"Linear": None, "Zero-order hold": "left"}


class PlotDock(QDockWidget):
    """ dock of a plot, the plot is deleted when the dock is closed """
    closed = pyqtSignal()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()


class PlotManager(QWidget):
    """
    The data points of the experiment as a tree with checkboxes and the plots of the plot area.
    A checked data point is shown in the current plot, the plot that was shown or clicked last.
    """
    #: coordinates of the mouse in a plot
    coords = pyqtSignal(object)  # (x, y) or None
    #: the last plot has been closed
    allPlotsClosed = pyqtSignal()
    #: an export has ended, `True` if successful
    exportDone = pyqtSignal(bool)

    def __init__(self, plotArea, anchorDock, dataDock, settings, currentMeasurement, dataPointNames, plotConfig,
                 parent=None):
        """
        :param plotArea: main window the plot docks are added to
        :param anchorDock: dock of the plot area the first plot is tabbed with
        :param dataDock: dock of the plot area that shows this widget, the "+" tab is kept next to it
        :param settings: :class:`pywisp.settings.Settings` with the plot colors
        :param currentMeasurement: function returning the measurement shown in the gui or `None`
        :param dataPointNames: function returning the names of the data points of the experiment
        :param plotConfig: function returning the config of new plots
        """
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.plotArea = plotArea
        self.anchorDock = anchorDock
        self.dataDock = dataDock
        self._settings = settings
        self._currentMeasurement = currentMeasurement
        self._dataPointNames = dataPointNames
        self._plotConfig = plotConfig
        # charts and docks by the object name of the dock, which stays when a plot is renamed
        self.plotCharts = {}
        self.plotDocks = {}
        self._lastBuffers = {}
        self.currentPlot = None
        self.exporter = None
        # names shown in the data point tree: [(name, [element names])]
        self._shownDataPoints = None
        # set while the tree is synchronized with the current plot, the changes are not user input
        self._syncing = False

        # data points, array data points have a child item per element
        self.dataPointTree = QTreeWidget()
        self.dataPointTree.setItemDelegate(TreeWidgetStyledItemDelegate(self.dataPointTree))
        self.dataPointTree.setStyleSheet(TREE_STYLE_SHEET)
        self.dataPointTree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.dataPointTree.itemChanged.connect(self._onItemChanged)
        self.dataPointTree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dataPointTree.customContextMenuRequested.connect(
            lambda pos: self._showContextMenu(self.dataPointTree.itemAt(pos),
                                              self.dataPointTree.viewport().mapToGlobal(pos)))

        # moving window of the current plot, it is often changed during a run, the plot menu has it too
        self.movingWindowCheck = QCheckBox("Moving window")
        self.movingWindowCheck.toggled.connect(
            lambda on: self.currentPlot and self.plotCharts[self.currentPlot].setEnableMovingWindow(on))
        self.movingWindowSize = QSpinBox()
        self.movingWindowSize.setRange(1, 10000)
        self.movingWindowSize.setSuffix(" s")
        # applied on enter, focus loss or the arrows, not on every typed digit
        self.movingWindowSize.setKeyboardTracking(False)
        self.movingWindowSize.valueChanged.connect(
            lambda value: self.currentPlot and self.plotCharts[self.currentPlot].setMovingWindowWidth(value))
        windowRow = QHBoxLayout()
        windowRow.setContentsMargins(4, 2, 4, 2)
        windowRow.addWidget(self.movingWindowCheck)
        windowRow.addStretch()
        windowRow.addWidget(self.movingWindowSize)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.dataPointTree)
        layout.addLayout(windowRow)
        self.setLayout(layout)
        self._updateHeader()

        # the tab bars of the plot area are created by Qt when docks are tabbed, a double click renames a plot
        self.plotArea.installEventFilter(self)

        # a click on the "+" tab next to the data dock adds a plot, the tab itself is never shown
        self.addTabDock = QDockWidget(ADD_TAB, self.plotArea)
        self.addTabDock.setObjectName(ADD_TAB)
        self.addTabDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addTabDock.setWidget(QWidget())
        self.addTabDock.visibilityChanged.connect(lambda visible: visible and QTimer.singleShot(0, self._leaveAddTab))
        # the data dock may be moved or a view restored, the tab follows it
        self.dataDock.dockLocationChanged.connect(lambda _: QTimer.singleShot(0, self.placeAddTab))
        self.dataDock.topLevelChanged.connect(lambda _: QTimer.singleShot(0, self.placeAddTab))
        self.placeAddTab()

    def updateDataPoints(self, dataPointNames):
        """
        Shows the given data point names in the data point tree. The elements of array data
        points (the element buffers of the shown measurement) are added as children.
        The tree is only rebuilt if the names have changed.
        :param dataPointNames: list of data point names
        """
        if not dataPointNames:
            return
        buffers = self.currentBuffers()
        shown = [(name, [key for key, buf in buffers.items()
                         if isinstance(buf, ElementBuffer) and buf.parent is buffers.get(name)])
                 for name in dataPointNames]
        if shown == self._shownDataPoints:
            return
        self._shownDataPoints = shown

        # an array data point checked before its elements were known is shown by its elements, the curve of
        # the whole array cannot be drawn
        for chart in self.plotCharts.values():
            for name, elements in shown:
                if elements and name in chart.plotCurves:
                    chart.removeCurve(name)
                    for element in elements:
                        if element not in chart.plotCurves:
                            chart.addCurve(element, buffers[element])

        tree = self.dataPointTree
        expanded = {tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())
                    if tree.topLevelItem(i).isExpanded()}
        self._syncing = True
        tree.clear()
        for name, elements in shown:
            item = QTreeWidgetItem([name])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            tree.addTopLevelItem(item)
            for element in elements:
                child = QTreeWidgetItem([element])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.addChild(child)
            item.setExpanded(name in expanded)
        self._syncing = False
        self._syncTree()

    def _leafItems(self):
        """ the items of the tree that stand for a curve: data points and the elements of array data points """
        tree = self.dataPointTree
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            yield from [item.child(j) for j in range(item.childCount())] or [item]

    def _syncTree(self):
        """ checks the data points shown in the current plot and shows their colors """
        chart = self.plotCharts.get(self.currentPlot)
        self._syncing = True
        for item in self._leafItems():
            name = item.text(0)
            shown = chart is not None and name in chart.plotCurves
            item.setCheckState(0, Qt.CheckState.Checked if shown else Qt.CheckState.Unchecked)
            item.setIcon(0, _colorIcon(chart.curveColor(name)) if shown else QIcon())
        self._syncing = False

    def _onItemChanged(self, item, column):
        # a data point with elements is checked through them
        if self._syncing or item.childCount():
            return
        name = item.text(0)
        checked = item.checkState(0) == Qt.CheckState.Checked
        if self.currentPlot is None:
            if not checked:
                return
            self.addPlot()
        chart = self.plotCharts[self.currentPlot]
        if checked and name not in chart.plotCurves:
            # elements of an array data point may not have arrived yet, the curve gets their data later
            chart.addCurve(name, self.currentBuffers().get(name, DataPointBuffer()))
        elif not checked and name in chart.plotCurves:
            chart.removeCurve(name)
        self._syncTree()

    def _contextMenu(self, item):
        """ menu to change the color and the interpolation of the curve of the item in the current plot """
        name = item.text(0)
        chart = self.plotCharts.get(self.currentPlot)
        shown = chart is not None and name in chart.plotCurves
        menu = QMenu(self)
        actColor = menu.addAction("&Color ...")
        actColor.setEnabled(shown)
        actColor.triggered.connect(lambda: self._chooseColor(chart, name))
        interpolationMenu = menu.addMenu("&Interpolation")
        interpolationMenu.setEnabled(shown)
        group = QActionGroup(interpolationMenu)
        for label, mode in INTERPOLATIONS.items():
            act = interpolationMenu.addAction(label)
            act.setCheckable(True)
            act.setChecked(shown and chart.curveStepMode(name) == mode)
            act.triggered.connect(lambda _, mode=mode: chart.setCurveStepMode(name, mode))
            group.addAction(act)
        return menu

    def _showContextMenu(self, item, globalPos):
        # a data point with elements has no curve of its own
        if item is None or item.childCount():
            return
        self._contextMenu(item).exec(globalPos)

    def _chooseColor(self, chart, name):
        color = QColorDialog.getColor(chart.curveColor(name), self, f"Color of '{name}'")
        if color.isValid():
            chart.setCurveColor(name, color)
            self._syncTree()

    def _updateHeader(self):
        title = self.plotDocks[self.currentPlot].windowTitle() if self.currentPlot else "no plot"
        self.dataPointTree.setHeaderLabels([f"Shown in: {title}"])
        self._syncMovingWindow()

    def _syncMovingWindow(self):
        """ shows the moving window of the current plot """
        chart = self.plotCharts.get(self.currentPlot)
        for widget in (self.movingWindowCheck, self.movingWindowSize):
            widget.setEnabled(chart is not None)
            widget.blockSignals(True)
        if chart is not None:
            self.movingWindowCheck.setChecked(chart.movingWindowEnable)
            self.movingWindowSize.setValue(chart.movingWindowWidth)
            self.movingWindowSize.setEnabled(chart.movingWindowEnable)
        for widget in (self.movingWindowCheck, self.movingWindowSize):
            widget.blockSignals(False)

    def setCurrentPlot(self, name):
        """ makes the plot with the given object name the one the checked data points are shown in """
        if name == self.currentPlot or name not in self.plotCharts:
            return
        self.currentPlot = name
        self._updateHeader()
        self._syncTree()

    def addPlot(self):
        """
        Adds an empty plot to the plot area, at its saved place or as a tab next to the current plot,
        and makes it the current plot
        :return: object name of the plot
        """
        index = 0
        while f"plot_{index:03d}" in self.plotDocks:
            index += 1
        name = f"plot_{index:03d}"

        chart = PlotChart(name, self._plotConfig())
        chart.coords.connect(self.coords)
        chart.scene().sigMouseClicked.connect(lambda _: self.setCurrentPlot(name))
        dock = PlotDock(name, self.plotArea)
        dock.setObjectName(name)
        dock.setWidget(chart)
        dock.closed.connect(lambda: self._removePlot(name))
        dock.visibilityChanged.connect(lambda visible: visible and self.setCurrentPlot(name))
        # catch up on the updates skipped while the plot was hidden
        dock.visibilityChanged.connect(lambda visible: visible and chart.updateCurves(self._lastBuffers))
        self.plotCharts[name] = chart
        self.plotDocks[name] = dock
        chart.movingWindowChanged.connect(lambda: name == self.currentPlot and self._syncMovingWindow())

        if not self.plotArea.restoreDockWidget(dock):
            self.plotArea.tabifyDockWidget(self.plotDocks.get(self.currentPlot, self.anchorDock), dock)
        dock.show()
        dock.raise_()
        self.setCurrentPlot(name)
        return name

    def placeAddTab(self):
        """ tabs the "+" tab with the data dock, hidden while the data dock floats """
        if self.dataDock.isFloating():
            self.addTabDock.hide()
            return
        if self.dataDock not in self.plotArea.tabifiedDockWidgets(self.addTabDock):
            self.plotArea.tabifyDockWidget(self.dataDock, self.addTabDock)
            self.dataDock.raise_()
        self.addTabDock.show()

    def tabPlots(self):
        """ shows the plots as tabs next to the anchor dock, e.g. in the standard view, which has no plots """
        for dock in self.plotDocks.values():
            self.plotArea.tabifyDockWidget(self.anchorDock, dock)
        if self.currentPlot is not None:
            self.plotDocks[self.currentPlot].raise_()

    def _leaveAddTab(self):
        """ shows the data dock if Qt has made the "+" tab the shown one, e.g. after restoring a view """
        if not self.addTabDock.visibleRegion().isEmpty():
            self.dataDock.raise_()

    def _removePlot(self, name):
        dock = self.plotDocks.pop(name, None)
        if dock is None:
            return
        self.plotCharts.pop(name, None)
        self.plotArea.removeDockWidget(dock)
        # until it is deleted, the dock would take the saved place of a new plot with its name
        dock.setObjectName("")
        dock.deleteLater()
        if self.currentPlot == name:
            # the current plot is chosen again when another plot is shown or clicked
            self.currentPlot = next(reversed(self.plotDocks), None)
            self._updateHeader()
            self._syncTree()
        if not self.plotDocks:
            self.allPlotsClosed.emit()

    def renamePlot(self, name):
        """ asks for a new title of the plot with the given object name """
        dock = self.plotDocks[name]
        title, ok = QInputDialog.getText(self, "Rename plot", "Title of the plot:", text=dock.windowTitle())
        title = title.strip()
        if not (ok and title) or title == dock.windowTitle():
            return
        if title == ADD_TAB or title in {d.windowTitle() for d in self.plotDocks.values()}:
            self._logger.error(f"A plot with the title '{title}' exists")
            return
        dock.setWindowTitle(title)
        self.plotCharts[name].title = title
        self._updateHeader()

    def eventFilter(self, obj, event):
        if obj is self.plotArea and event.type() == QEvent.Type.ChildPolished \
                and isinstance(event.child(), QTabBar):
            tabBar = event.child()
            tabBar.installEventFilter(self)
            # many plots: tabs keep a readable width and the bar scrolls with arrows, like browser tabs
            tabBar.setUsesScrollButtons(True)
            tabBar.setStyleSheet(f"QTabBar::tab {{ min-width: {TAB_MIN_WIDTH}; }}")
        elif isinstance(obj, QTabBar) and event.type() == QEvent.Type.MouseButtonPress \
                and event.button() == Qt.MouseButton.LeftButton \
                and obj.tabText(obj.tabAt(event.position().toPoint())) == ADD_TAB:
            self.addPlot()
            return True
        elif isinstance(obj, QTabBar) and event.type() == QEvent.Type.MouseButtonDblClick:
            title = obj.tabText(obj.tabAt(event.position().toPoint()))
            for name, dock in self.plotDocks.items():
                if dock.windowTitle() == title:
                    self.renamePlot(name)
                    return True
        return super().eventFilter(obj, event)

    def showData(self, dataPointBuffers):
        """ shows the given data in all plots, e.g. of another measurement """
        self._lastBuffers = dataPointBuffers
        for chart in self.plotCharts.values():
            chart.cache.clear()
            chart.updateCurves(dataPointBuffers)

    def updateCharts(self, dataPointBuffers):
        """ adds new data to the visible plots, hidden ones (e.g. other tabs) catch up when they are shown """
        self._lastBuffers = dataPointBuffers
        for name, chart in self.plotCharts.items():
            if not self.plotDocks[name].visibleRegion().isEmpty():
                chart.updateCurves(dataPointBuffers)

    def closeAllPlots(self):
        """ closes all plots """
        for dock in list(self.plotDocks.values()):
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

    def exportDataPoints(self):
        """ asks for the data points to export with :class:`ExportDialog`, then for the file """
        if self.exporter is not None:
            self._logger.error("There is already an export job running")
            return

        measurement = self._currentMeasurement()
        if measurement is None:
            self._logger.error("Nothing to export!")
            return

        expLabels = ExportDialog.getDataPoints(self._shownDataPoints or [], self)
        if expLabels is None:
            return
        if not expLabels:
            self._logger.error("Can't export data set: no data set selected.")
            return
        dataPointBuffers = measurement.dataPointBuffers

        self._logger.info(f"Measurements selected for export are: {expLabels}")
        dataPoints = {lbl: dataPointBuffers[lbl] for lbl in expLabels if lbl in dataPointBuffers}

        # snapshots share the memory, but are not affected by data that is still being added
        expData = {lbl: buf.snapshot() for lbl, buf in dataPoints.items()}
        # copied, confirmed parameters may still be logged during the export
        parameters = {key: list(values) for key, values in measurement.parameters.items()}
        self.exporter = Exporter(dataPoints=expData, parameters=parameters)
        self.exporter.done.connect(self._onExportDone)
        self.exporter.runExport()

    def _onExportDone(self, success):
        self.exporter = None
        self.exportDone.emit(success)


def _colorIcon(color):
    pixmap = QPixmap(12, 12)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)
