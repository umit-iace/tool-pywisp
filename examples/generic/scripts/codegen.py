import sympy as sp
from sympy import cos, sin, Matrix
import numpy as np
import settings as st
p, d, phi1, dphi1, phi2, dphi2 = sp.symbols('p, dp, phi1, dphi1, phi2, dphi2')
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
solution = solution.row_insert(0, Matrix([dp]))
solution = solution.row_insert(2, Matrix([dphi1]))
solution = solution.row_insert(4, Matrix([dphi2]))

stateVars = np.array([p, dp, phi1, dphi1, phi2, dphi2])
inputVars = np.array([F])

from sympy.printing import ccode

newline = '\n'

print(f"""{f"{newline}".join([
f"        auto {p} = state({i});" for i, p in enumerate(stateVars)
])}
{f"{newline}".join([
f"        auto {p} = u({i});" for i, p in enumerate(inputVars)
])}
    {ccode(solution, assign_to="tmp")}
    }};
}};
""")
