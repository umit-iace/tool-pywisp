import os
import pickle
import random
import string
import sys
import time
import unittest

import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import QApplication
from pywisp.widgets.plotchart import PlotChart
from pywisp.utils import DataPointBuffer


class PlotTestCase(unittest.TestCase):
    base_path = os.path.dirname(__file__)
    d_name = os.path.join(base_path, "plotPoints.pkl")

    def setUp(self):
        self.app = QApplication(sys.argv)
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
            t_end = 10000
            for t in range(0, t_end):
                for idx, d in enumerate(self.dataPoints.values()):
                    d.addValue(t, np.sin(20*idx*t/t_end))
            with open(self.d_name, "wb") as f:
                pickle.dump(self.dataPoints, f)

    def test_init(self):
        chart = PlotChart("test", False, 30, False, None)
        chart.show()
        chart.close()

    def test_plot_all(self):
        chart = PlotChart("test", False, 30, False, None)
        self.app.setActiveWindow(chart)
        self.app.processEvents()
        chart.show()
        t0 = time.perf_counter()
        for key, data in self.dataPoints.items():
            chart.addCurve(key, data)
            self.app.processEvents()
        dt = time.perf_counter() - t0
        ncurv = len(self.dataPoints)
        npoints = len(list(self.dataPoints.values())[0].time)
        print(f"\nPlotting {ncurv} curves of {npoints} points in {dt} seconds.")
        self.app.processEvents()
        chart.close()

    def test_plot_incremental(self):
        self._incrementaltest(True, True)
        self._incrementaltest(True, 1)
        self._incrementaltest(False, True)
        self._incrementaltest(False, 1)

    def _incrementaltest(self, moving, downsample):
        print(f"Plotting with"
              f"moving window: {moving}, "
              f"downsampling rate: {downsample}"
              )

        chart = PlotChart("test", moving, 30, downsample, "peak")
        self.app.processEvents()
        chart.show()
        ncurv = len(self.dataPoints)
        npoints = len(list(self.dataPoints.values())[0].time)
        dps = dict.fromkeys(self.dataPoints.keys())
        for name in dps.keys():
            dps[name] = DataPointBuffer()
            chart.addCurve(name, dps[name])
        self.app.processEvents()

        times = []
        for i in range(20, npoints, 20):
            for key, buf in dps.items():
                buf.time.extend(self.dataPoints[key].time[i-20: i])
                buf.values.extend(self.dataPoints[key].values[i-20: i])
            t0 = time.perf_counter()
            chart.updateCurves(dps)
            t1 = time.perf_counter()
            self.app.processEvents()
            t2 = time.perf_counter()

            # compute intervals
            t_full = t2 - t0
            t_update = t1 -t0
            t_render = t2 -t1
            times.append([i, t_full, t_update, t_render])
        chart.close()

        times = np.array(times).T
        print(f"{ncurv} curves with {npoints} points took {sum(times[1])} seconds.")
        mean = np.average(times[1])
        var = np.var(times[1])
        print(f"Mean: {mean}, Variance: {var}")

        timeplot = PlotChart("Timings",{"MovingWindowEnable": False})
        timeplot.addCurve("sum",    DataPointBuffer(times[0], times[1]))
        timeplot.addCurve("update", DataPointBuffer(times[0], times[2]))
        timeplot.addCurve("render", DataPointBuffer(times[0], times[3]))
        f_name = f"timings_for_moving_{moving}_downsampling_{downsample}.png"
        timeplot.export(f_name)

    def test_update_timings(self):
        # downsampling
        print("No windowing, no downsampling")
        self.get_update_timings(False, 0, 1, None)
        print("No windowing, auto downsampling with subsample mode")
        self.get_update_timings(False, 0, True, "subsample")
        print("No windowing, auto downsampling with mean mode")
        self.get_update_timings(False, 0, True, "mean")
        print("No windowing, auto downsampling with peak mode")
        self.get_update_timings(False, 0, True, "peak")

        # moving window
        print("windowing with w=100, no downsampling")
        self.get_update_timings(True, 100, 1, None)
        print("windowing with w=1000, no downsampling")
        self.get_update_timings(True, 1000, 1, None)


    def get_update_timings(self, windowing, window_size, downsample, d_method):
        chart = PlotChart(title="fixed window",
                          movingWindowEnable=windowing,
                          movingWindowWidth=window_size,
                          downsampling=downsample,
                          downsamplingMethod=d_method)
        for lbl, data in self.dataPoints.items():
            chart.addCurve(lbl, data)
        chart.show()
        self.app.processEvents()

        N = 10
        t0 = time.perf_counter()
        for i in range(N):
            chart.updateCurves(self.dataPoints)
            self.app.processEvents()
        dt = time.perf_counter() - t0
        chart.close()
        print(f"Average update time is {dt/N * 1e3} ms")

    def tearDown(self):
        self.app.exit()


if __name__ == '__main__':
    unittest.main()
