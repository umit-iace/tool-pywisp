# -*- coding: utf-8 -*-
import logging
import os
import shutil
import sys
import tempfile
import time

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
from PyQt6.QtCore import QSize, Qt, pyqtSlot, pyqtSignal, QModelIndex, QTimer, QCoreApplication
from PyQt6.QtGui import QAction, QActionGroup, QBrush, QFontDatabase, QGuiApplication, QIcon, QKeySequence, QPalette, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QSizePolicy, QSplashScreen, QStatusBar, QTextEdit, QStyle, QStyleOptionToolButton, QStylePainter, QToolBar, QToolButton, \
    QDockWidget, QTabWidget, QVBoxLayout, QWidget
from PyQt6.QtWidgets import QMessageBox

from .config import dumpExperiments, validateExperiments
from .connectionManager import ConnectionManager
from .registry import getRegisteredExperimentModules, getRegisteredVisualizers
from .session import Session
from .utils import getResource, setupLogging
from .widgets.connectionmenu import ConnectionMenu
from .widgets.common import PlainTextLogger
from .widgets.dialogs import DataIntDialog
from .widgets.experimentview import ExperimentView
from .widgets.remotepanel import RemotePanel

from .visualization import MplVisualizer, VtkVisualizer
from .gamepad import getAllGamepads, openGamepad
from .settings import Settings
from .themes import THEMES, applyTheme, isDark, themedIcon
from .widgets.plotmanager import PlotManager

__all__ = ["MainGui"]


class _CenteredToolButton(QToolButton):
    """ tool button showing one action, with a fixed width it centers icon and text, the styles align them left """

    def setDefaultAction(self, action):
        # with more than one action the button gets a menu arrow and a popup with them
        for act in self.actions():
            self.removeAction(act)
        super().setDefaultAction(action)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        # the bevel over the full width, with an empty label
        bevel = QStyleOptionToolButton(opt)
        bevel.text, bevel.icon = "", QIcon()
        bevel.toolButtonStyle = Qt.ToolButtonStyle.ToolButtonTextOnly
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, bevel)
        # the label in a rect of its natural width in the middle, without a second bevel
        offset = max(0, (self.width() - self.sizeHint().width()) // 2)
        opt.rect = self.rect().adjusted(offset, 0, -offset, 0)
        opt.state &= ~(QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Sunken | QStyle.StateFlag.State_On
                       | QStyle.StateFlag.State_Raised | QStyle.StateFlag.State_HasFocus)
        opt.state |= QStyle.StateFlag.State_AutoRaise
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)


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
        # Create and display the splash screen
        # without a display Qt waits in vain for the splash screen to become visible
        self.splashScreen = None
        if QGuiApplication.platformName() != "offscreen":
            self.splashScreenIcon = QPixmap(getResource("icon.svg"))
            self.splashScreen = QSplashScreen(self.splashScreenIcon, Qt.WindowType.WindowStaysOnTopHint)
            self.splashScreen.setEnabled(False)
            self.splashScreen.show()

        # runs the experiments, owns the connection to the rig and the experiment interactor
        self.session = Session(self)
        self.connectionManager = self.session.connectionManager
        self.exp = self.session.exp
        self.connectionManager.stateChanged.connect(self._onConnectionStateChanged)
        self.connectionManager.rigStatusChanged.connect(self._updateConnectionStatus)
        self.session.stateChanged.connect(self._onSessionStateChanged)
        self.session.measurementStarted.connect(self._onMeasurementStarted)
        self.session.measurementFinished.connect(self._onMeasurementFinished)
        self.session.measurementDropped.connect(self._onMeasurementDropped)
        self.session.dataReceived.connect(self._onDataReceived)
        self.session.commError.connect(self._setCommError)
        self.session.startAborted.connect(lambda msg: QMessageBox.warning(self, "Start failed", msg))
        # problem of the communication with the rig, shown by the yellow traffic light
        self._commError = None
        # the frames pass updateData, looked up on every call, so it can be replaced, e.g. in tests
        self.connectionManager.framesReceived.disconnect(self.session.handleFrames)
        self.connectionManager.framesReceived.connect(lambda frames: self.updateData(frames))
        self.selectedExp = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateDataPlots)

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
        # traffic light of the connection: red not connected, green connected, yellow a problem,
        # the tooltip tells which
        self.connectionLed = QLabel()
        self.connectionLed.setFixedSize(14, 14)
        self.statusBar.addPermanentWidget(self.connectionLed, 0)
        self._setConnectionLed('red', "Not connected")
        self.statusbarLabel = QLabel("")
        self.statusBar.addPermanentWidget(self.statusbarLabel, 1)
        # the mouse position in a plot and the times on the right, a caption in the color of disabled text and
        # the value in a fixed width font, so it does not jump while counting
        self.coordXLabel = self._addStatusValue("x", "mouse position in the plot", "")
        self.coordYLabel = self._addStatusValue("y", "mouse position in the plot", "")
        self.updateCoordInfo(None)
        self.guiTimeLabel = self._addStatusTime("GUI", "time since the start of the experiment in the gui")
        self.expTimeLabel = self._addStatusTime("Exp", "time of the experiment on the rig")
        self.guiStartTime = 0.0
        self.guiTimer = QTimer()
        self.guiTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self.guiTimer.timeout.connect(
            lambda: self.guiTimeLabel.setText(timeString(time.time() - self.guiStartTime))
        )

        # the docks can be rearranged at runtime, the plots and the animation in the plot area in the center,
        # the other docks around it
        self.plotArea = QMainWindow()
        for window in (self, self.plotArea):
            window.setDockOptions(QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.AllowNestedDocks
                                  | QMainWindow.DockOption.AnimatedDocks)
            window.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        self.setCentralWidget(self.plotArea)
        # the log spans the whole width
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)

        self.experimentDock = self._createDock("Experiments", self)
        self.lastMeasDock = self._createDock("Last Measurements", self)
        self.propertyDock = self._createDock("Parameters", self)
        self.remoteDock = self._createDock("Remote", self)
        self.logDock = self._createDock("Log", self)
        self.animationDock = self._createDock("Animation", self.plotArea)
        self.dataPointDock = self._createDock("Data", self.plotArea)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.experimentDock)
        # split before tabbing, a dock split from a tabbed one would become a tab as well
        self.splitDockWidget(self.experimentDock, self.propertyDock, Qt.Orientation.Vertical)
        self.splitDockWidget(self.propertyDock, self.remoteDock, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.experimentDock, self.lastMeasDock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.logDock)
        self.experimentDock.raise_()
        self.plotArea.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.animationDock)
        self.plotArea.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dataPointDock)

        # property dock
        self.targetView = ExperimentView(self)
        self.targetView.expanded.connect(self.targetViewChanged)
        self.targetView.collapsed.connect(self.targetViewChanged)

        self.propertyDock.setWidget(self.targetView)

        # animation dock
        self.animationWidget = QWidget()
        self.animationLayout = QVBoxLayout()
        self.animationFrame = None
        self.animationDock.setWidget(self.animationWidget)
        # catch up on the updates skipped while the animation was hidden
        self.animationDock.visibilityChanged.connect(lambda visible: visible and self._updateVisualizer())

        # experiment dock
        self.experimentList = QListWidget(self)
        self.experimentList.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # experiments are applied by a double click, the applied one is shown in bold and
        # the running one with a background, a selection would hide both
        self.experimentList.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.experimentDock.setWidget(self.experimentList)
        self.experimentList.itemDoubleClicked.connect(self.experimentDoubleClicked)
        self._currentExperimentIndex = None
        self._currentExperimentName = None
        self._experimentStartTime = 0

        self.actStartExperiment = QAction(self)
        self.actStartExperiment.setDisabled(True)
        self.actStartExperiment.setText("&Start experiment")
        self.actStartExperiment.setShortcut(QKeySequence("F5"))
        self.actStartExperiment.triggered.connect(self.startExperiment)

        self.actStopExperiment = QAction(self)
        self.actStopExperiment.setText("&Stop experiment")
        self.actStopExperiment.setDisabled(True)
        self.actStopExperiment.setShortcut(QKeySequence("F6"))
        self.actStopExperiment.triggered.connect(self.stopExperiment)

        self.actExport = QAction("&Export", self)
        self.actExport.setToolTip("Export data points to a file")

        self.visComboBox = QComboBox()

        # selection of the active connection, synced with the radio buttons of the connections menu
        self.connComboBox = QComboBox()
        self.connComboBox.setToolTip("Connection to the rig")
        self.connComboBox.addItems(list(self.connectionManager.connections))
        self.connComboBox.setCurrentText(self.connectionManager.activeConnection or "")
        self.connComboBox.currentTextChanged.connect(self._onConnComboBoxChanged)
        self.connectionManager.activeConnectionChanged.connect(self.connComboBox.setCurrentText)
        self.visComboBox.currentIndexChanged.connect(self.visualizerChanged)

        # lastmeas dock
        self.lastMeasList = QListWidget(self)
        self.lastMeasList.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lastMeasList.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lastMeasDock.setWidget(self.lastMeasList)
        self.lastMeasList.itemDoubleClicked.connect(self.loadLastMeas)
        # all recorded measurements, each list item holds its measurement as user data
        self.measurements = self.session.measurements

        # log dock
        self.logBox = QTextEdit(self)
        self.logBox.setReadOnly(True)
        self.logBox.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.logBox.ensureCursorVisible()
        self.logDock.setWidget(self.logBox)

        # plot area
        self.plotManager = PlotManager(self.plotArea, self.animationDock, self.dataPointDock, self._settings,
                                       currentMeasurement=self._currentMeasurement,
                                       dataPointNames=lambda: self.exp.getDataPoints(),
                                       plotConfig=lambda: self.config)
        self.plotManager.coords.connect(self.updateCoordInfo)
        self.plotManager.allPlotsClosed.connect(lambda: self.updateCoordInfo(None))
        self.plotManager.exportDone.connect(self.exportDone)
        self.actExport.triggered.connect(self.plotManager.exportDataPoints)
        self.dataPointDock.setWidget(self.plotManager)

        # init logger for logging box
        self.textLogger = PlainTextLogger(self._settings,
                                          logging.INFO)
        self.textLogger.setTargetCb(self.logBox)
        logging.getLogger().addHandler(self.textLogger)
        self._logger.info('Laboratory visualization')

        # menu bar
        fileMenu = self.menuBar().addMenu("&File")
        self.actSaveExperiments = fileMenu.addAction("&Save experiments", QKeySequence.StandardKey.Save,
                                                     lambda: self.saveExperiments())
        self.actSaveExperimentsAs = fileMenu.addAction("Save experiments &as ...", QKeySequence.StandardKey.SaveAs,
                                                       self.saveExperimentsAs)
        fileMenu.addSeparator()
        fileMenu.addAction("&Quit", QKeySequence("Ctrl+W"), self.close)

        # view
        self.viewMenu = self.menuBar().addMenu('&View')
        self.actLoadStandardState = QAction('&Load default view', self)
        self.viewMenu.addAction(self.actLoadStandardState)
        self.actLoadStandardState.triggered.connect(self.loadStandardDockState)
        self.viewMenu.addAction("Sa&ve view as default", self.saveDockState)
        self.viewMenu.addAction("&Reset default view", self.resetDockState)
        self.themeMenu = self.viewMenu.addMenu("&Theme")
        self._themeActions = QActionGroup(self)
        for name in THEMES:
            act = self.themeMenu.addAction(name, lambda name=name: self.setTheme(name))
            act.setCheckable(True)
            self._themeActions.addAction(act)
        self.actToggleTheme = QAction("Toggle &dark mode", self)
        self.actToggleTheme.triggered.connect(self.toggleTheme)
        self.viewMenu.addAction(self.actToggleTheme)

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

        self.connectionMenu = ConnectionMenu(self.connectionManager, self.connMenu, self)

        self.expMenu.addSeparator()
        self.actConnect = QAction('&Connect', self)
        self.actConnect.setShortcut(QKeySequence("F9"))
        self.expMenu.addAction(self.actConnect)
        self.actConnect.triggered.connect(self.connectRig)

        self.actDisconnect = QAction('&Disconnect', self)
        self.actDisconnect.setEnabled(False)
        self.actDisconnect.setShortcut(QKeySequence("F10"))
        self.actSendParameter = QAction('&Send all parameter', self)
        self.actSendParameter.setEnabled(False)
        self.actSendParameter.setShortcut(QKeySequence("F7"))
        self.expMenu.addAction(self.actSendParameter)
        self.actSendParameter.triggered.connect(self.sendParameter)
        self.actSendChangedParameter = QAction('&Send changed parameter', self)
        self.actSendChangedParameter.setEnabled(False)
        self.actSendChangedParameter.setShortcut(QKeySequence("F8"))
        self.expMenu.addAction(self.actSendChangedParameter)
        self.actSendChangedParameter.triggered.connect(self.sendChangedParameter)
        self.expMenu.addAction(self.actDisconnect)
        self.actDisconnect.triggered.connect(self.disconnectRig)
        self.expMenu.addSeparator()
        self.expMenu.addAction(self.actStartExperiment)
        self.expMenu.addAction(self.actStopExperiment)

        # toolbar
        self.toolbarExp = QToolBar("Experiment")
        self.toolbarExp.setObjectName("Experiment")
        self.toolbarExp.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.toolbarExp.setMovable(False)
        self.toolbarExp.setIconSize(iconSize)
        self.addToolBar(self.toolbarExp)
        # one toggle button each for connect/disconnect and start/stop, showing the action that is enabled
        def _swap(btn, a, b):
            btn.setDefaultAction(b if b.isEnabled() else a)

        self.connButton = _CenteredToolButton()
        self.expButton = _CenteredToolButton()
        self._toggleButtons = ((self.connButton, self.actConnect, self.actDisconnect),
                               (self.expButton, self.actStartExperiment, self.actStopExperiment))
        for btn, a, b in self._toggleButtons:
            # widgets added to a toolbar do not inherit its icon size and style
            btn.setIconSize(iconSize)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setAutoRaise(True)
            for act in (a, b):
                act.changed.connect(lambda btn=btn, a=a, b=b: _swap(btn, a, b))
            _swap(btn, a, b)
        self.toolbarExp.addWidget(self.connComboBox)
        self.toolbarExp.addWidget(self.connButton)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addWidget(self.expButton)
        self.toolbarExp.addSeparator()
        self.exportButton = QToolButton()
        self.exportButton.setDefaultAction(self.actExport)
        self.exportButton.setIconSize(iconSize)
        self.exportButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.exportButton.setAutoRaise(True)
        self.toolbarExp.addWidget(self.exportButton)
        self.toolbarExp.addSeparator()
        vSpacer = QWidget()
        vSpacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbarExp.addWidget(vSpacer)
        self.toolbarExp.addWidget(self.visComboBox)
        self.toolbarExp.addSeparator()
        self.toolbarExp.addAction(self.actToggleTheme)

        # the icons are drawn in the text color of the theme or in the given (light, dark) color
        green, red = ("#2e7d32", "#66bb6a"), ("#c62828", "#e57373")
        self._themedIcons = {self.actStartExperiment: ("play.png", green), self.actStopExperiment: ("stop.png", red),
                             self.actConnect: ("connected.png", green),
                             self.actDisconnect: ("disconnected.png", red),
                             self.actToggleTheme: ("theme.svg", None), self.actExport: ("export.svg", None)}

        self._currentExpListItem = None
        self._currentLastMeasItem = None
        # config file and all of its experiments, including those skipped by the validation
        self._configFile = None
        self._fileExperiments = []
        self._backedUpFiles = set()

        loadExpFromFileSuccess = self.loadExpFromFile(fileName)

        # sized when the window is shown
        self.standardDockState = (self.saveState(), self.plotArea.saveState())
        self._standardSizesPending = False
        # the view of the pyqtgraph docks of older versions cannot be restored
        self._settings.remove("view/dock_state")
        self.loadStandardDockState()

        self.targetView.setInteractor(self.exp)

        # remote dock
        self.remotePanel = RemotePanel(self.exp)
        self.remotePanel.parametersChanged.connect(self._sendRemoteParameters)
        self.remotePanel.saveRequested.connect(lambda: self.saveExperiments())
        self.remoteDock.setWidget(self.remotePanel)
        self.runExp.connect(self.exp.runExperiment)
        self.stopExp.connect(self.exp.stopExperiment)

        self.visualizer = None
        self.vtkWidget = None
        self.setTheme(self._settings.value("theme/name"))

        self._updateExperimentsList()

        if loadExpFromFileSuccess:
            self._applyFirstExperiment()
            self.selectedExp = True


        # close splash screen
        if self.splashScreen is not None:
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
            # owned by the menu, so clear() deletes it
            action = self.gamepadMenu.addAction(info.name)
            action.setCheckable(True)
            action.setChecked(self.selectedGamepadId == info.id)
            action.triggered.connect(lambda checked, info=info: self.selectGamepad(info))

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
        self.remotePanel.setGamepad(self.gamepad)

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

    def updateCoordInfo(self, coords):
        """ shows the mouse position ``(x, y)`` in a plot in the status bar, ``None`` clears it """
        x, y = (f"{v:>10.4g}" for v in coords) if coords else (f"{'–':>10}",) * 2
        self.coordXLabel.setText(x)
        self.coordYLabel.setText(y)

    def _currentMeasurement(self):
        """ the measurement shown in the gui or `None` """
        if self._currentLastMeasItem is None:
            return None
        return self._currentLastMeasItem.data(Qt.ItemDataRole.UserRole)

    def _measurementItem(self, measurement):
        """ the item of the given measurement in the list of measurements """
        for row in range(self.lastMeasList.count()):
            item = self.lastMeasList.item(row)
            if item.data(Qt.ItemDataRole.UserRole) is measurement:
                return item
        return None

    def exportDone(self, success):
        if success:
            self.statusbarLabel.setText("Export successful.")

    @pyqtSlot(QModelIndex)
    def targetViewChanged(self, index=None):
        self.targetView.resizeColumnToContents(0)

    @pyqtSlot()
    def startExperiment(self):
        """
        Sends the parameters of the experiment, once the rig confirmed them with a sync the experiment is started,
        see :meth:`Session.start`. Rigs without sync support are started right away. Disables the start button.
        """
        if self._currentExpListItem is None:
            self._logger.error("No experiment selected!")
            return
        self.session.start(self.config['HeartbeatTime'])

    def _onSessionStateChanged(self, state):
        """ buttons and the color of the experiment: yellow until the rig confirmed the start, then green """
        if state == Session.SYNCING:
            self._currentExperimentIndex = self.experimentList.row(self._currentExpListItem)
            self._currentExperimentName = self._experiments[self._currentExperimentIndex]["Name"]
            # stop stays possible while the rig confirms the parameters
            self.actStartExperiment.setDisabled(True)
            self.actStopExperiment.setDisabled(False)
            self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(Qt.GlobalColor.darkYellow))
            self.experimentList.repaint()
        elif state in (Session.STARTING, Session.RUNNING):
            color = Qt.GlobalColor.darkYellow if state == Session.STARTING else Qt.GlobalColor.darkGreen
            self.experimentList.item(self._currentExperimentIndex).setBackground(QBrush(color))
            self.experimentList.repaint()
        else:
            self._onStopped()

    def _onMeasurementStarted(self, measurement):
        if self.visualizer is not None:
            self.visualizer.setExpName(self._currentExperimentName)
            self.visualizer.startAnimation()

        self.actSendParameter.setDisabled(False)
        self.actSendChangedParameter.setDisabled(False)

        item = QListWidgetItem(measurement.label())
        item.setData(Qt.ItemDataRole.UserRole, measurement)
        self.lastMeasList.addItem(item)
        self.lastMeasList.scrollToItem(item)
        self.copyLastMeas(item)

        # cap the plot updates at 25 fps
        timeout = max(int(self.config['TimerTime']), 40)
        self.timer.start(timeout)
        self.guiStartTime = time.time()
        self.guiTimer.start(1000)

    @pyqtSlot()
    def stopExperiment(self):
        """
        Stops the experiment, the timer, clears the connections, and enables the start button.
        """
        self.session.stop()

    def _onStopped(self):
        if self.selectedExp:
            self.actStartExperiment.setDisabled(False)
        self.actStopExperiment.setDisabled(True)
        self.actSendParameter.setDisabled(True)
        self.actSendChangedParameter.setDisabled(True)
        for i in range(self.experimentList.count()):
            # reset to the default background of the current style
            self.experimentList.item(i).setData(Qt.ItemDataRole.BackgroundRole, None)
        self.experimentList.repaint()

        self.timer.stop()
        # show the complete data, the session detaches the buffers of the finished run afterwards
        if self.session.currentBuffers is not None:
            self.updateDataPlots()
        self.guiTimer.stop()

    def _showsRunningExperiment(self):
        """
        `True` if the gui shows the running experiment, otherwise a warning is logged
        since parameters would be sent to the wrong experiment
        """
        running = self.session.runningMeasurement
        if running is not None and self._currentMeasurement() is running and \
                self._currentExperimentIndex == self.experimentList.row(self._currentExpListItem):
            return True
        if running is None:
            self._logger.warning("No experiment is running!")
        else:
            row = self.experimentList.row(self._currentExpListItem)
            selectedName = self._experiments[row]["Name"] if row >= 0 else None
            self._logger.warning(f"Selected Experiment '{selectedName}' doesn't match "
                                 f"current running Experiment '{running.name}'!")
        return False

    def sendParameter(self):
        """
        Sends all parameters of the current experiment, see :meth:`Session.sendParameters`
        """
        if self._showsRunningExperiment():
            self.session.sendParameters()

    def sendChangedParameter(self):
        """
        Sends changed parameters of the current experiment, see :meth:`Session.sendParameters`
        """
        if self._showsRunningExperiment():
            self.session.sendParameters(changedOnly=True)

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

            # the valid experiments are normalized in place, so saving this list
            # keeps the changes as well as the skipped experiments
            fileExperiments = experiments
            experiments = validateExperiments(experiments,
                                              getRegisteredExperimentModules(),
                                              getRegisteredVisualizers(),
                                              logger=self._logger)
            if not experiments:
                self._logger.error(f"Config file {fileName} contains no usable experiments!")
                return False

            self._experiments = experiments
            self._fileExperiments = fileExperiments
            self._configFile = os.path.abspath(fileName)
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
        self.remotePanel.setExperimentConfig(self._experiments[idx])

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
            self.animationDock.setWidget(self.animationWidget)
        elif issubclass(vis, VtkVisualizer):
            if vtkAvailable:
                # vtk window
                if self.animationFrame is None:
                    self.animationFrame = QFrame()
                    self.vtkWidget = QVTKRenderWindowInteractor(self.animationFrame)
                self.animationLayout.addWidget(self.vtkWidget)
                self.animationFrame.setLayout(self.animationLayout)
                self.animationDock.setWidget(self.animationFrame)
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
        try:
            self.actSaveAnimation.toggled.disconnect()
        except TypeError:
            # no visualizer connected yet
            pass
        self.actSaveAnimation.toggled.connect(self.visualizer.checkSaveAnimation)
        self.visualizer.updateTheme()

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
        sucess = self.session.setExperiment(self._experiments[index])
        if sucess:
            self._currentExperimentIndex = index
            self._currentExperimentName = self._experiments[index]['Name']
            self.targetViewChanged()
        return sucess

    def closeEvent(self, QCloseEvent):
        """
        Is called by closing the GUI. Disconnects and sends close event.
        :param QCloseEvent:
        """
        self._logger.info("Close Event received, shutting down.")
        self.disconnectRig()
        self.connectionManager.shutdown()
        self.stopGamepad()
        self.plotManager.waitForExport()
        logging.getLogger().removeHandler(self.textLogger)
        super().closeEvent(QCloseEvent)

    @property
    def isConnected(self):
        """ `True` if the connection to the rig is established """
        return self.connectionManager.isConnected

    @pyqtSlot()
    def connectRig(self):
        """
        Establishes the active connection in the background, the button states are set
        once it is open.
        """
        self.session.connect()

    @pyqtSlot()
    def disconnectRig(self):
        """
        Stops a running experiment and disconnects.
        """
        self.session.disconnect()

    def _onConnComboBoxChanged(self, name):
        # a refused selection shows the active connection again
        if not self.connectionManager.setActiveConnection(name):
            self.connComboBox.setCurrentText(self.connectionManager.activeConnection or "")

    def _onMeasurementDropped(self, measurement):
        """ removes the item of a measurement that is not kept """
        item = self._measurementItem(measurement)
        if item is not None:
            self.lastMeasList.takeItem(self.lastMeasList.row(item))

    #: colors of the traffic light
    LED_COLORS = {'red': '#d9534f', 'yellow': '#f0ad4e', 'green': '#5cb85c'}

    def _setConnectionLed(self, state, tooltip):
        """ :param state: 'red', 'yellow' or 'green' """
        self.connectionLedState = state
        self.connectionLed.setStyleSheet(f"background-color: {self.LED_COLORS[state]}; border-radius: 7px;")
        self.connectionLed.setToolTip(tooltip)

    def _setCommError(self, error):
        """ problem of the communication shown by the traffic light, `None` once solved """
        self._commError = error
        self._updateConnectionStatus()

    def _updateConnectionStatus(self):
        """ traffic light and text of the status bar while connected """
        if not self.connectionManager.isConnected:
            return
        parts, problems = [], []
        name = self.connectionManager.activeConnection
        responding = self.connectionManager.isResponding()
        if not self.connectionManager.answered:
            problems.append(f"{name}: no answer from the rig yet")
        if responding is False:
            parts.append(f"{name}: no response")
            problems.append(f"{name}: the rig does not respond")
        elif responding:
            status = self.connectionManager.rigStatus[0]
            text = f"{name}: {'RUN' if status.running else 'IDLE'}"
            missing = [flag for bit, flag in enumerate(self.connectionManager.statusFlagNames())
                       if not status.flags & (1 << bit)]
            if missing:
                text += f", missing: {', '.join(missing)}"
                problems.append(f"{name}: missing {', '.join(missing)}")
            parts.append(text)
        if self._commError:
            problems.append(self._commError)
        self._setConnectionLed('yellow' if problems else 'green', "\n".join(["Connected"] + problems))
        self.statusbarLabel.setText(" | ".join(parts))

    def _onConnectionStateChanged(self, state):
        """ sets the button states and the status bar """
        self.connComboBox.setEnabled(state == ConnectionManager.DISCONNECTED)
        if state == ConnectionManager.CONNECTING:
            self.actConnect.setEnabled(False)
            self.actDisconnect.setEnabled(True)
            self._setConnectionLed('yellow', "Connecting ...")
            self.statusbarLabel.setText("")
        elif state == ConnectionManager.CONNECTED:
            self.actConnect.setEnabled(False)
            self.actDisconnect.setEnabled(True)
            if self._currentExpListItem is not None and self.selectedExp:
                self.actStartExperiment.setEnabled(True)
            self.actStopExperiment.setEnabled(False)
            self._commError = None
            self._updateConnectionStatus()
        else:
            self.actConnect.setEnabled(True)
            self.actDisconnect.setEnabled(False)
            self.actStartExperiment.setEnabled(False)
            self.actStopExperiment.setEnabled(False)
            self._setConnectionLed('red', "Not connected")
            self.statusbarLabel.setText("")

    def updateData(self, frames):
        """
        Stores the data points of the received frames in the buffers of the current measurement,
        see :meth:`Session.handleFrames`.
        :param frames: list of frames received by the connection
        """
        self.session.handleFrames(frames)

    def _onDataReceived(self, lastTime, newBuffers):
        if newBuffers:
            # the elements of an array data point are shown once their buffers exist
            self.updateDataPoints(self.exp.getDataPoints())
        self.expTimeLabel.setText(timeString(lastTime))

    def updateDataPlots(self):
        self._updateVisualizer()
        self.plotManager.updateCharts(self.session.currentBuffers)

    def _updateVisualizer(self):
        # a hidden animation costs as much as a shown one, skip it unless every frame is saved
        hidden = self.animationDock.visibleRegion().isEmpty() or self.isMinimized()
        buffers = self.session.currentBuffers
        running = buffers is not None  # also called on showing, without an experiment
        if self.visualizer and running and (not hidden or self.actSaveAnimation.isChecked()):
            try:
                self.visualizer.update(buffers)
                if self.vtkWidget is not None:
                    self.vtkWidget.GetRenderWindow().GetInteractor().Render()
            except Exception:
                # disable the visualizer, otherwise the error would repeat with every timer tick
                self._logger.exception(f"Visualizer '{type(self.visualizer).__name__}' failed and has been disabled")
                self.visualizer = None

    def _createDock(self, title, window):
        """ a dock of the given main window that cannot be closed, the title names it in the saved view """
        dock = QDockWidget(title, window)
        dock.setObjectName(title)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        return dock

    def showEvent(self, event):
        super().showEvent(event)
        if self._standardSizesPending:
            # the docks can only be sized once the window has its size
            self._standardSizesPending = False
            QTimer.singleShot(0, self._applyStandardSizes)

    def _applyStandardSizes(self):
        """
        the sizes of the standard view: the left docks two ninths of the width and of equal height, the log a
        twelfth of the height, the data points three sixteenths of the plot area
        """
        width, height = self.width(), self.height()
        self.resizeDocks([self.experimentDock], [width * 2 // 9], Qt.Orientation.Horizontal)
        self.resizeDocks([self.experimentDock, self.propertyDock, self.remoteDock, self.logDock],
                         [height // 3] * 3 + [height // 12], Qt.Orientation.Vertical)
        # the plot area gets its new width only with the next layout pass, a method is not called once deleted
        QTimer.singleShot(0, self._applyPlotAreaSizes)

    def _applyPlotAreaSizes(self):
        width = self.plotArea.width()
        self.plotArea.resizeDocks([self.animationDock, self.dataPointDock], [width * 13 // 16, width * 3 // 16],
                                  Qt.Orientation.Horizontal)

    def _restoreStandardView(self):
        self.restoreState(self.standardDockState[0])
        self.plotArea.restoreState(self.standardDockState[1])
        self.plotManager.tabPlots()
        if self.isVisible():
            self._applyStandardSizes()
        else:
            self._standardSizesPending = True

    def loadStandardDockState(self):
        """
        Loads the view saved by the user, or the standard one if there is none
        """
        mainState = self._settings.value("view/main_state")
        plotState = self._settings.value("view/plot_state")
        if mainState is None or plotState is None:
            self._restoreStandardView()
        elif not (self.restoreState(mainState) and self.plotArea.restoreState(plotState)):
            self._logger.warning("The saved view could not be restored, the standard view is used")
            self._restoreStandardView()
        # views of older versions do not have the "+" tab next to the data dock
        self.plotManager.placeAddTab()

    def saveDockState(self):
        """ saves the arrangement of the docks as the default view of the user """
        self._settings.setValue("view/main_state", self.saveState())
        self._settings.setValue("view/plot_state", self.plotArea.saveState())

    def resetDockState(self):
        """ removes the default view of the user and restores the standard one """
        self._settings.remove("view/main_state")
        self._settings.remove("view/plot_state")
        self._restoreStandardView()
        self.plotManager.placeAddTab()
    def _stretchable(cls, state):
        """
        Scales the splitter sizes of a dock area state to at most 255. pyqtgraph also uses the sizes as stretch
        factors, which Qt caps at 255, so larger sizes would split the space evenly on every resize.
        """
        def scale(node):
            typ, contents, props = node
            if typ == "dock":
                return node
            props = dict(props)
            if props.get("sizes"):
                top = max(max(props["sizes"]), 1)
                props["sizes"] = [max(1, round(255 * size / top)) for size in props["sizes"]]
            return typ, [scale(child) for child in contents], props

        return {**state, "main": state["main"] and scale(state["main"]),
                "float": [({**area, "main": area["main"] and scale(area["main"])}, geo)
                          for area, geo in state["float"]]}

    def _onMeasurementFinished(self, measurement):
        """ shows the end of the run in the label of the measurement """
        item = self._measurementItem(measurement)
        if item is not None:
            item.setText(measurement.label())

    def copyLastMeas(self, item):
        self._currentLastMeasItem = item
        measurement = item.data(Qt.ItemDataRole.UserRole)

        dataPointNames = self.exp.getDataPoints()
        dataPointBuffers = measurement.dataPointBuffers
        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        self.plotManager.showData(dataPointBuffers)

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
        # the remote widgets belong to the experiments, not to past measurements
        self.remotePanel.setExperimentConfig(None)

        measurement = item.data(Qt.ItemDataRole.UserRole)
        if measurement is None:
            self._logger.error(f"loadLastMeas(): No measurement stored for '{item.text()}'")
            return False
        self._currentLastMeasItem = item
        self._logger.info(f"Restore of measurement '{item.text()}'")

        success = self.exp.setExperiment(measurement.experiment)

        self.setQListItemBold(self.lastMeasList, item, success)
        self.setQListItemBold(self.experimentList, item, success)

        dataPointNames = self.exp.getDataPoints()
        dataPointBuffers = measurement.dataPointBuffers
        if dataPointNames:
            self.updateDataPoints(dataPointNames)

        self.plotManager.showData(dataPointBuffers)

        self._logger.info(f"Apply measurement '{measurement.name}'")

    def updateDataPoints(self, dataPointNames):
        """
        Clears and adds all given data point names to list widget
        :param dataPointNames: list of data point names
        """
        self.plotManager.updateDataPoints(dataPointNames)

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

    def _sendRemoteParameters(self):
        """ sends the parameters set by the remote widgets, if the experiment runs """
        if self.actSendParameter.isEnabled():
            self.sendChangedParameter()

    def saveExperiments(self, fileName=None):
        """
        Writes all experiments including the remote widgets and their positions to a config file.

        :param fileName: target file, defaults to the loaded config file
        :return: `True` if successful
        """
        fileName = fileName or self._configFile
        if fileName is None:
            return self.saveExperimentsAs()
        fileName = os.path.abspath(fileName)

        # positions of widgets that have not been moved yet
        self.remotePanel.storePositions()

        try:
            text = dumpExperiments(self._fileExperiments or self._experiments)
            # keep the hand written original, comments are lost when saving
            if os.path.exists(fileName) and fileName not in self._backedUpFiles:
                shutil.copy2(fileName, fileName + '.bak')
                self._backedUpFiles.add(fileName)
            # write to a temporary file first, so a failure does not destroy the config
            fd, tmpName = tempfile.mkstemp(dir=os.path.dirname(fileName), suffix='.sreg')
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write(text)
                # mkstemp creates the file only readable by the owner
                if os.path.exists(fileName):
                    shutil.copymode(fileName, tmpName)
                else:
                    umask = os.umask(0)
                    os.umask(umask)
                    os.chmod(tmpName, 0o666 & ~umask)
                os.replace(tmpName, fileName)
            except BaseException:
                os.unlink(tmpName)
                raise
        except (OSError, yaml.YAMLError) as e:
            self._logger.error(f"Cannot save experiments to {fileName}: {e}")
            return False

        self._configFile = fileName
        self._backedUpFiles.add(fileName)
        self._logger.info(f"Saved experiments to {fileName}")
        return True

    def saveExperimentsAs(self):
        """ asks for a file name and saves all experiments to it """
        start = self._configFile or os.path.join(os.getcwd(), 'default.sreg')
        fileName, _ = QFileDialog.getSaveFileName(self, "Save experiments", start,
                                                  "Experiment files (*.sreg);;All files (*)")
        if not fileName:
            return False
        if not os.path.splitext(fileName)[1]:
            fileName += '.sreg'
        return self.saveExperiments(fileName)

    def copyRemoteSource(self):
        self.remotePanel.copySource()

    def _addStatusTime(self, caption, tooltip):
        """ adds a time with its caption on the right of the status bar, returns the label of the value """
        return self._addStatusValue(caption, tooltip, timeString(0))

    def _addStatusValue(self, caption, tooltip, value):
        """ adds a value with its caption on the right of the status bar, returns the label of the value """
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.statusBar.addPermanentWidget(sep)

        widget = QWidget()
        widget.setToolTip(tooltip)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)
        captionLabel = QLabel(caption)
        captionLabel.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        valueLabel = QLabel(value)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setBold(True)
        valueLabel.setFont(font)
        layout.addWidget(captionLabel)
        layout.addWidget(valueLabel)
        self.statusBar.addPermanentWidget(widget)
        return valueLabel

    def setTheme(self, name):
        """ applies the theme with the given name, unknown names fall back to the system theme """
        if name not in THEMES:
            name = 'System'
        applyTheme(name)
        self._settings.setValue("theme/name", name)
        # the toggle returns to the last theme of the other kind
        self._settings.setValue("theme/dark" if isDark(name) else "theme/light", name)

        for act in self._themeActions.actions():
            act.setChecked(act.text() == name)
        self.actToggleTheme.setToolTip("Switch to light mode" if isDark(name) else "Switch to dark mode")
        for act, (icon, colors) in self._themedIcons.items():
            act.setIcon(themedIcon(getResource(icon), colors and colors[isDark(name)]))
        # fixed width of the longer label so the toolbar does not shift on a swap, the style sets the margins
        for btn, a, b in self._toggleButtons:
            current = btn.defaultAction()
            widths = []
            for act in (a, b):
                btn.setDefaultAction(act)
                widths.append(btn.sizeHint().width())
            btn.setDefaultAction(current)
            btn.setFixedWidth(max(widths))
        if self.visualizer is not None:
            self.visualizer.updateTheme()

    def toggleTheme(self):
        """ switches between the last used light and dark theme """
        dark = isDark(self._settings.value("theme/name"))
        self.setTheme(self._settings.value("theme/light" if dark else "theme/dark"))


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
