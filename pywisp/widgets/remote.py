# -*- coding: utf-8 -*-
"""
Movable widgets of the remote dock, that send parameters to the experiment.
"""
import logging

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QLabel, QLayout, QMenu, QPushButton, QSlider

__all__ = ["FreeLayout", "MovableWidget", "MovablePushButton", "DoubleSlider", "MovableSlider", "MovableSwitch",
           "MovableMultiButton", "REMOTE_WIDGETS", "registerRemoteWidget"]

#: registered remote widget classes by their `widgetType`
REMOTE_WIDGETS = {}


def registerRemoteWidget(cls):
    """
    Registers a remote widget class, so it can be used in the config files and the widget editor.
    The class derives from :class:`MovableWidget` and a Qt widget and implements its interface.
    Can be used as class decorator.
    """
    if not cls.widgetType:
        raise ValueError(f"{cls.__name__} has no widgetType")
    REMOTE_WIDGETS[cls.widgetType] = cls
    return cls



class FreeLayout(QLayout):
    """
    An empty layout for widgets with no position and placement management
    """

    def __init__(self):
        super(FreeLayout, self).__init__()
        self.list = []

    def count(self):
        return len(self.list)

    def sizeHint(self):
        return QSize()

    def itemAt(self, index):
        return

    def addItem(self, QLayoutItem):
        return

    def addWidget(self, widget):
        if not isinstance(widget, QLabel):
            self.list.append(widget)
        super(FreeLayout, self).addWidget(widget)

    def removeWidget(self, widget):
        if widget in self.list:
            self.list.remove(widget)
            self._dispose(widget)
        else:
            widget.setParent(None)

    def clearAll(self):
        for widget in self.list:
            self._dispose(widget)
        self.list = []

    @staticmethod
    def _dispose(widget):
        """
        Deletes a remote widget. It is disconnected from the gamepad first, otherwise
        the hidden widget would still react to it until it is garbage collected.
        """
        widget.updateGamepad(None)
        widget.hide()
        if widget.label:
            widget.label.hide()
            widget.label.deleteLater()
        widget.deleteLater()


class MovableWidget:
    """
    Mixin that makes a widget movable via right click & drag and adds a context menu.

    Must be listed before the Qt base class, so that its event handlers take precedence.
    """
    # True if the widget is driven by an absolute (analog) gamepad axis
    gamepadAbsolute = False

    #: name of the type in the config files
    widgetType = None
    #: keys of the config besides `widgetType`, `Module`, `Parameter`, `name` and `position`
    requiredKeys = ()
    #: optional keys of the config and their defaults
    optionalKeys = {}
    #: the widget sets a list of `targets` instead of a single `Module` and `Parameter`
    hasTargets = False
    #: (width, height) of the widget in the remote dock
    size = (100, 40)

    @classmethod
    def fromConfig(cls, config, exp):
        """
        Creates the widget from its config.

        :param config: config of the widget, as in the config file
        :param exp: current settings of the experiment by module
        :return: the widget or `None` if it cannot be created
        """
        raise NotImplementedError

    @classmethod
    def completeConfig(cls, config, exp):
        """ adds entries derived from the experiment to a config created by the widget editor """

    @classmethod
    def editor(cls, dialog):
        """
        Adds the settings of this widget type to the :class:`RemoteWidgetEdit` dialog.

        :return: function returning the edited settings as dict
        """
        return dict

    def applyConfig(self, config):
        """ takes over an edited config, :meth:`updateData` is called afterwards """
        self.widgetName = config['name']
        self.module = config.get('Module')
        self.parameter = config.get('Parameter')

    def connectActivation(self, callback):
        """ calls `callback(widget)` whenever the user activates the widget """
        raise NotImplementedError

    def updates(self):
        """ list of `(module, parameter, value)` an activation sets and sends to the rig """
        return []

    def resets(self):
        """ list of `(module, parameter, value)` set after sending the updates, without sending them """
        return []

    def showValue(self, module, parameter, value):
        """ shows a value another widget has set, if this widget belongs to the parameter """

    def __init__(self, name, label=None, shortcutKeyGp=None):
        self.widgetName = name
        self.label = label
        self.shortcutKeyGp = shortcutKeyGp
        self.gamepad = None
        self._gamepadConnection = None
        self._mousePressPos = None
        self._mouseMovePos = None
        # called with the widget after it has been moved by the user
        self.onMoved = None

        # owned by the widget, so it is deleted together with it
        self.contextMenu = QMenu(self)
        self.removeAction = self.contextMenu.addAction("Remove")
        self.editAction = self.contextMenu.addAction("Edit")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._mousePressPos = event.globalPosition().toPoint()
            self._mouseMovePos = event.globalPosition().toPoint()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.RightButton and self._mouseMovePos is not None:
            globalPos = event.globalPosition().toPoint()
            newPos = self.pos() + (globalPos - self._mouseMovePos)
            if self.parent().rect().contains(newPos):
                self.placeAt(newPos.x(), newPos.y())
                self._mouseMovePos = globalPos

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            if self._mousePressPos is not None:
                moved = event.globalPosition().toPoint() - self._mousePressPos
                self._mousePressPos = None
                self._mouseMovePos = None
                if moved.manhattanLength() > 0:
                    event.ignore()
                    if self.onMoved is not None:
                        self.onMoved(self)
                    return
                super().mouseReleaseEvent(event)
                self.contextMenu.exec(self.mapToGlobal(event.position().toPoint()))
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        # the context menu is handled in mouseReleaseEvent
        event.accept()

    def placeAt(self, x, y):
        """ move the widget and its label to the given position in the remote dock """
        self.move(int(x), int(y))
        if self.label:
            self.label.move(int(x) + 80, int(y) + 30)

    def position(self):
        return [self.x(), self.y()]

    def getData(self):
        pass

    def updateData(self):
        pass

    def updateGamepad(self, gamepad):
        """
        (Re-)connect the widget to the given gamepad, `None` disconnects it.
        """
        if self._gamepadConnection is not None:
            signal, slot = self._gamepadConnection
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
            self._gamepadConnection = None

        self.gamepad = gamepad
        if gamepad is None or not self.shortcutKeyGp:
            return

        if not gamepad.hasInput(self.shortcutKeyGp):
            self._logger.error(f"{self.shortcutKeyGp} is not a valid gamepad button!")
            return

        isAbsolute = gamepad.isAxis(self.shortcutKeyGp)
        if isAbsolute != self.gamepadAbsolute:
            article = "an" if isAbsolute else "not an"
            self._logger.error(f"{self.shortcutKeyGp} is {article} absolute button!")
            return

        signal = gamepad.signal(self.shortcutKeyGp)
        slot = self._onGamepad
        signal.connect(slot)
        self._gamepadConnection = (signal, slot)

    def _onGamepad(self, *args):
        pass


class MovablePushButton(MovableWidget, QPushButton):
    """ sends `valueOn` when clicked, afterwards the parameter is set to `valueReset` without sending it """
    widgetType = 'PushButton'
    requiredKeys = ('valueOn',)
    optionalKeys = {'valueReset': '', 'shortcut': '', 'shortcut-Gp': None}

    def __init__(self, name, valueOn, valueReset, shortcutKey, shortcutKeyGp, **kwargs):
        QPushButton.__init__(self)
        MovableWidget.__init__(self, name, shortcutKeyGp=shortcutKeyGp)
        self.setObjectName(name)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.valueOn = valueOn
        self.valueReset = valueReset

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

        self.shortcut = QShortcut(self)
        self.shortcut.setKey(shortcutKey)
        self.shortcut.setAutoRepeat(False)
        self.shortcut.activated.connect(lambda: self.animateClick())

        self.updateData()

    @classmethod
    def fromConfig(cls, config, exp):
        return cls(config['name'], config['valueOn'], config.get('valueReset') or '', config.get('shortcut') or '',
                   config.get('shortcut-Gp'), module=config['Module'], parameter=config['Parameter'])

    @classmethod
    def editor(cls, dialog):
        dialog.addValueField('valueText', "Value", 'valueOn', 0.0)
        dialog.addShortcutField('shortcutField', "Shortcut:", 'shortcut')
        dialog.addTextField('valueResetText', "Reset Value", 'valueReset', '')
        return lambda: {'valueOn': dialog.valueText.text(),
                        'shortcut': dialog.shortcutField.getKeySequence(),
                        'valueReset': dialog.valueResetText.text()}

    def applyConfig(self, config):
        super().applyConfig(config)
        self.valueOn = config['valueOn']
        self.valueReset = config['valueReset']
        self.shortcut.setKey(config['shortcut'])

    def connectActivation(self, callback):
        self.clicked.connect(lambda: callback(self))

    def updates(self):
        return [(self.module, self.parameter, self.valueOn)]

    def resets(self):
        if self.valueReset == '':
            return []
        return [(self.module, self.parameter, self.valueReset)]

    def _onGamepad(self):
        self.click()

    def getData(self):
        data = dict()

        data['widgetType'] = self.widgetType
        data['name'] = self.widgetName
        data['valueOn'] = self.valueOn
        data['valueReset'] = self.valueReset
        data['Module'] = self.module
        data['Parameter'] = self.parameter
        data['shortcut'] = self.shortcut.key().toString()
        data['shortcut-Gp'] = self.shortcutKeyGp
        data['position'] = self.position()

        return data

    def updateData(self):
        self.setText(self.widgetName + '\n' + self.valueOn)


class DoubleSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        super().setMinimum(0)
        super().setMaximum(1)

        self._minValue = 0.0
        self._maxValue = 1.0

        self._stepSize = 1

    @property
    def value(self):
        curValue = float(super().value())
        return self.calcValue(curValue)

    def calcValue(self, value):
        return round((value * self._stepSize) + self._minValue, 6)

    def setValue(self, value):
        super().setValue(int(round((value - self._minValue) / self._stepSize, 8)))

    def setConfig(self, min, max, step):
        self._minValue = min
        self._maxValue = max
        self._stepSize = step
        super().setMinimum(0)
        super().setMaximum(int((self._maxValue - self._minValue) / self._stepSize))
        super().setTickInterval(1)

    def minimum(self):
        return self._minValue

    def maximum(self):
        return self._maxValue


class MovableSlider(MovableWidget, DoubleSlider):
    """ sends its value when the slider has been released, the label below shows the value """
    gamepadAbsolute = True
    widgetType = 'Slider'
    requiredKeys = ('minSlider', 'maxSlider', 'stepSlider')
    optionalKeys = {'shortcutPlus': '', 'shortcutMinus': '', 'shortcut-Gp': None, 'invertSlider': False}
    size = (200, 30)

    def __init__(self, name, minSlider, maxSlider, invertSlider, stepSlider, label,
                 shortcutPlusKey, shortcutMinusKey, shortcutKeyGp,
                 startValue, **kwargs):
        DoubleSlider.__init__(self, Qt.Orientation.Horizontal)
        MovableWidget.__init__(self, name, label, shortcutKeyGp=shortcutKeyGp)
        self.setObjectName(name)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

        self.minSlider = minSlider
        self.maxSlider = maxSlider
        self.stepSlider = stepSlider
        self.invertSlider = bool(invertSlider)

        self.shortcutPlus = QShortcut(self)
        self.shortcutPlus.setKey(shortcutPlusKey)
        self.shortcutPlus.activated.connect(lambda: self.setValue(self.value + float(self.stepSlider)))
        self.shortcutMinus = QShortcut(self)
        self.shortcutMinus.setKey(shortcutMinusKey)
        self.shortcutMinus.activated.connect(lambda: self.setValue(self.value - float(self.stepSlider)))

        self.startValue = startValue
        self.setTracking(False)
        # show the value while the slider is moved, it is sent when the slider is released
        self.sliderMoved.connect(self._showSliderPosition)

        self.updateData()

    @classmethod
    def fromConfig(cls, config, exp):
        startValue = exp.get(config['Module'], {}).get(config['Parameter'])
        if startValue is None:
            logging.getLogger(cls.__name__).error(
                f"Cannot create slider '{config['name']}': parameter '{config['Parameter']}' "
                f"of module '{config['Module']}' not found!")
            return None
        label = QLabel()
        label.setFixedHeight(15)
        labelFont = label.font()
        labelFont.setPointSize(8)
        label.setFont(labelFont)
        return cls(config['name'], config['minSlider'], config['maxSlider'], config.get('invertSlider', False),
                   config['stepSlider'], label, config.get('shortcutPlus') or '', config.get('shortcutMinus') or '',
                   config.get('shortcut-Gp'), startValue, module=config['Module'], parameter=config['Parameter'])

    @classmethod
    def completeConfig(cls, config, exp):
        config['startValue'] = (exp or {}).get(config['Module'], {}).get(config['Parameter'], 0)

    @classmethod
    def editor(cls, dialog):
        dialog.addValueField('maxSliderText', "Max", 'maxSlider', 1)
        dialog.addValueField('minSliderText', "Min", 'minSlider', 0)
        dialog.addValueField('stepSliderText', "Step Size", 'stepSlider', 1)
        dialog.addShortcutField('shortcutFieldPlus', "Shortcut Plus:", 'shortcutPlus')
        dialog.addShortcutField('shortcutFieldMinus', "Shortcut Minus:", 'shortcutMinus')
        invert = dialog.initial.get('invertSlider', False)
        return lambda: {'minSlider': dialog.minSliderText.text(),
                        'maxSlider': dialog.maxSliderText.text(),
                        'stepSlider': dialog.stepSliderText.text(),
                        'shortcutPlus': dialog.shortcutFieldPlus.getKeySequence(),
                        'shortcutMinus': dialog.shortcutFieldMinus.getKeySequence(),
                        'invertSlider': invert}

    def applyConfig(self, config):
        super().applyConfig(config)
        self.minSlider = config['minSlider']
        self.maxSlider = config['maxSlider']
        self.stepSlider = config['stepSlider']
        self.shortcutPlus.setKey(config['shortcutPlus'])
        self.shortcutMinus.setKey(config['shortcutMinus'])
        if 'startValue' in config:
            self.startValue = config['startValue']

    def connectActivation(self, callback):
        self.valueChanged.connect(lambda _: callback(self))

    def updates(self):
        self._showValue(self.value)
        return [(self.module, self.parameter, self.value)]

    def showValue(self, module, parameter, value):
        if (module, parameter) != (self.module, self.parameter):
            return
        self.blockSignals(True)
        self.setValue(float(value))
        self.blockSignals(False)
        self._showValue(self.value)

    def _showSliderPosition(self, position):
        self._showValue(self.calcValue(position))

    def _showValue(self, value):
        self.label.setText(self.widgetName + f": {value:.3f}")

    def _onGamepad(self, absVal):
        """ map the axis value in [-0.5, 0.5] onto the slider range """
        lower, upper = float(self.minSlider), float(self.maxSlider)
        if self.invertSlider:
            absVal = -absVal
        self.setValue((lower + upper) / 2 + absVal * (upper - lower))

    def getData(self):
        data = dict()

        data['widgetType'] = self.widgetType
        data['name'] = self.widgetName
        data['minSlider'] = self.minSlider
        data['maxSlider'] = self.maxSlider
        data['stepSlider'] = self.stepSlider
        data['invertSlider'] = self.invertSlider
        data['Module'] = self.module
        data['Parameter'] = self.parameter
        data['shortcutPlus'] = self.shortcutPlus.key().toString()
        data['shortcutMinus'] = self.shortcutMinus.key().toString()
        data['shortcut-Gp'] = self.shortcutKeyGp
        data['position'] = self.position()

        return data

    def updateData(self):
        self.setConfig(float(self.minSlider), float(self.maxSlider), float(self.stepSlider))
        self.setPageStep(1)
        self.setSingleStep(1)
        self.setValue(float(self.startValue))
        self.label.setText(self.widgetName + ': ' + str(self.startValue))


class MovableSwitch(MovableWidget, QPushButton):
    """ toggles between sending `valueOn` and `valueOff`, the text shows the value of the next click """
    widgetType = 'Switch'
    requiredKeys = ('valueOn', 'valueOff')
    optionalKeys = {'shortcut': '', 'shortcut-Gp': None}

    def __init__(self, name, valueOn, valueOff, shortcutKey, shortcutKeyGp, **kwargs):
        QPushButton.__init__(self)
        MovableWidget.__init__(self, name, shortcutKeyGp=shortcutKeyGp)
        self.setObjectName(name)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.parameter = kwargs.get('parameter', None)
        self.module = kwargs.get('module', None)

        self.valueOn = valueOn
        self.valueOff = valueOff

        self.shortcut = QShortcut(self)
        self.shortcut.setKey(shortcutKey)
        self.shortcut.setAutoRepeat(False)
        self.shortcut.activated.connect(lambda: self.animateClick())

        self.setCheckable(True)

        self.updateData()

    @classmethod
    def fromConfig(cls, config, exp):
        return cls(config['name'], config['valueOn'], config['valueOff'], config.get('shortcut') or '',
                   config.get('shortcut-Gp'), module=config['Module'], parameter=config['Parameter'])

    @classmethod
    def editor(cls, dialog):
        dialog.addValueField('valueOnText', "Value On", 'valueOn', 0.0)
        dialog.addValueField('valueOffText', "Value Off", 'valueOff', 0.0)
        dialog.addShortcutField('shortcutField', "Shortcut:", 'shortcut')
        return lambda: {'valueOn': dialog.valueOnText.text(),
                        'valueOff': dialog.valueOffText.text(),
                        'shortcut': dialog.shortcutField.getKeySequence()}

    def applyConfig(self, config):
        super().applyConfig(config)
        self.valueOn = config['valueOn']
        self.valueOff = config['valueOff']
        self.shortcut.setKey(config['shortcut'])

    def connectActivation(self, callback):
        self.clicked.connect(lambda: callback(self))

    def updates(self):
        # the button has already been toggled by the click
        if self.isChecked():
            value, nextValue = self.valueOn, self.valueOff
        else:
            value, nextValue = self.valueOff, self.valueOn
        self.setText(self.widgetName + '\n' + nextValue)
        return [(self.module, self.parameter, value)]

    def _onGamepad(self):
        self.click()

    def getData(self):
        data = dict()

        data['widgetType'] = self.widgetType
        data['name'] = self.widgetName
        data['valueOn'] = self.valueOn
        data['valueOff'] = self.valueOff
        data['Module'] = self.module
        data['Parameter'] = self.parameter
        data['shortcut'] = self.shortcut.key().toString()
        data['shortcut-Gp'] = self.shortcutKeyGp
        data['position'] = self.position()

        return data

    def updateData(self):
        self.setChecked(False)
        self.setText(self.widgetName + '\n' + self.valueOn)


class MovableMultiButton(MovableWidget, QPushButton):
    """
    Push button that sets several parameters at once, e.g. an emergency stop for multiple motors.

    The targets are a list of dicts with the keys `Module`, `Parameter` and `value`.
    """
    widgetType = 'MultiButton'
    requiredKeys = ('targets',)
    optionalKeys = {'shortcut': '', 'shortcut-Gp': None}
    hasTargets = True

    def __init__(self, name, targets, shortcutKey, shortcutKeyGp):
        QPushButton.__init__(self)
        MovableWidget.__init__(self, name, shortcutKeyGp=shortcutKeyGp)
        self.setObjectName(name)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.targets = targets
        # the widget is not bound to a single parameter
        self.parameter = None
        self.module = None

        self.shortcut = QShortcut(self)
        self.shortcut.setKey(shortcutKey)
        self.shortcut.setAutoRepeat(False)
        self.shortcut.activated.connect(lambda: self.animateClick())

        self.updateData()

    @classmethod
    def fromConfig(cls, config, exp):
        return cls(config['name'], config['targets'], config.get('shortcut') or '', config.get('shortcut-Gp'))

    @classmethod
    def editor(cls, dialog):
        dialog.addShortcutField('shortcutField', "Shortcut:", 'shortcut')
        dialog.addTargetList()
        return lambda: {'shortcut': dialog.shortcutField.getKeySequence(),
                        'targets': dialog.readTargets()}

    def applyConfig(self, config):
        super().applyConfig(config)
        self.targets = config['targets']
        self.shortcut.setKey(config['shortcut'])

    def connectActivation(self, callback):
        self.clicked.connect(lambda: callback(self))

    def updates(self):
        return [(t['Module'], t['Parameter'], t['value']) for t in self.targets]

    def _onGamepad(self):
        self.click()

    def getData(self):
        data = dict()

        data['widgetType'] = self.widgetType
        data['name'] = self.widgetName
        data['targets'] = [dict(target) for target in self.targets]
        data['shortcut'] = self.shortcut.key().toString()
        data['shortcut-Gp'] = self.shortcutKeyGp
        data['position'] = self.position()

        return data

    def updateData(self):
        self.setText(self.widgetName + '\n' + f"{len(self.targets)} parameter")
        self.setToolTip('\n'.join(f"{t['Module']}.{t['Parameter']} = {t['value']}" for t in self.targets))


# the order is the one of the widget editor
for _cls in (MovablePushButton, MovableSwitch, MovableSlider, MovableMultiButton):
    registerRemoteWidget(_cls)
del _cls
