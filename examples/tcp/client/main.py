# -*- coding: utf-8 -*-
import sys

import testbench
import trajectory
from PyQt5.QtWidgets import QApplication
from connection import ConnTestTCP

import pywisp as pw

if __name__ == '__main__':
    pw.registerConnection(ConnTestTCP)
    pw.registerExperimentModule(testbench.TestTCP)
    pw.registerExperimentModule(trajectory.RampTrajectory)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec_()
