import io
import logging
import math
import numpy as np
from PyQt6.QtCore import QLineF, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMenu, QVBoxLayout
from pyqtgraph import AxisItem, GraphicsObject, PlotWidget, ViewBox, mkPen
from ..export import plotDataPoints
from .common import ContextLineEditAction
from .fileselector import FileSelector
from ..settings import Settings


class Grid(GraphicsObject):
    """
    Grid lines at the ticks of the axes, strong at the labeled ticks and faint in between. Replaces the grid of
    the axes (``showGrid``), which costs several times as much to draw, since the axes repaint the whole view on
    every change of the moving window.
    """
    MAJOR_ALPHA = 110
    MINOR_ALPHA = 35

    def __init__(self, plotItem):
        super().__init__()
        self.plotItem = plotItem
        # below the curves
        self.setZValue(-1000)
        plotItem.addItem(self, ignoreBounds=True)
        plotItem.getViewBox().sigRangeChanged.connect(self._rangeChanged)

    def _rangeChanged(self):
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        return self.plotItem.getViewBox().viewRect()

    def paint(self, painter, *args):
        viewBox = self.plotItem.getViewBox()
        rect = viewBox.viewRect()
        for name, vertical in (('bottom', True), ('left', False)):
            axis = self.plotItem.getAxis(name)
            # the time axis keeps the neutral color, the left one may take the color of a curve (separate axes)
            color = QColor(self.plotItem.getAxis('bottom').pen().color())
            lo, hi = (rect.left(), rect.right()) if vertical else (rect.top(), rect.bottom())
            size = viewBox.width() if vertical else viewBox.height()
            # the ticks of the axis, the first level is labeled, a level does not repeat the values of the others
            for level, (_, values) in enumerate(axis.tickValues(min(lo, hi), max(lo, hi), size)[:2]):
                color.setAlpha(self.MAJOR_ALPHA if level == 0 else self.MINOR_ALPHA)
                painter.setPen(mkPen(color, cosmetic=True))
                if vertical:
                    painter.drawLines([QLineF(v, rect.top(), v, rect.bottom()) for v in values])
                else:
                    painter.drawLines([QLineF(rect.left(), v, rect.right(), v) for v in values])


class PlotChart(PlotWidget):
    """
    Object containing the plot widgets and the associated plot curves
    """
    #: coordinates of the mouse in the plot
    #: the moving window was switched or resized, from any place (menu, data tab)
    movingWindowChanged = pyqtSignal()
    coords = pyqtSignal(object)  # (x, y) or None when the mouse left the plot

    def __init__(self, title, config):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.title = title
        self.plotCurves = {}
        # colors chosen by the user, the other curves take the palette color of their position
        self.curveColors = {}
        # complete data of the curves, the curves itself only show the moving window
        self.buffers = {}

        # plot settings
        self.settings = Settings()
        self.movingWindowEnable = config.get("MovingWindowEnable", True)
        # MovingWindowSize is the documented key, MovingWindowWidth is kept for compatibility
        self.movingWindowWidth = config.get("MovingWindowSize", config.get("MovingWindowWidth", 30))

        # plot widget settings
        self.gridLines = Grid(self.getPlotItem())
        self.getPlotItem().getAxis("bottom").setLabel(text="Time", units="s")

        # enable down-sampling and clipping for better performance
        self.setClipToView(True)
        self.config = {
            'downsamplingMethod': config.get("downsamplingMethod", 'peak')
        }
        self.cache = {}

        # separate y axes: the first curve keeps the main axis, the others get a view box and an axis to the right
        self.separateAxes = config.get("SeparateYAxes", False)
        self.axisViews = {}
        self.getPlotItem().vb.sigResized.connect(self._syncAxisViews)

        # the axis grid of pyqtgraph is too expensive, the cheap gridLines replace it, so its menu has to go
        plotItem = self.getPlotItem()
        for act in plotItem.ctrlMenu.actions():
            if act.menu() and any(getattr(a, 'defaultWidget', lambda: None)() is plotItem.ctrl.gridGroup
                                  for a in act.menu().actions()):
                plotItem.ctrlMenu.removeAction(act)

        def coordWrapper(pos):
            coords = plotItem.vb.mapSceneToView(pos)
            self.coords.emit((coords.x(), coords.y()))

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
        # the window may also be changed in the data tab, the menu shows the current values
        qMenuMovingWindow.aboutToShow.connect(lambda: (
            qActionMovingWindowSize.data.setText(str(self.movingWindowWidth)),
            qActionMovingWindowEnable.setChecked(self.movingWindowEnable)))

        self.actSeparateAxes = QAction("Separate Y Axes", self, checkable=True)
        self.actSeparateAxes.setChecked(self.separateAxes)
        self.actSeparateAxes.triggered.connect(self.setSeparateAxes)

        self.scene().contextMenu = [qActionSep1,
                                      QAction("Auto Range All", self),
                                      qActionSep2,
                                      QAction("Save Image", self),
                                      qActionSep3,
                                      qMenuMovingWindow,
                                      self.actSeparateAxes,
                                      ]

        self.scene().contextMenu[1].triggered.connect(self.setAutoRange)
        self.scene().contextMenu[3].triggered.connect(lambda: self.saveImage())

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self.coords.emit(None)

    def addCurve(self, name, data):
        """
        Adds a curve to the plot widget
        Args:
            dataPoint(DataPointBuffer): Data point which contains the data be added
        """
        color = self.curveColors.get(name) or self.settings.color(len(self.plotCurves))
        self.buffers[name] = data
        # add the actual curve
        self.plotCurves[name] = self.plot(name=name,
                                          pen=mkPen(color),
                                          skipFiniteCheck=True
                                          )
        if self.separateAxes:
            self._layoutAxes()
            self._applyColor(name)
        self.updateCurves({name:data})

    def removeCurve(self, name):
        self.cache.pop(name, None)
        self.buffers.pop(name, None)
        curve = self.plotCurves.pop(name, None)
        if curve is None:
            return
        if name not in self.axisViews:
            self.getPlotItem().removeItem(curve)
        # an own view box goes with its curve
        self._layoutAxes()
        # the remaining curves move up, so do their palette colors
        for curveName in self.plotCurves:
            self._applyColor(curveName)

    def setSeparateAxes(self, enable):
        """ shows each curve on its own y axis, or all curves on the main axis """
        self.separateAxes = enable
        self.actSeparateAxes.setChecked(enable)
        self._layoutAxes()
        for name in self.plotCurves:
            self._applyColor(name)
        # the main axis shows other curves now
        self.getPlotItem().enableAutoRange(y=True)

    def curveAxis(self, name):
        """ the y axis of the curve with the given name """
        if name in self.axisViews:
            return self.axisViews[name][1]
        return self.getPlotItem().getAxis('left')

    def _layoutAxes(self):
        """
        Moves the curves to their view boxes, the first curve stays on the main axis.
        Only called when curves or the mode change, the view boxes of the remaining curves are kept.
        """
        plotItem = self.getPlotItem()
        names = list(self.plotCurves)[1:] if self.separateAxes else []
        for name in [name for name in self.axisViews if name not in names]:
            viewBox, axis = self.axisViews.pop(name)
            plotItem.layout.removeItem(axis)
            self.scene().removeItem(axis)
            viewBox.setXLink(None)
            if name in self.plotCurves:
                # moved within the scene: a curve added to the scene without a parent fails to find its view box
                curve = self.plotCurves[name]
                curve.setParentItem(plotItem.vb.childGroup)
                viewBox.addedItems.remove(curve)
                plotItem.addItem(curve)
                plotItem.enableAutoRange(y=True)
            self.scene().removeItem(viewBox)
        for col, name in enumerate(names, start=3):
            if name not in self.axisViews:
                viewBox = ViewBox()
                # below the main view box, which keeps the mouse interaction, the axis changes the y range
                viewBox.setZValue(-100)
                # the curve is added before the view box is in the scene, for the same reason
                curve = self.plotCurves[name]
                plotItem.removeItem(curve)
                viewBox.addItem(curve)
                self.scene().addItem(viewBox)
                viewBox.setGeometry(plotItem.vb.sceneBoundingRect())
                viewBox.setXLink(plotItem.vb)
                axis = AxisItem('right')
                axis.linkToView(viewBox)
                self.axisViews[name] = (viewBox, axis)
            # the columns behind the right axis of the plot item, in the order of the curves
            plotItem.layout.addItem(self.axisViews[name][1], 2, col)
        if not self.separateAxes or not self.plotCurves:
            left = plotItem.getAxis('left')
            left.setPen()
            left.setTextPen()
            left.setLabel()

    def _syncAxisViews(self):
        """ the view boxes of the separate axes cover the main view box """
        rect = self.getPlotItem().vb.sceneBoundingRect()
        for viewBox, _ in self.axisViews.values():
            viewBox.setGeometry(rect)

    def _applyColor(self, name):
        """ the curve and its own axis get the color of the curve """
        pen = mkPen(self.curveColor(name))
        self.plotCurves[name].setPen(pen)
        if self.separateAxes:
            axis = self.curveAxis(name)
            axis.setPen(pen)
            axis.setTextPen(pen)
            axis.setLabel(name, color=pen.color().name())

    def curveColor(self, name):
        """ the color of the curve with the given name """
        if name in self.curveColors:
            return self.curveColors[name]
        return self.settings.color(list(self.plotCurves).index(name))

    def setCurveColor(self, name, color):
        self.curveColors[name] = QColor(color)
        self._applyColor(name)

    def curveStepMode(self, name):
        return self.plotCurves[name].opts['stepMode']

    def setCurveStepMode(self, name, mode):
        """
        :param mode: `None` interpolates linearly between the points, `"left"` holds each value until the next
            point (zero-order hold)
        """
        curve = self.plotCurves[name]
        # setData keeps the option, the next updates of the data are drawn the same way
        curve.opts['stepMode'] = mode
        curve.updateItems(styleUpdate=False)

    def setAutoRange(self):
        self.autoRange()
        self.enableAutoRange()
        for viewBox, _ in self.axisViews.values():
            viewBox.enableAutoRange(y=True)

    def setEnableMovingWindow(self, movingWindowEnable):
        self.movingWindowEnable = movingWindowEnable
        self.setAutoRange()
        self.movingWindowChanged.emit()

    def setMovingWindowWidth(self, movingWindowWidth):
        try:
            self.movingWindowWidth = int(movingWindowWidth)
        except ValueError:
            self._logger.error(f"Invalid moving window width '{movingWindowWidth}'")
            return
        self.movingWindowChanged.emit()

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
            self.buffers[name] = dataPoints[name]
            datax = dataPoints[name].time
            datay = dataPoints[name].values
            if self.movingWindowEnable:
                datax, datay = xRange(datax, datay)
                ds = self._sampleStep(datax)
                x, y = self._downsample(ds, datax, datay)
            else:
                x, y = self._cachedSample(name, datax, datay)
            self.plotCurves[name].setData(x, y)


    def saveImage(self, fileName=None):
        """
        Plots the complete data from time 0 on and saves it as image.
        Without a file name, a preview is shown and the file is selected afterwards.
        """
        dataPoints = {name: buf.snapshot() for name, buf in self.buffers.items()}
        fig = plotDataPoints(dataPoints)
        if fileName is None:
            if not self._previewImage(fig):
                return
            fileName = FileSelector(["PNG Image (*.png)", "JPEG Image (*.jpg)",
                                     "PDF Document (*.pdf)"]).getSaveFileName("Save Image")
            if fileName is None:
                return
        try:
            fig.savefig(fileName, dpi=300)
        except Exception as e:
            self._logger.error(f"Saving image to {fileName} failed: {e!r}")
            return
        self._logger.info(f"Image saved to {fileName}.")

    def _previewImage(self, fig):
        """ shows the figure, returns `True` if it should be saved """
        png = io.BytesIO()
        fig.savefig(png, format='png', dpi=80)
        pixmap = QPixmap()
        pixmap.loadFromData(png.getvalue())

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Save Image - {self.title}")
        label = QLabel(dialog)
        label.setPixmap(pixmap)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

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
