# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

__all__ = ["MplVisualizer"]


class Visualizer(metaclass=ABCMeta):
    """
    Base Class for animation
    """
    def __init__(self):
        pass

    @abstractmethod
    def update(self, x):
        pass


class MplVisualizer(Visualizer):
    """
    Base Class with some function the help visualizing the system using matplotlib
    """

    def __init__(self, qWidget, qLayout):
        Visualizer.__init__(self)
        self.qWidget = qWidget
        self.qLayout = qLayout
        self.dpi = 100
        self.fig = Figure((5.0, 4.0), facecolor='white', dpi=self.dpi)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self.qWidget)
        self.axes = self.fig.add_subplot(111)
        self.qLayout.addWidget(self.canvas)
        self.qWidget.setLayout(self.qLayout)

    def update(self, dataPoints):
        pass
