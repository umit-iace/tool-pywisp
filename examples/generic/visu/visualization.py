# -*- coding: utf-8 -*-

import matplotlib as mpl
import matplotlib.patches
import matplotlib.transforms
import numpy as np
from exampleData import settings as st

from pywisp.visualization import MplVisualizer


class MplDoublePendulumVisualizer(MplVisualizer):
    def __init__(self, q_widget, q_layout):
        MplVisualizer.__init__(self, q_widget, q_layout)
        self.axes.set_xlim(st.xMinPlot, st.xMaxPlot)
        self.axes.set_ylim(st.yMinPlot, st.yMaxPlot)
        self.axes.set_aspect("equal")

        self.beam = mpl.patches.Rectangle(xy=[-st.beamLength / 2,
                                              -(st.beamHeight
                                                + st.cartHeight / 2)],
                                          width=st.beamLength,
                                          height=st.beamHeight,
                                          color="lightgrey")

        self.cart = mpl.patches.Rectangle(xy=[-st.cartLength / 2,
                                              -st.cartHeight / 2],
                                          width=st.cartLength,
                                          height=st.cartHeight,
                                          color="dimgrey")

        self.pendulumShaft = mpl.patches.Circle(
            xy=(0, 0),
            radius=st.pendulumShaftRadius,
            color="lightgrey",
            zorder=3)

        self.pendulum1 = mpl.patches.Rectangle(
            xy=[-st.pendulum1Radius, 0],
            width=2 * st.pendulum1Radius,
            height=st.pendulum1Height,
            color="#E87B14",  # TUD CD HKS 07_K
            zorder=2)
        self.pendulum1Shaft = mpl.patches.Circle(
            xy=(0, st.pendulum1Height),
            radius=st.pendulumShaftRadius / 2,
            color="#000000",  # TUD CD HKS 07_K
            zorder=3)
        self.pendulum2 = mpl.patches.Rectangle(
            xy=[-st.pendulum2Radius, st.pendulum1Height],
            width=2 * st.pendulum2Radius,
            height=st.pendulum2Height,
            color="#0059A3",  # TUD CD HKS 44_K
            zorder=1)
        self.pendulum2Shaft = mpl.patches.Circle(
            xy=(0, st.pendulum1Height + st.pendulum2Height),
            radius=st.pendulumShaftRadius / 2,
            color="#000000",  # TUD CD HKS 07_K
            zorder=3)

        self.axes.add_patch(self.beam)
        self.axes.add_patch(self.cart)
        self.axes.add_patch(self.pendulumShaft)
        self.axes.add_patch(self.pendulum1)
        self.axes.add_patch(self.pendulum1Shaft)
        self.axes.add_patch(self.pendulum2)
        self.axes.add_patch(self.pendulum2Shaft)

        self.canvas.draw_idle()

    def update(self, dataPoints):
        x = phi1 = phi2 = 0
        for name, buffer in dataPoints.items():
            if buffer.values:
                if name == 'pos':
                    x = buffer.values[-1]
                elif name == 'phi1':
                    phi1 = -buffer.values[-1]
                elif name == 'phi2':
                    phi2 = -buffer.values[-1]

        x0 = np.array([x, 0])
        x1 = x0 + np.array([-np.sin(phi1), np.cos(phi1)]) * st.pendulum1Height
        x2 = x1 + np.array([-np.sin(phi2), np.cos(phi2)]) * st.pendulum2Height

        # cart and shaft
        self.cart.set_x(-st.cartLength / 2 + x)
        self.pendulumShaft.center = [x, 0]

        # pendulum 1
        t_phi1 = (mpl.transforms.Affine2D().rotate_around(x, 0, phi1)
                  + self.axes.transData)
        self.pendulum1.set_xy(x0 - np.array([st.pendulum1Radius, 0]))
        self.pendulum1.set_transform(t_phi1)
        self.pendulum1Shaft.set_center(x1)

        # # pendulum 2
        t_phi2 = (mpl.transforms.Affine2D().rotate_around(x1[0], x1[1], phi2)
                  + self.axes.transData)
        self.pendulum2.set_xy(x1 - np.array([st.pendulum2Radius, 0]))
        self.pendulum2.set_transform(t_phi2)
        self.pendulum2Shaft.set_center(x2)

        self.canvas.draw_idle()
        self.saveIfChecked()
