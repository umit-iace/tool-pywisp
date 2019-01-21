# -*- coding: utf-8 -*-
import sys

import testbench
import trajectory
from PyQt5.QtWidgets import QApplication
from connection import ConnTestSerial
from visualization import MplExampleVisualizer

import pywisp as pw

if __name__ == '__main__':
    pw.registerConnection(ConnTestSerial)
    pw.registerExperimentModule(testbench.Test)
    pw.registerExperimentModule(trajectory.RampTrajectory)
    pw.registerVisualizer(MplExampleVisualizer)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec_()
