import os
import pickle
import random
import string
import sys
import time
import unittest

import numpy as np

from PyQt5.QtWidgets import QApplication
from pywisp.widgets.plotchart import PlotChart
from pywisp.utils import DataPointBuffer


app = QApplication(sys.argv)
class PlotTestCase(unittest.TestCase):
    base_path = os.path.dirname(__file__)
    d_name = os.path.join(base_path, "plotPoints.pkl")

    def setUp(self):
        if os.path.exists(self.d_name):
            # load test data
            with open(self.d_name, "rb") as f:
                self.dataPoints = pickle.load(f)
        else:
            # create test data
            lttrs = string.ascii_letters
            lbls = ["".join(random.choice(lttrs) for i in range(10))
                        for j in range(10)]
            self.dataPoints = {lbl: DataPointBuffer() for lbl in lbls}
            for t in range(0, 10000):
                for d in self.dataPoints.values():
                    d.addValue(t, random.random())
            with open(self.d_name, "wb") as f:
                pickle.dump(self.dataPoints, f)

    def test_init(self):
        chart = PlotChart("test", False, 30)
        chart.show()
        chart.close()

    def test_plot_all(self):
        chart = PlotChart("test", False, 30)
        app.setActiveWindow(chart)
        app.processEvents()
        chart.show()
        t0 = time.perf_counter()
        for key, data in self.dataPoints.items():
            chart.addCurve(key, data)
            app.processEvents()
        dt = time.perf_counter() - t0
        ncurv = len(self.dataPoints)
        npoints = len(list(self.dataPoints.values())[0].time)
        print(f"\nPlotting {ncurv} curves of {npoints} points in {dt} seconds.")
        app.processEvents()
        chart.close()

    def test_plot_incremental_moving(self):
        self._incrementaltest(True)
    def test_plot_incremental_nonmoving(self):
        self._incrementaltest(False)

    def _incrementaltest(self, moving):
        chart = PlotChart("test", moving, 30)
        app.processEvents()
        chart.show()
        ncurv = len(self.dataPoints)
        npoints = len(list(self.dataPoints.values())[0].time)
        dps = {}.fromkeys(self.dataPoints.keys())
        for name in dps.keys():
            dps[name] = DataPointBuffer()
            chart.addCurve(name, dps[name])
        app.processEvents()
        t0 = time.perf_counter()
        times = []
        for i in range(20, npoints, 20):
            for key, buf in dps.items():
                buf.time.extend(self.dataPoints[key].time[i-20: i])
                buf.values.extend(self.dataPoints[key].values[i-20: i])
            ti = time.perf_counter()
            chart.updateCurves(dps)
            app.processEvents()
            te = time.perf_counter()
            times.append(te-ti)
        dt = time.perf_counter() - t0
        print(f"\n Plotting {"with" if moving else "without"} moving window")
        print(f"Plotting {ncurv} curves of {npoints} points incrementally in {dt} seconds.")
        print(f" Average: {np.average(times)}, first: {times[0]}, last: {times[-1]}")
        chart.close()

    def tearDown(self):
        app.exit()


if __name__ == '__main__':
    unittest.main()
