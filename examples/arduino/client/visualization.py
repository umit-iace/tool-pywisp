# -*- coding: utf-8 -*-

from matplotlib.offsetbox import *
from pywisp.visualization import MplVisualizer


class MplExampleVisualizer(MplVisualizer):
    def __init__(self, qWidget, qLayout):
        MplVisualizer.__init__(self, qWidget, qLayout)
        self.axes.set_axis_off()
        self.axes.set_aspect(1.5)
        self.axes.set_xlim(0, 1)
        self.axes.set_ylim(0, 1)

        top = 0.98
        mid = 0.5

        def makeValue(x, y, dir, text, textpos):
            arrLen = 30
            if dir == 'below':
                bx = 0
                by = arrLen
            elif dir == 'above':
                bx = 0
                by = -arrLen
            elif dir == 'left':
                bx = arrLen
                by = 0
            elif dir == 'right':
                bx = -arrLen
                by = 0
            elif dir is None:
                bx = 0
                by = 0

            tax, tay = 0.5, 0.5
            if textpos == 'below':
                tay = 1
                tx = 0
                ty = -15
            elif textpos == 'above':
                tay = 0
                tx = 0
                ty = 15
            elif textpos == 'left':
                tax = 1
                tx = -15
                ty = 0
            elif textpos == 'right':
                tax = 0
                tx = 15
                ty = 0
            # variable text
            textObject = TextArea('tmp', textprops=dict(size=8))
            ab = AnnotationBbox(textObject, xy=(x, y), xycoords=self.axes.transAxes,
                                xybox=(bx, by), boxcoords='offset points',
                                bboxprops=dict(boxstyle='circle'),
                                arrowprops=dict(arrowstyle="-"))
            self.axes.add_artist(ab)
            # annotating text
            tx = AnnotationBbox(HPacker(sep=0, pad=0, children=[TextArea(text, textprops=dict(size=8))]),
                                xy=(x, y), xycoords=self.axes.transAxes, box_alignment=(tax, tay),
                                xybox=(bx + tx, by + ty), boxcoords='offset points',
                                frameon=False)
            self.axes.add_artist(tx)
            return textObject

        self.Value1 = makeValue(0.1, mid, 'below', 'V$_{1}$', 'left')
        self.Value2 = makeValue(0.35, mid, None, 'V$_{2}$', 'below')
        self.Value3 = makeValue(0.65, mid, None, 'V$_{3}$', 'below')
        self.Value4 = makeValue(0.9, mid, 'below', 'V$_{4}$', 'right')
        self.ValueTraj = makeValue(mid, top, None, 'V$_{Traj}$', 'above')

        self.canvas.draw_idle()

    def update(self, dataPoints):
        dps = {'TrajOutput': [self.ValueTraj, '1'],
               'Value1': [self.Value1, '1'],
               'Value2': [self.Value2, '1'],
               'Value3': [self.Value3, '1'],
               'Value4': [self.Value4, '1'],
               }

        for key, value in dps.items():
            if dataPoints[key].values:
                formatStr = "%." + value[1] + "f"
                value[0].set_text(formatStr % dataPoints[key].values[-1])

        self.canvas.draw_idle()
        self.saveIfChecked()
