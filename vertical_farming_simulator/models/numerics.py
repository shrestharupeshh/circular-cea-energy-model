"""Numerical integration helper shared by the thermal and moisture balances.

Both balances have the form  dx/dt = a - k*x  once the inputs are held
constant over one time step. That equation has an exact solution, so the
step is integrated exactly instead of with explicit Euler:

    x(t+dt) = x_ss + (x - x_ss) * exp(-k*dt),   x_ss = a / k

This is unconditionally stable (no time-step limit from fast controllers or
high air-change rates) and its only error comes from holding the inputs
constant within the step.
"""

from __future__ import annotations

import math


def response_factor(k: float, dt: float) -> float:
    """phi = (1 - exp(-k*dt)) / k  [s]; tends to dt as k -> 0.

    A constant extra source q (in x-units per second) applied over the step
    changes x(t+dt) by q * phi.
    """
    if k * dt < 1e-9:
        return dt
    return -math.expm1(-k * dt) / k


def linear_step(x: float, a: float, k: float, dt: float) -> tuple[float, float]:
    """Advance dx/dt = a - k*x by dt exactly.

    Returns (x_next, x_mean) where x_mean is the time-average of x over the
    step. The mean is what makes the per-step balances close exactly:
    (x_next - x)/dt = a - k*x_mean.
    """
    phi = response_factor(k, dt)
    x_next = x + (a - k * x) * phi
    if k * dt < 1e-9:
        x_mean = x + 0.5 * a * dt
    else:
        x_mean = (a - (x_next - x) / dt) / k
    return x_next, x_mean
