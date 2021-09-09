# -*- coding: utf-8 -*-
import logging
import os
import time
from copy import deepcopy

import pkg_resources
import serial.tools.list_ports
import yaml

# vtk
vtk_error_msg = ""
try:
    import vtk

    from vtk import vtkRenderer
    from vtk import qt
    # import patched class that fixes scroll problem
    from .visualization import QVTKRenderWindowInteractor

    vtk_available = True
except ImportError as e:
    vtk_available = False
    vtk_error_msg = e
    vtkRenderer = None
    QVTKRenderWindowInteractor = None

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from PyQt5.QtCore import QSize, Qt, pyqtSlot, pyqtSignal, QModelIndex, QTimer, QSettings, QCoreApplication
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pyqtgraph import PlotWidget, TextItem
from pyqtgraph.dockarea import *

from .connection import SerialConnection, TcpConnection
from .experiments import ExperimentInteractor, ExperimentView
from .registry import *
from .utils import getResource, PlainTextLogger, DataPointBuffer, PlotChart, Exporter, DataIntDialog, \
    DataTcpIpDialog, RemoteWidgetEdit, FreeLayout, MovablePushButton, MovableSwitch, MovableSlider, PinnedDock, \
    ContextLineEditAction, TreeWidgetStyledItemDelegate

from .visualization import MplVisualizer, VtkVisualizer


class MainGui(QMainWindow):
    """
    Main class for the GUI
    """
    runExp = pyqtSignal()
    stopExp = pyqtSignal()

    def __init__(self, fileName=None, parent=None):
        super(MainGui, self).__init__(parent)

        QCoreApplication.setOrganizationName("IACE")
        QCoreApplication.setOrganizationDomain("https://umit.at/iace")
        QCoreApplication.setApplicationVersion(
            pkg_resources.require("PyWisp")[0].version)
        QCoreApplication.setApplicationName(globals()["__package__"])

        # general config parameters
        self.config = {'TimerTime': 100,
                       'HeartbeatTime': 0,
                       'InterpolationPoints': 100,
                       'MovingWindowEnable': False,
                       'MovingWindowSize': 10,
                       }
        self.configDefaults = self.config.copy()
        QStyleSheet = """
            QListView::item:selected {
                color: black;
            }
            QListView::item:selected:!active {
                background: transparent;
            }
            QListView::item:selected:active {
                background: transparent;
            }
            QListView::item:hover { }
            QTreeView {
                selection-background-color: transparent;
            }
            QTreeView::item:selected { }
            QTreeView::item:hover { }
            QTreeView::item:hover:selected { }
        """

        # Create and display the splash screen
        self.splashScreenIcon = QPixmap(getResource("icon.svg"))
        self.splashScreen = QSplashScreen(self, self.splashScreenIcon, Qt.WindowStaysOnTopHint)
        self.splashScreen.setEnabled(False)
        self.splashScreen.show()

        self.connections = {}
        self.isConnected = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateDataPlots)
        self.heartbeatTimer = QTimer()
        self.heartbeatTimer.timeout.connect(self.heartbeat)

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

        # load settings
        self._settings = QSettings()
        self._initSettings()

        # create experiment
        self._experiments = []

        # window properties
        iconSize = QSize(25, 25)
        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)
        self.resize(1000, 700)
        self.setWindowTitle('Visualization')

        # status bar
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self.statusbarLabel = QLabel("Not connected!")
        self.statusBar.addPermanentWidget(self.statusbarLabel, 1)
        self.guiStartTime = 0.0
        self.guiTimer = QTimer()
        # set most precise timer type
        self.guiTimer.setTimerType(0)
        self.guiTimer.timeout.connect(self.updateGuiTimeLabel)
        self.guiTimeLabel = QLabel("GUI time=00:00:00")
        self.statusBar.addPermanentWidget(self.guiTimeLabel, 1)
        self.expTimeLabel = QLabel("Exp time=00:00:00")
        self.statusBar.addPermanentWidget(self.expTimeLabel, 1)
        statusBarDummyLabel = QLabel("")
        self.statusBar.addPermanentWidget(statusBarDummyLabel, 4)
        self.coordTimer = QTimer()
        self.coordTimer.timeout.connect(self.disableCoord)
        self.coordLabel = QLabel("x=0.0 y=0.0")
        self.coordLabel.setVisible(False)
        self.statusBar.addPermanentWidget(self.coordLabel, 2)

        # the docking area allows to rearrange the user interface at runtime
        self.area = DockArea()
        self.setCentralWidget(self.area)

        # create docks
        self.experimentDock = PinnedDock("Experiments")
        self.lastMeasDock = PinnedDock("Last Measurements")
        self.propertyDock = PinnedDock("Parameters")
        self.logDock = PinnedDock("Log")
        self.dataDock = PinnedDock("Data")
        self.animationDock = PinnedDock("Animation")
        self.remoteDock = PinnedDock("Remote")

        # arrange docks
        self.area.addDock(self.animationDock, "right")
        self.area.addDock(self.lastMeasDock, "left", self.animationDock)
        self.area.addDock(self.propertyDock, "bottom", self.lastMeasDock)
        self.area.addDock(self.dataDock, "bottom", self.propertyDock)
        self.area.addDock(self.logDock, "bottom", self.dataDock)
        self.area.addDock(self.experimentDock, "left", self.lastMeasDock)
        self.area.addDock(self.remoteDock, "right", self.propertyDock)
        self.nonPlottingDocks = list(self.area.findAll()[1].keys())

        # property dock
        self.targetView = ExperimentView(self)
        self.targetView.expanded.connect(self.targetViewChanged)
        self.targetView.collapsed.connect(self.targetViewChanged)

        self.propertyDock.addWidget(self.targetView)

        # animation dock
        self.animationWidget = QWidget()
        self.animationLayout = QVBoxLayout()
        self.animationDock.addWidget(self.animationWidget)

        # experiment dock
        self.experimentList = QListWidget(self)
        self.experimentList.setFocusPolicy(Qt.NoFocus)
        self.experimentList.setStyleSheet(QStyleSheet)
        self.experimentList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.experimentDock.addWidget(self.experimentList)
        self.experimentList.itemDoubleClicked.connect(self.experimentDclicked)
        self._currentExperimentIndex = None
        self._currentExperimentName = None
        self._experimentStartTime = 0

        self.actStartExperiment = QAction(self)
        self.actStartExperiment.setDisabled(True)
        self.actStartExperiment.setText("&Start experiment")
        self.actStartExperiment.setIcon(QIcon(getResource("play.png")))
        self.actStartExperiment.setShortcut(QKeySequence("F5"))
        self.actStartExperiment.triggered.connect(self.startExperiment)

        self.actStopExperiment = QAction(self)
        self.actStopExperiment.setText("&Stop experiment")
        self.actStopExperiment.setDisabled(True)
        self.actStopExperiment.setIcon(QIcon(getResource("stop.png")))
        self.actStopExperiment.setShortcut(QKeySequence("F6"))
        self.actStopExperiment.triggered.connect(self.stopExperiment)

        self.visComboBox = QComboBox()

        # lastmeas dock
        self.lastMeasList = QListWidget(self)
        self.lastMeasList.setFocusPolicy(Qt.NoFocus)
        self.lastMeasList.setStyleSheet(QStyleSheet)
        self.lastMeasDock.addWidget(self.lastMeasList)
        self.lastMeasList.itemDoubleClicked.connect(self.loadLastMeas)
        self.measurements = []

        # log dock
        self.logBox = QTextEdit(self)
        self.logBox.setReadOnly(True)
        self.logBox.setLineWrapMode(QTextEdit.NoWrap)
        self.logBox.moveCursor(QTextCursor.End)
        self.logBox.ensureCursorVisible()
        self.logBox.moveCursor(QTextCursor.End)
        self.logDock.addWidget(self.logBox)

        # daten dock
        self.dataWidget = QWidget()
        self.dataLayout = QHBoxLayout()

        self.dataPointListWidget = QListWidget()
        self.dataPointListLayout = QVBoxLayout()
        self.dataPointListWidget.setLayout(self.dataPointListLayout)
        self.dataPointListWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.dataLayout.addWidget(self.dataPointListWidget)

        self.dataPointManipulationWidget = QWidget()
        self.dataPointManipulationLayout = QVBoxLayout()
        self.dataPointManipulationLayout.addStretch()
        self.dataPointManipulationLayout.setSpacing(5)
        self.dataPointRightButtonWidget = QWidget()
        self.dataPointRightButtonLayout = QVBoxLayout()
        self.dataPointRightButton = QPushButton(chr(0x226b), self)
        self.dataPointRightButton.setToolTip(
            "Add the selected data set from the left to the selected plot "
            "on the right.")
        self.dataPointRightButton.clicked.connect(self.addDatapointToTree)
        self.dataPointLabel = QLabel('DataPoint', self)
        self.dataPointLabel.setAlignment(Qt.AlignCenter)
        self.dataPointManipulationLayout.addWidget(self.dataPointLabel)
        self.dataPointManipulationLayout.addWidget(self.dataPointRightButton)
        self.dataPointLeftButtonWidget = QWidget()
        self.dataPointLeftButtonLayout = QVBoxLayout()
        self.dataPointLeftButton = QPushButton(chr(0x03A7), self)
        self.dataPointLeftButton.setToolTip(
            "Remove the selected data set from the plot on the right."
        )
        self.dataPointLeftButton.clicked.connect(self.removeDatapointFromTree)
        self.dataPointManipulationLayout.addWidget(self.dataPointLeftButton)
        self.dataPointExportButton = QPushButton(chr(0x25BC), self)
        self.dataPointExportButton.setToolTip(
            "Export the selected data set from the left to a csv or png file."
        )
        self.dataPointExportButton.clicked.connect(self.exportDataPointFromTree)
        self.dataPointManipulationLayout.addWidget(self.dataPointExportButton)
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
        custom_QStyledItemDelegate = TreeWidgetStyledItemDelegate()
        self.dataPointTreeWidget.setItemDelegate(custom_QStyledItemDelegate)
        self.dataPointTreeWidget.setStyleSheet(QStyleSheet)
        self.dataPointTreeWidget.setHeaderLabels(["PlotTitle", "DataPoint"])
        self.dataPointTreeWidget.itemDoubleClicked.connect(self.plotVectorClicked)
        self.dataPointTreeWidget.setExpandsOnDoubleClick(0)
        self.dataPointTreeLayout = QVBoxLayout()

        self.dataPointTreeWidget.setLayout(self.dataPointTreeLayout)
        self.dataLayout.addWidget(self.dataPointTreeWidget)

        self.dataWidget.setLayout(self.dataLayout)
        self.dataDock.addWidget(self.dataWidget)

        # init logger for logging box
        self.textLogger = PlainTextLogger(self._settings,
                                          logging.INFO)
        self.textLogger.setTargetCb(self.logBox)
        logging.getLogger().addHandler(self.textLogger)
        self._logger.info('Laboratory visualization')

        # remote dock
        self.remoteWidget = QWidget()
        self.remoteWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.remoteWidget.customContextMenuRequested.connect(self.remoteWidgetMenue)
        self.remoteWidgetLayout = FreeLayout()
        self.remoteWidget.setLayout(self.remoteWidgetLayout)
        self.remoteDock.addWidget(self.remoteWidget)

        # menu bar
        dateiMenu = self.menuBar().addMenu("&File")
        dateiMenu.addAction("&Quit", self.close, QKeySequence(Qt.CTRL + Qt.Key_W))

        # view
        self.viewMenu = self.menuBar().addMenu('&View')
        self.actLoadStandardState = QAction('&Load default view')
        self.viewMenu.addAction(self.actLoadStandardState)
        self.actLoadStandardState.triggered.connect(self.loadStandardDockState)
        self.actShowCoords = QAction("&Show coordinates", self)
        self.actShowCoords.setCheckable(True)
        self.actShowCoords.setChecked(
            self._settings.value("view/show_coordinates") == "True"
        )
        self.viewMenu.addAction(self.actShowCoords)
        self.actShowCoords.changed.connect(self.updateShowCoordsSetting)

        # options
        self.optMenu = self.menuBar().addMenu('&Options')
        self.actTimerTime = QAction("&Timer time", self)
        self.optMenu.addAction(self.actTimerTime)
        self.actTimerTime.triggered.connect(self.setTimerTime)

        # experiment
        self.expMenu = self.menuBar().addMenu('&Experiment')
        self.connMenu = self.menuBar().addMenu('&Connections')

        availableConns = getRegisteredConnections()
        if availableConns:
            for cls, name in availableConns:
                self._logger.info("Found Connection: {}".format(name))
                self.connections[cls] = {}
        else:
            self._logger.error("No Connections found, return!")
            # return

        serialCnt = 0
        for conn, connInstance in self.connections.items():
            if issubclass(conn, SerialConnection):
                serialMenu = self.connMenu.addMenu(conn.__name__)
                self._getSerialMenu(serialMenu, conn.settings)
                if conn.settings['port'] == '':
                    self.setDefaultComPort(conn.settings, serialCnt)
                serialCnt += 1
            elif issubclass(conn, TcpConnection):
                actTcp = self.connMenu.addAction(conn.__name__)
                actTcp.triggered.connect(lambda _, settings=conn.settings: self._getTcpMenu(settings))
            else:
                self._logger.warning("Cannot handle the connection type!")
            self.connMenu.addSeparator()

        self.expMenu.addSeparator()
        self.actConnect = QAction('&Connect')
        self.actConnect.setIcon(QIcon(getResource("connected.png")))
        self.actConnect.setShortcut(QKeySequence("F9"))
        self.expMenu.addAction(self.actConnect)
        self.actConnect.triggered.connect(self.connect)

        self.actDisconnect = QAction('&Disconnect')
        self.actDisconnect.setEnabled(False)
        self.actDisconnect.setIcon(QIcon(getResource("disconnected.png")))
        self.actDisconnect.setShortcut(QKeySequence("F10"))
        self.actSendParameter = QAction('&Send all parameter')
        self.actSendParameter.setEnabled(False)
        self.actSendParameter.setShortcut(QKeySequence("F7"))
        self.expMenu.addAction(self.actSendParameter)
        self.actSendParameter.triggered.connect(self.sendParameter)
        self.actSendChangedParameter = QAction('&Send changed parameter')
        self.actSendChangedParameter.setEnabled(False)
        self.actSendChangedParameter.setShortcut(QKeySequence("F8"))
        self.expMenu.addAction(self.actSendChangedParameter)
        self.actSendChangedParameter.triggered.connect(self.sendChangedParameter)
        self.expMenu.addAction(self.actDisconnect)
        self.actDisconnect.triggered.connect(self.disconnect)
        self.expMenu.addSeparator()
        self.expMenu.addAction(self.actStartExperiment)
        self.expMenu.addAction(self.actStopExperiment)
        self.expMenu.addAction(self.actSendParameter)
        self.expMenu.addAction(self.actSendChangedParameter)

        # toolbar
        self.toolbarExp = QToolBar("Experiment")
        self.toolbarExp.setContextMenuPolicy(Qt.PreventContextMenu)
        self.toolbarExp.setMovable(False)
        self.toolbarExp.setIconSize(iconSize)
        self.addToolBar(self.toolbarExp)
        self.toolbarExp.addAction(self.actConnect)
        self.toolbarExp.addAction(self.actDisconnect)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actStartExperiment)
        self.toolbarExp.addAction(self.actStopExperiment)
        self.toolbarExp.addSeparator()
        vSpacer = QWidget()
        vSpacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbarExp.addWidget(vSpacer)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addWidget(self.visComboBox)

        self._currentExpListItem = None
        self._currentLastMeasItem = None
        self._currentDataPointBuffers = None
        self.plotCharts = []

        loadExpFromFileSuccess = self.loadExpFromFile(fileName)

        self.standardDockState = self.area.saveState()

        self.exp = ExperimentInteractor(self.targetView, self)
        self.exp.sendData.connect(self.writeToConnection)
        self.runExp.connect(self.exp.runExperiment)
        self.stopExp.connect(self.exp.stopExperiment)
        self.exp.expFinished.connect(self.saveLastMeas)
        self.exp.expStop.connect(self.stopExperiment)

        self.visualizer = None

        self._updateExperimentsList()

        if loadExpFromFileSuccess:
            self._applyFirstExperiment()
            self.selectedExp = True

        # close splash screen
        self.splashScreen.finish(self)

    def visualizerChanged(self, idx):
        for i in reversed(range(self.animationLayout.count())):
            self.animationLayout.itemAt(i).widget().setParent(None)

        visName = self.visComboBox.itemText(idx)
        availableVis = getRegisteredVisualizers()

        for aVis in availableVis:
            if aVis[1] == visName:
                self.setVisualizer(aVis[0])
                break

    def _getTcpMenu(self, settings):
        # ip and port
        ip, port, ok = DataTcpIpDialog.getData(ip=settings['ip'], port=settings['port'])

        if ok:
            settings['ip'] = ip
            settings['port'] = port

    def _getSerialMenu(self, serialMenu, settings):
        # port
        portMenu = serialMenu.addMenu("Port")
        portMenu.aboutToShow.connect(lambda: self.getComPorts(settings, portMenu))

        # baud
        baudMenu = serialMenu.addMenu("Baud")
        baudMenu.aboutToShow.connect(lambda: self.getBauds(settings, baudMenu))

        return serialMenu

    def getBauds(self, settings, connMenu):
        """
        Sets the baud rate in serial connection menu
        :param settings: serial connection settings
        :param connMenu: serial connection menu
        """

        def setBaud(baud):
            def fn():
                settings['baud'] = baud

            return fn

        baud = settings['baud']
        bauds = ['1200', '2400', '4800', '9600', '14400', '19200', '28800',
                 '38400', '57600', '115200', '125000', '250000', '500000']
        connMenu.clear()
        for _baud in bauds:
            baudAction = QAction(_baud, self)
            baudAction.setCheckable(True)
            baudAction.setChecked(True if _baud in str(baud) else False)
            baudAction.triggered.connect(setBaud(_baud))
            connMenu.addAction(baudAction)

    def setDefaultComPort(self, settings, cnt):
        """
        Sets the default port in given connection settings if an Arduino can found. If more than one Arduino can found,
        the counter describes the connection number.
        :param settings: serial connection settings
        :param cnt: counter for serial connection
        """
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]

            if len(arduinoPorts) != 0 and len(arduinoPorts) >= cnt:
                settings['port'] = arduinoPorts[cnt]
            else:
                self._logger.warning("Can't set comport for Arduino automatically! Set the port manually!")
        else:
            self._logger.warning("No ComPorts for Arduino available, connect a device!")

    def getComPorts(self, settings, connMenu):
        """

        :param settings:
        :param connMenu:
        """

        def setPort(port):
            def fn():
                settings['port'] = port

            return fn

        port = settings['port']
        connMenu.clear()
        comPorts = serial.tools.list_ports.comports()
        if comPorts:
            if port == '':
                arduinoPorts = [p.device for p in comPorts if 'Arduino' in p.description]
                if len(arduinoPorts) != 0:
                    port = arduinoPorts[0]
                    settings['port'] = port
            for p in comPorts:
                portAction = QAction(p.device, self)
                portAction.setCheckable(True)
                portAction.setChecked(True if p.device in port else False)
                portAction.triggered.connect(setPort(p.device))
                connMenu.addAction(portAction)
        else:
            noAction = QAction("(None)", self)
            noAction.setEnabled(False)
            connMenu.addAction(noAction)

    def _updateExperimentsList(self):
        self.experimentList.clear()
        for exp in self._experiments:
            self._logger.debug("Add '{}' to experiment list".format(exp["Name"]))
            self.experimentList.addItem(exp["Name"])

    def setTimerTime(self):
        """
        Sets the timer time in settings with a dialog.
        """
        self._settings.beginGroup('plot')
        timerTime, ok = DataIntDialog.getData(title="Timer Time", min=2, max=10000, unit='ms',
                                              current=self.config['TimerTime'])

        if ok:
            self.config['TimerTime'] = timerTime
            self._logger.info("Set timer time to {}".format(timerTime))

        self._settings.endGroup()

    def _addSetting(self, group, setting, value):
        """
        Adds a setting, if setting is present, no changes are made.
        :param setting (str): Setting to add.
        :param value: Value to be set.
        """
        if not self._settings.contains(group + '/' + setting):
            self._settings.beginGroup(group)
            self._settings.setValue(setting, value)
            self._settings.endGroup()

    def _initSettings(self):
        """
        Provides initial settings for view, plot and log management.
        """
        # path management
        self._addSetting("path", "previous_plot_export", os.path.curdir)
        self._addSetting("path", "previous_plot_format", ".csv")

        # view management
        self._addSetting("view", "show_coordinates", "True")

        # log management
        self._addSetting("log_colors", "CRITICAL", "#DC143C")
        self._addSetting("log_colors", "ERROR", "#B22222")
        self._addSetting("log_colors", "WARNING", "#DAA520")
        self._addSetting("log_colors", "INFO", "#101010")
        self._addSetting("log_colors", "DEBUG", "#4682B4")
        self._addSetting("log_colors", "NOTSET", "#000000")

        # plot management
        self._addSetting("plot_colors", "blue", "#1f77b4")
        self._addSetting("plot_colors", "orange", "#ff7f0e")
        self._addSetting("plot_colors", "green", "#2ca02c")
        self._addSetting("plot_colors", "red", "#d62728")
        self._addSetting("plot_colors", "purple", "#9467bd")
        self._addSetting("plot_colors", "brown", "#8c564b")
        self._addSetting("plot_colors", "pink", "#e377c2")
        self._addSetting("plot_colors", "gray", "#7f7f7f")
        self._addSetting("plot_colors", "olive", "#bcbd22")
        self._addSetting("plot_colors", "cyan", "#17becf")

    def updateCoordInfo(self, pos, widget, coordItem):
        self.coordLabel.setVisible(True)
        self.coordTimer.start(5000)
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

    def disableCoord(self):
        self.coordLabel.setVisible(False)
        self.coordTimer.stop()

    # event functions
    def addPlotTreeItem(self, default=False):
        text = "plot_{:03d}".format(self.dataPointTreeWidget.topLevelItemCount())
        if not default:
            name, ok = QInputDialog.getText(self,
                                            "Select a plot title",
                                            "Name of the new plot:",
                                            text=text)
            if not (ok and name):
                return
        else:
            name = text

        similarItems = self.dataPointTreeWidget.findItems(name, Qt.MatchExactly)
        if similarItems:
            self._logger.error("Name '{}' exists.".format(name))
            return

        topLevelItem = QTreeWidgetItem()
        topLevelItem.setText(0, name)
        self.dataPointTreeWidget.addTopLevelItem(topLevelItem)
        topLevelItem.setExpanded(1)

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
        buttonReply = QMessageBox.warning(self, "Plot delete", text, QMessageBox.Ok | QMessageBox.Cancel)
        if buttonReply == QMessageBox.Ok:
            openDocks = [dock.title() for dock in self.findAllPlotDocks()]
            if item.text(0) in openDocks:
                self.area.docks[item.text(0)].close()

            self.dataPointTreeWidget.takeTopLevelItem(self.dataPointTreeWidget.indexOfTopLevelItem(item))

    def addDatapointToTree(self):
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

        for idx, dataPoint in enumerate(self.dataPointListWidget.selectedItems()):
            if dataPoint.text() not in topLevelItemList:
                child = QTreeWidgetItem()
                child.setText(1, dataPoint.text())

                toplevelItem.addChild(child)

        for i in range(toplevelItem.childCount()):
            self._settings.beginGroup('plot_colors')
            cKeys = self._settings.childKeys()
            colorIdxItem = i % len(cKeys)
            colorItem = QColor(self._settings.value(cKeys[colorIdxItem]))
            self._settings.endGroup()
            toplevelItem.child(i).setBackground(0, colorItem)

        self.plots(toplevelItem)

    def exportDataPointFromTree(self):
        if not self.dataPointListWidget.selectedIndexes():
            self._logger.error("Can't export data set: no data set selected.")
            return

        if self._currentLastMeasItem is None:
            self._logger.error("Nothing to export!")
            return

        idx = self.lastMeasList.row(self._currentLastMeasItem)
        dataPointBuffers = self.measurements[idx]['dataPointBuffers']

        dataPoints = dict()
        for item in self.dataPointListWidget.selectedItems():
            for key, value in dataPointBuffers.items():
                if key == item.text():
                    dataPoints[key] = value
                    break

        self.export(dataPoints)

    def removeDatapointFromTree(self):
        items = self.dataPointTreeWidget.selectedItems()
        if not items:
            self._logger.error("Cannot delete dataset: No dataset selected.")
            return

        toplevelItem = items[0]
        while toplevelItem.parent():
            toplevelItem = toplevelItem.parent()

        toplevelItem.takeChild(toplevelItem.indexOfChild(self.dataPointTreeWidget.selectedItems()[0]))

        for i in range(toplevelItem.childCount()):
            self._settings.beginGroup('plot_colors')
            cKeys = self._settings.childKeys()
            colorIdxItem = i % len(cKeys)
            colorItem = QColor(self._settings.value(cKeys[colorIdxItem]))
            self._settings.endGroup()
            toplevelItem.child(i).setBackground(0, colorItem)

        self.plots(toplevelItem)

    def plots(self, item):
        title = item.text(0)

        if self._currentLastMeasItem is None:
            self._logger.warning("No Measurement to plot!")
            return

        idx = self.lastMeasList.row(self._currentLastMeasItem)
        dataPointBuffers = self.measurements[idx]['dataPointBuffers']

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
                self.updatePlot(item, dataPointBuffers)

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
            if self._currentLastMeasItem is None:
                dataPointNames = self.exp.getDataPoints()
                dataPointBuffers = dict()
                for data in dataPointNames:
                    dataPointBuffers[data] = DataPointBuffer()
            else:
                idx = self.lastMeasList.row(self._currentLastMeasItem)
                dataPointBuffers = self.measurements[idx]['dataPointBuffers']

            self.updatePlot(item, dataPointBuffers)
            try:
                self.area.docks[title].raiseDock()
            except:
                pass
        else:
            self.plotDataVector(item)

    def updatePlot(self, item, dataPointBuffers):
        title = item.text(0)

        # get the new datapoints
        newDataPoints = dict()
        for indx in range(item.childCount()):
            for key, value in dataPointBuffers.items():
                if key == item.child(indx).text(1):
                    newDataPoints[key] = value

        # set the new datapoints
        for chart in self.plotCharts:
            if chart.title == title:
                chart.clear()
                for key, value in newDataPoints.items():
                    chart.addPlotCurve(key, value)
                chart.updatePlot()
                break

    def plotDataVector(self, item):
        title = str(item.text(0))

        # create plot widget
        widget = PlotWidget()
        chart = PlotChart(title,
                          self._settings,
                          self.config['InterpolationPoints'],
                          self.config['MovingWindowEnable'],
                          self.config['MovingWindowSize'])
        chart.plotWidget = widget
        widget.showGrid(True, True)
        widget.getPlotItem().getAxis("bottom").setLabel(text="Time", units="s")

        if self._currentLastMeasItem is None:
            dataPointNames = self.exp.getDataPoints()
            dataPointBuffers = dict()
            for name in dataPointNames:
                dataPointBuffers[name] = DataPointBuffer()
        else:
            idx = self.lastMeasList.row(self._currentLastMeasItem)
            dataPointBuffers = self.measurements[idx]['dataPointBuffers']

        for idx in range(item.childCount()):
            for key, value in dataPointBuffers.items():
                if key == item.child(idx).text(1):
                    chart.addPlotCurve(key, value)

        # before adding the PlotChart object to the list check if the plot contains any data points
        if chart.dataPoints is not None:
            self.plotCharts.append(chart)
        else:
            return

        chart.updatePlot()

        coordItem = TextItem(text='', anchor=(0, 1))
        widget.getPlotItem().addItem(coordItem, ignoreBounds=True)

        def infoWrapper(pos):
            self.updateCoordInfo(pos, widget, coordItem)

        widget.scene().sigMouseMoved.connect(infoWrapper)

        qActionSep1 = QAction("", self)
        qActionSep1.setSeparator(True)
        qActionSep2 = QAction("", self)
        qActionSep2.setSeparator(True)
        qActionSep3 = QAction("", self)
        qActionSep3.setSeparator(True)

        qActionMovingWindowEnable = QAction('Enable', self, checkable=True)
        qActionMovingWindowEnable.setChecked(self.config['MovingWindowEnable'])
        qActionMovingWindowEnable.triggered.connect(lambda state, _chart=chart: self.enableMovingWindow(state, _chart))

        qActionMovingWindowSize = ContextLineEditAction(min=0, max=10000, current=chart.getMovingWindowWidth(),
                                                        unit='s', title='Size', parent=self)
        qActionMovingWindowSize.dataEmit.connect(lambda data,
                                                        _chart=chart,
                                                        _widget=widget: self.setMovingWindowWidth(data, _chart,
                                                                                                  _widget))

        qActionInterpolationPoints = ContextLineEditAction(min=0, max=10000, current=chart.getInterpolataionPoints(),
                                                           unit='', title='Size', parent=self)
        qActionInterpolationPoints.dataEmit.connect(lambda data,
                                                           _chart=chart: self.setInterpolationPoints(data, _chart))

        qMenuMovingWindow = QMenu('Moving Window', self)
        qMenuMovingWindow.addAction(qActionMovingWindowSize)
        qMenuMovingWindow.addAction(qActionMovingWindowEnable)

        qMenuInterpolation = QMenu('Interpolation Points', self)
        qMenuInterpolation.addAction(qActionInterpolationPoints)

        widget.scene().contextMenu = [qActionSep1,
                                      QAction("Auto Range All", self),
                                      qActionSep2,
                                      QAction("Export as ...", self),
                                      qActionSep3,
                                      qMenuMovingWindow,
                                      qMenuInterpolation,
                                      ]

        def _export_wrapper(export_func):
            def _wrapper():
                return export_func(widget.getPlotItem(), )

            return _wrapper

        widget.scene().contextMenu[1].triggered.connect(lambda: self.setAutoRange(widget))
        widget.scene().contextMenu[3].triggered.connect(_export_wrapper(self.exportPlotItem))

        # create dock container and add it to dock area
        dock = Dock(title, closable=True)
        dock.addWidget(widget)
        dock.sigClosed.connect(self.closedDock)

        plotWidgets = self.findAllPlotDocks()
        if plotWidgets:
            self.area.addDock(dock, "above", plotWidgets[0])
        else:
            self.area.addDock(dock, "bottom", self.animationDock)

    def setInterpolationPoints(self, data, chart):
        """
        Sets the interpolation points in settings with a dialog.
        """
        chart.setInterpolationPoints(int(data))

    def setMovingWindowWidth(self, data, chart, widget):
        """
        Sets the moving window width and autorange.
        """
        chart.setMovingWindowWidth(int(data))
        widget.autoRange()
        widget.enableAutoRange()

    def enableMovingWindow(self, state, chart):
        chart.setEnableMovingWindow(state)

    def closedDock(self):
        """
        Gets called when a dock was closed, if it was a plot dock remove the corresponding PlotChart object
        form the list

        """
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        for indx, plot in enumerate(self.plotCharts):
            if not plot.title in openDocks:
                self.plotCharts.pop(indx)

        if len(self.findAllPlotDocks()) == 0:
            self.disableCoord()

    def setAutoRange(self, widget):
        widget.autoRange()
        widget.enableAutoRange()

    def exportPlotItem(self, plotItem):
        dataPoints = dict()
        for i, c in enumerate(plotItem.curves):
            if c.getData() is None:
                continue
            if len(c.getData()) > 2:
                self._logger.warning('Can not handle the amount of data!')
                continue
            dataPoints[c.name()] = DataPointBuffer(time=c.getData()[0], values=c.getData()[1])

        self.export(dataPoints)

    def export(self, dataPoints):
        try:
            exporter = Exporter(dataPoints=dataPoints)
        except Exception as e:
            self._logger.error("Can't instantiate exporter! " + str(e))
            return

        lastPath = self._settings.value("path/previous_plot_export")
        lastFormat = self._settings.value("path/previous_plot_format")
        exportFormats = ["CSV Data (*.csv)", "PNG Image (*.png)"]
        if lastFormat == ".png":
            exportFormats[:] = exportFormats[::-1]
        formatStr = ";;".join(exportFormats)
        defaultFile = os.path.join(lastPath, "export" + lastFormat)
        filename = QFileDialog.getSaveFileName(self,
                                               "Export as ...",
                                               defaultFile,
                                               formatStr)

        if filename[0]:
            file, ext = os.path.splitext(filename[0])
            self._settings.setValue("path/previous_plot_export",
                                    os.path.dirname(file))
            if ext == '.csv':
                exporter.exportCsv(filename[0])
            elif ext == '.png':
                exporter.exportPng(filename[0])
            else:
                self._logger.error("Wrong extension used!")
                return
            self._logger.info("Export successful as '{}.".format(filename[0]))

    @pyqtSlot(QModelIndex)
    def targetViewChanged(self, index=None):
        self.targetView.resizeColumnToContents(0)

    @pyqtSlot()
    def updateShowCoordsSetting(self):
        self._settings.setValue("view/show_coordinates", str(self.actShowCoords.isChecked()))

    @pyqtSlot()
    def startExperiment(self):
        """
        Starts the experiment, the timer, and the connections. Disables the start button.
        """
        self._currentExperimentIndex = self.experimentList.row(self._currentExpListItem)
        self._currentExperimentName = self._experiments[self._currentExperimentIndex]["Name"]

        self._settings.beginGroup('plot')
        self._settings.endGroup()

        if self._currentExperimentIndex is None:
            expName = ""
        else:
            expName = str(self.experimentList.item(self._currentExperimentIndex).text())

        self._logger.info("Experiment: {}".format(expName))

        self.actStartExperiment.setDisabled(True)
        self.actStopExperiment.setDisabled(False)
        self.actSendParameter.setDisabled(False)
        self.actSendChangedParameter.setDisabled(False)
        if self._currentExperimentIndex is not None:
            self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(Qt.darkGreen))
            self.experimentList.repaint()

        dataPointNames = self.exp.getDataPoints()

        if dataPointNames:
            self._currentDataPointBuffers = dict()
            for data in dataPointNames:
                self._currentDataPointBuffers[data] = DataPointBuffer()
        else:
            return

        for chart in self.plotCharts:
            chart.updatePlot()

        data = {}
        data.update({'dataPointBuffers': self._currentDataPointBuffers})
        data.update({'exp': deepcopy(self.exp.getExperiment())})
        self.measurements.append(data)

        item = QListWidgetItem(str(self.lastMeasList.count() + 1) + ": "
                               + self._currentExperimentName + " ~current~")
        self.lastMeasList.addItem(item)
        self.lastMeasList.scrollToItem(item)
        self.copyLastMeas(item)

        for conn, connInstance in self.connections.items():
            if connInstance:
                connInstance.doRead = True

        self.timer.start(int(self.config['TimerTime']))
        if self.config['HeartbeatTime']:
            self.heartbeatTimer.start(int(self.config['HeartbeatTime']))
        self.exp.runExperiment()

        self.guiStartTime = time.time()
        self.updateGuiTimeLabel()
        self.guiTimer.start(1000)

    @pyqtSlot()
    def stopExperiment(self):
        """
        Stops the experiment, the timer, clears the connections, and enables the start button.
        """
        if self.selectedExp:
            self.actStartExperiment.setDisabled(False)
        self.actStopExperiment.setDisabled(True)
        self.actSendParameter.setDisabled(True)
        self.actSendChangedParameter.setDisabled(True)
        for i in range(self.experimentList.count()):
            self.experimentList.item(i).setBackground(QBrush(Qt.white))
        self.experimentList.repaint()

        self.timer.stop()
        self.heartbeatTimer.stop()
        self.exp.stopExperiment()

        time.sleep(1)

        for conn, connInstance in self.connections.items():
            if connInstance:
                connInstance.doRead = False
                connInstance.clear()

        self.guiTimer.stop()

    def sendParameter(self):
        """
        Sends all parameters of the current experiment with `ExperimentInteractor` function `sendParameterExperiment`
        """
        if self._currentExperimentIndex == self.experimentList.row(self._currentExpListItem) and \
                "~current~" in self._currentLastMeasItem.text():
            self.exp.sendParameterExperiment()
        else:
            self._logger.warning("Selected Experiment '{}' doesn't match current running Experiment '{}'!".format(
                self._currentExperimentName,
                self._experiments[self.experimentList.row(self._currentExpListItem)]["Name"]))

    def sendChangedParameter(self):
        """
        Sends changed parameters of the current experiment with `ExperimentInteractor`
        function `sendChangedParameterExperiment`
        """
        if self._currentExperimentIndex == self.experimentList.row(self._currentExpListItem) and \
                "~current~" in self._currentLastMeasItem.text():
            self.exp.sendChangedParameterExperiment()
        else:
            self._logger.warning("Selected Experiment '{}' doesn't match current running Experiment '{}'!".format(
                self._currentExperimentName,
                self._experiments[self.experimentList.row(self._currentExpListItem)]["Name"]))

    def loadExpFromFile(self, fileName):
        """
        Loads experiments from file
        :param fileName: name of the file with experiments
        """
        success = True
        if fileName is None:
            if os.path.isfile('default.sreg'):
                fileName = 'default.sreg'
            else:
                self._logger.error('No default.sreg found!')
                success = False
        else:
            if not os.path.isfile(fileName):
                self._logger.error('Config file {} does not exists!'.format(fileName))
                success = False

        if success:
            self._logger.info("Load config file: {0}".format(fileName))

            with open(fileName.encode(), "r") as f:
                self._experiments = yaml.load(f, Loader=Loader)

            self._logger.info("Loading {} experiments".format(len(self._experiments)))

        return success

    def _applyFirstExperiment(self):
        """
        Applies the first experiment update the experiment index.
        :return: `True` if successful, `False` if errors occurred
        """
        idx = 0

        # apply
        success = self._applyExperimentByIdx(idx)
        self._currentExpListItem = self.experimentList.item(idx)

        self.setQListItemBold(self.experimentList, self._currentExpListItem, success)
        self.setQListItemBold(self.lastMeasList, self._currentExpListItem, success)

        dataPointNames = self.exp.getDataPoints()

        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        if success:
            self.configureRemote(idx)
            self.configureVisualizer(idx)
            self.configureConfig(idx)
            self.targetViewChanged()

        return success

    def configureConfig(self, idx):
        self.config = self.configDefaults.copy()
        if 'Config' not in self._experiments[idx]:
            return
        for key, value in self._experiments[idx]['Config'].items():
            if key in self.config:
                self.config[key] = value
            else:
                self._logger.warning("Experiment config key '{}' does not exist.\n\
                Possible keys: {}".format(key, [key for key in self.config.keys()]))

    def configureRemote(self, idx):
        self.remoteWidgetLayout.clearAll()

        if 'Remote' not in self._experiments[idx]:
            return
        if self._experiments[idx] is None:
            self._logger.warning("Remote not correct configured in file!")
            return
        for name in self._experiments[idx]['Remote']:
            config = self._experiments[idx]['Remote'][name]
            config['name'] = name
            self.remoteAddWidget(config)

    def configureVisualizer(self, idx):
        if self.visualizer is not None:
            for i in reversed(range(self.animationLayout.count())):
                self.animationLayout.itemAt(i).widget().setParent(None)
        availableVis = getRegisteredVisualizers()
        used = []
        if availableVis and 'Visu' in self._experiments[idx]:
            if self._experiments[idx]['Visu'] is not None:
                for vis in self._experiments[idx]['Visu']:
                    for avis in availableVis:
                        if vis == avis[1]:
                            used.append(avis)
                            break
            else:
                self._logger.warning("No Visualization configured!")
                self.visualizer = None

        if not used:
            return

        for vis in used:
            self.visComboBox.addItem(vis[1])
        self.visComboBox.currentIndexChanged.connect(self.visualizerChanged)
        self._logger.info("loading visualizer '{}'".format(used[0][1]))
        self.setVisualizer(used[0][0])

    def setVisualizer(self, vis):
        if issubclass(vis, MplVisualizer):
            self.visualizer = vis(self.animationWidget,
                                  self.animationLayout)
            self.animationDock.addWidget(self.animationWidget)
        elif issubclass(vis, VtkVisualizer):
            if vtk_available:
                # vtk window
                self.animationFrame = QFrame()
                self.vtkWidget = QVTKRenderWindowInteractor(self.animationFrame)
                self.animationLayout.addWidget(self.vtkWidget)
                self.animationFrame.setLayout(self.animationLayout)
                self.animationDock.addWidget(self.animationFrame)
                self.vtkRenderer = vtkRenderer()
                self.vtkWidget.GetRenderWindow().AddRenderer(self.vtkRenderer)
                self.visualizer = vis(self.vtkRenderer)
                self.vtkWidget.Initialize()
            else:
                self._logger.warning("visualizer depends on vtk which is "
                                     "not available on this system!")

    @pyqtSlot(QListWidgetItem)
    def experimentDclicked(self, item):
        """
        Apply the selected experiment to the current target and set it bold.
        :param item: item of the experiment in the `ExperimentList`
        """
        idx = self.experimentList.row(item)
        success = self._applyExperimentByIdx(idx)
        self._currentExpListItem = item

        self.setQListItemBold(self.experimentList, item, success)
        self.setQListItemBold(self.lastMeasList, item, success)

        dataPointNames = self.exp.getDataPoints()

        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        if success:
            self.configureRemote(idx)
            self.configureVisualizer(idx)
            self.configureConfig(idx)

            if self.isConnected:
                # check if experiment runs
                if not self.actStopExperiment.isEnabled():
                    self.actStartExperiment.setDisabled(False)
            self.selectedExp = True

    def _applyExperimentByIdx(self, index=0):
        """
        Applies the given experiment.
        :param index: Index of the experiment in the `ExperimentList`
        :return: `True` if successful, `False` if errors occurred
        """
        if index >= len(self._experiments):
            self._logger.error("applyExperiment: index error! ({})".format(index))
            return False

        expName = self._experiments[index]["Name"]
        self._logger.info("Experiment '{}' applied".format(expName))

        if self.isConnected:
            # check if experiment runs
            if not self.actStopExperiment.isEnabled():
                self.actStartExperiment.setDisabled(False)
        sucess = self.exp.setExperiment(self._experiments[index])
        if sucess:
            self._currentExperimentIndex = index
            self._currentExperimentName = self._experiments[index]['Name']
            self.targetViewChanged()
        return sucess

    def closeEvent(self, QCloseEvent):
        """
        Is called by closing the GUI. Disconnects all connections and sends close event.
        :param QCloseEvent:
        """
        if self.isConnected:
            self.disconnect()
        self._logger.info("Close Event received, shutting down.")
        logging.getLogger().removeHandler(self.textLogger)
        super().closeEvent(QCloseEvent)

    @pyqtSlot()
    def connect(self):
        """
        Connects all connections and sets the button states.
        """
        for conn, _ in self.connections.items():
            connInstance = conn()
            self.connections[conn] = connInstance
            if connInstance.connect():
                self._logger.info("Connection for {} established!".format(conn.__name__))
                self.actConnect.setEnabled(False)
                self.actDisconnect.setEnabled(True)
                if self._currentExpListItem is not None and self.selectedExp:
                    self.actStartExperiment.setEnabled(True)
                self.actStopExperiment.setEnabled(False)
                self.statusbarLabel.setText("Connected!")
                connInstance.received.connect(lambda frame, conn=conn: self.updateData(frame, conn))
                connInstance.start()
                self.isConnected = True
            else:
                self.connections[conn] = None
                self._logger.warning("No connection for {} established! Check your settings!".format(conn.__name__))
                self.isConnected = False
                return

    def writeToConnection(self, data):
        """
        PySignal function, that sends the given data to the connections
        :param data: to send data
        """
        for conn, connInstance in self.connections.items():
            if connInstance and data['id'] == 1:
                connInstance.writeData(data)
            elif connInstance and data['connection'] == conn.__name__:
                connInstance.writeData(data)

    @pyqtSlot()
    def disconnect(self):
        """
        Disconnects all connections and resets the button states.
        """
        if self.actStopExperiment.isEnabled():
            self.stopExperiment()

        for conn, connInstance in self.connections.items():
            if connInstance:
                connInstance.disconnect()
                connInstance.received.disconnect()
                self.connections[conn] = None
        self.actConnect.setEnabled(True)
        self.actDisconnect.setEnabled(False)
        self.actStartExperiment.setEnabled(False)
        self.actStopExperiment.setEnabled(False)
        self.statusbarLabel.setText('Not Connected')
        self.isConnected = False

    def findAllPlotDocks(self):
        """
        Finds all docks with plots inside
        :return: list of docks with plots
        """
        list = []
        for title, dock in self.area.findAll()[1].items():
            if title in self.nonPlottingDocks:
                continue
            else:
                list.append(dock)

        return list

    def updateData(self, frame, connection):
        data = self.exp.handleFrame(frame, connection)
        if data is None:
            return
        time = data['Time'] / 1000.0
        dataPoints = data['DataPoints']
        names = data['DataPoints'].keys()

        for key, value in self._currentDataPointBuffers.items():
            if key in names:
                value.addValue(time, dataPoints[key])

        time_text = "Exp time={:02d}:{:02d}:{:02d}".format(int(time // 3600), int(time // 60), int(time % 60))
        self.expTimeLabel.setText(time_text)

    def updateDataPlots(self):
        if self.visualizer:
            self.visualizer.update(self._currentDataPointBuffers)

        for chart in self.plotCharts:
            chart.updatePlot()

    def heartbeat(self):
        self.writeToConnection({'id': 1,
                                'msg': bytes([1 << 1])})

    def loadStandardDockState(self):
        """
        Loads the standard dock configuration of the GUI
        """
        self.plotCharts.clear()

        for dock in self.findAllPlotDocks():
            dock.close()
        self.area.restoreState(self.standardDockState)

    def saveLastMeas(self):
        """
        Saves at the end of an experiment the data in the measurements dict
        """
        if self._currentExperimentIndex is None:
            return

        items = self.lastMeasList.findItems('~current~', Qt.MatchContains)
        if len(items) != 1:
            self._logger.warning('Error, more than one ~current~ measurement available. Using first one!')

        item = items[0]
        item.setText(item.text().replace(' ~current~', ''))

        idx = self.lastMeasList.row(item)
        self.measurements[idx].update({'dataPointBuffers': deepcopy(self._currentDataPointBuffers)})

    def copyLastMeas(self, item):
        self._currentLastMeasItem = item
        idx = self.lastMeasList.row(item)

        measurement = self.measurements[idx]

        dataPointNames = self.exp.getDataPoints()
        dataPointBuffers = measurement['dataPointBuffers']
        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        for i in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.updatePlot(self.dataPointTreeWidget.topLevelItem(i), dataPointBuffers)

    def loadLastMeas(self, item):
        """
        Loads the measurement data from the measurement dict by given item from last measurement list
        :param item: last measurement list item
        """
        self.actStartExperiment.setDisabled(True)
        self.selectedExp = False
        self.remoteWidgetLayout.clearAll()

        expName = str(item.text())
        self._currentLastMeasItem = item
        try:
            idx = self.lastMeasList.row(item)
        except ValueError:
            self._logger.error("loadLastMeas(): No measurement called '{0}".format(expName))
            return False

        if idx >= len(self.measurements):
            self._logger.error("loadLastMeas(): Invalid index '{}')".format(idx))
            return False

        self._logger.info("Restore of measurement '{}'".format(expName))

        measurement = self.measurements[idx]

        success = self.exp.setExperiment(measurement['exp'])

        self.setQListItemBold(self.lastMeasList, item, success)
        self.setQListItemBold(self.experimentList, item, success)

        dataPointNames = self.exp.getDataPoints()
        dataPointBuffers = measurement['dataPointBuffers']
        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        for i in range(self.dataPointTreeWidget.topLevelItemCount()):
            self.updatePlot(self.dataPointTreeWidget.topLevelItem(i), dataPointBuffers)

        self._logger.info("Apply measurement '{}'".format(measurement['exp']['Name']))

    def updateDataPoints(self, dataPointNames):
        """
        Clears and adds all given data point names to list widget
        :param dataPointNames: list of data point names
        """
        if dataPointNames:
            self.dataPointListWidget.clear()
            self.dataPointListWidget.addItems(dataPointNames)

    def setQListItemBold(self, qList=None, item=None, state=True):
        """
        Sets the bold state of the item in the given list.
        :param qList: list with item
        :param item: item that should repaint
        :param state: `True` repaint in bold, `False` repaint in without bold
        """
        for i in range(qList.count()):
            newfont = qList.item(i).font()
            if qList.item(i) == item and state:
                newfont.setBold(1)
            else:
                newfont.setBold(0)
            qList.item(i).setFont(newfont)
        qList.repaint()

    def remoteRemoveWidget(self, widget):
        idx = self.experimentList.row(self._currentExpListItem)
        del self._experiments[idx]['Remote'][widget.widgetName]
        self.remoteWidgetLayout.removeWidget(widget)

    def remoteConfigWidget(self, widget, editWidget=True):
        idx = self.experimentList.row(self._currentExpListItem)
        exp = self.exp.getExperiment()
        del exp['Name']
        config, ok = RemoteWidgetEdit.getData(exp, editWidget, **(widget.getData()))
        if not ok:
            return
        if not 'Remote' in self._experiments[idx]:
            self._experiments[idx]['Remote'] = {}
        del self._experiments[idx]['Remote'][widget.widgetName]

        widget.widgetName = config['name']
        widget.widgetType = config['widgetType']
        widget.module = config['Module']
        widget.parameter = config['Parameter']
        if config['widgetType'] == "PushButton":
            widget.valueOn = config['valueOn']
            widget.valueReset = config['valueReset']
            widget.shortcut.setKey(config['shortcut'])
        elif config['widgetType'] == "Switch":
            widget.valueOn = config['valueOn']
            widget.valueOff = config['valueOff']
            widget.shortcut.setKey(config['shortcut'])
        elif config['widgetType'] == "Slider":
            widget.minSlider = config['minSlider']
            widget.maxSlider = config['maxSlider']
            widget.stepSlider = config['stepSlider']
            widget.shortcutPlus.setKey(config['shortcutPlus'])
            widget.shortcutMinus.setKey(config['shortcutMinus'])
        self._experiments[idx]['Remote'][config['name']] = config
        widget.updateData()

    def remoteAddWidget(self, config=None, **kwargs):
        """
        Adds a new widget to the remoteDock
        :param config: RemoteWidgetEdit object containing widget parameters and information
        """
        changed = False
        idx = self.experimentList.row(self._currentExpListItem)
        exp = self.exp.getExperiment()
        del exp['Name']
        if not config:
            config, ok = RemoteWidgetEdit.getData(exp=exp, **kwargs)
            if not ok:
                return
            changed = True
            if not 'Remote' in self._experiments[idx]:
                self._experiments[idx]['Remote'] = {}
            self._experiments[idx]['Remote'][config['name']] = {}

        if changed:
            self._experiments[idx]['Remote'][config['name']] = config
        sliderLabel = None
        if config['widgetType'] == "PushButton":
            if 'valueReset' not in config:
                config['valueReset'] = ''
            widget = MovablePushButton(config['name'], config['valueOn'], config['valueReset'], config['shortcut'],
                                       module=config['Module'], parameter=config['Parameter'])
            widget.setFixedHeight(40)
            widget.setFixedWidth(100)
            widget.clicked.connect(lambda: self.remotePushButtonSendParameter(widget))
            widget.editAction.triggered.connect(lambda _: self.remoteConfigWidget(
                widget, editWidget=True))
            widget.removeAction.triggered.connect(lambda _: self.remoteRemoveWidget(widget))
        elif config['widgetType'] == "Switch":
            widget = MovableSwitch(config['name'], config['valueOn'], config['valueOff'], config['shortcut'],
                                   module=config['Module'], parameter=config['Parameter'])
            widget.setFixedHeight(40)
            widget.setFixedWidth(100)
            widget.clicked.connect(lambda: self.remoteSwitchSendParameter(widget))
            widget.editAction.triggered.connect(lambda _: self.remoteConfigWidget(
                widget, editWidget=True))
            widget.removeAction.triggered.connect(lambda _: self.remoteRemoveWidget(widget))
        elif config['widgetType'] == "Slider":
            sliderLabel = QLabel()
            sliderLabel.setFixedHeight(15)
            labelFont = sliderLabel.font()
            labelFont.setPointSize(8)
            sliderLabel.setFont(labelFont)
            self.remoteWidgetLayout.addWidget(sliderLabel)
            widget = MovableSlider(config['name'], config['minSlider'], config['maxSlider'], config['stepSlider'],
                                   sliderLabel, config['shortcutPlus'], config['shortcutMinus'],
                                   exp[config['Module']][config['Parameter']], module=config['Module'],
                                   parameter=config['Parameter'])
            widget.setFixedHeight(30)
            widget.setFixedWidth(200)
            widget.valueChanged.connect(lambda value, _wid=widget: self.remoteSliderSendParameter(_wid, value))
            widget.sliderMoved.connect(lambda value, _wid=widget: self.remoteSliderUpdate(_wid, value))
            widget.editAction.triggered.connect(lambda _: self.remoteConfigWidget(
                widget, editWidget=True))
            widget.removeAction.triggered.connect(lambda _, widget=widget: self.remoteRemoveWidget(widget))
        else:
            return
        widget.move((self.remoteWidgetLayout.count() % 2) * 200, (self.remoteWidgetLayout.count() // 2) * 40)
        if sliderLabel:
            sliderLabel.move((self.remoteWidgetLayout.count() % 2) * 200 + 80,
                             (self.remoteWidgetLayout.count() // 2) * 40 + 30)
        self.remoteWidgetLayout.addWidget(widget)

    def remotePushButtonSendParameter(self, widget):
        """
        Gets called when a user interacts with the pushbutton and sends the specified parameter to the bench
        :param widget: the widget the user interacted with
        """
        value = widget.valueOn
        self.remoteSendParamter(widget.module, widget.parameter, value)
        self.remoteSliderUpdate(widget, value, sliderMoved=False)

        if widget.valueReset != '':
            self.remoteSetParamter(widget.module, widget.parameter, widget.valueReset)

    def remoteSwitchSendParameter(self, widget):
        """
        Gets called when a user interacts with the switch and sends the specified parameter to the bench
        :param widget: the widget the user interacted with
        """
        if widget.isChecked():
            value = widget.valueOn
            widget.setText(widget.widgetName + '\n' + widget.valueOff)
        else:
            value = widget.valueOff
            widget.setText(widget.widgetName + '\n' + widget.valueOn)

        self.remoteSendParamter(widget.module, widget.parameter, value)
        self.remoteSliderUpdate(widget, value, sliderMoved=False)

    def remoteSliderSendParameter(self, widget, value):
        """
        Gets called when a user interacts with the slider and sends the specified parameter to the bench
        :param widget: the widget the user interacted with
        :param value: the actual value of the widget
        """
        self.remoteSliderUpdate(widget, value)
        self.remoteSendParamter(widget.module, widget.parameter, widget.value)

    def remoteSliderUpdate(self, widget, value, sliderMoved=True):
        """
        Gets called when a user interacts with the slider
        :param widget: the widget the user interacted with
        :param value: the actual value of the widget
        :param sliderMoved: False if gets called from another widget
        """
        if not sliderMoved:
            for wid in self.remoteWidgetLayout.list:
                if isinstance(wid, MovableSlider):
                    if wid.module == widget.module and wid.parameter == widget.parameter:
                        wid.valueChanged.disconnect()
                        wid.setValue(float(value))
                        wid.valueOn = value
                        wid.label.setText(wid.widgetName + ": {:.3f}".format(wid.value))
                        wid.valueChanged.connect(lambda value, _wid=wid: self.remoteSliderSendParameter(_wid, value))
        else:
            widget.valueOn = value

            if isinstance(widget, MovableSlider):
                value = widget.calcValue(value)

            widget.label.setText(widget.widgetName + ": {:.3f}".format(value))

    def remoteSendParamter(self, module, parameter, value):
        self.remoteSetParamter(module, parameter, value)
        if self.actSendParameter.isEnabled():
            self.sendChangedParameter()

    def remoteSetParamter(self, module, parameter, value):
        exp = deepcopy(self.exp.getExperiment())
        del exp['Name']

        for key, val in exp.items():
            if key != module:
                continue
            for k, v in val.items():
                if k != parameter:
                    continue
                exp[key][k] = value
                self.exp.editExperiment(exp)
                return

    def copyRemoteSource(self):
        text = "  Remote:\n"
        if 'Remote' in self._experiments[self._currentExperimentIndex]:
            text += yaml.dump(self._experiments[self._currentExperimentIndex]['Remote'], default_flow_style=False)
        text = text.replace("\n", "\n    ")
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def remoteWidgetMenue(self, position):
        """
        Gets called when a user opens the context menu from the remoteDock
        :param position: the position where the user opened the context menu
        """
        menu = QMenu(self)
        addAction = menu.addAction("Add widget")
        saveAction = menu.addAction("Copy remote source")
        action = menu.exec_(self.remoteWidget.mapToGlobal(position))
        if action == addAction:
            self.remoteAddWidget()
        elif action == saveAction:
            self.copyRemoteSource()

    def updateGuiTimeLabel(self):
        elapsedSeconds = time.time() - self.guiStartTime
        time_text = "GUI time={:02d}:{:02d}:{:02d}".format(int(elapsedSeconds // 3600), int(elapsedSeconds // 60),
                                                           int(elapsedSeconds % 60))
        self.guiTimeLabel.setText(time_text)
