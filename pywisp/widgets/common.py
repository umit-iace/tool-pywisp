# -*- coding: utf-8 -*-
"""
Small widgets and helpers used by the main window.
"""
import logging

from PyQt6.QtCore import QObject, Qt, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIntValidator, QPainter, QPen, QTextCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QStyle, QStyledItemDelegate, QWidget, QWidgetAction
from pyqtgraph.dockarea import Dock

__all__ = ["PlainTextLogger", "PinnedDock", "ContextLineEditAction", "TreeWidgetStyledItemDelegate"]


class _LogBridge(QObject):
    """ carries log messages into the thread the logger has been created in """
    message = pyqtSignal(str, QColor)


class PlainTextLogger(logging.Handler):
    """
    Logging handler, that formats log data for line display.

    Records may be emitted from any thread, the target widget is only accessed in the
    thread the handler has been created in (the gui thread).
    """

    def __init__(self, settings, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        self.name = "PlainTextLogger"
        self.settings = settings

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S")
        self.setFormatter(formatter)

        self.cb = None
        # direct connection in the gui thread, queued from all other threads
        self._bridge = _LogBridge()
        self._bridge.message.connect(self._append)

    def setTargetCb(self, cb):
        self.cb = cb

    def emit(self, record):
        try:
            msg = self.format(record)
            clr = self.settings.color(record.levelname, 'log')
            self._bridge.message.emit(msg, clr)
        except RuntimeError:
            # the bridge has already been deleted on the C++ side
            logging.getLogger().removeHandler(self)

    def _append(self, msg, clr):
        if self.cb is None:
            # logging an error here would end up in this handler again
            return
        try:
            self.cb.setTextColor(clr)
            self.cb.append(msg)
            self.cb.moveCursor(QTextCursor.MoveOperation.End)
        except RuntimeError:
            # the target widget has already been deleted on the C++ side
            self.cb = None
            logging.getLogger().removeHandler(self)


class PinnedDock(Dock):
    def __init__(self, *args):
        super(PinnedDock, self).__init__(*args)
        self.label.mouseDoubleClickEvent = lambda event: event.ignore()


class ContextLineEditAction(QWidgetAction):
    dataEmit = pyqtSignal(str)

    def __init__(self, **kwargs):
        parent = kwargs.get("parent", None)
        super().__init__(parent)

        self.minValue = kwargs.get("min", 1)
        self.maxValue = kwargs.get("max", 1000)
        self.currentValue = kwargs.get("current", 0)
        self.unit = kwargs.get("unit", "")
        self.title = kwargs.get("title", "pywisp")

        mainLayout = QHBoxLayout()
        titleLabel = QLabel(parent)
        titleLabel.setText(self.title)
        mainLayout.addWidget(titleLabel)

        self.data = QLineEdit()
        self.data.setText(str(self.currentValue))
        self.data.setValidator(QIntValidator(self.minValue, self.maxValue, self))

        mainLayout.addWidget(self.data)

        if not self.unit == "":
            unitLabel = QLabel()
            unitLabel.setText(self.unit)
            mainLayout.addWidget(unitLabel)

        mainWidget = QWidget()
        mainWidget.setLayout(mainLayout)
        self.setDefaultWidget(mainWidget)

        self.data.editingFinished.connect(self.onChange)

    def onChange(self):
        self.dataEmit.emit(self.data.text())


class TreeWidgetStyledItemDelegate(QStyledItemDelegate):
    """
        For overriding behavior of selection and hovering in QTreeView and QTreeWidget

        When you set background color (QtGui.QColor()) to QTreeWidgetItem you also must set this color like:
            item.setData(0, QtCore.Qt.ItemDataRole.BackgroundRole, QtGui.QColor())
    """

    def paint(self, painter, option, index):
        def drawSelected(option, painter, brush, text, icon):
            if brush is None:
                brush = QColor(255, 255, 255,
                               0)  # This is original background color. I just set alpha to 0 which means it is transparent

            x, y = (option.rect.x(), option.rect.y())
            h = option.rect.height()
            painter.save()

            painter.setFont(option.font)
            if icon:
                icon = icon.pixmap(h, h)
                painter.drawPixmap(QRect(x, y, h, h), icon)
                painter.drawText(option.rect.adjusted(h, 0, 0, 0), Qt.AlignmentFlag.AlignLeft, text)
            else:
                painter.drawText(option.rect, Qt.AlignmentFlag.AlignLeft, text)

            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.fillRect(option.rect, brush)
            painter.setBackgroundMode(Qt.BGMode.OpaqueMode)
            painter.setBackground(brush)
            painter.drawRect(option.rect)
            painter.restore()

        # Also should be activated in StyleSheet
        #                             Selected
        if (option.state & QStyle.StateFlag.State_Selected):
            option.font.setWeight(QFont.Weight.Bold)

            brush = index.data(Qt.ItemDataRole.BackgroundRole)
            text = index.data(Qt.ItemDataRole.DisplayRole)
            icon = index.data(Qt.ItemDataRole.DecorationRole)

            drawSelected(option=option, painter=painter, brush=brush, text=text, icon=icon)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)
