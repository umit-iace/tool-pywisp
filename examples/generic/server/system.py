import sympy as sp
import pickle
from sympy import cos, sin, Matrix, lambdify
import numpy as np
import settings as st


class System:
    def __init__(self):
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
        inputVars = F
        self.f = lambdify((stateVars, inputVars), solution, modules='numpy')

        self.ffLastStart = 0
        with open("ex8_ConstrainedDoublePendulum.pkl", "rb") as ffFile:
            self.ffTraj = pickle.load(ffFile, fix_imports=True, encoding="latin1")
        self.ffStart = self.ffTraj[0, 0]
        self.ffDuration = self.ffTraj[-1, 0] - self.ffStart

    def feedForwardControl(self, t):
        relTime = t - self.ffLastStart - self.ffStart

        if 0 <= relTime <= self.ffDuration:
            return np.interp( relTime, self.ffTraj[:, 0], self.ffTraj[:, 1])

        else:
            return 0

    def feedForwardIsRunning(self, t):
        return t - self.ffLastStart - self.ffStart < self.ffDuration

    def rhs(self, t, x, u):
        return self.f(x, u + self.feedForwardControl(t))


if __name__ == "__main__":
    system = System()