# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# global default settings for physical simulation
# ---------------------------------------------------------------------

# beam parameter
beamLength = 1.575                      # m
beamHeight = 0.010                      # m

# cart parameter
cartLength = 0.145                      # m
cartHeight = 0.060                      # m

# pendulum parameter
pendulumShaftRadius = 0.040 / 2         # m

pendulum1Height = 0.250 + pendulumShaftRadius                   # m
pendulum1Radius = 0.010 / 2         # m

pendulum2Height = 0.250 + pendulumShaftRadius                    # m
pendulum2Radius = 0.010 / 2          # m

# xlim for mpl plot
xMinPlot = -0.850
xMaxPlot = 0.850

yMinPlot = (-pendulum1Height - pendulum2Height) * 1.1
yMaxPlot = -yMinPlot
