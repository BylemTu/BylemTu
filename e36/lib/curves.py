"""Small curve helpers (monotone cubic / PCHIP) used to describe the E36 profile."""
import numpy as np


class Curve:
    """Monotone piecewise-cubic interpolation through (x, y) control points.

    Values outside the control range are clamped to the end values.
    """

    def __init__(self, pts):
        p = np.asarray(sorted(pts), float)
        self.x, self.y = p[:, 0], p[:, 1]
        h = np.diff(self.x)
        d = np.diff(self.y) / h
        n = len(self.x)
        m = np.zeros(n)
        if n == 2:
            m[:] = d[0]
        else:
            for k in range(1, n - 1):
                if d[k - 1] * d[k] <= 0:
                    m[k] = 0.0
                else:
                    w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
                    m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
            m[0], m[-1] = d[0], d[-1]
        self.m, self.h = m, h

    def __call__(self, x):
        scalar = np.isscalar(x)
        x = np.clip(np.asarray(x, float), self.x[0], self.x[-1])
        k = np.clip(np.searchsorted(self.x, x) - 1, 0, len(self.x) - 2)
        h = self.h[k]
        t = (x - self.x[k]) / h
        t2, t3 = t * t, t * t * t
        y = ((2 * t3 - 3 * t2 + 1) * self.y[k] + (t3 - 2 * t2 + t) * h * self.m[k]
             + (-2 * t3 + 3 * t2) * self.y[k + 1] + (t3 - t2) * h * self.m[k + 1])
        return float(y) if scalar else y


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t
