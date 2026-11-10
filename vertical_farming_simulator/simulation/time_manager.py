"""Central simulation clock. Every model uses this one time convention.

Time is stored in seconds from t = 0, which is 00:00 on day 1. The run is
divided into n equal steps; step i covers [t_start[i], t_start[i] + dt).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.constants import SECONDS_PER_DAY, SECONDS_PER_HOUR


@dataclass(frozen=True)
class TimeGrid:
    dt_s: float
    n_steps: int

    @classmethod
    def from_config(cls, simulation: dict) -> "TimeGrid":
        dt_s = float(simulation["time_step_min"]) * 60.0
        n_steps = int(round(float(simulation["duration_days"]) * SECONDS_PER_DAY / dt_s))
        if n_steps < 1:
            raise ValueError("Simulation needs at least one time step.")
        return cls(dt_s=dt_s, n_steps=n_steps)

    @property
    def t_start_s(self) -> np.ndarray:
        return np.arange(self.n_steps) * self.dt_s

    @property
    def t_mid_s(self) -> np.ndarray:
        return self.t_start_s + 0.5 * self.dt_s

    @property
    def duration_s(self) -> float:
        return self.n_steps * self.dt_s

    @property
    def duration_days(self) -> float:
        return self.duration_s / SECONDS_PER_DAY

    @property
    def dt_h(self) -> float:
        return self.dt_s / SECONDS_PER_HOUR
