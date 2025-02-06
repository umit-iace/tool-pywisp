import math
import numpy as np
from bisect import bisect_left
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAction, QMenu, QWidget
from pyqtgraph import PlotWidget, TextItem, mkPen
from pywisp.utils import ContextLineEditAction, DataPointBuffer, Exporter
from ..settings import Settings

class PlotChart(PlotWidget):
    """
    Object containing the plot widgets and the associated plot curves
    """
    coords = pyqtSignal(str)

    def __init__(self, title, config):
        super().__init__()
        self.title = title
        self.plotCurves = {}

        # plot settings
        self.settings = Settings()
        self.movingWindowEnable = config.get("MovingWindowEnable", True)
        self.movingWindowWidth = config.get("MovingWindowWidth", 30)

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
            coord_text = "x={:.3e} y={:.3e}".format(coords.x(), coords.y())
            if self.settings.value("view/show_coordinates"):
                coordItem.setText(coord_text.replace(" ", "\n"))
                coordItem.setPos(coords.x(), coords.y())
                coordItem.show()
                self.timer.start(5000)

            self.coords.emit(coord_text)

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
        if name in self.plotCurves:
            curve = self.plotCurves.pop(name)
        if name in self.cache:
            del self.cache[name]
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
        self.movingWindowWidth = int(movingWindowWidth)

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
                     if dataPoints[name].time ]
        if not lastX:
            return
        firstX = max(lastX) - self.movingWindowWidth

        def xRange(time, values):
            start = bisect_left(time, firstX)
            return time[start:], values[start:]

        for name in keys:
            datax = dataPoints[name].time
            datay = dataPoints[name].values
            if self.movingWindowEnable:
                datax, datay = xRange(datax, datay)
                ds = self._samplestep(datax)
                x, y = self._downsample(ds, datax, datay)
            else:
                x, y = self._cachedsample(name, datax, datay)
            self.plotCurves[name].setData(x, y)


    def export(self, filename=None):
        dataPoints = dict()
        for c in self.getPlotItem().curves:
            data, name = c.getData(), c.name()
            if data is None:
                continue
            if len(data) > 2:
                self._logger.warning('Can not handle the amount of data!')
                continue
            dataPoints[name] = DataPointBuffer(time=data[0], values=data[1])

        self.exporter = Exporter(dataPoints=dataPoints, fileName=filename)
        self.exporter.runExport()

    def _samplestep(self, X):
        ds = 1
        if not X:
            return ds
        view = self.getViewBox()
        if view is None:
            view_range = None
        else:
            view_range = view.viewRect()  # this is always up-to-date
        if view_range is None:
            view_range = self.viewRect()
        if view_range is not None and len(X) > 1:
            dx = float(X[-1]-X[0]) / (len(X)-1)
            if dx != 0.0:
                width = self.getViewBox().width()
                if width != 0.0:  # autoDownsampleFactor _should_ be > 1.0
                    ds_float = max(
                        1.0,
                        abs(
                            view_range.width() /
                            dx /
                            (width * 3)
                        )
                    )
                    if math.isfinite(ds_float):
                        ds = int(ds_float)
        return ds

    def _downsample(self, ds, x, y):
        if ds <= 1:
            return x, y
        if self.config['downsamplingMethod'] == 'subsample':
            x = x[::ds]
            y = y[::ds]
        elif self.config['downsamplingMethod'] == 'mean':
            n = len(x) // ds
            # start of x-values try to select a somewhat centered point
            stx = ds // 2
            x = x[stx:stx + n * ds:ds]
            y = np.array(y[:n * ds]).reshape(n, ds).mean(axis=1).tolist()
        elif self.config['downsamplingMethod'] == 'peak':
            n = len(x) // ds
            x1 = np.empty((n, 2))
            # start of x-values; try to select a somewhat centered point
            stx = ds // 2
            x1[:] = np.array(x)[stx:stx + n * ds:ds, np.newaxis]
            x = x1.reshape(n * 2).tolist()
            y1 = np.empty((n, 2))
            y2 = np.array(y[:n * ds]).reshape((n, ds))
            y1[:, 0] = y2.max(axis=1)
            y1[:, 1] = y2.min(axis=1)
            y = y1.reshape(n * 2).tolist()
        else:
            ...
        return x, y

    def _cachedsample(self, name, x, y):
        ds = self._samplestep(x)
        if name in self.cache:
            cds, cx, cy = self.cache[name]
            if ds == cds:
                ## reuse cached data, append new
                ix = bisect_left(x, cx[-1])
                ex, ey = x[ix+1:], y[ix+1:]
                assert( len(x) > ix )
                if ex:
                    ex, ey = self._downsample(ds, ex, ey)
                cx.extend(ex)
                cy.extend(ey)
                return cx, cy
        ## recalculate whole downsampling
        x, y = self._downsample(ds, x, y)
        self.cache[name] = (ds, x, y)
        return x, y
