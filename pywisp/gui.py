# -*- coding: utf-8 -*-

import os
from operator import itemgetter

import yaml
from PyQt5.QtCore import QSize, Qt, pyqtSlot, pyqtSignal, QModelIndex, QRectF
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pyqtgraph import PlotWidget, exporters
from pyqtgraph.dockarea import *
from copy import deepcopy

from .connection import SerialConnection
from .experiments import ExperimentInteractor, ExperimentView, PropertyItem
from .registry import *
from .utils import get_resource, PlainTextLogger, DataPointBuffer, PlotChart
from .visualization import MplVisualizer
from . import experimentModules


class MainGui(QMainWindow):
    runExp = pyqtSignal()
    stopExp = pyqtSignal()

    def __init__(self, moduleList, parent=None):
        super(MainGui, self).__init__(parent)
        self.connection = None

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

        # create experiment backend
        self.exp = ExperimentInteractor(moduleList, self)
        self.exp.sendData.connect(self.writeToSerial)
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
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusbarLabel = QLabel("Nicht Verbunden")
        self.statusBar.addPermanentWidget(self.statusbarLabel, 1)

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
        self.area.addDock(self.experimentDock, "above", self.lastMeasDock)
        self.area.addDock(self.propertyDock, "bottom", self.experimentDock)
        self.area.addDock(self.dataDock, "bottom", self.propertyDock)
        self.area.addDock(self.logDock, "bottom", self.dataDock)
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
        self.actLadeExperiments.setShortcut(QKeySequence.Open)
        self.actLadeExperiments.triggered.connect(self.loadExpDialog)

        self.actSpeichereExperiments = QAction(self)
        self.actSpeichereExperiments.setText("&Speichere Experimente in Datei")
        self.actSpeichereExperiments.setIcon(QIcon(get_resource("save.png")))
        self.actSpeichereExperiments.setDisabled(False)
        self.actSpeichereExperiments.setShortcut(QKeySequence.Save)
        self.actSpeichereExperiments.triggered.connect(self.saveExpDialog)

        self.actStartExperiment = QAction(self)
        self.actStartExperiment.setDisabled(True)
        self.actStartExperiment.setText("&Starte Experiment")
        self.actStartExperiment.setIcon(QIcon(get_resource("play.png")))
        self.actStartExperiment.setShortcut(QKeySequence("F5"))
        self.actStartExperiment.triggered.connect(self.startExperiment)

        self.actStopExperiment = QAction(self)
        self.actStopExperiment.setText("&Stope Experiment")
        self.actStopExperiment.setDisabled(True)
        self.actStopExperiment.setIcon(QIcon(get_resource("stop.png")))
        self.actStopExperiment.setShortcut(QKeySequence("F6"))
        self.actStopExperiment.triggered.connect(self.stopExperiment)

        # lastmeas dock
        self.lastMeasList = QListWidget(self)
        self.lastMeasDock.addWidget(self.lastMeasList)
        self.lastMeasList.itemDoubleClicked.connect(self.loadLastMeas)
        self.exp.expfinished.connect(self.saveLastMeas)
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
            "Add the selected data set from the left side to the selected plot "
            "on the right.")
        self.dataPointRightButton.clicked.connect(self.addDatapointToTree)
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
        self._logger.info('Visualisierung für Versuchsstand Ball in Tube')

        # menu bar
        dateiMenu = self.menuBar().addMenu("&Datei")
        dateiMenu.addAction(self.actLadeExperiments)
        dateiMenu.addAction(self.actSpeichereExperiments)
        dateiMenu.addAction("&Quit", self.close, QKeySequence(Qt.CTRL + Qt.Key_W))

        # view
        self.viewMenu = self.menuBar().addMenu('&Ansicht')
        self.actLoadStandardState = QAction('Lade Standarddockansicht')
        self.viewMenu.addAction(self.actLoadStandardState)
        self.actLoadStandardState.triggered.connect(self.loadStandardDockState)

        # experiment
        self.expMenu = self.menuBar().addMenu('&Experiment')
        self.actConnect = QAction('Versuchsaufbau verbinden')
        self.actConnect.setIcon(QIcon(get_resource("connected.png")))
        self.actConnect.setShortcut(QKeySequence("F9"))
        self.expMenu.addAction(self.actConnect)
        self.actConnect.triggered.connect(self.connect)

        self.actDisconnect = QAction('Versuchsaufbau trennen')
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
        self.toolbarExp.addAction(self.actSpeichereExperiments)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actConnect)
        self.toolbarExp.addAction(self.actDisconnect)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actStartExperiment)
        self.toolbarExp.addAction(self.actStopExperiment)

        self.expSettingsChanged = False
        self.exp.parameterItemChanged.connect(self.parameterItemChangedHandler)

    # event functions
    def addPlotTreeItem(self):
        name, ok = QInputDialog.getText(self, "Plottitel", "Plottitel:")
        if not(ok and name):
            return
        similar_items = self.dataPointTreeWidget.findItems(name, Qt.MatchExactly)
        if similar_items:
            self._logger.error("Name '{}' existiert bereits!".format(name))
            return

        toplevelitem = QTreeWidgetItem()
        toplevelitem.setText(0, name)
        self.dataPointTreeWidget.addTopLevelItem(toplevelitem)
        toplevelitem.setExpanded(1)

    def removeSelectedPlotTreeItems(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
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
        if not(self.dataPointListWidget.selectedIndexes() and self.dataPointTreeWidget.selectedIndexes()):
            return

        dataPoints = []
        for item in self.dataPointListWidget.selectedItems():
            for data in self.dataPointBuffers:
                if data.name == item.text():
                    dataPoints.append(data)
                    continue

        toplevelItem = self.dataPointTreeWidget.selectedItems()[0]
        while toplevelItem.parent():
            toplevelItem = toplevelItem.parent()

        topLevelItemList = []
        for i in range(toplevelItem.childCount()):
            topLevelItemList.append(toplevelItem.child(i).text(1))

        for dataPoint in dataPoints:
            if dataPoint.name not in topLevelItemList:
                child = QTreeWidgetItem()
                child.setText(1, dataPoint.name)
                toplevelItem.addChild(child)

        self.plots(toplevelItem)

    def removeDatapointFromTree(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
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
        widget.scene().contextMenu = [QAction("Export png", self),
                                      QAction("Export csv", self)]
        widget.scene().contextMenu[0].triggered.connect(lambda: self.exportPng(widget.getPlotItem(), title))
        widget.scene().contextMenu[1].triggered.connect(lambda: self.exportCsv(widget.getPlotItem(), title))

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

    def exportCsv(self, plotItem, name):
        exporter = exporters.CSVExporter(plotItem)
        filename = QFileDialog.getSaveFileName(self, "CSV export", name + ".csv", "CSV Data (*.csv)")
        if filename[0]:
            exporter.export(filename[0])

    def exportPng(self, plotItem, name):
        # Notwendig da Fehler in PyQtGraph
        exporter = exporters.ImageExporter(plotItem)
        oldGeometry = plotItem.geometry()
        plotItem.setGeometry(QRectF(0, 0, 1920, 1080))
        # TODO Farben ändern Background, grid und pen
        # exporter.parameters()['background'] = QColor(255, 255, 255)
        exporter.params.param('width').setValue(1920, blockSignal=exporter.widthChanged)
        exporter.params.param('height').setValue(1080, blockSignal=exporter.heightChanged)

        filename = QFileDialog.getSaveFileName(self, "PNG export", name + ".png", "PNG Image (*.png)")
        if filename[0]:
            exporter.export(filename[0])

        # restore old state
        plotItem.setGeometry(QRectF(oldGeometry))

    @pyqtSlot(QModelIndex)
    def targetViewChanged(self, index):
        self.targetView.resizeColumnToContents(0)

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
        self.runExp.emit()

    @pyqtSlot()
    def stopExperiment(self):
        self.actStartExperiment.setDisabled(False)
        self.actStopExperiment.setDisabled(True)
        if self._currentExperimentIndex is not None:
            self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(Qt.white))
            self.experimentList.repaint()

        self.stopExp.emit()

    def loadExpDialog(self):
        filename = QFileDialog.getOpenFileName(self, "Experiment file öffnen", "", "Experiment files (*.sreg)");
        if filename[0]:
            self.loadExpFromFile(filename[0])
            return True
        else:
            return False

    def saveExpDialog(self):
        filename = QFileDialog.getSaveFileName(self, "Experiment file speichern", "", "Experiment files (*.sreg)");
        if filename[0]:
            self.saveExpToFile(filename[0])
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

    def saveExpToFile(self, filePath):
        """
        save experiments to file
        :param file_name:
        """
        fileName = os.path.split(filePath)[-1][:-5]
        self._logger.info("Speichere Experimentedatei: {0}".format(fileName))

        for row in range(self.exp.targetModel.rowCount()):
            index = self.exp.targetModel.index(row, 0)
            parent = index.model().itemFromIndex(index)
            child = index.model().item(index.row(), 1)
            moduleName = parent.data(role=PropertyItem.RawDataRole)
            subModuleName = child.data(role=PropertyItem.RawDataRole)
 
            if subModuleName is None:
                continue
            moduleClass = getattr(experimentModules, moduleName, None)
            subModuleClass = getExperimentModuleClassByName(moduleClass, subModuleName)
 
            settings = self.exp._getSettings(self.exp.targetModel, moduleName)
            for key, val in settings.items():
                if val is not None:
                    self._experiments[self._currentExperimentIndex][moduleName][key] = val

        with open(filePath.encode(), "w") as f:
            yaml.dump(self._experiments, f, default_flow_style=False)
        
        self.expSettingsChanged = False

        return

    def parameterItemChangedHandler(self, item):
        self.expSettingsChanged = True

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
        self.exp.applayingExperiment = True
        sucess = self._applyExperimentByIdx(self.experimentList.row(item))
        self.exp.applayingExperiment = False

        self.setQListItemBold(self.experimentList, item, [sucess])
        self.setQListItemBold(self.lastMeasList, item, [sucess])

    def applyExperimentByName(self, experimentName):
        """
        Apply the experiment given by `experimentName` and update the experiment index.
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        # get regime idx
        try:
            idx = list(map(itemgetter("Name"), self._experiments)).index(experimentName)
        except ValueError as e:
            self._logger.error("apply_regime_by_name(): Error no regime called "
                               "'{0}'".format(experimentName))
            return False

        # apply
        return self._applyExperimentByIdx(idx)

    def _applyExperimentByIdx(self, index=0):
        """
        Apply the given experiment.
        Args:
            index(int): Index of the experiment in the `ExperimentList` .
        Returns:
            bool: `True` if successful, `False` if errors occurred.
        """
        if index >= len(self._experiments):
            self._logger.error("applyExperiment: index error! ({})".format(index))
            return False

        exp_name = self._experiments[index]["Name"]
        self._logger.info("Experiment '{}' übernommen".format(exp_name))

        self._currentExperimentIndex = index
        self._currentExperimentName = exp_name

        if self.connection is not None:
            self.actStartExperiment.setDisabled(False)
        return self.exp.setExperiment(self._experiments[index])

    def closeEvent(self, QCloseEvent):
        if self.expSettingsChanged:
            buttonReply = QMessageBox.warning(self, "Experiment geändert",
                                              "Sie haben ein Experiment geändert, möchten Sie Ihre Änderungen speichern?",
                                              QMessageBox.Yes | QMessageBox.No)
            if buttonReply == QMessageBox.Yes:
                if not self.saveExpDialog():
                    QCloseEvent.ignore()
                    return
        if self.connection:
            self.disconnect()
        self._logger.info("Close Event received, shutting down.")
        logging.getLogger().removeHandler(self.textLogger)
        super().closeEvent(QCloseEvent)

    def connect(self):
        self.connection = SerialConnection()
        if self.connection.connect():
            self._logger.info("Mit Arduino auf " + self.connection.port + " verbunden.")
            self.actConnect.setEnabled(False)
            self.actDisconnect.setEnabled(True)
            if self._currentExperimentIndex is not None:
                self.actStartExperiment.setEnabled(True)
            self.actStopExperiment.setEnabled(False)
            self.statusbarLabel.setText("Verbunden")
            self.connection.received.connect(self.updateData)
            self.connection.start()
        else:
            self.connection = None
            self._logger.warning("Keinen Arduino gefunden. Erneut Verbinden!")
            self.statusbarLabel.setText("Nicht Verbunden")

    def disconnect(self):
        self.stopExperiment()
        self.connection.disconnect()
        self.connection.stop()
        self.connection.received.disconnect()
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

    def updateData(self, data):
        if len(data.split(';')) != len(self.dataPointBuffers) + 1:
            self._logger.warning("Fehler bei der Datenübertragung")
            return
        for value in data.split(';'):
            _val = value.split(': ')
            name = _val[0]
            value = float(_val[1])
            if name == 'Zeit':
                time = value
                continue
            for buffer in self.dataPointBuffers:
                if name == buffer.name:
                    buffer.addValue(time, value)
                    if self.visualizer:
                        for dataPoint in self.visualizer.dataPoints:
                            if buffer.name == dataPoint:
                                self.visualizer.update({dataPoint: value})
                    continue

        for chart in self.plotCharts:
            chart.updatePlot()

    def loadStandardDockState(self):
        self.plotCharts.clear()

        for dock in self.findAllPlotDocks():
            dock.close()
            # TODO hier kommt noch ein Fehler und prüfen ob experiment nicht gerade läuft
        self.area.restoreState(self.standardDockState)

    def writeToSerial(self, data):
        if self.connection:
            self.connection.writeData(data)
        else:
            self._logger.error('Keine Verbindung vorhanden!')

    def saveLastMeas(self):
        data = {}
        data.update({'datapointbuffers':deepcopy(self.dataPointBuffers)})

        experiment = deepcopy( self._experiments[self._currentExperimentIndex])

        # save actual parameter
        for row in range(self.exp.targetModel.rowCount()):
            index = self.exp.targetModel.index(row, 0)
            parent = index.model().itemFromIndex(index)
            child = index.model().item(index.row(), 1)
            moduleName = parent.data(role=PropertyItem.RawDataRole)
            subModuleName = child.data(role=PropertyItem.RawDataRole)

            if subModuleName is None:
                continue
            moduleClass = getattr(experimentModules, moduleName, None)
            subModuleClass = getExperimentModuleClassByName(moduleClass, subModuleName)

            settings = self.exp._getSettings(self.exp.targetModel, moduleName)
            for key, val in settings.items():
                if val is not None:
                    experiment[moduleName][key] = val
        data.update({'exp':experiment})
        
        self.lastMeasurements.append(data)
        self.lastMeasList.addItem(QListWidgetItem(str(self.lastMeasList.count()+1)+": "+self._currentExperimentName))

    def loadLastMeas(self, item):
        measurement = self.lastMeasurements[self.lastMeasList.row(item)]

        self.exp.applayingExperiment = True
        sucess = self.exp.setExperiment(measurement['exp'])
        self.exp.applayingExperiment = False

        self.setQListItemBold(self.lastMeasList, item, [sucess])
        self.setQListItemBold(self.experimentList, item, [sucess])

        self.dataPointBuffers = measurement['datapointbuffers']

        for i in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.updatePlot(self.dataPointTreeWidget.topLevelItem(i))
        
        self._logger.info("Letzte Messung '{}' übernommen".format(measurement['exp']['Name']))

    def setQListItemBold(self, QList=None, item=None, args=[]):
        sucess = True
        for arg in args:
            if arg == False:
                sucess = False
                break
        for i in range(QList.count()):
            newfont = QList.item(i).font()
            if QList.item(i) == item and sucess:
                newfont.setBold(1)
            else:
                newfont.setBold(0)
            QList.item(i).setFont(newfont)
        QList.repaint()