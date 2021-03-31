# -*- coding: utf-8 -*-
import sys

import pywisp as pw
import testbench
import trajectory
from PyQt5.QtWidgets import QApplication
from connection import ConnTestTCP
from visualization import MplExampleVisualizer

if __name__ == '__main__':
    pw.registerConnection(ConnTestTCP)
    pw.registerExperimentModule(testbench.Test)
    pw.registerExperimentModule(trajectory.RampTrajectory)
    pw.registerExperimentModule(trajectory.SeriesTrajectory)
    pw.registerVisualizer(MplExampleVisualizer)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec_()
