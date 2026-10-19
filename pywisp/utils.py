# -*- coding: utf-8 -*-
import logging
import os
import struct

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QObject, QRegExp, QSize, pyqtSignal, QRect, QThread
from PyQt5.QtGui import QColor, QIntValidator, QRegExpValidator, QIcon, QKeySequence, QFont, QPen, \
    QPainter, QTextCursor
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox, QDialog, QLineEdit, QLabel, QHBoxLayout, QFormLayout, \
    QLayout, QComboBox, QPushButton, QWidget, QSlider, QMenu, QWidgetAction, QShortcut, QStyledItemDelegate, QStyle
from pyqtgraph.dockarea import Dock

from .widgets.fileselector import FileSelector

__all__ = ["createDir", "getResource", "packArrayToFrame", "coroutine", "pipe"]


def flatten(lst):
    """ flatten an arbitrarily nested list """
    ret = []
    if isinstance(lst, list):
        for item in lst:
            if isinstance(item, list):
                ret.extend(flatten(item))
            else:
                ret.append(item)
        return ret
    else:
        return lst


def coroutine(func):
    """ wrapper for starting coroutine upon creation """

    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr

    return start


def pipe(coros):
    """ start a pipe of coroutines """
    coros = flatten(coros)

    ret = coros[-1]()
    for coro in reversed(coros[:-1]):
        ret = coro(ret)
    return ret


def createDir(dirName):
    """
    Checks if directory exists and create the directory if not.
    :param dirName: directory name
    :return: path of directory
    """
    path = os.path.join(os.getcwd(), dirName)
    os.makedirs(path, exist_ok=True)
    return path


def getResource(resName, resType="icons"):
    """
    Build absolute path to specified resource within the package
    :param resName: name of the ressource
    :param resType: sub directory
    :return: path to resource
    """
    own_path = os.path.dirname(__file__)
    resource_path = os.path.abspath(os.path.join(own_path, "resources", resType))
    return os.path.join(resource_path, resName)


def getFormatedStructString(dataLenFloat: int, dataLenInt: int , lenFloat: int) -> str:
    """
    Returns a format string for the struct package by given float and integer length and
    count of floats.

    :param dataLenFloat: length of float datatype
    :type dataLenFloat: int
    :param dataLenInt: length of integer datatype
    :type dataLenInt: int
    :param lenFloat: length of float data
    :type lenFloat: int

    :return: Struct-type format string that encodes the reuqired data fields.
    """
    if dataLenFloat == 4:
        floatStr = 'f'
    elif dataLenFloat == 8:
        floatStr = 'd'
    else:
        floatStr = 'f'

    if dataLenInt == 1:
        intStr = 'B'
    elif dataLenInt == 2:
        intStr = 'H'
    elif dataLenInt == 4:
        intStr = 'I'
    elif dataLenInt == 8:
        intStr = 'Q'
    else:
        intStr = ''

    fmtStr = '<{}{}{}'.format(intStr, lenFloat, floatStr)

    return fmtStr


def packArrayToFrame(id: int, data: list[float], frameLen: int, dataLenFloat: int, dataLenInt: int) -> list[dict]:
    """
    Packs a data array into a list of payloads that do not exceed a given frame length

    :param id: Frame ID to use
    :type id: int
    :param data: Data to pack
    :type data: List of floats
    :param frameLen: Maximum size of frame for the given architecture
    :type frameLen: int
    :param dataLenFloat: Size of a float on the given architecture in bytes
    :type dataLenFloat: int
    :param dataLenInt: Size of an int on the given architecture in bytes
    :type dataLenInt: int

    :return: List of MIN-Frames, encoded in dictionaries with keys `id` and `msg`.
    """
    # the first frame carries the length of the array (occupying one float slot)
    # followed by floats, all following frames are filled with floats only
    restCnt = frameLen // dataLenFloat
    firstCnt = restCnt - 1
    if firstCnt < 0 or dataLenInt > dataLenFloat:
        raise ValueError("frameLen is too small for the given data types")

    values = [float(d) for d in data]
    first, rest = values[:firstCnt], values[firstCnt:]

    fmtStr = getFormatedStructString(dataLenFloat, dataLenInt, len(first))
    dataPoints = [{'id': id, 'msg': struct.pack(fmtStr, len(values), *first)}]
    for i in range(0, len(rest), restCnt):
        chunk = rest[i:i + restCnt]
        fmtStr = getFormatedStructString(dataLenFloat, 0, len(chunk))
        dataPoints.append({'id': id, 'msg': struct.pack(fmtStr, *chunk)})
    return dataPoints


class PlainTextLogger(logging.Handler):
    """
    Logging handler, that formats log data for line display.
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

    def setTargetCb(self, cb):
        self.cb = cb

    def emit(self, record):
        msg = self.format(record)
        if self.cb:
            clr = self.settings.color(record.levelname, 'log')
            try:
                self.cb.setTextColor(clr)
                self.cb.append(msg)
                self.cb.moveCursor(QTextCursor.End)
            except RuntimeError:
                # the target widget has already been deleted on the C++ side
                self.cb = None
                logging.getLogger().removeHandler(self)
        else:
            logging.getLogger().error("No callback configured!")


class BufferView(np.ndarray):
    """
    Read only numpy view on the data of a :class:`DataPointBuffer`.

    In contrast to a plain array its truth value behaves like the one of a list,
    so ``if buffer.values:`` keeps working.
    """

    def __bool__(self):
        if self.ndim == 0:
            return bool(self.item())
        return self.size > 0


class DataPointBuffer(object):
    """
    Buffer object to store the values of the data points.

    The data is kept in numpy arrays that grow in chunks, :attr:`time` and :attr:`values`
    return views on the filled part.
    """
    _initialCapacity = 1024

    def __init__(self, time=None, values=None):
        time = np.asarray([] if time is None else time, dtype=float)
        values = np.asarray([] if values is None else values, dtype=float)
        if time.shape != values.shape:
            raise ValueError("time and values must have the same length")
        self._setData(time, values)

    def _setData(self, time, values):
        self._size = len(time)
        capacity = max(self._initialCapacity, self._size)
        self._time = np.empty(capacity)
        self._values = np.empty(capacity)
        self._time[:self._size] = time
        self._values[:self._size] = values

    def _view(self, arr):
        view = arr[:self._size].view(BufferView)
        view.flags.writeable = False
        return view

    @property
    def time(self):
        """ time stamps of the values (x axis) """
        return self._view(self._time)

    @property
    def values(self):
        """ values of the data point (y axis) """
        return self._view(self._values)

    def __len__(self):
        return self._size

    def _reserve(self, size):
        capacity = len(self._time)
        if size <= capacity:
            return
        # grow geometrically to keep appending amortized O(1)
        capacity = max(size, 2 * capacity)
        for name in ('_time', '_values'):
            old = getattr(self, name)
            new = np.empty(capacity)
            new[:self._size] = old[:self._size]
            setattr(self, name, new)

    def addValue(self, time, value):
        """
        Adds a new value to the data point buffer
        :param time: time(stamp) of the corresponding value (x axis)
        :param value: the new value for the data point (y axis)
        :return:
        """
        self._reserve(self._size + 1)
        # write the value first, so a failing conversion leaves the buffer untouched
        self._values[self._size] = value
        self._time[self._size] = time
        self._size += 1

    def extend(self, time, values):
        """
        Adds several values to the data point buffer
        :param time: time stamps of the values
        :param values: the new values
        """
        time = np.asarray(time, dtype=float)
        values = np.asarray(values, dtype=float)
        if time.shape != values.shape:
            raise ValueError("time and values must have the same length")
        n = len(time)
        self._reserve(self._size + n)
        self._time[self._size:self._size + n] = time
        self._values[self._size:self._size + n] = values
        self._size += n

    def snapshot(self):
        """
        Returns a buffer containing the current data without copying it.
        Data added later on to this buffer does not show up in the snapshot.
        """
        snap = DataPointBuffer.__new__(DataPointBuffer)
        snap._size = self._size
        snap._time = self._time[:self._size]
        snap._values = self._values[:self._size]
        return snap

    def clearBuffer(self):
        """
        Clears all the buffers of the data point
        """
        # allocate new memory, views handed out before must not see new data
        self._setData(np.empty(0), np.empty(0))

    def __getstate__(self):
        return {'time': self.time.view(np.ndarray).copy(), 'values': self.values.view(np.ndarray).copy()}

    def __setstate__(self, state):
        # also handles pickles of the former list based implementation
        self._setData(np.asarray(state['time'], dtype=float), np.asarray(state['values'], dtype=float))


class Exporter(QObject):
    """
    Class exports data points from GUI to different formats (csv, png) as pandas dataframe.
    """
    done = pyqtSignal(bool)

    def __init__(self, **kwargs):
        super().__init__()
        dataPoints = kwargs.get("dataPoints", None)
        fileName = kwargs.get("fileName", None) or FileSelector(
            ["CSV Data (*.csv)", "PNG Image (*.png)"]
        ).getSaveFileName()

        self.worker = self.ExportThread(dataPoints, fileName)
        self.logger = logging.getLogger("Exporter")
        def handleLog(done, lvl, msg):
            self.logger.log(lvl, msg)
            if done:
                self.done.emit(lvl != logging.ERROR)
        self.worker.info.connect(handleLog)

    def runExport(self):
        self.worker.start()

    def wait(self):
        try:
            self.worker.wait()
        except RuntimeError: # happens when ExportThread already cleaned up on C++ side
            pass

    class ExportThread(QThread):
        info = pyqtSignal(bool,int,str)
        def __init__(self, data, file):
            super().__init__()
            self.dataPoints = data
            self.fileName = file
            self.df = None

        def run(self):
            if self.dataPoints is None:
                self.info.emit(True, logging.ERROR, "Export failed: No data given")
                return
            if self.fileName is None:
                self.info.emit(True, logging.ERROR, "Export failed: No file name given")
                return
            self.info.emit(False, logging.INFO, f"Export to {self.fileName} started.")
            self._buildFrame()
            if self.df is None:
                self.info.emit(True, logging.ERROR, "Export failed: Cannot build data frame")
                return
            file, ext = os.path.splitext(self.fileName)
            if ext == '.csv':
                self.exportCsv()
            elif ext == '.png':
                self.exportPng()
            else:
                self.info.emit(True, logging.ERROR, f"Export failed: Unsupported file extension '{ext}'.")
                return
            self.info.emit(True, logging.INFO, "Export successful.")

        def _buildFrame(self):
            # build pandas data frame
            d = {key: pd.Series(val.values, index=val.time)
                 for key, val in self.dataPoints.items()}
            try:
                self.df = pd.DataFrame.from_dict(d, orient='index').transpose()
                self.df.index.name = 'time'
                self.df.sort_index(inplace=True)
            except Exception:
                self.df = None

        def exportPng(self):
            """
            Exports the data point dataframe as png with matplotlib.
            :param fileName: name of file with extension
            """

            # use the object oriented api, pyplot is not thread safe and
            # switching the global backend would break the gui
            fig = Figure(figsize=(10, 6))
            FigureCanvasAgg(fig)
            axes = fig.add_subplot(1, 1, 1)

            for col in self.df.columns:
                series = self.df[col].dropna()
                axes.plot(series.index, series.values, label=col)

            axes.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=4,
                        ncol=4, mode="expand", borderaxespad=0., framealpha=0.5)

            axes.grid(True)
            if self.df.index.name == 'time':
                axes.set_xlabel(r"Time (s)")

            fig.savefig(self.fileName, dpi=300)

        def exportCsv(self, sep=','):
            """
            Exports the data point dataframe as csv
            :param sep: separator for csv (default: ,)
            """
            self.df.to_csv(self.fileName, sep=sep)


class DataIntDialog(QDialog):
    """
    Qt Dialog handler for integer settings with a min and max value
    """

    def __init__(self, **kwargs):
        parent = kwargs.get("parent", None)
        super(DataIntDialog, self).__init__(parent)

        self.minValue = kwargs.get("min", 1)
        self.maxValue = kwargs.get("max", 1000)
        self.currentValue = kwargs.get("current", 0)
        self.unit = kwargs.get("unit", "")
        self.title = kwargs.get("title", "pywisp")

        self.setWindowTitle(self.title)

        mainLayout = QVBoxLayout(self)
        labelLayout = QHBoxLayout()
        inputLayout = QHBoxLayout()

        minLabel = QLabel(self)
        minLabel.setText("min. value: {}".format(self.minValue))
        labelLayout.addWidget(minLabel)
        maxLabel = QLabel(self)
        maxLabel.setText("max. value: {}".format(self.maxValue))
        labelLayout.addWidget(maxLabel)
        mainLayout.addLayout(labelLayout)

        self.data = QLineEdit(self)
        self.data.setText(str(self.currentValue))

        self.data.setValidator(QIntValidator(self.minValue, self.maxValue, self))

        inputLayout.addWidget(self.data)

        if not self.unit == "":
            unitLabel = QLabel(self)
            unitLabel.setText(self.unit)
            inputLayout.addWidget(unitLabel)

        mainLayout.addLayout(inputLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)

    def _getData(self):
        return self.data.text()

    @staticmethod
    def getData(**kwargs):
        dialog = DataIntDialog(**kwargs)
        result = dialog.exec_()
        data = dialog._getData()

        return data, result == QDialog.Accepted

class DataTcpIpDialog(QDialog):
    """
    Qt Dialog handler for tcp settings
    """

    def __init__(self, **kwargs):
        parent = kwargs.get('parent', None)
        super(DataTcpIpDialog, self).__init__(parent)

        self.ipValue = kwargs.get("ip", '127.0.0.1')
        self.portValue = kwargs.get("port", 0)

        ipRange = "(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])"  # Part of the regular expression
        # regular expression
        ipRegex = QRegExp("^" + ipRange + "\\." + ipRange + "\\." + ipRange + "\\." + ipRange + "$")
        ipValidator = QRegExpValidator(ipRegex, self)

        mainLayout = QVBoxLayout(self)

        self.ipData = QLineEdit(self)
        self.ipData.setText(str(self.ipValue))
        self.ipData.setValidator(ipValidator)

        self.portData = QLineEdit(self)
        self.portData.setText(str(self.portValue))
        self.portData.setValidator(QIntValidator(0, 65535, self))

        horizonalLayout = QHBoxLayout()

        horizonalLayout.addWidget(self.ipData)
        horizonalLayout.addWidget(self.portData)
        mainLayout.addLayout(horizonalLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)

    def _getData(self):
        return self.ipData.text(), self.portData.text()

    @staticmethod
    def getData(**kwargs):
        dialog = DataTcpIpDialog(**kwargs)
        result = dialog.exec_()
        ipData, portData = dialog._getData()

        return ipData, portData, result == QDialog.Accepted


class RemoteWidgetEdit(QDialog):
    """
    Creates a dialog to add and edit remote widgets of different types
    """

    def __init__(self, editWidget=False, **kwargs):
        parent = kwargs.get('parent', None)
        super(RemoteWidgetEdit, self).__init__(parent)
        self.widgetType = kwargs.get('widgetType', 'PushButton')
        self.name = kwargs.get('name', 'New')
        self.valueOn = str(kwargs.get('valueOn', 0.0))
        self.valueReset = str(kwargs.get('valueReset', ''))
        self.valueOff = str(kwargs.get('valueOff', 0.0))
        self.minSlider = str(kwargs.get('minSlider', 0))
        self.maxSlider = str(kwargs.get('maxSlider', 1))
        self.stepSlider = str(kwargs.get('stepSlider', 1))
        self.shortcut = str(kwargs.get('shortcut', ""))
        self.shortcutPlus = str(kwargs.get('shortcutPlus', ""))
        self.shortcutMinus = str(kwargs.get('shortcutMinus', ""))
        self.shortcutGp = kwargs.get('shortcut-Gp', None)
        self.invertSlider = kwargs.get('invertSlider', False)

        self.curModule = kwargs.get('Module', None)
        self.curParameter = kwargs.get('Parameter', None)

        self.editWidget = editWidget

        self.minSliderText = None
        self.maxSliderText = None
        self.stepSliderText = None
        self.valueOffText = None
        self.valueOnText = None
        self.valueText = None
        self.valueResetText = None
        self.shortcutField = None
        self.shortcutFieldPlus = None
        self.shortcutFieldMinus = None

        mainLayout = QFormLayout()

        self.nameText = QLineEdit(self.name)
        mainLayout.addRow(QLabel("Name"), self.nameText)
        self.nameText.mousePressEvent = lambda event: self.nameText.selectAll()

        self.typeList = QComboBox()
        self.typeList.addItems(["PushButton", "Switch", "Slider"])
        self.typeList.setCurrentText(self.widgetType)
        self.typeList.currentIndexChanged.connect(self.typeListChanged)
        self.typeList.setEnabled(not self.editWidget)
        mainLayout.addRow(QLabel("Widget type"), self.typeList)

        self.moduleList = QComboBox()
        self.paramList = QComboBox()
        self.modules = dict()
        exp = kwargs.get('exp', None) or {}
        for key, value in exp.items():
            self.modules[key] = [k for k, v in value.items()]

            self.moduleList.addItem(key)

        self.moduleList.currentIndexChanged.connect(self.moduleChanged)
        if self.curModule is None:
            self.moduleList.setCurrentIndex(0)
            self.moduleChanged()
        else:
            self.moduleList.setCurrentText(self.curModule)
            self.moduleChanged()

        if self.curParameter is not None:
            self.paramList.setCurrentText(self.curParameter)

        mainLayout.addRow(QLabel("Modules:"), self.moduleList)
        mainLayout.addRow(QLabel("Parameter:"), self.paramList)

        self.settingsWidget = QWidget()
        self.settingsWidgetLayout = QFormLayout()
        self.settingsWidget.setLayout(self.settingsWidgetLayout)
        mainLayout.addRow(self.settingsWidget)

        self.typeListChanged()

        self.setLayout(mainLayout)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        mainLayout.addWidget(buttons)

        self.setWindowTitle("Add Remote Widget ...")
        resPath = getResource("icon.svg")
        self.icon = QIcon(resPath)
        self.setWindowIcon(self.icon)
        self.setFixedSize(self.sizeHint())

    def typeListChanged(self):
        for i in reversed(range(self.settingsWidgetLayout.count())):
            self.settingsWidgetLayout.itemAt(i).widget().deleteLater()

        height = QLineEdit().sizeHint().height()
        doubleValidator = QRegExpValidator(QRegExp("[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?"), self)

        if self.typeList.currentText() == "PushButton":
            self.valueText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value"), self.valueText)
            self.valueText.setValidator(doubleValidator)
            self.valueText.mousePressEvent = lambda event: self.valueText.selectAll()
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
            self.valueResetText = QLineEdit(self.valueReset)
            self.settingsWidgetLayout.addRow(QLabel("Reset Value"), self.valueResetText)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy2 = QLabel("")
            dummy2.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy2)
        elif self.typeList.currentText() == "Switch":
            self.valueOnText = QLineEdit(self.valueOn)
            self.settingsWidgetLayout.addRow(QLabel("Value On"), self.valueOnText)
            self.valueOnText.setValidator(doubleValidator)
            self.valueOnText.mousePressEvent = lambda event: self.valueOnText.selectAll()
            self.valueOffText = QLineEdit(self.valueOff)
            self.settingsWidgetLayout.addRow(QLabel("Value Off"), self.valueOffText)
            self.valueOffText.mousePressEvent = lambda event: self.valueOffText.selectAll()
            self.valueOffText.setValidator(doubleValidator)
            self.shortcutField = ShortcutCreator()
            self.shortcutField.setText(self.shortcut)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut:"), self.shortcutField)
            dummy = QLabel("")
            dummy.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy)
            dummy2 = QLabel("")
            dummy2.setFixedHeight(height)
            self.settingsWidgetLayout.addRow(None, dummy2)
        elif self.typeList.currentText() == "Slider":
            self.maxSliderText = QLineEdit(str(self.maxSlider))
            self.settingsWidgetLayout.addRow(QLabel("Max"), self.maxSliderText)
            self.maxSliderText.setValidator(doubleValidator)
            self.maxSliderText.mousePressEvent = lambda event: self.maxSliderText.selectAll()
            self.minSliderText = QLineEdit(str(self.minSlider))
            self.settingsWidgetLayout.addRow(QLabel("Min"), self.minSliderText)
            self.minSliderText.setValidator(doubleValidator)
            self.minSliderText.mousePressEvent = lambda event: self.minSliderText.selectAll()
            self.stepSliderText = QLineEdit(str(self.stepSlider))
            self.settingsWidgetLayout.addRow(QLabel("Step Size"), self.stepSliderText)
            self.stepSliderText.setValidator(doubleValidator)
            self.stepSliderText.mousePressEvent = lambda event: self.stepSliderText.selectAll()
            self.shortcutFieldPlus = ShortcutCreator()
            self.shortcutFieldPlus.setText(self.shortcutPlus)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Plus:"), self.shortcutFieldPlus)
            self.shortcutFieldMinus = ShortcutCreator()
            self.shortcutFieldMinus.setText(self.shortcutMinus)
            self.settingsWidgetLayout.addRow(QLabel("Shortcut Minus:"), self.shortcutFieldMinus)

    def moduleChanged(self):
        self.paramList.clear()
        module = self.moduleList.currentText()

        for p in self.modules.get(module, []):
            self.paramList.addItem(p)

    def _getData(self):
        msg = dict()
        msg['name'] = self.nameText.text()
        msg['widgetType'] = self.typeList.currentText()
        msg['Module'] = self.moduleList.currentText()
        msg['Parameter'] = self.paramList.currentText()
        msg['shortcut-Gp'] = self.shortcutGp

        if self.typeList.currentText() == "PushButton":
            msg['valueOn'] = self.valueText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
            msg['valueReset'] = self.valueResetText.text()
        elif self.typeList.currentText() == "Switch":
            msg['valueOn'] = self.valueOnText.text()
            msg['valueOff'] = self.valueOffText.text()
            msg['shortcut'] = self.shortcutField.getKeySequence()
        elif self.typeList.currentText() == "Slider":
            msg['minSlider'] = self.minSliderText.text()
            msg['maxSlider'] = self.maxSliderText.text()
            msg['stepSlider'] = self.stepSliderText.text()
            msg['shortcutPlus'] = self.shortcutFieldPlus.getKeySequence()
            msg['shortcutMinus'] = self.shortcutFieldMinus.getKeySequence()
            msg['invertSlider'] = self.invertSlider

        return msg

    @staticmethod
    def getData(exp=None, editWidget=False, **kwargs):
        dialog = RemoteWidgetEdit(exp=exp, editWidget=editWidget, **kwargs)
        result = dialog.exec_()
        msg = dialog._getData()

        if msg['widgetType'] == "Slider":
            if exp and msg['Parameter'] in exp.get(msg['Module'], {}):
                msg['startValue'] = exp[msg['Module']][msg['Parameter']]
            else:
                msg['startValue'] = 0

        return msg, result == QDialog.Accepted


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

    def itemAt(self, p_int):
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
                self.move(newPos)
                if self.label:
                    self.label.move(newPos.x() + 80, newPos.y() + 30)
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
                    return
                super().mouseReleaseEvent(event)
                self.contextMenu.exec_(self.mapToGlobal(event.pos()))
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        # the context menu is handled in mouseReleaseEvent
        event.accept()

    def getData(self):
        pass

    def updateData(self):
        pass

    def updateGamePad(self, gamepad):
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

        names = [name for name, abbrev in gamepad.getAbbrevs().items() if abbrev == self.shortcutKeyGp]
        if not names:
            self._logger.error("{} is not a valid gamepad button!".format(self.shortcutKeyGp))
            return

        isAbsolute = names[0].startswith('Absolute')
        if isAbsolute != self.gamepadAbsolute:
            self._logger.error("{} is {} absolute button!".format(
                self.shortcutKeyGp, "an" if isAbsolute else "not an"))
            return

        prefix = 'abs' if isAbsolute else 'btn'
        signal = getattr(gamepad, prefix + self.shortcutKeyGp)
        slot = self._onGamePad
        signal.connect(slot)
        self._gamepadConnection = (signal, slot)

    def _onGamePad(self, *args):
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

    def _onGamePad(self):
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

    def _onGamePad(self, absVal):
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

    def _onGamePad(self):
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

        return data

    def updateData(self):
        self.setChecked(False)
        self.setText(self.widgetName + '\n' + self.valueOn)


class ShortcutCreator(QLineEdit):
    def __init__(self, parent=None):
        super(ShortcutCreator, self).__init__(parent)
        self.KeySequence = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control or \
                event.key() == Qt.Key_Alt or \
                event.key() == Qt.Key_AltGr or \
                event.key() == Qt.Key_Escape or \
                event.key() == Qt.Key_Shift or \
                event.key() == Qt.Key_CapsLock or \
                event.key() == Qt.Key_Space or \
                event.key() == Qt.Key_Tab:
            self.setText('')
        else:
            self.KeySequence = QKeySequence(event.key()).toString()
            self.setText(self.KeySequence)

    def getKeySequence(self):
        return self.KeySequence

    def setText(self, p_str):
        self.KeySequence = p_str
        super(ShortcutCreator, self).setText(p_str)


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
            item.setData(0, QtCore.Qt.BackgroundRole, QtGui.QColor())
    """

    def paint(self, painter, option, index):
        def draw_my(option, painter, brush, text, icon):
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
                painter.drawText(option.rect.adjusted(h, 0, 0, 0), Qt.AlignLeft, text)
            else:
                painter.drawText(option.rect, Qt.AlignLeft, text)

            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.setPen(QPen(Qt.NoPen))
            painter.fillRect(option.rect, brush)
            painter.setBackgroundMode(Qt.OpaqueMode)
            painter.setBackground(brush)
            painter.drawRect(option.rect)
            painter.restore()

        # Also should be activated in StyleSheet
        #                             Selected
        if (option.state & QStyle.State_Selected):
            option.font.setWeight(QFont.Bold)

            brush = index.data(Qt.BackgroundRole)
            text = index.data(Qt.DisplayRole)
            icon = index.data(Qt.DecorationRole)

            draw_my(option=option, painter=painter, brush=brush, text=text, icon=icon)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

