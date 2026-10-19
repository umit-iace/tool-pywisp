# -*- coding: utf-8 -*-
"""
Movable widgets of the remote dock, that send parameters to the experiment.
"""
import logging

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QLabel, QLayout, QMenu, QPushButton, QShortcut, QSlider

__all__ = ["FreeLayout", "MovableWidget", "MovablePushButton", "DoubleSlider", "MovableSlider", "MovableSwitch"]


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
            if widget.label:
                widget.label.setParent(None)
            self.list.remove(widget)
        widget.setParent(None)

    def clearAll(self):
        for i in self.list:
            if i.label:
                i.label.setParent(None)
            i.setParent(None)
        self.list = []


class MovableWidget:
    """
    Mixin that makes a widget movable via right click & drag and adds a context menu.

    Must be listed before the Qt base class, so that its event handlers take precedence.
    """
    # True if the widget is driven by an absolute (analog) gamepad axis
    gamepadAbsolute = False

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

        self.contextMenu = QMenu()
        self.removeAction = self.contextMenu.addAction("Remove")
        self.editAction = self.contextMenu.addAction("Edit")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._mousePressPos = event.globalPos()
            self._mouseMovePos = event.globalPos()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.RightButton and self._mouseMovePos is not None:
            globalPos = event.globalPos()
            newPos = self.pos() + (globalPos - self._mouseMovePos)
            if self.parent().rect().contains(newPos):
                self.placeAt(newPos.x(), newPos.y())
                self._mouseMovePos = globalPos

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            if self._mousePressPos is not None:
                moved = event.globalPos() - self._mousePressPos
                self._mousePressPos = None
                self._mouseMovePos = None
                if moved.manhattanLength() > 0:
                    event.ignore()
                    if self.onMoved is not None:
                        self.onMoved(self)
                    return
                super().mouseReleaseEvent(event)
                self.contextMenu.exec_(self.mapToGlobal(event.pos()))
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

    def _onGamepad(self):
        self.click()

    def getData(self):
        data = dict()

        data['widgetType'] = 'PushButton'
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
    gamepadAbsolute = True

    def __init__(self, name, minSlider, maxSlider, invertSlider, stepSlider, label,
                 shortcutPlusKey, shortcutMinusKey, shortcutKeyGp,
                 startValue, **kwargs):
        DoubleSlider.__init__(self, Qt.Horizontal)
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

        self.updateData()

    def _onGamepad(self, absVal):
        """ map the axis value in [-0.5, 0.5] onto the slider range """
        lower, upper = float(self.minSlider), float(self.maxSlider)
        if self.invertSlider:
            absVal = -absVal
        self.setValue((lower + upper) / 2 + absVal * (upper - lower))

    def getData(self):
        data = dict()

        data['widgetType'] = 'Slider'
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

    def _onGamepad(self):
        self.click()

    def getData(self):
        data = dict()

        data['widgetType'] = 'Switch'
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
