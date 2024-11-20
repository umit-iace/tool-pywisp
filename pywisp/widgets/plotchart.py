from bisect import bisect_left
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAction, QMenu, QWidget
from pyqtgraph import PlotWidget, TextItem, mkPen
from pywisp.utils import ContextLineEditAction, DataPointBuffer, Exporter
from .utils import settings

_default = {
    "plot_colors": [
        ("blue", "#1f77b4"),
        ("orange", "#ff7f0e"),
        ("green", "#2ca02c"),
        ("red", "#d62728"),
        ("purple", "#9467bd"),
        ("brown", "#8c564b"),
        ("pink", "#e377c2"),
        ("gray", "#7f7f7f"),
        ("olive", "#bcbd22"),
        ("cyan", "#17becf"),
    ],
    "view": [
        ("show_coordinates", "True")
    ]
}

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
        self.settings = settings(_default)
        self.movingWindowEnable = config.get("MovingWindowEnable", True)
        self.movingWindowWidth = config.get("MovingWindowWidth", 30)

        # plot widget settings
        self.showGrid(True, True)
        self.getPlotItem().getAxis("bottom").setLabel(text="Time", units="s")

        # enable down-sampling and clipping for better performance
        method = config.get("downsamplingMethod", 'peak')
        self.setDownsampling(ds=1 if method == 'off' else None,
                             auto=None if method == 'off' else True,
                             mode='peak' if method == 'off' else method)
        self.setClipToView(True)

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
        # get plot color
        self.settings.beginGroup('plot_colors')
        cKeys = self.settings.childKeys()
        colorIdxItem = len(self.plotCurves) % len(cKeys)
        colorItem = QColor(self.settings.value(cKeys[colorIdxItem]))
        self.settings.endGroup()

        # add the actual curve
        self.plotCurves[name] = self.plot(x=data.time, y=data.values,
                                          name=name,
                                          pen=mkPen(colorItem, width=1),
                                          skipFiniteCheck=True
                                          )

    def removeCurve(self, name):
        if name in self.plotCurves:
            curve = self.plotCurves.pop(name)
        self.getPlotItem().removeItem(curve)

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
        lastX = [ dataPoints[name].time[-1]
                     for name in self.plotCurves.keys()
                     if dataPoints[name].time ]
        if not lastX:
            return
        firstX = max(lastX) - self.movingWindowWidth

        def xRange(time, values):
            start = bisect_left(time, firstX)
            return time[start:], values[start:]

        for name, curve in self.plotCurves.items():
            datax = dataPoints[name].time
            datay = dataPoints[name].values
            if self.movingWindowEnable:
                datax, datay = xRange(datax, datay)
            curve.setData(datax, datay)

    def clear(self):
        """
        Clears the data point and curve lists and the plot items
        """
        self.getPlotItem().clear()
        self.plotCurves.clear()

    def export(self, filename=None):
        dataPoints = dict()
        for i, c in enumerate(self.getPlotItem().curves):
            if c.getData() is None:
                continue
            if len(c.getData()) > 2:
                self._logger.warning('Can not handle the amount of data!')
                continue
            dataPoints[c.name()] = DataPointBuffer(time=c.getData()[0], values=c.getData()[1])

        self.exporter = Exporter(dataPoints=dataPoints, fileName=filename)
        self.exporter.runExport()
