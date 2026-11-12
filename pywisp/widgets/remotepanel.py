# -*- coding: utf-8 -*-
"""
The content of the remote dock: movable widgets that set parameters of the experiment.
"""
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from ..config import dumpExperiments
from .dialogs import RemoteWidgetEdit
from .remote import REMOTE_WIDGETS, FreeLayout

__all__ = ["RemotePanel"]


class RemotePanel(QWidget):
    """
    Shows the remote widgets of an experiment and sets their parameters in the
    :class:`pywisp.experiments.ExperimentInteractor`.

    The widgets are configured in the `Remote` section of the experiment config, the panel
    keeps that section up to date when widgets are added, edited, moved or removed.
    """
    #: parameters have been set by a widget, they should be sent to the rig
    parametersChanged = pyqtSignal()
    #: the user wants to save the experiments
    saveRequested = pyqtSignal()

    def __init__(self, interactor, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.exp = interactor
        # config of the shown experiment, its 'Remote' section holds the widgets
        self.expConfig = None
        self.gamepad = None

        self.widgetLayout = FreeLayout()
        self.setLayout(self.widgetLayout)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showMenu)

    @property
    def widgets(self):
        return self.widgetLayout.list

    def _remote(self, create=False):
        """ the 'Remote' section of the shown experiment """
        if self.expConfig is None:
            return None
        if create and not self.expConfig.get('Remote'):
            self.expConfig['Remote'] = {}
        return self.expConfig.get('Remote')

    def _settings(self):
        """ the current settings of the experiment by module """
        exp = self.exp.getExperiment()
        del exp['Name']
        return exp

    def setExperimentConfig(self, expConfig):
        """
        Shows the widgets of the given experiment config, `None` removes all widgets.
        """
        self.widgetLayout.clearAll()
        self.expConfig = expConfig
        remote = self._remote()
        if remote is None:
            return
        if not isinstance(remote, dict):
            self._logger.warning("Remote not correct configured in file!")
            return
        for name, config in remote.items():
            config['name'] = name
            self.addWidget(config)

    def setGamepad(self, gamepad):
        """ (re-)connect all widgets to the given gamepad, `None` disconnects them """
        self.gamepad = gamepad
        for wid in self.widgets:
            wid.updateGamepad(gamepad)

    def addWidget(self, config=None, **kwargs):
        """
        Adds a new widget
        :param config: config of the widget, if `None` it is created with the widget editor
        """
        if self.expConfig is None:
            self._logger.error("No experiment selected!")
            return
        exp = self._settings()
        if not config:
            config, ok = RemoteWidgetEdit.getData(exp=exp, **kwargs)
            if not ok:
                return
            self._remote(create=True)[config['name']] = config

        cls = REMOTE_WIDGETS.get(config['widgetType'])
        if cls is None:
            self._logger.error(f"Unknown remote widget type '{config['widgetType']}'")
            return
        widget = cls.fromConfig(config, exp)
        if widget is None:
            return
        widget.setFixedSize(*cls.size)
        # looked up on every call, so it can be replaced, e.g. in tests
        widget.connectActivation(lambda wid: self.widgetActivated(wid))
        widget.editAction.triggered.connect(lambda _, widget=widget: self.configWidget(widget))
        widget.removeAction.triggered.connect(lambda _, widget=widget: self.removeWidget(widget))
        if widget.label:
            self.widgetLayout.addWidget(widget.label)

        position = config.get('position')
        if position is None:
            # place new widgets in two columns
            cnt = self.widgetLayout.count()
            position = ((cnt % 2) * 200, (cnt // 2) * 40)
        widget.placeAt(*position)
        widget.onMoved = self.widgetMoved
        self.widgetLayout.addWidget(widget)
        widget.updateGamepad(self.gamepad)

    def configWidget(self, widget, editWidget=True):
        """ edits a widget with the widget editor """
        config, ok = RemoteWidgetEdit.getData(self._settings(), editWidget, **(widget.getData()))
        if not ok:
            return
        remote = self._remote(create=True)
        remote.pop(widget.widgetName, None)
        widget.applyConfig(config)
        config['position'] = widget.position()
        remote[config['name']] = config
        widget.updateData()

    def removeWidget(self, widget):
        remote = self._remote()
        if remote is not None:
            remote.pop(widget.widgetName, None)
        self.widgetLayout.removeWidget(widget)

    def widgetMoved(self, widget):
        """ store the position of a moved widget in the experiment """
        config = (self._remote() or {}).get(widget.widgetName)
        if config is not None:
            config['position'] = widget.position()

    def storePositions(self):
        """ stores the positions of all widgets, also of those that have not been moved yet """
        for widget in self.widgets:
            self.widgetMoved(widget)

    def widgetActivated(self, widget):
        """
        Gets called when the user activates a widget. Sets the parameters of the widget, they are
        sent to the rig at once with :attr:`parametersChanged`.
        :param widget: the widget the user interacted with
        """
        for module, parameter, value in widget.updates():
            self.exp.setParameter(module, parameter, value)
            self.syncWidgets(module, parameter, value, source=widget)
        self.parametersChanged.emit()

        # e.g. the reset value of a push button, it is not sent and not detected as change
        for module, parameter, value in widget.resets():
            self.exp.setParameter(module, parameter, value)
            self.exp.updateSendParameter(module, parameter, value)

    def syncWidgets(self, module, parameter, value, source=None):
        """ shows the value on all other widgets of the given parameter, without sending it """
        for wid in self.widgets:
            if wid is not source:
                wid.showValue(module, parameter, value)

    def copySource(self):
        """ copies the 'Remote' section of the experiment to the clipboard """
        if self.expConfig is None:
            self._logger.error("No experiment selected!")
            return
        self.storePositions()
        text = dumpExperiments([{'Remote': self._remote() or {}}])
        # indented like an entry of an experiment, without the list marker
        text = "  " + text[2:]
        QApplication.clipboard().setText(text)

    def showMenu(self, position):
        """
        Gets called when a user opens the context menu of the panel
        :param position: the position where the user opened the context menu
        """
        menu = QMenu(self)
        addAction = menu.addAction("Add widget")
        menu.addSeparator()
        saveAction = menu.addAction("Save experiments")
        copyAction = menu.addAction("Copy remote source")
        action = menu.exec(self.mapToGlobal(position))
        if action == addAction:
            self.addWidget()
        elif action == saveAction:
            self.saveRequested.emit()
        elif action == copyAction:
            self.copySource()
