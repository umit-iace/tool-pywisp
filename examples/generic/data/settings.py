# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# global default settings for physical simulation
# ---------------------------------------------------------------------
g = 9.81                                                            # m / s2 gravitational acceleration

# beam parameter
beamLength = 1.575                                                  # m
beamHeight = 0.010                                                  # m

# cart parameter
cartMass = 10.0                                                     # kg
cartLength = 0.145                                                  # m
cartHeight = 0.060                                                  # m

# pendulum parameter
pendulumShaftRadius = 0.040 / 2                                     # m
pendulum1Mass = 0.1                                                 # kg
pendulum2Mass = 0.1                                                 # kg
pendulum1Length = 0.25                                              # m
pendulum2Length = 0.25                                              # m
pendulum1Height = 0.250 + pendulumShaftRadius                       # m
pendulum2Height = 0.250 + pendulumShaftRadius                       # m
pendulum1Radius = 0.010 / 2                                         # m
pendulum2Radius = 0.010 / 2                                         # m

pendulum1Inertia = 4.0 / 3.0 * pendulum1Mass * pendulum1Length ** 2
pendulum2Inertia = 4.0 / 3.0 * pendulum2Mass * pendulum2Length ** 2

# xlim for visu
xMinPlot = -0.850
xMaxPlot = 0.850

yMinPlot = (-pendulum1Height - pendulum2Height) * 1.1
yMaxPlot = -yMinPlot
