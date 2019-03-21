# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# global default settings for physical simulation
# ---------------------------------------------------------------------

g = 9.81                                    # m / s2 gravitational acceleration

# beam parameter
beamLength = 1.575                          # m
beamHeight = 0.010                          # m

# cart parameter
cartMass = 1.0                              # kg

# pendulum parameter
pendulum1Mass = 0.1                         # kg
pendulum2Mass = 0.1                         # kg
pendulum1Length = 0.25                      # m
pendulum2Length = 0.25                      # m

pendulum1Inertia = 4.0 / 3.0 * pendulum1Mass * pendulum1Length ** 2  
pendulum2Inertia = 4.0 / 3.0 * pendulum2Mass * pendulum2Length ** 2 
