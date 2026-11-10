"""Smoke test of the Streamlit interface (headless): every page renders and a run completes."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_every_page_renders_before_and_after_a_run():
    app = AppTest.from_file(APP, default_timeout=120).run()
    assert not app.exception
    pages = app.sidebar.radio[0].options
    assert len(pages) == 9
    for page in pages:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
    app.session_state.config["simulation"]["duration_days"] = 2.0
    next(b for b in app.sidebar.button if b.label == "Run simulation").click().run()
    assert not app.exception
    assert app.session_state.result is not None
    for page in pages:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        assert not app.error, page


def test_scenario_comparison_page_runs_examples():
    app = AppTest.from_file(APP, default_timeout=180).run()
    app.session_state.config["simulation"]["duration_days"] = 1.0
    app.sidebar.radio[0].set_value("7. Scenario comparison").run()
    next(b for b in app.button if b.label.startswith("Add the six")).click().run()
    assert not app.exception
    assert len(app.session_state.compare) == 6
