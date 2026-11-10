import pytest

from config.parameters import default_config, with_overrides
from simulation.engine import run_simulation

FAST = {"simulation": {"duration_days": 3.0, "time_step_min": 10.0}}


@pytest.fixture
def config():
    return default_config()


@pytest.fixture
def fast_config():
    """Baseline shortened to 3 days for tests that do not need the full cycle."""
    return with_overrides(default_config(), FAST)


@pytest.fixture(scope="session")
def baseline_result():
    """Full 30-day baseline, run once per test session."""
    return run_simulation(default_config())
