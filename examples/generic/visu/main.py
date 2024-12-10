# -*- coding: utf-8 -*-
import sys
import pywisp as pw
import testbench
import trajectory
import visualization
from PyQt5.QtWidgets import QApplication
from connection import Connection

if __name__ == '__main__':
    # connection
    pw.registerConnection(Connection)

    # model
    pw.registerExperimentModule(testbench.DoublePendulum)
    # trajectory
    pw.registerExperimentModule(trajectory.Trajectory)

    # visu
    pw.registerVisualizer(visualization.MplDoublePendulumVisualizer)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec_()
