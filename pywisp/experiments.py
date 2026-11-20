# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict

from PyQt6.QtCore import pyqtSignal, QObject

from .config import RESERVED_KEYS as NON_MODULE_KEYS
from .experimentModules import ExperimentModuleException
from .measurement import elementName
from .min import CONTROL_FRAME_ID, SYSTEM_FRAME_IDS, Control, controlFrame
from .registry import *
import copy as cp


class ExperimentException(Exception):
    pass


def rigStopReason(reason):
    """ text for the reason of a stop by the rig (second payload byte of its control frame) """
    if reason == 0:
        return "the rig missed the heartbeat and stopped the experiment"
    return f"the rig stopped the experiment (error code {reason})"


class ExperimentInteractor(QObject):
    """
    Class that interacts between the gui which controls the programs execution
    and the Experiment
    """
    expFinished = pyqtSignal()
    expStop = pyqtSignal()
    sendData = pyqtSignal(object)
    #: the rig missed the heartbeat and stopped the experiment, kept for compatibility, see :attr:`rigStopped`
    missedbeat = pyqtSignal()
    #: the rig stopped the experiment by itself, with the reason: 0 missed heartbeat, else a rig specific error code
    rigStopped = pyqtSignal(int)
    #: an experiment was applied, its modules and settings changed, see :meth:`getExperiment`
    experimentChanged = pyqtSignal()
    #: module, setting and new value of a setting set with :meth:`setParameter`
    settingChanged = pyqtSignal(str, str, object)
    #: :attr:`rigSettings` or :attr:`trackingRig` changed
    rigSettingsChanged = pyqtSignal()

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        #: name of the applied experiment
        self.name = None
        self.dataPoints = None
        self.dataPointElements = {}
        self.runningExperiment = False
        # settings of the modules of the applied experiment, {module: {setting: value}}
        self._settings = OrderedDict()
        # parameter change settings
        self.modSets = {}
        # instances of the modules of the applied experiment
        self._instances = {}
        # name of the active connection, passed to the modules as their `connection` attribute
        self.connection = None
        # modules that handle incoming frames, None until first needed
        self._frameHandlerCache = None
        # number of failed handleFrame calls per module
        self._frameErrors = {}
        #: settings sent by the last parameter function, {module: settings}, see :meth:`confirmSettings`
        self.lastSent = {}
        #: settings confirmed by the rig, {module: settings}, `None` if unknown
        self.rigSettings = None
        #: the rig confirms parameters, a view shows its values compared to the settings
        self.trackingRig = False

    def _readSettings(self, moduleName):
        """
        Reads the public settings from an experiment module.
        :param moduleName: the given experiment module name
        :return: settings of module or raise an exception if module is unknown
        """
        return self._getModule(moduleName).publicSettings

    def _readDataPoints(self, moduleName):
        """
        Reads the data points from an experiment module.
        :param moduleName: the given experiment module name
        :return: data points of module or raise an exception if module is unknown
        """
        return self._getModule(moduleName).dataPoints

    @staticmethod
    def _getModule(moduleName):
        """
        Looks up a registered experiment module by name.
        :raises ExperimentException: if the module is unknown
        """
        try:
            return getRegisteredExperimentModules()[moduleName]
        except KeyError:
            raise ExperimentException(f"Experiment module '{moduleName}' is not registered!") from None

    def _getInstance(self, moduleName):
        """
        Returns the instance of a module of the applied experiment, it is created on first use.
        :raises ExperimentModuleException: if the module cannot be instantiated
        """
        instance = self._instances.get(moduleName)
        if instance is None:
            cls = self._getModule(moduleName)
            try:
                instance = cls()
            except Exception as e:
                raise ExperimentModuleException(f"Cannot create experiment module '{moduleName}': {e!r}") from e
            instance.connection = self.connection
            self._instances[moduleName] = instance
        return instance

    def setConnection(self, name):
        """
        Sets the name of the active connection, also in all module instances.
        :param name: name of the connection class
        """
        self.connection = name
        for instance in self._instances.values():
            instance.connection = name

    def getParameter(self, module, parameter):
        """ :return: the value of a setting of a module of the applied experiment """
        return self._settings[module][parameter]

    def setExperiment(self, exp):
        """
        Load the given experiment settings into the applied experiment.
        :param exp: the given experiment
        :return: `True` if successful, `False` if errors occurred.
        """
        if exp is None:
            return
        if isinstance(exp, list):
            self._logger.error("setExperiment(): only scalar input allowed!")
            return False

        return self._applyExperiment(exp)

    def editExperiment(self, exp):
        """
        Edit the given experiment settings into the applied experiment.
        :param exp: the given experiment
        :return: `True` if successful, `False` if errors occurred.
        """
        if exp is None:
            return
        if isinstance(exp, list):
            self._logger.error("editExperiment(): only scalar input allowed!")
            return False

        return self._editExperiment(exp)

    def _applyExperiment(self, exp):
        """
        Set all module settings to those provided in the experiment.
        :param exp: the provided experiment
        :return: `True` if successful, `False` if errors occurred.
        """
        self.dataPoints = []
        self._instances = {}
        self._frameHandlerCache = None
        self._settings = OrderedDict()
        self.name = exp.get('Name')
        try:
            return self._applyModules(exp)
        finally:
            self.experimentChanged.emit()

    def _applyModules(self, exp):
        """ reads the settings and data points of the modules of the experiment, see :meth:`_applyExperiment` """
        settings = OrderedDict()
        declaredElements = {}
        for moduleName in exp:
            if moduleName in NON_MODULE_KEYS:
                continue
            try:
                settings[moduleName] = OrderedDict(self._readSettings(moduleName))
                self.dataPoints += self._readDataPoints(moduleName)
                for dp, names in self._getModule(moduleName).dataPointElements.items():
                    if isinstance(names, str):
                        raise ExperimentException(f"dataPointElements of '{moduleName}': the names of '{dp}' "
                                                  f"must be a list, not the string {names!r}")
                    if dp in declaredElements:
                        raise ExperimentException(f"dataPointElements: '{dp}' is declared by more than one module")
                    declaredElements[dp] = names
                self._getInstance(moduleName)
            except (ExperimentException, ExperimentModuleException) as e:
                self._logger.error(e)
                return False
        self.dataPointElements = self._resolveElementNames(declaredElements)

        for moduleName, moduleValue in exp.items():
            if moduleName in NON_MODULE_KEYS or not moduleValue:
                continue

            for valKey, valVal in moduleValue.items():
                if valKey in settings[moduleName]:
                    settings[moduleName][valKey] = valVal
                else:
                    self._logger.warning(f"_applyExperiment(): Setting: '{valKey}' not "
                                         f"available for Module: '{moduleName}'")

        self._settings = settings
        for mod, _, modSettings in self.activeModules():
            mod.settings = OrderedDict(modSettings)

        return True

    def setParameter(self, module, parameter, value):
        """
        Sets a setting of a module of the applied experiment, it is sent with the next parameter update.
        :return: `True` if the module has the setting
        """
        settings = self._settings.get(module)
        if settings is None or parameter not in settings:
            self._logger.warning(f"Setting '{parameter}' not available for Module '{module}'")
            return False
        settings[parameter] = value
        self.settingChanged.emit(module, parameter, value)
        return True

    def trackRig(self, enabled):
        """
        Enables showing the rig values (:attr:`trackingRig`), a view colors them green if they equal the values,
        else red. Only for rigs that confirm the parameters, otherwise the rig values are not shown.
        """
        self.trackingRig = enabled
        self.rigSettingsChanged.emit()

    def confirmSettings(self, snapshot):
        """
        Takes over settings confirmed by the rig.
        :param snapshot: confirmed settings {module: settings}, e.g. :attr:`lastSent`
        :return: list of the (module, setting, value) that changed on the rig
        """
        if self.rigSettings is None:
            self.rigSettings = {}
        changes = []
        for module, settings in snapshot.items():
            rig = self.rigSettings.setdefault(module, {})
            for key, value in settings.items():
                if key not in rig or rig[key] != value:
                    changes.append((module, key, value))
                rig[key] = value
        self.rigSettingsChanged.emit()
        return changes

    def clearRigSettings(self):
        """ forgets the rig values, e.g. after a disconnect or a restart of the rig """
        self.rigSettings = None
        self.rigSettingsChanged.emit()

    def _editExperiment(self, exp):
        """
        Edit all module settings to those provided in the experiment.
        :param exp: the provided experiment
        :return: `True` if successful, `False` if errors occurred.
        """
        for moduleName, moduleValue in exp.items():
            if moduleName in NON_MODULE_KEYS or not moduleValue:
                continue
            for valKey, valVal in moduleValue.items():
                self.setParameter(moduleName, valKey, valVal)

        return True

    def _resolveElementNames(self, declared):
        """
        Checks the element names declared in `dataPointElements` of the modules, an invalid name
        is logged and replaced by the default name of the element.
        :return: element names by data point
        """
        def isDefaultName(name):
            return any(name.startswith(dp + '.') and name[len(dp) + 1:].isdigit() for dp in self.dataPoints)

        used = set(self.dataPoints)
        resolved = {}
        for dp, names in declared.items():
            if dp not in self.dataPoints:
                self._logger.error(f"dataPointElements: '{dp}' is not a data point")
                continue
            resolved[dp] = []
            for idx, name in enumerate(names):
                default = elementName(dp, idx)
                key = elementName(dp, 0, [name])
                # the keys must be unique buffer keys, also with respect to default names of other elements
                if not isinstance(name, str) or key != default and (key in used or isDefaultName(key)):
                    self._logger.error(f"dataPointElements: invalid or duplicate name {name!r} for element "
                                       f"{idx + 1} of '{dp}', using '{default}'")
                    # the number gives the default name
                    name, key = str(idx + 1), default
                used.add(key)
                resolved[dp].append(name)
        return resolved

    def getDataPointElements(self):
        """
        Returns the element names of the array data points of the experiment.
        :return: dict mapping data point names to the names of their elements
        """
        return self.dataPointElements

    def getDataPoints(self):
        """
        Returns all data points of the experiment.
        :return: data points
        """
        return self.dataPoints

    def handleFrame(self, frame):
        """
        Returns the corresponding data points of a frame of the test rig.
        :param frame: data from the test rig
        :return: data points or None if nothing found
        """
        if frame.id == CONTROL_FRAME_ID:
            # payload[0] is 0 (stop), the optional payload[1] the reason
            reason = frame.payload[1] if len(frame.payload) > 1 else 0
            self.stopExperiment(broadcast=False)
            self._logger.warning(rigStopReason(reason))
            if reason == 0:
                self.missedbeat.emit()
            self.rigStopped.emit(reason)
            return None
        for mod, name in self._frameHandlers():
            try:
                dataPoints = mod.handleFrame(frame)
            except Exception:
                self._reportFrameError(name, frame)
                continue
            if dataPoints:
                return dataPoints

        return None

    def _frameHandlers(self):
        """
        Returns the modules handling frames.
        The result is cached, since this is called for every received frame.
        """
        if self._frameHandlerCache is None:
            self._frameHandlerCache = list(self._activeModuleInstances())
        return self._frameHandlerCache

    def _reportFrameError(self, name, frame):
        """
        Logs a failing `handleFrame` call. Only the first error of a module is logged with
        its traceback, otherwise a broken module would flood the log at the frame rate.
        """
        cnt = self._frameErrors.get(name, 0) + 1
        self._frameErrors[name] = cnt
        if cnt == 1:
            self._logger.exception(f"Module '{name}' failed to handle frame {frame.id}, "
                                   f"further errors of this module are suppressed")

    def _logFrameErrorSummary(self):
        for name, cnt in self._frameErrors.items():
            self._logger.error(f"Module '{name}' failed to handle {cnt} frame(s)")
        self._frameErrors = {}

    def _collectParams(self, mod, name, funcName, settings, abort=False):
        """
        Calls a parameter function of a module and returns the valid frames.
        Errors in user code are logged instead of crashing the gui.
        :param settings: current settings of the module, also stored in its `settings` attribute
        :param abort: re-raise the error as `ExperimentModuleException`
        """
        mod.settings = OrderedDict(settings)
        try:
            params = getattr(mod, funcName)(list(settings.values()))
        except Exception as e:
            if abort:
                raise ExperimentModuleException(f"{name}.{funcName}() failed: {e!r}") from e
            self._logger.exception(f"{name}.{funcName}() failed")
            self._collectFailed = True
            return []

        frames = []
        if not params:
            params = []
        elif not isinstance(params, list):
            params = [params]
        for frame in params:
            problem = checkFrame(frame)
            if problem is None:
                frames.append(frame)
                continue
            msg = f"{name}.{funcName}() returned an invalid frame {frame!r}: {problem}"
            if abort:
                raise ExperimentModuleException(msg)
            self._logger.error(msg + ", dropping it")
            self._collectFailed = True
        return frames

    def _collectSent(self, mod, name, settings, data):
        """
        Adds the parameter frames of a module to `data`. Modules with dropped frames stay out of
        :attr:`lastSent`, others would be taken for confirmed values.
        """
        self._collectFailed = False
        data.extend(self._collectParams(mod, name, 'getParams', settings))
        # a module without frames has nothing to confirm, its settings count as on the rig
        if not self._collectFailed:
            self.lastSent[name] = cp.deepcopy(settings)

    def updateSendParameter(self, module, parameter, value):
        if module in self.modSets:
            self.modSets[module][parameter] = value

    def prepareExperiment(self):
        """
        Sends the start parameters and parameters of all modules of the applied experiment,
        :meth:`runExperiment` starts it afterwards. The sent settings are stored in :attr:`lastSent`.

        :return: the sent frames, for the rig to confirm, see :meth:`ConnectionManager.sync`,
            `None` if the experiment cannot be started
        """
        data = []
        self.lastSent = {}
        try:
            for mod, name, settings in self.activeModules():

                self.modSets[name] = cp.copy(settings)

                frames = self._collectParams(mod, name, 'getStartParams', settings, abort=True)
                frames += self._collectParams(mod, name, 'getParams', settings, abort=True)
                data.extend(frames)
                # a module without frames has nothing to confirm, its settings count as on the rig
                self.lastSent[name] = cp.deepcopy(settings)

        except ExperimentModuleException as eme:
            self._logger.error(eme)
            self.lastSent = {}
            self.expFinished.emit()
            self.expStop.emit()
            return None

        for _data in data:
            self.sendData.emit(_data)
        return self._expected(data)

    def runExperiment(self):
        """ sends the general start command (control frame), after :meth:`prepareExperiment` """
        self.runningExperiment = True
        self._frameErrors = {}
        self.sendData.emit(controlFrame(Control.START))

    @staticmethod
    def _expected(data):
        """ the sent frames, control frames excluded """
        return [_data for _data in data if _data['id'] != CONTROL_FRAME_ID]

    def sendChangedParameterExperiment(self):
        """
        Sends changed parameters of all modules that are of the applied experiment to an experiment.

        :return: the sent frames, for the rig to confirm, see
            :meth:`ConnectionManager.sync`, `None` if nothing was sent
        """
        data = []
        self.lastSent = {}
        for mod, name, settings in self.activeModules():

            if self.modSets.get(name) == settings:
                continue
            self.modSets[name] = cp.copy(settings)
            self._collectSent(mod, name, settings, data)

        for _data in data:
            self.sendData.emit(_data)
        return self._expected(data) if data else None

    def sendParameterExperiment(self):
        """
        Sends all parameters of all modules that are of the applied experiment to an experiment.

        :return: as :meth:`sendChangedParameterExperiment`
        """
        data = []
        self.lastSent = {}
        for mod, name, settings in self.activeModules():

            self._collectSent(mod, name, settings, data)

        for _data in data:
            self.sendData.emit(_data)
        return self._expected(data) if data else None

    def stopExperiment(self, broadcast=True):
        """
        Sends all stop parameters of all modules that are of the applied experiment to stop an experiment and
        adds and frame with id 1 and payload 0 as general stop command.
        """
        data = []

        if not self.runningExperiment:
            return

        self.runningExperiment = False
        for mod, name, settings in self.activeModules():

            data.extend(self._collectParams(mod, name, 'getStopParams', settings))

        # stop experiment
        if broadcast:
            data.append(controlFrame(Control.STOP))
            for _data in data:
                self.sendData.emit(_data)

        self._logFrameErrorSummary()
        self.expFinished.emit()

    def getExperiment(self):
        """
        Returns an dict for the current experiment with all settings of it.
        :return: experiment
        """
        exp = {'Name': self.name}

        for name, settings in self._settings.items():
            exp[name] = OrderedDict(settings)

        return exp

    def _activeModuleInstances(self):
        """ like :meth:`activeModules`, but without copying the settings """
        for name in self._settings:
            yield self._getInstance(name), name

    def activeModules(self):
        """ yields instance, name and a copy of the settings of every module of the applied experiment """
        for name, settings in self._settings.items():
            yield self._getInstance(name), name, OrderedDict(settings)


def checkFrame(frame):
    """
    Checks a frame returned by an experiment module.

    :return: description of the problem or `None` if the frame is valid
    """
    if not isinstance(frame, dict):
        return "frames must be dicts with the keys 'id' and 'msg'"
    fid = frame.get('id')
    if not isinstance(fid, int) or isinstance(fid, bool) or not 0 <= fid <= 255:
        return "the id must be an integer in [0, 255]"
    if fid in SYSTEM_FRAME_IDS:
        return (f"the id {fid} is reserved for the system frames "
                f"({min(SYSTEM_FRAME_IDS)}..{max(SYSTEM_FRAME_IDS)}), use another id")
    if not isinstance(frame.get('msg'), (bytes, bytearray)):
        return "the payload 'msg' must be bytes"
    return None
