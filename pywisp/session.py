# -*- coding: utf-8 -*-
"""
Run orchestration of an experiment without a user interface.

A :class:`Session` owns the connection to the rig and the experiment interactor. It sends the parameters,
starts and stops the experiment, checks the confirmations of the rig and stores the received data in the
buffers of the running measurement. It only uses QtCore and runs under a ``QCoreApplication``, the gui
(:class:`pywisp.MainGui`) reacts to its signals.
"""
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from .connectionManager import ConnectionManager
from .experiments import ExperimentInteractor, rigStopReason
from .measurement import Measurement, addDataPointValue

__all__ = ["Session"]


class Session(QObject):
    """
    Runs experiments on the rig.

    The parameters are sent first and the experiment is started once the rig confirmed them with a sync,
    rigs without sync support are started right away. Rigs that send status frames confirm the start,
    a start that is not confirmed is tried once more. The rig may stop the experiment itself, it is
    never restarted automatically then.
    """
    #: no experiment is running
    IDLE = 'idle'
    #: the parameters are sent, waiting for the rig to confirm them before the start
    SYNCING = 'syncing'
    #: the start command is sent, waiting for the rig to confirm it
    STARTING = 'starting'
    #: the experiment runs (confirmed by the rig, or the rig does not confirm starts)
    RUNNING = 'running'

    #: one of :attr:`IDLE`, :attr:`SYNCING`, :attr:`STARTING`, :attr:`RUNNING`, emitted on every stop as well
    stateChanged = pyqtSignal(str)
    #: a measurement has been created for the started run
    measurementStarted = pyqtSignal(object)
    #: the run of the measurement ended
    measurementFinished = pyqtSignal(object)
    #: the measurement of a start that is tried again has been removed from :attr:`measurements`
    measurementDropped = pyqtSignal(object)
    #: data arrived, once per batch of frames: time of the last data [s], `True` if new buffers were created
    dataReceived = pyqtSignal(float, bool)
    #: problem of the communication with the rig, `None` once solved
    commError = pyqtSignal(object)
    #: the experiment was not started, since the rig did not confirm the parameters
    startAborted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.state = self.IDLE

        self.connectionManager = ConnectionManager(self)
        self.exp = ExperimentInteractor(self)
        cm = self.connectionManager
        cm.stateChanged.connect(self._onConnectionStateChanged)
        cm.connectionLost.connect(self.disconnect)
        cm.rigStatusChanged.connect(self._onRigStatusChanged)
        cm.startConfirmed.connect(self._onStartConfirmed)
        cm.startFailed.connect(self._onStartFailed)
        cm.syncConfirmed.connect(self._onSyncConfirmed)
        cm.syncFailed.connect(self._onSyncFailed)
        cm.rigRestarted.connect(lambda: self.exp.clearRigSettings())
        cm.framesReceived.connect(self.handleFrames)
        cm.activeConnectionChanged.connect(self.exp.setConnection)
        self.exp.sendData.connect(cm.write)
        self.exp.setConnection(cm.activeConnection)
        self.exp.expFinished.connect(self._onExpFinished)
        self.exp.rigStopped.connect(self._onRigStopped)
        self.exp.expStop.connect(self.stop)

        #: interval of the heartbeat [ms] of the run, 0 disables it, see :meth:`start`
        self.heartbeatTime = 0
        #: all recorded measurements
        self.measurements = []
        #: the measurement of the run, `None` if none runs
        self.runningMeasurement = None
        #: buffers the data of the run is stored in, kept after the run ended until :meth:`stop`
        self.currentBuffers = None
        self._dataWarnings = set()
        # start of the running experiment confirmed by the rig, a second start attempted
        self._startConfirmed = False
        self._startRetried = False
        # sync id of all parameters sent again after a failed sync, None if none is pending
        self._recoverySyncId = None
        # sync id of the parameters sent before the start, None if none is pending
        self._startSyncId = None
        # settings sent with the pending syncs {syncId: {module: settings}}, confirmed with the sync
        self._syncSnapshots = {}

    @property
    def isConnected(self):
        """ `True` if the connection to the rig is established """
        return self.connectionManager.isConnected

    @property
    def isActive(self):
        """ `True` from the start until the experiment is stopped """
        return self.state != self.IDLE

    def _setState(self, state):
        self.state = state
        self.stateChanged.emit(state)

    def connect(self):
        """ establishes the active connection in the background """
        self.connectionManager.connect()

    def disconnect(self):
        """ stops a running experiment and disconnects """
        if self.isActive:
            self.stop()
        self.connectionManager.disconnect()

    def setExperiment(self, exp):
        """
        Applies an experiment, see :meth:`ExperimentInteractor.setExperiment`.
        :return: `True` if successful
        """
        return self.exp.setExperiment(exp)

    def start(self, heartbeatTime=0):
        """
        Sends the parameters of the applied experiment, once the rig confirmed them with a sync the
        experiment is started, see :meth:`_beginRun`.
        :param heartbeatTime: interval of the heartbeat [ms] during the run, 0 disables it
        :return: `False` if the experiment cannot be started
        """
        if self.exp.name is None:
            self._logger.error("No experiment selected!")
            return False
        if not self.exp.getDataPoints():
            self._logger.error("The selected experiment does not provide any data points!")
            return False
        self._logger.info(f"Experiment: {self.exp.name}")
        self.heartbeatTime = heartbeatTime
        # stop stays possible while the rig confirms the parameters
        self._setState(self.SYNCING)

        if self.connectionManager.isResponding() is False:
            self._logger.warning("the rig does not respond")
        self._startConfirmed = False
        self._startRetried = False
        self.commError.emit(None)
        self._prepareStart()
        return True

    def _prepareStart(self):
        """ sends the parameters, the rig confirms them with a sync before the start command is sent """
        expected = self.exp.prepareExperiment()
        if expected is None:
            # the experiment has already been stopped
            return
        syncId = self.connectionManager.sync(expected)
        if syncId is None:
            self._logger.warning("The rig does not confirm parameters (no sync support), "
                                 "starting without confirmation")
            # not confirmed, only taken over for the parameter log
            self.exp.confirmSettings(self.exp.lastSent)
            self._beginRun(expected)
            return
        self._startSyncId = syncId
        self._syncSnapshots[syncId] = self.exp.lastSent

    def _beginRun(self, expected):
        """
        Creates the measurement and sends the start command.
        :param expected: the frames the rig has to report with the start, see
            :meth:`ConnectionManager.expectStart`, none after a confirmed sync
        """
        measurement = Measurement(len(self.measurements) + 1, self.exp.getExperiment(), self.exp.getDataPoints())
        self.measurements.append(measurement)
        self.runningMeasurement = measurement
        self.currentBuffers = measurement.dataPointBuffers
        self._dataWarnings = set()
        self.measurementStarted.emit(measurement)

        self.connectionManager.startHeartbeat(self.heartbeatTime)
        self.exp.runExperiment()
        # rigs that send status frames confirm the start
        self._setState(self.STARTING if self.connectionManager.expectStart(expected) else self.RUNNING)

        rig = self.exp.rigSettings or {}
        measurement.logParameters(0.0, [(module, key, value) for module in measurement.experiment if module in rig
                                        for key, value in rig[module].items()])

    def stop(self):
        """ stops the experiment and the checks of the rig, the buffers of the run are detached afterwards """
        self.connectionManager.stopHeartbeat()
        self.connectionManager.cancelStartCheck()
        self.connectionManager.cancelSyncChecks()
        self._startConfirmed = False
        self._recoverySyncId = None
        self._startSyncId = None
        self._syncSnapshots.clear()
        self.exp.stopExperiment()
        # the listeners show the complete data, then the buffers of the finished run are detached, so
        # frames arriving late do not modify the stored measurement
        self._setState(self.IDLE)
        self.currentBuffers = None

    def sendParameters(self, changedOnly=False):
        """
        Sends the parameters of the running experiment, the rig confirms them with a sync.
        :param changedOnly: only send the settings changed since they were sent last
        :return: the sync id, `None` if nothing was sent or the rig does not support syncs
        """
        if self.runningMeasurement is None:
            self._logger.warning("No experiment is running!")
            return None
        if changedOnly:
            return self._syncParameters(self.exp.sendChangedParameterExperiment())
        return self._syncParameters(self.exp.sendParameterExperiment())

    def _syncParameters(self, expected):
        """
        Lets the rig confirm the parameters sent during the run.
        :return: the sync id, `None` if nothing was sent or the rig does not support syncs
        """
        if expected is None:
            return None
        syncId = self.connectionManager.sync(expected)
        if syncId is None:
            # rigs without sync support do not confirm, the sent values are logged
            self._logParameters(self.exp.confirmSettings(self.exp.lastSent))
        else:
            self._syncSnapshots[syncId] = self.exp.lastSent
        return syncId

    def _logParameters(self, changes):
        """ logs changed rig values in the running measurement at the time of the last data """
        measurement = self.runningMeasurement
        if measurement is not None and changes:
            measurement.logParameters(measurement.lastTime, changes)

    def _onSyncConfirmed(self, syncId):
        snapshot = self._syncSnapshots.pop(syncId, None)
        changes = self.exp.confirmSettings(snapshot) if snapshot is not None else []
        if syncId == self._startSyncId:
            self._startSyncId = None
            self._logger.info("Parameters confirmed by the rig, starting the experiment")
            # the sync reset the frame counter of the rig, it reports no frames with the start
            self._beginRun([])
            return
        self._logParameters(changes)
        if syncId == self._recoverySyncId:
            self._recoverySyncId = None
            self.commError.emit(None)
            self._logger.info("Parameters confirmed by the rig after sending them again")

    def _onSyncFailed(self, syncId, reason):
        """
        Does not start the experiment if the parameters sent before the start are not confirmed.
        During the run all parameters are sent once more, the experiment is stopped if they are not confirmed either.
        """
        self._syncSnapshots.pop(syncId, None)
        if syncId == self._startSyncId:
            self._startSyncId = None
            msg = f"Parameters not confirmed by the rig, the experiment is not started: {reason}"
            self._logger.error(msg)
            self.stop()
            self.commError.emit(msg)
            self.startAborted.emit(msg)
            return
        if not self.isActive:
            return
        if self._recoverySyncId is not None:
            if syncId == self._recoverySyncId:
                self._logger.error(f"Parameters not confirmed, experiment stopped: {reason}")
                self.commError.emit(f"Parameters not confirmed, experiment stopped: {reason}")
                self.stop()
            # older changes are covered by sending all parameters again
            return
        self._logger.warning(f"Parameters not confirmed, sending all of them again: {reason}")
        self.commError.emit(f"Parameters not confirmed, sending all of them again: {reason}")
        self.connectionManager.cancelSyncChecks()
        self._recoverySyncId = self._syncParameters(self.exp.sendParameterExperiment())

    def _onStartConfirmed(self):
        if not self.isActive:
            return
        self._startConfirmed = True
        self._setState(self.RUNNING)
        self.commError.emit(None)
        self._logger.info("Start confirmed by the rig")

    def _onStartFailed(self, reason):
        """ sends the parameters once more, stops the experiment if that fails as well """
        if not self.isActive:
            return
        if not self._startRetried:
            self._startRetried = True
            self._logger.warning(f"Start not confirmed, trying again: {reason}")
            self.commError.emit(f"Start not confirmed, trying again: {reason}")
            failed = self.runningMeasurement
            self.exp.stopExperiment()
            # the retry records a new measurement, one per start of the user
            self._dropMeasurement(failed)
            self._prepareStart()
            return
        self._logger.error(f"Start not confirmed, experiment stopped: {reason}")
        self.commError.emit(f"Start not confirmed, experiment stopped: {reason}")
        self.stop()

    def _dropMeasurement(self, measurement):
        """ removes a measurement from the list of measurements """
        if measurement is None:
            return
        self.measurements.remove(measurement)
        if self.runningMeasurement is measurement:
            self.runningMeasurement = None
        self.measurementDropped.emit(measurement)

    def _onExpFinished(self):
        """
        Marks the running measurement as finished at the end of an experiment.
        The measurement already references the buffers of the run, so nothing is copied.
        """
        measurement = self.runningMeasurement
        if measurement is None:
            return
        measurement.finish()
        self.runningMeasurement = None
        self.measurementFinished.emit(measurement)

    def _onRigStopped(self, reason=0):
        """ the rig stopped the experiment (missed heartbeat or error), it is not restarted """
        self.stop()
        self.commError.emit(rigStopReason(reason))

    def _onRigStatusChanged(self):
        """ stops the experiment if the rig ended it by itself """
        status = self.connectionManager.rigStatus
        # only rigs that support syncs confirm parameters
        self.exp.trackRig(status is not None and status[0].syncId is not None)
        if status is not None and self._startConfirmed and not status[0].running and self.isActive:
            self._logger.error("the rig ended the experiment, e.g. by a restart")
            self.stop()
            self.commError.emit("the rig ended the experiment, e.g. by a restart")

    def _onConnectionStateChanged(self, state):
        if state == ConnectionManager.DISCONNECTED:
            # the rig values are unknown until the next confirmation
            self.exp.trackRig(False)
            self.exp.clearRigSettings()

    def handleFrames(self, frames):
        """
        Stores the data points of the received frames in the buffers of the running measurement.
        :param frames: list of frames received by the connection
        """
        lastTime = None
        newBuffers = False
        handleFrame = self.exp.handleFrame
        for frame in frames:
            data = handleFrame(frame)
            # looked up per frame, a frame of the rig may stop the run and detach the buffers
            buffers = self.currentBuffers
            if data is None or buffers is None:
                continue
            try:
                time = data['Time'] / 1000.0
                dataPoints = data['DataPoints']
            except (KeyError, TypeError):
                self._warnOnce(('format',),
                               "handleFrame() must return a dict with the keys 'Time' and 'DataPoints'")
                continue

            elementNames = self.exp.getDataPointElements()
            for key, value in dataPoints.items():
                try:
                    newBuffers |= addDataPointValue(buffers, key, time, value, elementNames.get(key))
                except KeyError:
                    self._warnOnce(('key', key), f"Received unknown data point '{key}'")
                except (TypeError, ValueError):
                    self._warnOnce(('value', key),
                                   f"Data point '{key}' must be a number or a 1d array of numbers, got {value!r}")
            lastTime = time

        if lastTime is not None:
            if self.runningMeasurement is not None:
                self.runningMeasurement.lastTime = lastTime
            self.dataReceived.emit(lastTime, newBuffers)

    def _warnOnce(self, key, msg):
        """ log a warning only once per experiment run, the data path is called at the frame rate """
        if key not in self._dataWarnings:
            self._dataWarnings.add(key)
            self._logger.warning(msg)
