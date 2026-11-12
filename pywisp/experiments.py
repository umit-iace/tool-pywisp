# -*- coding: utf-8 -*-
import ast
import logging
from collections import OrderedDict

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QBrush, QColor, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QItemDelegate, QTreeView

from .config import RESERVED_KEYS as NON_MODULE_KEYS
from .experimentModules import ExperimentModuleException
from .measurement import elementName
from .min import CONTROL_FRAME_ID, SYSTEM_FRAME_IDS, Control, controlFrame
from .registry import *
import copy as cp


class ExperimentException(Exception):
    pass


class ExperimentModel(QStandardItemModel):
    """
    Model to provide item model that includes an additional name attribute.

    It only displays the settings of the :class:`ExperimentInteractor`, values edited
    by the user are reported with :attr:`settingEdited`.
    """
    #: module, setting and new value of a setting edited in the view
    settingEdited = pyqtSignal(str, str, object)

    def __init__(self, parent=None):
        QStandardItemModel.__init__(self, parent)
        self._name = None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        ok = super().setData(index, value, role)
        if role == Qt.ItemDataRole.EditRole and index.column() == 1 and index.parent().isValid():
            module = self.itemFromIndex(index.parent()).data(PropertyItem.RawDataRole)
            key = self.itemFromIndex(index.siblingAtColumn(0)).data(PropertyItem.RawDataRole)
            # the item keeps its old value if the text cannot be parsed
            self.settingEdited.emit(module, key, self.itemFromIndex(index).data(PropertyItem.RawDataRole))
        return ok

    def setName(self, name):
        self._name = name

    def getName(self):
        return self._name

    def flags(self, index):
        if index.column() == 1:
            return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled
        else:
            return Qt.ItemFlag.ItemIsEnabled


class PropertyItem(QStandardItem):
    RawDataRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, data):
        QStandardItem.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._text = self._getText(data)

    def type(self):
        return QStandardItem.ItemType.UserType

    def _getText(self, data):
        return str(data)

    def setData(self, Any, role=None, *args, **kwargs):
        if role == Qt.ItemDataRole.EditRole:
            try:
                self._data = ast.literal_eval(Any)
            except (SyntaxError, ValueError) as e:
                self._logger.exception(e)
                return
            self._text = str(self._data)

        elif role == self.RawDataRole:
            self._data = Any
            self._text = self._getText(Any)

        else:
            raise NotImplementedError

    def data(self, role=None, *args, **kwargs):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text
        elif role == Qt.ItemDataRole.EditRole:
            if isinstance(self._data, str):
                return "'" + self._text + "'"
            else:
                return self._text
        elif role == self.RawDataRole:
            return self._data

        else:
            return super().data(role, *args, **kwargs)


class PropertyDelegate(QItemDelegate):
    """
    A delegate that manages all property settings.
    For now it uses a combobox for experimentModules and a standard
    delegate for the rest.
    """

    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        if index.parent().isValid():
            return QItemDelegate.createEditor(self, parent, option, index)
        else:
            # no parent -> top of hierarchy
            return None

    def setEditorData(self, editor, index):
        QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        QItemDelegate.setModelData(self, editor, model, index)


class ExperimentView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegateForColumn(1, PropertyDelegate(self))

    def sizeHint(self):
        return QSize(300, 150)

    def minimumSizeHint(self):
        return self.sizeHint()


class ExperimentInteractor(QObject):
    """
    Class that interacts between the gui which controls the programs execution
    and the Experiment
    """
    expFinished = pyqtSignal()
    expStop = pyqtSignal()
    sendData = pyqtSignal(object)
    missedbeat = pyqtSignal()

    #: background of a rig value that equals the value (`True`) or not (`False`)
    RIG_COLORS = {True: QColor(92, 184, 92, 110), False: QColor(217, 83, 79, 110)}

    def __init__(self, targetView, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.targetView = targetView
        self.dataPoints = None
        self.dataPointElements = {}
        self.runningExperiment = False
        # create model
        self.targetModel = ExperimentModel(self)
        self.targetModel.itemChanged.connect(self.itemChanged)
        self.targetModel.settingEdited.connect(self._onSettingEdited)
        # settings of the modules of the applied experiment, the model only displays them
        self._settings = OrderedDict()
        # value items of the model by (module, setting)
        self._settingItems = {}
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
        # the rig confirms parameters, its values are shown with colors
        self._trackRig = False
        # rig items of the model by (module, setting)
        self._rigItems = {}

    def _addSettings(self, moduleName, parent):
        """
        Sets the settings from an experiment module.
        :param moduleName: the given experiment module name
        :param parent: the given experiment module parent
        """
        settings = self._readSettings(moduleName)

        for key, val in settings.items():
            settingName = PropertyItem(key)
            settingValue = PropertyItem(val)
            parent.appendRow([settingName, settingValue, QStandardItem()])

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

    def itemChanged(self, item):
        """
        Updates settings of an experiment module.
        :param item: the given experiment module
        """
        if item.parent():
            return

        idx = item.index()
        moduleItem = idx.model().item(idx.row())

        # delete all old settings
        moduleItem.removeRows(0, moduleItem.rowCount())

        # insert new settings
        parent = moduleItem.index().model().itemFromIndex(moduleItem.index())
        moduleName = parent.data(role=PropertyItem.RawDataRole)
        self._addSettings(moduleName, parent)

    def getSettings(self, item):
        """
        Returns a dict with all settings of the item of an experiment.
        :param item: experiment module
        :return: settings
        """
        settings = OrderedDict()
        for row in range(item.rowCount()):
            propertyName = self.targetModel.data(item.child(row, 0).index(),
                                                 role=PropertyItem.RawDataRole)
            propertyVal = self.targetModel.data(item.child(row, 1).index(),
                                                role=PropertyItem.RawDataRole)
            settings.update({propertyName: propertyVal})

        return settings

    def setExperiment(self, exp):
        """
        Load the given experiment settings into the target model.
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
        Edit the given experiment settings into the target model.
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
        declaredElements = {}
        self._instances = {}
        self._frameHandlerCache = None
        self._settings = OrderedDict()
        self._settingItems = {}
        self._rigItems = {}
        self.targetModel.clear()
        # insert header
        self.targetModel.setHorizontalHeaderLabels(['Property', 'Value', 'Rig'])
        # insert main items
        for key, value in exp.items():
            if key == 'Name':
                self.targetModel.setName(value)
            if key in NON_MODULE_KEYS:
                continue

            name = PropertyItem(key)
            value = None
            newItems = [name, value]
            self.targetModel.appendRow(newItems)

        # insert default settings
        for row in range(self.targetModel.rowCount()):
            index = self.targetModel.index(row, 0)
            try:
                parent = index.model().itemFromIndex(index)
                moduleName = parent.data(role=PropertyItem.RawDataRole)
                self._addSettings(moduleName, parent)
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
                modules = self.targetModel.findItems(moduleName)[0]

                for row in range(modules.rowCount()):
                    if self.targetModel.data(modules.child(row, 0).index()) == valKey:
                        valueIdx = self.targetModel.index(row, 1, self.targetModel.indexFromItem(modules))
                        self.targetModel.setData(valueIdx, valVal, role=PropertyItem.RawDataRole)
                        break
                else:
                    self._logger.warning(f"_applyExperiment(): Setting: '{valKey}' not "
                                         f"available for Module: '{moduleName}'")

        for row in range(self.targetModel.rowCount()):
            moduleItem = self.targetModel.item(row, 0)
            moduleName = moduleItem.data(role=PropertyItem.RawDataRole)
            self._settings[moduleName] = self.getSettings(moduleItem)
            for child in range(moduleItem.rowCount()):
                key = moduleItem.child(child, 0).data(role=PropertyItem.RawDataRole)
                self._settingItems[(moduleName, key)] = moduleItem.child(child, 1)
                self._rigItems[(moduleName, key)] = moduleItem.child(child, 2)
        self._updateRigItems()

        for mod, _, settings in self.activeModules():
            mod.settings = OrderedDict(settings)

        self.targetView.setModel(self.targetModel)

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
        item = self._settingItems[(module, parameter)]
        item.setData(value, role=PropertyItem.RawDataRole)
        self.targetModel.dataChanged.emit(item.index(), item.index())
        self._updateRigItem(module, parameter)
        return True

    def _onSettingEdited(self, module, parameter, value):
        """ takes over a value the user has edited in the view """
        if module in self._settings:
            self._settings[module][parameter] = value
            self._updateRigItem(module, parameter)

    def trackRig(self, enabled):
        """
        Shows the rig values with their background, green if they equal the values, else red.
        Only for rigs that confirm the parameters, otherwise the rig values are not shown.
        """
        self._trackRig = enabled
        self._updateRigItems()

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
        self._updateRigItems()
        return changes

    def clearRigSettings(self):
        """ forgets the rig values, e.g. after a disconnect or a restart of the rig """
        self.rigSettings = None
        self._updateRigItems()

    def _updateRigItems(self):
        for module, key in self._rigItems:
            self._updateRigItem(module, key)

    def _updateRigItem(self, module, key):
        item = self._rigItems.get((module, key))
        if item is None:
            return
        rig = (self.rigSettings or {}).get(module, {})
        known = self._trackRig and key in rig
        item.setText(str(rig[key]) if known else "")
        brush = None
        if self._trackRig:
            brush = QBrush(self.RIG_COLORS[known and rig[key] == self._settings[module][key]])
        item.setData(brush, Qt.ItemDataRole.BackgroundRole)

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
            self.stopExperiment(broadcast=False)
            self._logger.warning("rig missed heartbeat! the experiment has been stopped by the rig")
            self.missedbeat.emit()
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
        Sends changed parameters of all modules that are registered in the target model to an experiment.

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
        Sends all parameters of all modules that are registered in the target model to an experiment.

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
        Sends all stop parameters of all modules that are registered in the target model to stop an experiment and
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
        exp = {'Name': self.targetModel.getName()}

        for _, name, settings in self.activeModules():
            exp[name] = settings

        return exp

    def _activeModuleInstances(self):
        """ like :meth:`activeModules`, but without reading the settings from the model """
        for row in range(self.targetModel.rowCount()):
            name = self.targetModel.item(row, 0).data(role=PropertyItem.RawDataRole)
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
