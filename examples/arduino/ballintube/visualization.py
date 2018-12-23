# -*- coding: utf-8 -*-
import sys

import matplotlib as mpl
import matplotlib.patches
import os

sys.path.insert(0, os.path.dirname(os.path.realpath('__file__')) + '/../../../Identifikation/')
import settingsV3 as st
from pywisp.visualization import MplVisualizer


class MplBallInTubeVisualizer(MplVisualizer):
    def __init__(self, qWidget, qLayout):
        MplVisualizer.__init__(self, qWidget, qLayout)

        self.dataPoints = ['Position']

        self.axes.set_xlim(-0.3, 0.3)
        self.axes.set_ylim(-0.05, 1.55)
        self.axes.set_aspect("equal")
        self.axes.get_xaxis().set_visible(False)
        tube_out = mpl.patches.Rectangle(xy=[-st.rR * st.scale, 0],
                                         width=2.0 * st.rR * st.scale,
                                         height=st.l,
                                         linewidth=1,
                                         fill=False)
        self.axes.add_patch(tube_out)

        self.ball = mpl.patches.Circle(xy=[0, st.rB * st.scale],
                                       radius=st.rB * st.scale,
                                       color="#0059A3",
                                       linewidth=1)
        self.ball.set_edgecolor("black")
        self.axes.add_patch(self.ball)

    def update(self, x):
        self.ball.center = (0, x[self.dataPoints[0]] + st.rB * st.scale)
        self.canvas.draw()
