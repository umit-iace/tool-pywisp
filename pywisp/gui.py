# -*- coding: utf-8 -*-
import logging
import os
import sys
import time
from copy import deepcopy

import serial.tools.list_ports
import yaml

# vtk
vtkErrorMsg = ""
try:
    from vtk import vtkRenderer
    # import patched class that fixes scroll problem
    from .visualization import QVTKRenderWindowInteractor

    vtkAvailable = True
except ImportError as e:
    vtkAvailable = False
    vtkErrorMsg = e
    vtkRenderer = None
    QVTKRenderWindowInteractor = None

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader
from PyQt5.QtCore import QSize, Qt, pyqtSlot, pyqtSignal, QModelIndex, QTimer, QCoreApplication
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pyqtgraph.dockarea import *

from .config import validateExperiments
from .connection import SerialConnection, SocketConnection
from .experiments import ExperimentInteractor, ExperimentView
from .registry import *
from .buffer import DataPointBuffer
from .export import Exporter
from .utils import getResource, setupLogging
from .widgets.common import PlainTextLogger, PinnedDock, TreeWidgetStyledItemDelegate
from .widgets.dialogs import DataIntDialog, DataTcpIpDialog, RemoteWidgetEdit
from .widgets.remote import FreeLayout, MovablePushButton, MovableSwitch, MovableSlider

from .visualization import MplVisualizer, VtkVisualizer
from .gamepad import getAllGamepads, openGamepad
from .settings import Settings
from .widgets.plotchart import PlotChart

__all__ = ["MainGui"]


class MainGui(QMainWindow):
    """
    Main class for the GUI
    """
    runExp = pyqtSignal()
    stopExp = pyqtSignal()

    def __init__(self, fileName=None, parent=None):
        super(MainGui, self).__init__(parent)

        # keeps a logging config of the application
        setupLogging()

        # log errors in slots instead of letting PyQt abort the application,
        # but do not replace a hook somebody else installed
        if sys.excepthook is sys.__excepthook__:
            sys.excepthook = logUncaughtException

        from . import __version__
        QCoreApplication.setOrganizationName("IACE")
        QCoreApplication.setOrganizationDomain("https://umit-tirol.at/iace")
        QCoreApplication.setApplicationVersion(__version__)
        QCoreApplication.setApplicationName(__package__)

        # general config parameters
        self.config = {'TimerTime': 40, # [] = ms
                       'HeartbeatTime': 0,
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
        self.selectedExp = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateDataPlots)
        self.heartbeatTimer = QTimer()
        self.heartbeatTimer.timeout.connect(self.heartbeat)

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

        # load settings
        self._settings = Settings()

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
        self.guiTimer.setTimerType(Qt.PreciseTimer)
        self.guiTimer.timeout.connect(
            lambda: self.guiTimeLabel.setText(
                f"GUI time={timeString(time.time()-self.guiStartTime)}"
            )
        )
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
        self.animationFrame = None
        self.animationDock.addWidget(self.animationWidget)

        # experiment dock
        self.experimentList = QListWidget(self)
        self.experimentList.setFocusPolicy(Qt.NoFocus)
        self.experimentList.setStyleSheet(QStyleSheet)
        self.experimentList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.experimentDock.addWidget(self.experimentList)
        self.experimentList.itemDoubleClicked.connect(self.experimentDoubleClicked)
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
        self.visComboBox.currentIndexChanged.connect(self.visualizerChanged)

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
        self.logBox.ensureCursorVisible()
        self.logDock.addWidget(self.logBox)

        # data dock
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
        self.dataPointRightButton.clicked.connect(self.addDataPointToTree)
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
        self.dataPointLeftButton.clicked.connect(self.removeDataPointFromTree)
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
        self.remoteWidget.customContextMenuRequested.connect(self.remoteWidgetMenu)
        self.remoteWidgetLayout = FreeLayout()
        self.remoteWidget.setLayout(self.remoteWidgetLayout)
        self.remoteDock.addWidget(self.remoteWidget)

        # menu bar
        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction("&Quit", self.close, QKeySequence(Qt.CTRL + Qt.Key_W))

        # view
        self.viewMenu = self.menuBar().addMenu('&View')
        self.actLoadStandardState = QAction('&Load default view')
        self.viewMenu.addAction(self.actLoadStandardState)
        self.actLoadStandardState.triggered.connect(self.loadStandardDockState)
        self.actShowCoords = QAction("&Show coordinates", self)
        self.actShowCoords.setCheckable(True)
        self.actShowCoords.setChecked(
            self._settings.value("view/show_coordinates", type=bool)
        )
        self.viewMenu.addAction(self.actShowCoords)
        self.actShowCoords.changed.connect(self.updateShowCoordsSetting)

        self.gamepad = None
        self.selectedGamepadId = None

        ### options
        self.optMenu = self.menuBar().addMenu('&Options')
        # timer
        self.actTimerTime = QAction("&Timer time", self)
        self.optMenu.addAction(self.actTimerTime)
        self.actTimerTime.triggered.connect(self.setTimerTime)
        # select gamepad
        self.gamepadMenu = self.optMenu.addMenu('&Select Gamepad')
        self.gamepadMenu.aboutToShow.connect(lambda: self.detectGamepads())
        # animation
        self.actSaveAnimation = QAction("&Save Animation", self, checkable=True)
        self.optMenu.addAction(self.actSaveAnimation)

        # experiment
        self.expMenu = self.menuBar().addMenu('&Experiment')
        self.connMenu = self.menuBar().addMenu('&Connections')

        availableConns = getRegisteredConnections()
        if availableConns:
            for name, cls in availableConns.items():
                self._logger.info(f"Found Connection: {name}")
                self.connections[name] = {'cls':cls}
        else:
            self._logger.error("No Connections found, return!")
            # return

        serialCnt = 0
        for name, conn in self.connections.items():
            cls = conn['cls']
            if issubclass(cls, SerialConnection):
                serialMenu = self.connMenu.addMenu(name)
                self._getSerialMenu(serialMenu, cls.settings)
                if cls.settings['port'] == '':
                    self.setDefaultComPort(cls.settings, serialCnt)
                serialCnt += 1
            elif issubclass(cls, SocketConnection):
                actTcp = self.connMenu.addAction(name)
                actTcp.triggered.connect(lambda _, settings=cls.settings: self._getTcpMenu(settings))
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
        self._dataWarnings = set()
        self.plotCharts = {}

        loadExpFromFileSuccess = self.loadExpFromFile(fileName)

        self.standardDockState = self.area.saveState()

        self.exp = ExperimentInteractor(self.targetView, self)
        self.exp.sendData.connect(self.writeToConnection)
        self.runExp.connect(self.exp.runExperiment)
        self.stopExp.connect(self.exp.stopExperiment)
        self.exp.expFinished.connect(self.saveLastMeas)
        self.exp.missedbeat.connect(self.disconnect)
        self.exp.expStop.connect(self.stopExperiment)

        self.visualizer = None
        self.vtkWidget = None

        self._updateExperimentsList()

        if loadExpFromFileSuccess:
            self._applyFirstExperiment()
            self.selectedExp = True

        self.exporter = None

        # close splash screen
        self.splashScreen.finish(self)

    def visualizerChanged(self, idx):
        for i in reversed(range(self.animationLayout.count())):
            self.animationLayout.itemAt(i).widget().setParent(None)
        if idx == -1:
            return

        visName = self.visComboBox.itemText(idx)
        available = getRegisteredVisualizers()

        try:
            self.setVisualizer(available[visName])
        except Exception:
            self._logger.exception(f"Cannot load visualizer '{visName}'")
            self.visualizer = None

    def _getTcpMenu(self, settings):
        # ip and port
        ip, port, ok = DataTcpIpDialog.getData(parent=self,ip=settings['ip'], port=settings['port'])

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

        baud = int(settings['baud'])
        connMenu.clear()
        for _baud in SerialConnection.supportedBaudrates:
            baudAction = QAction(str(_baud), self)
            baudAction.setCheckable(True)
            baudAction.setChecked(_baud == baud)
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

            if len(arduinoPorts) > cnt:
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
                portAction.setChecked(p.device == port)
                portAction.triggered.connect(setPort(p.device))
                connMenu.addAction(portAction)
        else:
            noAction = QAction("(None)", self)
            noAction.setEnabled(False)
            connMenu.addAction(noAction)

    def _updateExperimentsList(self):
        self.experimentList.clear()
        for exp in self._experiments:
            self._logger.debug(f"Add '{exp['Name']}' to experiment list")
            self.experimentList.addItem(exp["Name"])

    def detectGamepads(self):
        """ fill the gamepad menu with the connected gamepads """
        self.gamepadMenu.clear()

        gamepads = getAllGamepads()
        if not gamepads:
            noneAction = self.gamepadMenu.addAction("No gamepad found")
            noneAction.setEnabled(False)
            return

        for info in gamepads:
            action = QAction(info.name, self)
            action.setCheckable(True)
            action.setChecked(self.selectedGamepadId == info.id)
            action.triggered.connect(lambda checked, info=info: self.selectGamepad(info))
            self.gamepadMenu.addAction(action)

    def selectGamepad(self, info):
        self.stopGamepad()
        self.gamepad = openGamepad(info.id)
        if self.gamepad is not None:
            self._logger.info(f"Gamepad '{info.name}' connected")
            self.selectedGamepadId = info.id
            # the gamepad stops by itself when it is unplugged
            pad = self.gamepad
            pad.finished.connect(lambda: self._onGamepadFinished(pad))
        self.updateRemoteGamepad()

    def _onGamepadFinished(self, pad):
        if pad is self.gamepad:
            self.stopGamepad()

    def stopGamepad(self):
        if self.gamepad is not None:
            self.gamepad.stop()
            self.gamepad = None
            self.selectedGamepadId = None
            self.updateRemoteGamepad()

    def updateRemoteGamepad(self):
        """ (re-)connect all remote widgets to the current gamepad """
        for wid in self.remoteWidgetLayout.list:
            wid.updateGamepad(self.gamepad)

    def setTimerTime(self):
        """
        Sets the timer time in settings with a dialog.
        """
        # plot updates are capped at 25 fps, see startExperiment
        timerTime, ok = DataIntDialog.getData(parent=self, title="Timer Time", min=40, max=10000, unit='ms',
                                              current=self.config['TimerTime'])
        if ok and timerTime:
            timerTime = int(timerTime)
            self.config['TimerTime'] = timerTime
            self._logger.info(f"Set timer time to {timerTime}")

    def updateCoordInfo(self, coordText):
        self.coordLabel.setText(coordText)
        self.coordLabel.setVisible(True)
        self.coordTimer.start(5000)

    def disableCoord(self):
        self.coordLabel.setText("")
        self.coordTimer.stop()

    # event functions
    def addPlotTreeItem(self, default=False):
        text = f"plot_{self.dataPointTreeWidget.topLevelItemCount():03d}"
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
            self._logger.error(f"Name '{name}' exists.")
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

        if self._currentLastMeasItem is None:
            self._logger.error("Nothing to export!")
            return

        idx = self.lastMeasList.row(self._currentLastMeasItem)
        dataPointBuffers = self.measurements[idx]['dataPointBuffers']

        expLabels = [item.text()
                    for item in self.dataPointListWidget.selectedItems()]
        self._logger.info(f"Measurements selected for export are: {expLabels}")
        dataPoints = {lbl: dataPointBuffers[lbl] for lbl in expLabels}

        # snapshots share the memory, but are not affected by data that is still being added
        expData = {lbl: buf.snapshot() for lbl, buf in dataPoints.items()}
        self.exporter = Exporter(dataPoints=expData)
        self.exporter.done.connect(self.exportDone)
        self.exporter.runExport()

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

    def updatePlotChart(self, item):
        title = item.text(0)

        if self._currentLastMeasItem is None:
            self._logger.warning("No Measurement to plot!")
            return

        idx = self.lastMeasList.row(self._currentLastMeasItem)
        dataPointBuffers = self.measurements[idx]['dataPointBuffers']

        # check if a top level item has been clicked
        if not item.parent():
            if title in self.nonPlottingDocks:
                self._logger.error(f"Title '{title}' not allowed for a plot window since"
                                   "it would shadow on of the reserved "
                                   "names")
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
                ubLabels = [lbl for lbl in chart.plotCurves.keys()
                    if lbl not in reqLabels]
                [chart.removeCurve(lbl) for lbl in ubLabels]

    def plotVectorClicked(self, item):
        # ignore non-top level items
        if item.parent():
            return

        title = item.text(0)
        if title in self.nonPlottingDocks:
            self._logger.error(f"Title '{title}' not allowed for a plot window since"
                               "it would shadow on of the reserved "
                               "names")
            return

        # check if plot has already been opened
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        if title in openDocks:
            # dataPointBuffers = self.getCurrentDataPoints()
            # self.updatePlot(item, dataPointBuffers)
            dock = self.area.docks.get(title)
            if dock is not None:
                dock.raiseDock()
        else:
            self.plotDataVector(item)

    def getCurrentDataPoints(self):
        if self._currentLastMeasItem is None:
            dataPointNames = self.exp.getDataPoints()
            dataPointBuffers = dict()
            for data in dataPointNames:
                dataPointBuffers[data] = DataPointBuffer()
        else:
            idx = self.lastMeasList.row(self._currentLastMeasItem)
            dataPointBuffers = self.measurements[idx]['dataPointBuffers']
        return dataPointBuffers

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
        chart = PlotChart(title, self.config)
        chart.coords.connect(self.updateCoordInfo)
        self.plotCharts[title] = chart

        # add curves
        dataPointBuffers = self.getCurrentDataPoints()
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
            self.area.addDock(dock, "bottom", self.animationDock)

    def closedDock(self):
        """
        Gets called when a dock was closed, if it was a plot dock remove the corresponding PlotChart object
        form the list
        """
        openDocks = [dock.title() for dock in self.findAllPlotDocks()]
        dLabels = [lbl for lbl in self.plotCharts.keys() if lbl not in openDocks]
        [self.plotCharts.pop(lbl, None) for lbl in dLabels]

        if len(openDocks) == 0:
            self.disableCoord()

    def exportDone(self, success):
        if success:
            self.statusbarLabel.setText("Export successful.")
        self.exporter = None

    @pyqtSlot(QModelIndex)
    def targetViewChanged(self, index=None):
        self.targetView.resizeColumnToContents(0)

    @pyqtSlot()
    def updateShowCoordsSetting(self):
        self._settings.setValue("view/show_coordinates", self.actShowCoords.isChecked())

    @pyqtSlot()
    def startExperiment(self):
        """
        Starts the experiment, the timer, and the connections. Disables the start button.
        """
        if self._currentExpListItem is None:
            self._logger.error("No experiment selected!")
            return

        dataPointNames = self.exp.getDataPoints()
        if not dataPointNames:
            self._logger.error("The selected experiment does not provide any data points!")
            return

        self._currentExperimentIndex = self.experimentList.row(self._currentExpListItem)
        self._currentExperimentName = self._experiments[self._currentExperimentIndex]["Name"]
        expName = self._currentExperimentName
        self._logger.info(f"Experiment: {expName}")

        if self.visualizer is not None:
            self.visualizer.setExpName(expName)
            self.visualizer.startAnimation()

        self.actStartExperiment.setDisabled(True)
        self.actStopExperiment.setDisabled(False)
        self.actSendParameter.setDisabled(False)
        self.actSendChangedParameter.setDisabled(False)
        self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(Qt.darkGreen))
        self.experimentList.repaint()

        self._currentDataPointBuffers = {data: DataPointBuffer() for data in dataPointNames}
        self._dataWarnings = set()

        data = {}
        data.update({'dataPointBuffers': self._currentDataPointBuffers})
        data.update({'exp': deepcopy(self.exp.getExperiment())})
        self.measurements.append(data)

        item = QListWidgetItem(str(self.lastMeasList.count() + 1) + ": "
                               + self._currentExperimentName + " ~current~")
        self.lastMeasList.addItem(item)
        self.lastMeasList.scrollToItem(item)
        self.copyLastMeas(item)

        # cap the plot updates at 25 fps
        timeout = max(int(self.config['TimerTime']), 40)
        self.timer.start(timeout)
        if self.config['HeartbeatTime']:
            self.heartbeatTimer.start(int(self.config['HeartbeatTime']))
        self.exp.runExperiment()

        if self.actStopExperiment.isEnabled():
            self.guiStartTime = time.time()
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
            # reset to the default background of the current style
            self.experimentList.item(i).setData(Qt.BackgroundRole, None)
        self.experimentList.repaint()

        self.timer.stop()
        self.heartbeatTimer.stop()
        self.exp.stopExperiment()

        # show the complete data, then detach the buffers of the finished run, so
        # frames arriving late do not modify the stored measurement
        if self._currentDataPointBuffers is not None:
            self.updateDataPlots()
            self._currentDataPointBuffers = None

        self.guiTimer.stop()

    def sendParameter(self):
        """
        Sends all parameters of the current experiment with `ExperimentInteractor` function `sendParameterExperiment`
        """
        if self._currentExperimentIndex == self.experimentList.row(self._currentExpListItem) and \
                "~current~" in self._currentLastMeasItem.text():
            self.exp.sendParameterExperiment()
        else:
            runningName = self._experiments[self.experimentList.row(self._currentExpListItem)]["Name"]
            self._logger.warning(f"Selected Experiment '{self._currentExperimentName}' doesn't match "
                                 f"current running Experiment '{runningName}'!")

    def sendChangedParameter(self):
        """
        Sends changed parameters of the current experiment with `ExperimentInteractor`
        function `sendChangedParameterExperiment`
        """
        if self._currentExperimentIndex == self.experimentList.row(self._currentExpListItem) and \
                "~current~" in self._currentLastMeasItem.text():
            self.exp.sendChangedParameterExperiment()
        else:
            runningName = self._experiments[self.experimentList.row(self._currentExpListItem)]["Name"]
            self._logger.warning(f"Selected Experiment '{self._currentExperimentName}' doesn't match "
                                 f"current running Experiment '{runningName}'!")

    def loadExpFromFile(self, fileName):
        """
        Loads experiments from file
        :param fileName: name of the file with experiments
        """
        success = True
        if fileName is None:
            fileName = findDefaultConfig()
            if fileName is None:
                self._logger.error('No default.sreg found!')
                success = False
        else:
            if not os.path.isfile(fileName):
                self._logger.error(f'Config file {fileName} does not exists!')
                success = False

        if success:
            self._logger.info(f"Load config file: {fileName}")

            try:
                with open(fileName, "r") as f:
                    experiments = yaml.load(f, Loader=SafeLoader)
            except yaml.YAMLError as e:
                self._logger.error(f"Cannot parse config file {fileName}: {e}")
                return False

            if not isinstance(experiments, list) or not experiments:
                self._logger.error(f"Config file {fileName} contains no experiments!")
                return False

            experiments = validateExperiments(experiments,
                                              getRegisteredExperimentModules(),
                                              getRegisteredVisualizers(),
                                              logger=self._logger)
            if not experiments:
                self._logger.error(f"Config file {fileName} contains no usable experiments!")
                return False

            self._experiments = experiments
            self._logger.info(f"Loading {len(self._experiments)} experiments")

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
        self.config.update(self._experiments[idx].get('Config', {}))

    def configureRemote(self, idx):
        self.remoteWidgetLayout.clearAll()

        remote = self._experiments[idx].get('Remote')
        if remote is None:
            return
        if not isinstance(remote, dict):
            self._logger.warning("Remote not correct configured in file!")
            return
        for name, config in remote.items():
            config['name'] = name
            self.remoteAddWidget(config)
        self.updateRemoteGamepad()

    def configureVisualizer(self, idx):
        availableVis = getRegisteredVisualizers()
        used = []
        vis = ''

        try:
            for vis in self._experiments[idx]['Visu']:
                used.append(availableVis[vis])
        except KeyError:
            self._logger.warning(f"Cannot configure visualization '{vis}'")

        self.visComboBox.clear()

        if used:
            self.visComboBox.addItems([vis.__name__ for vis in used])

    def setVisualizer(self, vis):
        if issubclass(vis, MplVisualizer):
            self.visualizer = vis(self.animationWidget,
                                  self.animationLayout)
            self.animationDock.addWidget(self.animationWidget)
        elif issubclass(vis, VtkVisualizer):
            if vtkAvailable:
                # vtk window
                if self.animationFrame is None:
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
        else:
            self._logger.warning("visualizer is not a subclass of MplVisualizer or VtkVisualizer")
            return
        self._logger.info(f"loading visualizer '{vis.__name__}'")

        self.visualizer.checkSaveAnimation(self.actSaveAnimation.isChecked())
        self.actSaveAnimation.disconnect()
        self.actSaveAnimation.toggled.connect(self.visualizer.checkSaveAnimation)

    @pyqtSlot(QListWidgetItem)
    def experimentDoubleClicked(self, item):
        """
        Apply the selected experiment to the current target and set it bold.
        :param item: item of the experiment in the `ExperimentList`
        """
        if self.isConnected and self.actStopExperiment.isEnabled():
            self._logger.info("stop the running experiment to change experiments")
            return
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
            self._logger.error(f"applyExperiment: index error! ({index})")
            return False

        expName = self._experiments[index]["Name"]
        self._logger.info(f"Experiment '{expName}' applied")

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
        self._logger.info("Close Event received, shutting down.")
        if self.isConnected:
            self.disconnect()
        self.stopGamepad()
        if self.exporter is not None:
            self._logger.warning("Export in progress, waiting!")
            self.exporter.wait()
        logging.getLogger().removeHandler(self.textLogger)
        super().closeEvent(QCloseEvent)

    @pyqtSlot()
    def connect(self):
        """
        Connects all connections and sets the button states.
        """
        if not self.connections:
            self._logger.error("No connections registered!")
            return

        for name, conn in self.connections.items():
            connInstance = conn['cls']()
            if not connInstance.open():
                self._logger.warning(f"No connection for {name} established! Check your settings!")
                # do not leave the other connections half open
                self.disconnect()
                return
            self._logger.info(f"Connection for {name} established!")
            # bind name as default argument, otherwise all lambdas would see the last name
            connInstance.receivedFrames.connect(lambda frames, name=name: self.updateData(frames, name))
            connInstance.finished.connect(self.disconnect)
            conn['inst'] = connInstance

        self.actConnect.setEnabled(False)
        self.actDisconnect.setEnabled(True)
        if self._currentExpListItem is not None and self.selectedExp:
            self.actStartExperiment.setEnabled(True)
        self.actStopExperiment.setEnabled(False)
        self.statusbarLabel.setText("Connected!")
        self.isConnected = True

    def writeToConnection(self, data):
        """
        PySignal function, that sends the given data to the connections
        :param data: to send data
        """
        if data['id'] == 1:
            targets = list(self.connections.values())
        else:
            conn = self.connections.get(data['connection'])
            if conn is None:
                self._logger.error(f"Unknown connection '{data['connection']}'!")
                return
            targets = [conn]

        for conn in targets:
            if 'inst' in conn:
                conn['inst'].writeData(data)

    @pyqtSlot()
    def disconnect(self):
        """
        Disconnects all connections and resets the button states.
        """
        if self.actStopExperiment.isEnabled():
            self.stopExperiment()

        for conn in self.connections.values():
            inst = conn.pop('inst', None)
            if inst is not None:
                inst.close()
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

    def updateData(self, frames, connection):
        """
        Stores the data points of the received frames in the buffers of the current measurement.
        :param frames: list of frames received by the connection
        :param connection: name of the connection
        """
        lastTime = None
        for frame in frames:
            data = self.exp.handleFrame(frame, connection)
            if data is None or self._currentDataPointBuffers is None:
                continue
            try:
                time = data['Time'] / 1000.0
                dataPoints = data['DataPoints']
            except (KeyError, TypeError):
                self._warnOnce(('format', connection),
                               "handleFrame() must return a dict with the keys 'Time' and 'DataPoints'")
                continue

            for key, value in dataPoints.items():
                buf = self._currentDataPointBuffers.get(key)
                if buf is None:
                    self._warnOnce(('key', key), f"Received unknown data point '{key}'")
                    continue
                try:
                    buf.addValue(time, value)
                except (TypeError, ValueError):
                    self._warnOnce(('value', key), f"Data point '{key}' must be a number, got {value!r}")
            lastTime = time

        if lastTime is not None:
            self.expTimeLabel.setText(f"Exp time={timeString(lastTime)}")

    def _warnOnce(self, key, msg):
        """ log a warning only once per experiment run, the data path is called at the frame rate """
        if key not in self._dataWarnings:
            self._dataWarnings.add(key)
            self._logger.warning(msg)

    def updateDataPlots(self):
        if self.visualizer:
            try:
                self.visualizer.update(self._currentDataPointBuffers)
                if self.vtkWidget is not None:
                    self.vtkWidget.GetRenderWindow().GetInteractor().Render()
            except Exception:
                # disable the visualizer, otherwise the error would repeat with every timer tick
                self._logger.exception(f"Visualizer '{type(self.visualizer).__name__}' failed and has been disabled")
                self.visualizer = None

        for chart in self.plotCharts.values():
            chart.updateCurves(self._currentDataPointBuffers)

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
        if not items:
            return
        if len(items) != 1:
            self._logger.warning('Error, more than one ~current~ measurement available. Using first one!')

        # the measurement already references the buffers of the run, no need to copy them
        item = items[0]
        item.setText(item.text().replace(' ~current~', ''))

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
        if self.isConnected and self.actStopExperiment.isEnabled():
            self._logger.info("stop the running experiment to view past measurements")
            return
        self.actStartExperiment.setDisabled(True)
        self.selectedExp = False
        self.remoteWidgetLayout.clearAll()

        expName = str(item.text())
        self._currentLastMeasItem = item
        try:
            idx = self.lastMeasList.row(item)
        except ValueError:
            self._logger.error(f"loadLastMeas(): No measurement called '{expName}")
            return False

        if idx >= len(self.measurements):
            self._logger.error(f"loadLastMeas(): Invalid index '{idx}')")
            return False

        self._logger.info(f"Restore of measurement '{expName}'")

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

        self._logger.info(f"Apply measurement '{measurement['exp']['Name']}'")

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
        self._experiments[idx].get('Remote', {}).pop(widget.widgetName, None)
        widget.updateGamepad(None)
        self.remoteWidgetLayout.removeWidget(widget)

    def remoteConfigWidget(self, widget, editWidget=True):
        idx = self.experimentList.row(self._currentExpListItem)
        exp = self.exp.getExperiment()
        del exp['Name']
        config, ok = RemoteWidgetEdit.getData(exp, editWidget, **(widget.getData()))
        if not ok:
            return
        if not self._experiments[idx].get('Remote'):
            self._experiments[idx]['Remote'] = {}
        self._experiments[idx]['Remote'].pop(widget.widgetName, None)

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
        idx = self.experimentList.row(self._currentExpListItem)
        exp = self.exp.getExperiment()
        del exp['Name']
        if not config:
            config, ok = RemoteWidgetEdit.getData(exp=exp, **kwargs)
            if not ok:
                return
            if not self._experiments[idx].get('Remote'):
                self._experiments[idx]['Remote'] = {}
            self._experiments[idx]['Remote'][config['name']] = config
        sliderLabel = None
        if config['widgetType'] == "PushButton":
            if 'valueReset' not in config:
                config['valueReset'] = ''
            if 'shortcut-Gp' not in config:
                config['shortcut-Gp'] = None
            widget = MovablePushButton(config['name'], config['valueOn'], config['valueReset'],
                                       config['shortcut'], config['shortcut-Gp'],
                                       module=config['Module'], parameter=config['Parameter'])
            widget.setFixedHeight(40)
            widget.setFixedWidth(100)
            widget.clicked.connect(lambda: self.remotePushButtonSendParameter(widget))
            widget.editAction.triggered.connect(lambda _: self.remoteConfigWidget(
                widget, editWidget=True))
            widget.removeAction.triggered.connect(lambda _: self.remoteRemoveWidget(widget))
        elif config['widgetType'] == "Switch":
            if 'shortcut-Gp' not in config:
                config['shortcut-Gp'] = None
            widget = MovableSwitch(config['name'], config['valueOn'], config['valueOff'],
                                   config['shortcut'], config['shortcut-Gp'],
                                   module=config['Module'], parameter=config['Parameter'])
            widget.setFixedHeight(40)
            widget.setFixedWidth(100)
            widget.clicked.connect(lambda: self.remoteSwitchSendParameter(widget))
            widget.editAction.triggered.connect(lambda _: self.remoteConfigWidget(
                widget, editWidget=True))
            widget.removeAction.triggered.connect(lambda _: self.remoteRemoveWidget(widget))
        elif config['widgetType'] == "Slider":
            if 'shortcut-Gp' not in config:
                config['shortcut-Gp'] = None
            if 'invertSlider' not in config:
                config['invertSlider'] = False
            startValue = exp.get(config['Module'], {}).get(config['Parameter'])
            if startValue is None:
                self._logger.error(f"Cannot create slider '{config['name']}': parameter '{config['Parameter']}' "
                                   f"of module '{config['Module']}' not found!")
                return
            sliderLabel = QLabel()
            sliderLabel.setFixedHeight(15)
            labelFont = sliderLabel.font()
            labelFont.setPointSize(8)
            sliderLabel.setFont(labelFont)
            self.remoteWidgetLayout.addWidget(sliderLabel)
            widget = MovableSlider(config['name'], config['minSlider'], config['maxSlider'], config['invertSlider'], config['stepSlider'],
                                   sliderLabel,
                                   config['shortcutPlus'], config['shortcutMinus'], config['shortcut-Gp'],
                                   startValue, module=config['Module'],
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
        self.remoteSendParameter(widget.module, widget.parameter, value)
        self.remoteSliderUpdate(widget, value, sliderMoved=False)

        if widget.valueReset != '':
            self.remoteSetParameter(widget.module, widget.parameter, widget.valueReset)
            self.exp.updateSendParameter(widget.module, widget.parameter, widget.valueReset)

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

        self.remoteSendParameter(widget.module, widget.parameter, value)
        self.remoteSliderUpdate(widget, value, sliderMoved=False)

    def remoteSliderSendParameter(self, widget, value):
        """
        Gets called when a user interacts with the slider and sends the specified parameter to the bench
        :param widget: the widget the user interacted with
        :param value: the actual value of the widget
        """
        self.remoteSliderUpdate(widget, value)
        self.remoteSendParameter(widget.module, widget.parameter, widget.value)

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
                        wid.blockSignals(True)
                        wid.setValue(float(value))
                        wid.blockSignals(False)
                        wid.valueOn = value
                        wid.label.setText(wid.widgetName + f": {wid.value:.3f}")
        else:
            widget.valueOn = value

            if isinstance(widget, MovableSlider):
                value = widget.calcValue(value)

            widget.label.setText(widget.widgetName + f": {value:.3f}")

    def remoteSendParameter(self, module, parameter, value):
        self.remoteSetParameter(module, parameter, value)
        if self.actSendParameter.isEnabled():
            self.sendChangedParameter()

    def remoteSetParameter(self, module, parameter, value):
        exp = deepcopy(self.exp.getExperiment())
        del exp['Name']

        for key, val in exp.items():
            if key != module:
                continue
            for k in val:
                if k != parameter:
                    continue
                exp[key][k] = value
                self.exp.editExperiment(exp)

                return

    def copyRemoteSource(self):
        if self._currentExperimentIndex is None:
            self._logger.error("No experiment selected!")
            return
        text = "  Remote:\n"
        if 'Remote' in self._experiments[self._currentExperimentIndex]:
            text += yaml.dump(self._experiments[self._currentExperimentIndex]['Remote'], default_flow_style=False)
        text = text.replace("\n", "\n    ")
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def remoteWidgetMenu(self, position):
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

def logUncaughtException(excType, excValue, excTraceback):
    """
    Exception hook that logs uncaught exceptions. Since PyQt 5.5 an unhandled exception
    in a slot aborts the application if the default hook is installed.
    """
    if issubclass(excType, KeyboardInterrupt):
        sys.__excepthook__(excType, excValue, excTraceback)
        return
    logging.getLogger("pywisp").critical("Unhandled exception",
                                         exc_info=(excType, excValue, excTraceback))


def findDefaultConfig(name='default.sreg'):
    """
    Looks for the default config file in the current working directory and
    in the directory of the main script.
    :return: path of the config file or `None`
    """
    dirs = [os.getcwd()]
    mainFile = getattr(sys.modules.get('__main__'), '__file__', None)
    if mainFile:
        dirs.append(os.path.dirname(os.path.abspath(mainFile)))
    for d in dirs:
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None


def timeString(seconds):
    return f"{int(seconds // 3600):02d}:{int(seconds % 3600 // 60):02d}:{int(seconds % 60):02d}"

