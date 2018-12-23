# -*- coding: utf-8 -*-
import sys

from PyQt5.QtWidgets import QApplication

import controller
import pywisp as pw
import testbench
import trajectory
import visualization

if __name__ == '__main__':
    pw.registerExperimentModule(testbench.BallInTube)
    pw.registerExperimentModule(trajectory.ConstTrajectory)
    pw.registerExperimentModule(trajectory.SinoidTrajectory)
    pw.registerExperimentModule(controller.PIDController)
    pw.registerVisualizer(visualization.MplBallInTubeVisualizer)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec_()
