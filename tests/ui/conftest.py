import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def hermetic_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DIJKSTRA_DASHBOARD_CONFIG", str(tmp_path / "config.json"))


@pytest.fixture(autouse=True)
def reset_theme_state():
    try:
        from dijkstra_dashboard.ui import theme
    except ImportError:
        yield
        return

    theme._reset_theme_manager_for_tests()
    theme._reset_font_cache_for_tests()
    yield
    theme._reset_theme_manager_for_tests()
    theme._reset_font_cache_for_tests()
