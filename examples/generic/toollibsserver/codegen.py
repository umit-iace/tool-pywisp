import sympy as sp
from sympy import cos, sin, Matrix
import numpy as np
import settings as st
x, dx, phi1, dphi1, phi2, dphi2 = sp.symbols('x, dx, phi1, dphi1, phi2, dphi2')
F, = sp.symbols('F,')

m = st.cartMass
m1 = st.pendulum1Mass
m2 = st.pendulum1Mass
l1 = st.pendulum1Length
l2 = st.pendulum2Length
I1 = st.pendulum1Inertia
I2 = st.pendulum2Inertia
g = st.g

# mass matrix
M = Matrix([[m + m1 + m2, (m1 + 2 * m2) * l1 * cos(phi1), m2 * l2 * cos(phi2)],
            [(m1 + 2 * m2) * l1 * cos(phi1), I1 + (m1 + 4 * m2) * l1 ** 2, 2 * m2 * l1 * l2 * cos(phi2 - phi1)],
            [m2 * l2 * cos(phi2), 2 * m2 * l1 * l2 * cos(phi2 - phi1), I2 + m2 * l2 ** 2]])

# and right hand site
B = Matrix([[F + (m1 + 2 * m2) * l1 * sin(phi1) * dphi1 ** 2 + m2 * l2 * sin(phi2) * dphi2 ** 2],
            [(m1 + 2 * m2) * g * l1 * sin(phi1) + 2 * m2 * l1 * l2 * sin(phi2 - phi1) * dphi2 ** 2],
            [m2 * g * l2 * sin(phi2) + 2 * m2 * l1 * l2 * sin(phi1 - phi2) * dphi1 ** 2]])

solution = M.solve(B)
solution = solution.row_insert(0, Matrix([dx]))
solution = solution.row_insert(2, Matrix([dphi1]))
solution = solution.row_insert(4, Matrix([dphi2]))

stateVars = np.array([x, dx, phi1, dphi1, phi2, dphi2])
inputVars = np.array([F])

from sympy.printing import ccode

newline = '\n'

with open('inc/doublependulum.h', 'w') as file:
    file.write(f"""/** This file is autogenerated, do not edit */
#pragma once
#include <Eigen/Dense>
#include <cmath>
using Eigen::Matrix;
struct DoublePendulum {{
    using Input = Matrix<double, {len(inputVars)}, 1>;
    using State = Matrix<double, {len(stateVars)}, 1>;
    Input u{{}};
    State state{{}};
    void setInput(const Input &input) {{ u = input; }}
    void compute(uint32_t dt) {{
{f"{newline}".join([
f"        auto {x} = state({i});" for i, x in enumerate(stateVars)
])}
{f"{newline}".join([
f"        auto {x} = u({i});" for i, x in enumerate(inputVars)
])}
        State tmp{{}};
        {ccode(solution, assign_to="tmp")}
        state += dt / 1000. * tmp;
    }};
}};
""")
