# -*- coding: utf-8 -*-
import sys
import pywisp as pw
import testbench
import trajectory
import visualization
from PyQt6.QtWidgets import QApplication
from connection import Tcp, Udp

if __name__ == '__main__':
    # connections, the first one is selected by default, the other one in the connections menu
    pw.registerConnection(Udp)
    pw.registerConnection(Tcp)

    # model
    pw.registerExperimentModule(testbench.DoublePendulum)
    # trajectory
    pw.registerExperimentModule(trajectory.Trajectory)

    # visu
    pw.registerVisualizer(visualization.MplDoublePendulumVisualizer)
    app = QApplication(sys.argv)
    form = pw.MainGui()
    form.show()
    app.exec()
