# -*- coding: utf-8 -*-
import os
import serial.tools.list_ports
import yaml
from PyQt5.QtCore import QSize, Qt, pyqtSlot, pyqtSignal, QModelIndex, QRectF, QTimer, QSettings
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from copy import deepcopy
from operator import itemgetter
from pyqtgraph import PlotWidget, exporters, TextItem, mkBrush
from pyqtgraph.dockarea import *
from queue import Queue

from .connection import SerialConnection
from .experiments import ExperimentInteractor, ExperimentView, PropertyItem
from .registry import *
from .utils import get_resource, PlainTextLogger, DataPointBuffer, PlotChart, CSVExporter
from .visualization import MplVisualizer
from pywisp import TABLEAU_COLORS


class MainGui(QMainWindow):
    runExp = pyqtSignal()
    stopExp = pyqtSignal()

    def __init__(self, moduleList, parent=None):
        super(MainGui, self).__init__(parent)
        self.connection = None
        self.inputQueue = Queue()
        self.outputQueue = Queue()
        self.port = ''

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateData)

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

        # load settings
        self._settings = QSettings()
        self._readSettings()

        # create experiment backend
        self.exp = ExperimentInteractor(moduleList, self.inputQueue, self)
        self.runExp.connect(self.exp.runExperiment)
        self.stopExp.connect(self.exp.stopExperiment)

        # window properties
        icon_size = QSize(25, 25)
        res_path = get_resource("icon.png")
        icon = QIcon(res_path)
        self.setWindowIcon(icon)
        self.resize(1000, 700)
        self.setWindowTitle('Visualisierung')

        # status bar
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self.statusbarLabel = QLabel("Nicht Verbunden")
        self.statusBar.addPermanentWidget(self.statusbarLabel, 1)
        self.coordLabel = QLabel("x=0.0 y=0.0")
        self.statusBar.addPermanentWidget(self.coordLabel)

        # the docking area allows to rearrange the user interface at runtime
        self.area = DockArea()
        self.setCentralWidget(self.area)

        # create docks
        self.experimentDock = Dock("Experimente")
        self.lastMeasDock = Dock("Vorherige Messungen")
        self.propertyDock = Dock("Parameter")
        self.logDock = Dock("Log")
        self.dataDock = Dock("Daten")
        self.animationDock = Dock("Animation")

        # arrange docks
        self.area.addDock(self.animationDock, "right")
        self.area.addDock(self.lastMeasDock, "left", self.animationDock)
        self.area.addDock(self.propertyDock, "bottom", self.lastMeasDock)
        self.area.addDock(self.dataDock, "bottom", self.propertyDock)
        self.area.addDock(self.logDock, "bottom", self.dataDock)
        self.area.addDock(self.experimentDock, "left", self.lastMeasDock)
        self.nonPlottingDocks = list(self.area.findAll()[1].keys())

        self.standardDockState = self.area.saveState()

        # property dock
        self.targetView = ExperimentView(self)
        self.targetView.setModel(self.exp.targetModel)
        self.targetView.expanded.connect(self.targetViewChanged)
        self.targetView.collapsed.connect(self.targetViewChanged)

        self.propertyDock.addWidget(self.targetView)

        # animation dock
        self.animationWidget = QWidget()
        availableVis = getRegisteredVisualizers()
        self._logger.info("Visualisierung gefunden: {}".format([name for cls, name in availableVis]))
        if availableVis:
            # instantiate the first visualizer
            self._logger.info("loading visualizer '{}'".format(availableVis[0][1]))
            self.animationLayout = QVBoxLayout()
            if issubclass(availableVis[0][0], MplVisualizer):
                self.animationWidget = QWidget()
                self.visualizer = availableVis[0][0](self.animationWidget,
                                                     self.animationLayout)
                self.animationDock.addWidget(self.animationWidget)
        else:
            self.visualizer = None
        self.animationDock.addWidget(self.animationWidget)

        # experiment dock
        self.experimentList = QListWidget(self)
        self.experimentList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.experimentDock.addWidget(self.experimentList)
        self.experimentList.itemDoubleClicked.connect(self.experimentDclicked)
        self._experiments = []
        self._experimentsFileName = ""
        self._currentExperimentIndex = None
        self._currentExperimentName = None
        self._experimentStartTime = 0

        self.actLadeExperiments = QAction(self)
        self.actLadeExperiments.setText("&Lade Experimente aus Datei")
        self.actLadeExperiments.setIcon(QIcon(get_resource("load.png")))
        self.actLadeExperiments.setDisabled(False)
        self.actLadeExperiments.setShortcut(QKeySequence("Ctrl+L"))
        self.actLadeExperiments.triggered.connect(self.loadExpDialog)

        self.actStartExperiment = QAction(self)
        self.actStartExperiment.setDisabled(True)
        self.actStartExperiment.setText("&Starte Experiment")
        self.actStartExperiment.setIcon(QIcon(get_resource("play.png")))
        self.actStartExperiment.setShortcut(QKeySequence("F5"))
        self.actStartExperiment.triggered.connect(self.startExperiment)

        self.actStopExperiment = QAction(self)
        self.actStopExperiment.setText("&Stoppe Experiment")
        self.actStopExperiment.setDisabled(True)
        self.actStopExperiment.setIcon(QIcon(get_resource("stop.png")))
        self.actStopExperiment.setShortcut(QKeySequence("F6"))
        self.actStopExperiment.triggered.connect(self.stopExperiment)

        # lastmeas dock
        self.lastMeasList = QListWidget(self)
        self.lastMeasDock.addWidget(self.lastMeasList)
        self.lastMeasList.itemDoubleClicked.connect(self.loadLastMeas)
        self.exp.expFinished.connect(self.saveLastMeas)
        self.lastMeasurements = []

        # log dock
        self.logBox = QPlainTextEdit(self)
        self.logBox.setReadOnly(True)
        self.logDock.addWidget(self.logBox)

        # daten dock
        self.dataWidget = QWidget()
        self.dataLayout = QHBoxLayout()

        self.dataPointListWidget = QListWidget()
        self.dataPointListLayout = QVBoxLayout()
        dataPointNames = self.exp.getDataPoints()
        self.plotCharts = []
        if dataPointNames:
            self.dataPointBuffers = [DataPointBuffer(data) for data in dataPointNames]
            self.dataPointListWidget.addItems(dataPointNames)
        self.dataPointListWidget.setLayout(self.dataPointListLayout)
        self.dataPointListWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.dataLayout.addWidget(self.dataPointListWidget)

        self.dataPointManipulationWidget = QWidget()
        self.dataPointManipulationLayout = QVBoxLayout()
        self.dataPointManipulationLayout.addStretch(0)
        self.dataPointRightButtonWidget = QWidget()
        self.dataPointRightButtonLayout = QVBoxLayout()
        self.dataPointRightButton = QPushButton(chr(0x226b), self)
        self.dataPointRightButton.setToolTip(
            "Add the selected data set from the left to the selected plot "
            "on the right.")
        self.dataPointRightButton.clicked.connect(self.addDatapointToTree)
        self.dataPointLabel = QLabel('Datenpunkt', self)
        self.dataPointLabel.setAlignment(Qt.AlignCenter)
        self.dataPointManipulationLayout.addWidget(self.dataPointLabel)
        self.dataPointManipulationLayout.addWidget(self.dataPointRightButton)
        self.dataPointLeftButtonWidget = QWidget()
        self.dataPointLeftButtonLayout = QVBoxLayout()
        self.dataPointLeftButton = QPushButton(chr(0x226a), self)
        self.dataPointLeftButton.setToolTip(
            "Remove the selected data set from the plot on the right."
        )
        self.dataPointLeftButton.clicked.connect(self.removeDatapointFromTree)
        self.dataPointManipulationLayout.addWidget(self.dataPointLeftButton)
        self.dataPointManipulationLayout.addStretch(0)
        self.dataPointPlotAddButtonWidget = QWidget()
        self.dataPointPlotAddButtonLayout = QVBoxLayout()
        self.dataPointPlotAddButton = QPushButton("+", self)
        self.dataPointPlotAddButton.setToolTip(
            "Create a new plot window."
        )
        self.dataPointPlotAddButton.clicked.connect(self.addPlotTreeItem)
        self.plotLabel = QLabel('Plots', self)
        self.plotLabel.setAlignment(Qt.AlignCenter)
        self.dataPointManipulationLayout.addWidget(self.plotLabel)
        self.dataPointManipulationLayout.addWidget(self.dataPointPlotAddButton)
        self.dataPointPlotRemoveButtonWidget = QWidget()
        self.dataPointPlotRemoveButtonLayout = QVBoxLayout()
        self.dataPointPlotRemoveButton = QPushButton("-", self)
        self.dataPointPlotRemoveButton.setToolTip(
            "Delete the selected plot window."
        )
        self.dataPointPlotRemoveButton.clicked.connect(self.removeSelectedPlotTreeItems)
        self.dataPointManipulationLayout.addWidget(self.dataPointPlotRemoveButton)
        self.dataPointManipulationWidget.setLayout(self.dataPointManipulationLayout)
        self.dataLayout.addWidget(self.dataPointManipulationWidget)

        self.dataPointTreeWidget = QTreeWidget()
        self.dataPointTreeWidget.setHeaderLabels(["Plottitel", "Datenpunkte"])
        self.dataPointTreeWidget.itemDoubleClicked.connect(self.plotVectorClicked)
        self.dataPointTreeWidget.setExpandsOnDoubleClick(0)
        self.dataPointTreeLayout = QVBoxLayout()

        self.dataPointTreeWidget.setLayout(self.dataPointTreeLayout)
        self.dataLayout.addWidget(self.dataPointTreeWidget)

        self.dataWidget.setLayout(self.dataLayout)
        self.dataDock.addWidget(self.dataWidget)

        # init logger for logging box
        self.textLogger = PlainTextLogger()
        self.textLogger.set_target_cb(self.logBox.appendPlainText)
        logging.getLogger().addHandler(self.textLogger)
        self._logger.info('Laborvisualisierung')

        # menu bar
        dateiMenu = self.menuBar().addMenu("&Datei")
        dateiMenu.addAction(self.actLadeExperiments)
        dateiMenu.addAction("&Quit", self.close, QKeySequence(Qt.CTRL + Qt.Key_W))

        # view
        self.viewMenu = self.menuBar().addMenu('&Ansicht')
        self.actLoadStandardState = QAction('&Lade Standarddockansicht')
        self.viewMenu.addAction(self.actLoadStandardState)
        self.actLoadStandardState.triggered.connect(self.loadStandardDockState)
        self.actShowCoords = QAction("&Zeige Koordinaten", self)
        self.actShowCoords.setCheckable(True)
        self.actShowCoords.setChecked(
            self._settings.value("view/show_coordinates") == "True"
        )
        self.viewMenu.addAction(self.actShowCoords)
        self.actShowCoords.changed.connect(self.updateShowCoordsSetting)

        # experiment
        self.expMenu = self.menuBar().addMenu('&Experiment')

        self.comMenu = self.expMenu.addMenu('&Verbindungsport')
        self.comMenu.aboutToShow.connect(self.getComPorts)
        self.expMenu.addSeparator()
        self.actConnect = QAction('&Versuchsaufbau verbinden')
        self.actConnect.setIcon(QIcon(get_resource("connected.png")))
        self.actConnect.setShortcut(QKeySequence("F9"))
        self.expMenu.addAction(self.actConnect)
        self.actConnect.triggered.connect(self.connect)

        self.actDisconnect = QAction('&Versuchsaufbau trennen')
        self.actDisconnect.setEnabled(False)
        self.actDisconnect.setIcon(QIcon(get_resource("disconnected.png")))
        self.actDisconnect.setShortcut(QKeySequence("F10"))
        self.expMenu.addAction(self.actDisconnect)
        self.actDisconnect.triggered.connect(self.disconnect)

        # toolbar
        self.toolbarExp = QToolBar("Experiment")
        self.toolbarExp.setContextMenuPolicy(Qt.PreventContextMenu)
        self.toolbarExp.setMovable(False)
        self.toolbarExp.setIconSize(icon_size)
        self.addToolBar(self.toolbarExp)
        self.toolbarExp.addAction(self.actLadeExperiments)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actConnect)
        self.toolbarExp.addAction(self.actDisconnect)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actStartExperiment)
        self.toolbarExp.addAction(self.actStopExperiment)

        self.setDefaultComPort()

    def _readSettings(self):
        # add default settings if none are present
        if not self._settings.contains("view/show_coordinates"):
            self._settings.setValue("view/show_coordinates", "True")

    def _writeSettings(self):
        """ Store the application state. """
        pass

    def updateCoordInfo(self, pos, widget, coordItem):
        mouseCoords = widget.getPlotItem().vb.mapSceneToView(pos)
        coordItem.setPos(mouseCoords.x(), mouseCoords.y())
        coord_text = "x={:.3e} y={:.3e}".format(mouseCoords.x(),
                                                mouseCoords.y())
        self.coordLabel.setText(coord_text)

        show_info = self._settings.value("view/show_coordinates") == "True"
        if widget.sceneBoundingRect().contains(pos) and show_info:
            coordItem.setText(coord_text.replace(" ", "\n"))
            coordItem.show()
        else:
            coordItem.hide()

    # event functions
    def setDefaultComPort(self):
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]

            if len(arduinoPorts) != 0:
                self.port = arduinoPorts[0]
            else:
                self._logger.warning("Can't set comport for arduino automatically! Set the port manually!")
        else:
            self._logger.warning("No ComPorts avaiable, connect device!")

    def getComPorts(self):
        def setPort(port):
            def fn():
                self.port = port

            return fn

        self.comMenu.clear()
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            if self.port == '':
                arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]
                if len(arduinoPorts) != 0:
                    self.port = arduinoPorts[0]
            for p in comPorts:
                portAction = QAction(p.device, self)
                portAction.setCheckable(True)
                portAction.setChecked(True if p.device in self.port else False)
                portAction.triggered.connect(setPort(p.device))
                self.comMenu.addAction(portAction)
        else:
            noAction = QAction("(None)", self)
            noAction.setEnabled(False)
            self.comMenu.addAction(noAction)

    def addPlotTreeItem(self, default=False):
        text = "plot_{:03d}".format(self.dataPointTreeWidget.topLevelItemCount())
        if not default:
            name, ok = QInputDialog.getText(self,
                                            "PlotTitle",
                                            "PlotTitle:",
                                            text=text)
            if not (ok and name):
                return
        else:
            name = text

        similarItems = self.dataPointTreeWidget.findItems(name, Qt.MatchExactly)
        if similarItems:
            self._logger.error("Name '{}' existiert bereits".format(name))
            return

        toplevelitem = QTreeWidgetItem()
        toplevelitem.setText(0, name)
        self.dataPointTreeWidget.addTopLevelItem(toplevelitem)
        toplevelitem.setExpanded(1)

    def removeSelectedPlotTreeItems(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
            self._logger.error("Kann Plot nicht löschen: Kein Plot ausgewählt.")
            return

        for item in items:
            self.removePlotTreeItem(item)

    def removePlotTreeItem(self, item):
        # get the  top item
        while item.parent():
            item = item.parent()

        text = "Der markierte Plot '" + item.text(0) + "' wird gelöscht!"
        buttonReply = QMessageBox.warning(self, "Plot delete", text, QMessageBox.Ok | QMessageBox.Cancel)
        if buttonReply == QMessageBox.Ok:
            openDocks = [dock.title() for dock in self.findAllPlotDocks()]
            if item.text(0) in openDocks:
                self.area.docks[item.text(0)].close()

            self.dataPointTreeWidget.takeTopLevelItem(self.dataPointTreeWidget.indexOfTopLevelItem(item))

    def addDatapointToTree(self):
        if not self.dataPointListWidget.selectedIndexes():
            self._logger.error("Kann Datenpunkt nicht hinzufügen: Keine Datenpunkte ausgewählt.")
            return

        dataPoints = []
        for item in self.dataPointListWidget.selectedItems():
            for data in self.dataPointBuffers:
                if data.name == item.text():
                    dataPoints.append(data)
                    continue

        toplevelItems = self.dataPointTreeWidget.selectedItems()
        if not toplevelItems:
            if self.dataPointTreeWidget.topLevelItemCount() < 2:
                if self.dataPointTreeWidget.topLevelItemCount() < 1:
                    self.addPlotTreeItem(default=True)
                toplevelItem = self.dataPointTreeWidget.topLevelItem(0)
            else:
                self._logger.error("Kann Datenset nicht hinzufügen: Kein Datenset ausgewählt.")
                return
        else:
            toplevelItem = toplevelItems[0]

        while toplevelItem.parent():
            toplevelItem = toplevelItem.parent()

        topLevelItemList = []
        for i in range(toplevelItem.childCount()):
            topLevelItemList.append(toplevelItem.child(i).text(1))

        for idx, dataPoint in enumerate(dataPoints):
            if dataPoint.name not in topLevelItemList:
                child = QTreeWidgetItem()
                child.setText(1, dataPoint.name)

                toplevelItem.addChild(child)

        for i in range(toplevelItem.childCount()):
            colorIdxItem = i % len(TABLEAU_COLORS)
            colorItem = QColor(TABLEAU_COLORS[colorIdxItem][1])
            toplevelItem.child(i).setBackground(0, colorItem)

        self.plots(toplevelItem)

    def removeDatapointFromTree(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
            self._logger.error("Kann Datenset nicht löschen: Kein Datenset ausgewählt")
            return

        toplevelitem = items[0]
        while toplevelitem.parent():
            toplevelitem = toplevelitem.parent()

        toplevelitem.takeChild(toplevelitem.indexOfChild(self.dataPointTreeWidget.selectedItems()[0]))
        self.plots(toplevelitem)

    def plots(self, item):
        title = item.text(0)

        # check if a top level item has been clicked
        if not item.parent():
            if title in self.nonPlottingDocks:
                self._logger.error("Title '{}' not allowed for a plot window since"
                                   "it would shadow on of the reserved "
                                   "names".format(title))
                return

            # check if plot has already been opened
            openDocks = [dock.title() for dock in self.findAllPlotDocks()]
            if title in openDocks:
                self.updatePlot(item)

    def plotVectorClicked(self, item):

        # check if a top level item has been clicked
        if item.parent():
            return

        title = item.text(0)
        if title in self.nonPlottingDocks:
            self._logger.error("Title '{}' not allowed for a plot window since"
                               "it would shadow on of the reserved "
                               "names".format(title))
            return

        # check if plot has already been opened
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        if title in openDocks:
            self.updatePlot(item)
            try:
                self.area.docks[title].raiseDock()
            except:
                pass
        else:
            self.plotDataVector(item)

    def updatePlot(self, item):
        title = item.text(0)

        # get the new datapoints
        newDataPoints = []
        for indx in range(item.childCount()):
            for dataPoint in self.dataPointBuffers:
                if dataPoint.name == item.child(indx).text(1):
                    newDataPoints.append(dataPoint)

        # set the new datapoints
        for chart in self.plotCharts:
            if chart.title == title:
                chart.clear()
                for dataPoint in newDataPoints:
                    chart.addPlotCurve(dataPoint)
                chart.updatePlot()
                break

    def plotDataVector(self, item):
        title = str(item.text(0))

        # create plot widget
        widget = PlotWidget()
        chart = PlotChart(title)
        chart.plotWidget = widget
        widget.showGrid(True, True)
        widget.getPlotItem().getAxis("bottom").setLabel(text="Time", units="s")

        for idx in range(item.childCount()):
            for datapoint in self.dataPointBuffers:
                if datapoint.name == item.child(idx).text(1):
                    chart.addPlotCurve(datapoint)

        # before adding the PlotChart object to the list check if the plot contains any data points
        if chart.dataPoints is not None:
            self.plotCharts.append(chart)
        else:
            return

        chart.updatePlot()

        coordItem = TextItem(text='', anchor=(0, 1))
        widget.getPlotItem().addItem(coordItem, ignoreBounds=True)

        def info_wrapper(pos):
            self.updateCoordInfo(pos, widget, coordItem)

        widget.scene().sigMouseMoved.connect(info_wrapper)

        widget.scene().contextMenu = [QAction("Export png", self),
                                      QAction("Export csv", self)]
        widget.scene().contextMenu[0].triggered.connect(lambda: self.exportPng(widget.getPlotItem(), title, coordItem))
        widget.scene().contextMenu[1].triggered.connect(lambda: self.exportCsv(chart, title))

        # create dock container and add it to dock area
        dock = Dock(title, closable=True)
        dock.addWidget(widget)
        dock.sigClosed.connect(self.closedDock)

        plotWidgets = self.findAllPlotDocks()
        if plotWidgets:
            self.area.addDock(dock, "above", plotWidgets[0])
        else:
            self.area.addDock(dock, "bottom", self.animationDock)

    def closedDock(self):
        """ Gets called when a dock was closed, if it was a plot dock remove the corresponding PlotChart object
        form the list

        Returns
        -------

        """
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        for indx, plot in enumerate(self.plotCharts):
            if not plot.title in openDocks:
                self.plotCharts.pop(indx)

    def exportCsv(self, chart, name):
        exporter = CSVExporter(chart)
        filename = QFileDialog.getSaveFileName(self, "CSV export", name + ".csv", "CSV Data (*.csv)")
        if filename[0]:
            exporter.export(filename[0])

    def exportPng(self, plotItem, name, coordItem):
        # Notwendig da Fehler in PyQtGraph
        exporter = exporters.ImageExporter(plotItem)
        oldGeometry = plotItem.geometry()
        plotItem.setGeometry(QRectF(0, 0, 1920, 1080))

        bgBrush = mkBrush('w')
        exporter.params.param('background').setValue(bgBrush.color())
        exporter.params.param('width').setValue(1920, blockSignal=exporter.widthChanged)
        exporter.params.param('height').setValue(1080, blockSignal=exporter.heightChanged)

        flag = 0
        if coordItem.isVisible():
            coordItem.hide()
            flag = 1

        filename = QFileDialog.getSaveFileName(self, "PNG export", name + ".png", "PNG Image (*.png)")
        if filename[0]:
            exporter.export(filename[0])

        # restore old state
        if flag == 1:
            coordItem.show()
        plotItem.setGeometry(QRectF(oldGeometry))

    @pyqtSlot(QModelIndex)
    def targetViewChanged(self, index):
        self.targetView.resizeColumnToContents(0)

    @pyqtSlot()
    def updateShowCoordsSetting(self):
        self._settings.setValue("view/show_coordinates", str(self.actShowCoords.isChecked()))

    @pyqtSlot()
    def startExperiment(self):
        """
        start the experiment and disable start button
        """
        if self._currentExperimentIndex is None:
            expName = ""
        else:
            expName = str(self.experimentList.item(self._currentExperimentIndex).text())

        self._logger.info("Experiment: {}".format(expName))

        self.actStartExperiment.setDisabled(True)
        self.actStopExperiment.setDisabled(False)
        if self._currentExperimentIndex is not None:
            self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(Qt.darkGreen))
            self.experimentList.repaint()

        for buffer in self.dataPointBuffers:
            buffer.clearBuffer()

        for chart in self.plotCharts:
            chart.updatePlot()

        while not self.outputQueue.empty():
            self.outputQueue.get()

        self.connection.doRead = True
        self.timer.start(100)
        self.exp.runExperiment()

    @pyqtSlot()
    def stopExperiment(self):
        self.actStartExperiment.setDisabled(False)
        self.actStopExperiment.setDisabled(True)
        for i in range(self.experimentList.count()):
            self.experimentList.item(i).setBackground(QBrush(Qt.white))
        self.experimentList.repaint()

        self.connection.doRead = False
        self.timer.stop()
        self.exp.stopExperiment()

    def loadExpDialog(self):
        filename = QFileDialog.getOpenFileName(self, "Experiment file öffnen", "", "Experiment files (*.sreg)")
        if filename[0]:
            self.loadExpFromFile(filename[0])
            return True
        else:
            return False

    def loadExpFromFile(self, fileName):
        """
        load experiments from file
        :param file_name:
        """
        self._experimentsFileName = os.path.split(fileName)[-1][:-5]
        self._logger.info("Lade Experimentedatei: {0}".format(self._experimentsFileName))
        with open(fileName.encode(), "r") as f:
            self._experiments += yaml.load(f)

        self._updateExperimentsList()

        self._logger.info("Lade {} Experimente".format(len(self._experiments)))
        return

    def _updateExperimentsList(self):
        self.experimentList.clear()
        for exp in self._experiments:
            self._logger.debug("Füge '{}' zur Experimentliste hinzu".format(exp["Name"]))
            self.experimentList.addItem(exp["Name"])

    @pyqtSlot(QListWidgetItem)
    def experimentDclicked(self, item):
        """
        Apply the selected experiment to the current target and set it bold.
        """
        success = self._applyExperimentByIdx(self.experimentList.row(item))

        self.setQListItemBold(self.experimentList, item, success)
        self.setQListItemBold(self.lastMeasList, item, success)

    def _applyExperimentByIdx(self, index=0):
        """
        Apply the given experiment.
        Args:
            index(int): Index of the experiment in the `ExperimentList` .
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        if self.connection is not None:
            # check if experiment runs
            if not self.actStopExperiment.isEnabled():
                self.actStartExperiment.setDisabled(False)
                return False

        if index >= len(self._experiments):
            self._logger.error("applyExperiment: index error! ({})".format(index))
            return False

        exp_name = self._experiments[index]["Name"]
        self._logger.info("Experiment '{}' übernommen".format(exp_name))

        self._currentExperimentIndex = index
        self._currentExperimentName = exp_name

        return self.exp.setExperiment(self._experiments[index])

    def closeEvent(self, QCloseEvent):
        if self.connection:
            self.disconnect()
        self._logger.info("Close Event received, shutting down.")
        logging.getLogger().removeHandler(self.textLogger)
        super().closeEvent(QCloseEvent)

    def connect(self):
        self.connection = SerialConnection(self.inputQueue, self.outputQueue, self.port)
        if self.connection.connect():
            self._logger.info("Mit Arduino auf " + self.connection.port + " verbunden.")
            self.actConnect.setEnabled(False)
            self.actDisconnect.setEnabled(True)
            if self._currentExperimentIndex is not None:
                self.actStartExperiment.setEnabled(True)
            self.actStopExperiment.setEnabled(False)
            self.statusbarLabel.setText("Verbunden")
            self.connection.start()
        else:
            self.connection = None
            self._logger.warning("Keinen Arduino gefunden. Erneut Verbinden!")
            self.statusbarLabel.setText("Nicht Verbunden")

    def disconnect(self):
        self.stopExperiment()
        self.connection.disconnect()
        self.connection = None
        self._logger.info("Arduino getrennt.")
        self.actConnect.setEnabled(True)
        self.actDisconnect.setEnabled(False)
        self.actStartExperiment.setEnabled(False)
        self.actStopExperiment.setEnabled(False)
        self.statusbarLabel.setText("Nicht Verbunden")

    def findAllPlotDocks(self):
        list = []
        for title, dock in self.area.findAll()[1].items():
            if title in self.nonPlottingDocks:
                continue
            else:
                list.append(dock)

        return list

    def updateData(self):
        if self.outputQueue.empty():
            return

        frames = []
        for i in range(0, self.outputQueue.qsize()):
            frames.append(self.outputQueue.get())

        for frame in frames:
            data = self.exp.handleFrame(frame)
            time = data['Zeit'] / 1000.0
            datapoints = data['Punkte']
            names = data['Punkte'].keys()
            for buffer in self.dataPointBuffers:
                if buffer.name in names:
                    buffer.addValue(time, datapoints[buffer.name])

        for chart in self.plotCharts:
            chart.updatePlot()

    def loadStandardDockState(self):
        self.plotCharts.clear()

        for dock in self.findAllPlotDocks():
            dock.close()
            # TODO hier kommt noch ein Fehler und prüfen ob experiment nicht gerade läuft
        self.area.restoreState(self.standardDockState)

    def saveLastMeas(self):
        if self._currentExperimentIndex is None:
            return

        data = {}
        data.update({'datapointbuffers': deepcopy(self.dataPointBuffers)})

        experiment = deepcopy(self._experiments[self._currentExperimentIndex])

        # save actual parameter
        for row in range(self.exp.targetModel.rowCount()):
            index = self.exp.targetModel.index(row, 0)
            parent = index.model().itemFromIndex(index)
            child = index.model().item(index.row(), 1)
            moduleName = parent.data(role=PropertyItem.RawDataRole)
            subModuleName = child.data(role=PropertyItem.RawDataRole)

            if subModuleName is None:
                continue

            settings = self.exp.getSettings(self.exp.targetModel, moduleName)
            for key, val in settings.items():
                if val is not None:
                    experiment[moduleName][key] = val
        data.update({'exp': experiment})

        self.lastMeasurements.append(data)
        self.lastMeasList.addItem(
            QListWidgetItem(str(self.lastMeasList.count() + 1) + ": " + self._currentExperimentName))

    def loadLastMeas(self, item):
        expName = str(item.text())
        try:
            idx = self.lastMeasList.row(item)
        except ValueError:
            self._logger.error("loadLastMeas(): No measurement called '{0}".format(expName))
            return False

        if idx >= len(self.lastMeasurements):
            self._logger.error("loadLastMeas(): Invalid index '{}')".format(idx))
            return False

        self._logger.info("Wiederherstellung der Messung '{}'".format(expName))

        measurement = self.lastMeasurements[idx]

        success = self.exp.restoreExperiment(measurement['exp'])

        self.setQListItemBold(self.lastMeasList, item, success)
        self.setQListItemBold(self.experimentList, item, success)

        self.dataPointBuffers = measurement['datapointbuffers']

        for i in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.updatePlot(self.dataPointTreeWidget.topLevelItem(i))

        self._logger.info("Messung '{}' übernommen".format(measurement['exp']['Name']))

    def setQListItemBold(self, qList=None, item=None, state=True):
        for i in range(qList.count()):
            newfont = qList.item(i).font()
            if qList.item(i) == item and state:
                newfont.setBold(1)
            else:
                newfont.setBold(0)
            qList.item(i).setFont(newfont)
        qList.repaint()
