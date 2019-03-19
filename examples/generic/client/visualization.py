# -*- coding: utf-8 -*-

from pywisp.visualization import MplVisualizer
import matplotlib as mpl
import matplotlib.patches
import matplotlib.transforms
import numpy as np
import settings as st

class MplTwoPendulumVisualizer(MplVisualizer):

    def __init__(self, q_widget, q_layout):
        MplVisualizer.__init__(self, q_widget, q_layout)
        self.axes.set_xlim(st.x_min_plot, st.x_max_plot)
        self.axes.set_ylim(st.y_min_plot, st.y_max_plot)
        self.axes.set_aspect("equal")

        self.beam = mpl.patches.Rectangle(xy=[-st.beam_length/2,
                                              -(st.beam_height
                                                + st.cart_height/2)],
                                          width=st.beam_length,
                                          height=st.beam_height,
                                          color="lightgrey")

        self.cart = mpl.patches.Rectangle(xy=[-st.cart_length/2,
                                              -st.cart_height/2],
                                          width=st.cart_length,
                                          height=st.cart_height,
                                          color="dimgrey")

        self.pendulum_shaft = mpl.patches.Circle(
            xy=(0, 0),
            radius=st.pendulum_shaft_radius,
            color="lightgrey",
            zorder=3)

        self.pendulum1 = mpl.patches.Rectangle(
            xy=[-st.short_pendulum_radius, 0],
            width=2*st.short_pendulum_radius,
            height=st.short_pendulum_height,
            color="#E87B14",  # TUD CD HKS 07_K
            zorder=2)
        self.pendulum1_shaft = mpl.patches.Circle(
            xy=(0, st.short_pendulum_height),
            radius=st.pendulum_shaft_radius / 2,
            color="#000000",  # TUD CD HKS 07_K
            zorder=3)
        self.pendulum2 = mpl.patches.Rectangle(
            xy=[-st.long_pendulum_radius, st.short_pendulum_height],
            width=2*st.long_pendulum_radius,
            height=st.long_pendulum_height,
            color="#0059A3",  # TUD CD HKS 44_K
            zorder=1)
        self.pendulum2_shaft = mpl.patches.Circle(
            xy=(0, st.short_pendulum_height + st.long_pendulum_height),
            radius=st.pendulum_shaft_radius / 2,
            color="#000000",  # TUD CD HKS 07_K
            zorder=3)

        self.axes.add_patch(self.beam)
        self.axes.add_patch(self.cart)
        self.axes.add_patch(self.pendulum_shaft)
        self.axes.add_patch(self.pendulum1)
        self.axes.add_patch(self.pendulum1_shaft)
        self.axes.add_patch(self.pendulum2)
        self.axes.add_patch(self.pendulum2_shaft)

        self.canvas.draw()

    def update(self, dataPoints):
        x = phi1 = phi2 = 0
        for name, buffer in dataPoints.items():
            if buffer.values:
                if name == 'Value1':
                    x = buffer.values[-1]
                elif name == 'Value2':
                    phi1 = -buffer.values[-1]
                elif name == 'Value3':
                    phi2 = -buffer.values[-1]

        x0 = np.array([x, 0])
        x1 = x0 + np.array([-np.sin(phi1), np.cos(phi1)]) * st.short_pendulum_height
        x2 = x1 + np.array([-np.sin(phi2), np.cos(phi2)]) * st.long_pendulum_height

        # cart and shaft
        self.cart.set_x(-st.cart_length/2 + x)
        self.pendulum_shaft.center = [x, 0]

        # pendulum 1
        t_phi1 = (mpl.transforms.Affine2D().rotate_around(x, 0, phi1)
                  + self.axes.transData)
        self.pendulum1.set_xy(x0 - np.array([st.short_pendulum_radius, 0]))
        self.pendulum1.set_transform(t_phi1)
        self.pendulum1_shaft.set_center(x1)

        # # pendulum 2
        t_phi2 = (mpl.transforms.Affine2D().rotate_around(x1[0], x1[1], phi2)
                  + self.axes.transData)
        self.pendulum2.set_xy(x1 - np.array([st.long_pendulum_radius, 0]))
        self.pendulum2.set_transform(t_phi2)
        self.pendulum2_shaft.set_center(x2)

        self.canvas.draw()
