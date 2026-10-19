# -*- coding: utf-8 -*-
import os
import time
from abc import ABCMeta, abstractmethod

from .utils import createDir
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

__all__ = ["Visualizer", "MplVisualizer", "VtkVisualizer"]

try:
    import vtk
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


    class QVTKRenderWindowInteractor(QVTKRenderWindowInteractor):
        """
        overload class to patch problem with zooming in vtk window
        the reason is that the QWheelEvent in PyQt6 hasn't the function delta()
        so we have to replace that with angleDelta()
        the error is caused by vtk 7.0.0
        """

        # override function
        def wheelEvent(self, ev):
            if ev.angleDelta().y() >= 0:
                self._Iren.MouseWheelForwardEvent()
            else:
                self._Iren.MouseWheelBackwardEvent()

except ImportError:
    QVTKRenderWindowInteractor = None


class Visualizer(metaclass=ABCMeta):
    """
    Base class for all visualizations
    """
    def __init__(self):
        self.frameCounter = 0
        self.fileNameCounter = 0
        self.timeStamp = ''
        self.picturePath = None
        self.expName = None
        self.saveAnimation = False

    def checkSaveAnimation(self, state):
        self.saveAnimation = state
        if state:
            self._preparePicturePath()

    def startAnimation(self):
        self.frameCounter = 0
        self.fileNameCounter = 0
        self.timeStamp = time.strftime("%d_%m_%Y_%H_%M_%S") + '_'
        if self.saveAnimation:
            self._preparePicturePath()

    def setExpName(self, name):
        self.expName = name
        self.picturePath = None

    def _preparePicturePath(self):
        # only create the directory if pictures are actually saved
        if self.picturePath is None and self.expName is not None:
            safeName = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.expName)
            self.picturePath = createDir('ani_' + safeName)

    @abstractmethod
    def saveIfChecked(self) -> bool:
        pass

    @abstractmethod
    def update(self, dataPoints: dict):
        """
        Update the canvas with new measurement values.

        :param dataPoints: All measurements from the current time step
        :type dataPoints: dict
        """
        pass


class VtkVisualizer(Visualizer):
    """
    Base Class with some functionality the help visualizing the system using vtk
    """

    def __init__(self, renderer):
        Visualizer.__init__(self)

        assert isinstance(renderer, vtk.vtkRenderer)
        self.ren = renderer

        self.canResetView = False
        self.position = None
        self.focalPoint = None
        self.viewUp = None
        self.viewAngle = None
        self.parallelProjection = None
        self.parallelScale = None
        self.clippingRange = None

    def resetCamera(self):
        """
        Reset camera to original view.
         
        Will be available if you implement the attributes below and set the
        'canResetView' flag.
        """
        if self.canResetView:
            camera = self.ren.GetActiveCamera()
            camera.SetPosition(self.position)
            camera.SetFocalPoint(self.focalPoint)
            camera.SetViewUp(self.viewUp)
            camera.SetViewAngle(self.viewAngle)
            camera.SetParallelProjection(self.parallelProjection)
            camera.SetParallelScale(self.parallelScale)
            camera.SetClippingRange(self.clippingRange)
        else:
            self.ren.ResetCamera()

    def saveCameraPose(self):
        # add camera reset functionality
        camera = self.ren.GetActiveCamera()
        self.position = camera.GetPosition()
        self.focalPoint = camera.GetFocalPoint()
        self.viewUp = camera.GetViewUp()
        self.viewAngle = camera.GetViewAngle()
        self.parallelProjection = camera.GetParallelProjection()
        self.parallelScale = camera.GetParallelScale()
        self.clippingRange = camera.GetClippingRange()

        self.canResetView = True


class MplVisualizer(Visualizer):
    """
    Base Class with some function the help visualizing the system using matplotlib
    """

    def __init__(self, qWidget, qLayout):
        Visualizer.__init__(self)
        self.qWidget = qWidget
        self.qLayout = qLayout
        self.dpi = 100
        self.fig = Figure((5.0, 4.0), dpi=self.dpi)

        self.fig.patch.set_alpha(0)

        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self.qWidget)

        self.axes = self.fig.add_subplot(111)

        self.canvas.setStyleSheet("background-color:transparent;")

        self.qLayout.addWidget(self.canvas)
        self.qWidget.setLayout(self.qLayout)

    def saveIfChecked(self):
        """
        Must be called after self.draw_idle() in implementation.
        """
        if self.saveAnimation and self.picturePath is not None:
            fileName = self.picturePath + os.path.sep + self.timeStamp + "%04d" % self.fileNameCounter + '.png'
            self.fig.savefig(fileName, format='png', dpi=self.dpi)
            self.fileNameCounter += 1
            self.frameCounter += 1
