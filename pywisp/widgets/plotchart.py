import logging
import math
import numpy as np
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu
from pyqtgraph import PlotWidget, TextItem, mkPen
from ..buffer import DataPointBuffer
from ..export import Exporter
from .common import ContextLineEditAction
from ..settings import Settings

class PlotChart(PlotWidget):
    """
    Object containing the plot widgets and the associated plot curves
    """
    coords = pyqtSignal(str)

    def __init__(self, title, config):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.title = title
        self.plotCurves = {}

        # plot settings
        self.settings = Settings()
        self.movingWindowEnable = config.get("MovingWindowEnable", True)
        # MovingWindowSize is the documented key, MovingWindowWidth is kept for compatibility
        self.movingWindowWidth = config.get("MovingWindowSize", config.get("MovingWindowWidth", 30))

        # plot widget settings
        self.showGrid(True, True)
        self.getPlotItem().getAxis("bottom").setLabel(text="Time", units="s")

        # enable down-sampling and clipping for better performance
        self.setClipToView(True)
        self.config = {
            'downsamplingMethod': config.get("downsamplingMethod", 'peak')
        }
        self.cache = {}

        coordItem = TextItem(text='', anchor=(0, 1))
        self.getPlotItem().addItem(coordItem, ignoreBounds=True)
        self.timer = QTimer()
        def wrapCoordHide():
            try:
                coordItem.hide()
            except RuntimeError: # happens when Chart got garbage collected in the meantime
                pass
        self.timer.timeout.connect(wrapCoordHide)

        def coordWrapper(pos):
            coords = self.getPlotItem().vb.mapSceneToView(pos)
            coordText = f"x={coords.x():.3e} y={coords.y():.3e}"
            if self.settings.value("view/show_coordinates", type=bool):
                coordItem.setText(coordText.replace(" ", "\n"))
                coordItem.setPos(coords.x(), coords.y())
                coordItem.show()
                self.timer.start(5000)

            self.coords.emit(coordText)

        self.scene().sigMouseMoved.connect(coordWrapper)

        qActionSep1 = QAction("", self)
        qActionSep1.setSeparator(True)
        qActionSep2 = QAction("", self)
        qActionSep2.setSeparator(True)
        qActionSep3 = QAction("", self)
        qActionSep3.setSeparator(True)

        qActionMovingWindowEnable = QAction('Enable', self, checkable=True)
        qActionMovingWindowEnable.setChecked(self.movingWindowEnable)
        qActionMovingWindowEnable.triggered.connect(self.setEnableMovingWindow)

        qActionMovingWindowSize = ContextLineEditAction(min=0, max=10000, current=self.getMovingWindowWidth(),
                                                        unit='s', title='Size', parent=self)
        qActionMovingWindowSize.dataEmit.connect(lambda data: self.setMovingWindowWidth(data))
        qMenuMovingWindow = QMenu('Moving Window', self)
        qMenuMovingWindow.addAction(qActionMovingWindowSize)
        qMenuMovingWindow.addAction(qActionMovingWindowEnable)

        self.scene().contextMenu = [qActionSep1,
                                      QAction("Auto Range All", self),
                                      qActionSep2,
                                      QAction("Export as ...", self),
                                      qActionSep3,
                                      qMenuMovingWindow,
                                      ]

        self.scene().contextMenu[1].triggered.connect(self.setAutoRange)
        self.scene().contextMenu[3].triggered.connect(self.export)

    def addCurve(self, name, data):
        """
        Adds a curve to the plot widget
        Args:
            dataPoint(DataPointBuffer): Data point which contains the data be added
        """
        color = self.settings.color(len(self.plotCurves))
        # add the actual curve
        self.plotCurves[name] = self.plot(name=name,
                                          pen=mkPen(color),
                                          skipFiniteCheck=True
                                          )
        self.updateCurves({name:data})

    def removeCurve(self, name):
        self.cache.pop(name, None)
        curve = self.plotCurves.pop(name, None)
        if curve is None:
            return
        self.getPlotItem().removeItem(curve)
        # update colors of remaining curves
        for ix, curve in enumerate(self.plotCurves.values()):
            color = self.settings.color( ix )
            curve.setPen(mkPen(color))

    def setAutoRange(self):
        self.autoRange()
        self.enableAutoRange()

    def setEnableMovingWindow(self, movingWindowEnable):
        self.movingWindowEnable = movingWindowEnable
        self.setAutoRange()

    def setMovingWindowWidth(self, movingWindowWidth):
        try:
            self.movingWindowWidth = int(movingWindowWidth)
        except ValueError:
            self._logger.error(f"Invalid moving window width '{movingWindowWidth}'")

    def getMovingWindowWidth(self):
        return self.movingWindowWidth

    def updateCurves(self, dataPoints):
        """
        Updates all curves of the plot with the actual data in the buffers
        """
        keys = [ name for name in self.plotCurves.keys()
                    if name in dataPoints ]
        lastX = [ dataPoints[name].time[-1]
                     for name in keys
                     if len(dataPoints[name].time) ]
        if not lastX:
            return
        firstX = max(lastX) - self.movingWindowWidth

        def xRange(time, values):
            start = np.searchsorted(time, firstX)
            return time[start:], values[start:]

        for name in keys:
            datax = dataPoints[name].time
            datay = dataPoints[name].values
            if self.movingWindowEnable:
                datax, datay = xRange(datax, datay)
                ds = self._sampleStep(datax)
                x, y = self._downsample(ds, datax, datay)
            else:
                x, y = self._cachedSample(name, datax, datay)
            self.plotCurves[name].setData(x, y)


    def export(self, filename=None):
        dataPoints = dict()
        for c in self.getPlotItem().curves:
            (x, y), name = c.getData(), c.name()
            if x is None or y is None:
                self._logger.warning(f"Curve '{name}' contains no data, skipping it.")
                continue
            dataPoints[name] = DataPointBuffer(time=x, values=y)

        self.exporter = Exporter(dataPoints=dataPoints, fileName=filename)
        self.exporter.runExport()

    def _sampleStep(self, X):
        ds = 1
        if len(X) == 0:
            return ds
        view = self.getViewBox()
        if view is None:
            viewRange = None
        else:
            viewRange = view.viewRect()  # this is always up-to-date
        if viewRange is None:
            viewRange = self.viewRect()
        if viewRange is not None and len(X) > 1:
            dx = float(X[-1]-X[0]) / (len(X)-1)
            if dx != 0.0:
                width = self.getViewBox().width()
                if width != 0.0:  # autoDownsampleFactor _should_ be > 1.0
                    dsFloat = max(
                        1.0,
                        abs(
                            viewRange.width() /
                            dx /
                            (width * 3)
                        )
                    )
                    if math.isfinite(dsFloat):
                        ds = int(dsFloat)
        return ds

    def _downsample(self, ds, x, y):
        """
        Reduces the given data by the factor `ds` according to the configured method.
        Only complete blocks of `ds` samples are used.
        :return: numpy arrays with the downsampled data
        """
        x = np.asarray(x)
        y = np.asarray(y)
        if ds <= 1:
            return x, y
        method = self.config['downsamplingMethod']
        n = len(x) // ds
        # start of x-values; try to select a somewhat centered point
        stx = ds // 2
        if method == 'subsample':
            x = x[:n * ds:ds]
            y = y[:n * ds:ds]
        elif method == 'mean':
            x = x[stx:stx + n * ds:ds]
            y = y[:n * ds].reshape(n, ds).mean(axis=1)
        elif method == 'peak':
            x = np.repeat(x[stx:stx + n * ds:ds], 2)
            blocks = y[:n * ds].reshape(n, ds)
            y = np.empty(2 * n)
            y[0::2] = blocks.max(axis=1)
            y[1::2] = blocks.min(axis=1)
        return x, y

    def _cachedSample(self, name, x, y):
        """
        Downsamples the complete data set, reusing the result of the last call.
        Only the samples added since then are processed.
        """
        x = np.asarray(x)
        y = np.asarray(y)
        ds = self._sampleStep(x)
        cached = self.cache.get(name)
        if cached is not None and cached[0] == ds and cached[1] <= len(x):
            _, used, cx, cy = cached
        else:
            used, cx, cy = 0, np.empty(0), np.empty(0)

        # only process complete blocks, the remainder is handled with the next call
        n = (len(x) - used) // ds * ds
        if n:
            nx, ny = self._downsample(ds, x[used:used + n], y[used:used + n])
            cx, cy = np.concatenate((cx, nx)), np.concatenate((cy, ny))
            used += n
        self.cache[name] = (ds, used, cx, cy)

        # show the not yet downsampled tail as it is
        return np.concatenate((cx, x[used:])), np.concatenate((cy, y[used:]))
