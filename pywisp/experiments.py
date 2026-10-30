# -*- coding: utf-8 -*-
import ast
import logging
from collections import OrderedDict

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QItemDelegate, QTreeView

from .config import RESERVED_KEYS as NON_MODULE_KEYS
from .experimentModules import ExperimentModuleException
from .min import CONTROL_FRAME_ID, Control, controlFrame
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

    def __init__(self, targetView, parent=None):
        QObject.__init__(self, parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.targetView = targetView
        self.dataPoints = None
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
        # modules per connection that handle incoming frames
        self._frameHandlerCache = {}
        # number of failed handleFrame calls per module
        self._frameErrors = {}

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
            parent.appendRow([settingName, settingValue])

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
            self._instances[moduleName] = instance
        return instance

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
        self._instances = {}
        self._frameHandlerCache = {}
        self._settings = OrderedDict()
        self._settingItems = {}
        self.targetModel.clear()
        # insert header
        self.targetModel.setHorizontalHeaderLabels(['Property', 'Value'])
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
                self._getInstance(moduleName)
            except (ExperimentException, ExperimentModuleException) as e:
                self._logger.error(e)
                return False

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
        return True

    def _onSettingEdited(self, module, parameter, value):
        """ takes over a value the user has edited in the view """
        if module in self._settings:
            self._settings[module][parameter] = value

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

    def getDataPoints(self):
        """
        Returns all data points of the experiment.
        :return: data points
        """
        return self.dataPoints

    def handleFrame(self, frame, connection):
        """
        Returns the corresponding data points of a frame of the test rig.
        :param frame: data from the test rig
        :param connection: connection of the frame
        :return: data points or None if nothing found
        """
        if frame.id == CONTROL_FRAME_ID:
            self.stopExperiment(broadcast=False)
            self._logger.warning("rig missed heartbeat! disconnecting...")
            self.missedbeat.emit()
            return None
        for mod, name in self._frameHandlers(connection):
            try:
                dataPoints = mod.handleFrame(frame)
            except Exception:
                self._reportFrameError(name, frame)
                continue
            if dataPoints:
                return dataPoints

        return None

    def _frameHandlers(self, connection):
        """
        Returns the modules handling frames of the given connection.
        The result is cached, since this is called for every received frame.
        """
        handlers = self._frameHandlerCache.get(connection)
        if handlers is None:
            handlers = [(mod, name) for mod, name in self._activeModuleInstances()
                        if mod.connection == connection]
            self._frameHandlerCache[connection] = handlers
        return handlers

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
        Calls a parameter function of a module and converts the result to connection data.
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
            return []

        frames = []
        for frame in self.paramsToConnData(params, mod.connection):
            problem = checkFrame(frame)
            if problem is None:
                frames.append(frame)
                continue
            msg = f"{name}.{funcName}() returned an invalid frame {frame!r}: {problem}"
            if abort:
                raise ExperimentModuleException(msg)
            self._logger.error(msg + ", dropping it")
        return frames

    def updateSendParameter(self, module, parameter, value):
        if module in self.modSets:
            self.modSets[module][parameter] = value

    def runExperiment(self):
        """
        Sends all start parameters of all modules that are registered in the target model to start an experiment and
        adds and frame with id 1 and payload 1 as general start command.
        """
        data = []
        self.runningExperiment = True
        self._frameErrors = {}
        try:
            for mod, name, settings in self.activeModules():

                self.modSets[name] = cp.copy(settings)

                data.extend(self._collectParams(mod, name, 'getStartParams', settings, abort=True))
                data.extend(self._collectParams(mod, name, 'getParams', settings, abort=True))

        except ExperimentModuleException as eme:
            self._logger.error(eme)
            self.runningExperiment = False
            self.expFinished.emit()
            self.expStop.emit()
            return

        data.append(controlFrame(Control.START))
        for _data in data:
            self.sendData.emit(_data)

    def sendChangedParameterExperiment(self):
        """
        Sends changed parameters of all modules that are registered in the target model to an experiment.
        """
        data = []
        for mod, name, settings in self.activeModules():

            if self.modSets.get(name) == settings:
                continue
            self.modSets[name] = cp.copy(settings)
            data.extend(self._collectParams(mod, name, 'getParams', settings))

        for _data in data:
            self.sendData.emit(_data)

    def sendParameterExperiment(self):
        """
        Sends all parameters of all modules that are registered in the target model to an experiment.
        """
        data = []
        for mod, name, settings in self.activeModules():

            data.extend(self._collectParams(mod, name, 'getParams', settings))

        for _data in data:
            self.sendData.emit(_data)

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

    def paramsToConnData(self, params, conn):
        if not params:
            return []
        if not isinstance(params, list):
            params = [params]
        return [dict(p, connection=conn) if isinstance(p, dict) else p for p in params]


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
    if fid == CONTROL_FRAME_ID:
        return f"the id {CONTROL_FRAME_ID} is reserved for the experiment control"
    if not isinstance(frame.get('msg'), (bytes, bytearray)):
        return "the payload 'msg' must be bytes"
    return None
