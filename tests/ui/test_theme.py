import json

import pytest
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtTest import QSignalSpy

import dijkstra_dashboard.ui.theme as theme
from dijkstra_dashboard.ui.theme import (
    EDGE_STATES,
    NODE_STATES,
    ThemeManager,
    lerp_color,
    parse_qss_theme_overrides,
    theme_from_dict,
    theme_to_dict,
)


@pytest.mark.ui
def test_three_themes_registered_with_default_neon_dark():
    manager = ThemeManager()

    assert set(manager.theme_ids()) == {"neon-dark", "midnight", "paper-light"}
    assert manager.current.id == "neon-dark"


@pytest.mark.ui
def test_every_theme_has_all_node_and_edge_states():
    manager = ThemeManager()

    for theme_id in manager.theme_ids():
        registered = ThemeManager.THEMES[theme_id]
        assert set(registered.node_styles) == set(NODE_STATES)
        assert set(registered.edge_styles) == set(EDGE_STATES)


@pytest.mark.ui
def test_style_alias_resolution_and_unknown_fallback():
    registered = ThemeManager.THEMES["neon-dark"]

    assert registered.node_style("unused") == registered.node_styles["not_in_path"]
    assert registered.node_style("idle") == registered.node_styles["default"]
    assert registered.edge_style("visited") == registered.edge_styles["relaxed"]
    assert registered.node_style("zzz") == registered.node_styles["default"]
    assert registered.edge_style("zzz") == registered.edge_styles["default"]


@pytest.mark.ui
def test_not_in_path_opacity_is_dimmed_in_all_themes():
    manager = ThemeManager()

    for theme_id in manager.theme_ids():
        registered = ThemeManager.THEMES[theme_id]
        assert registered.node_styles["not_in_path"].opacity < 1.0
        assert registered.edge_styles["not_in_path"].opacity < 1.0


@pytest.mark.ui
def test_neon_final_labels_match_path_cyan_and_non_path_labels_are_gray():
    neon = ThemeManager.THEMES["neon-dark"]

    assert neon.edge_styles["final"].label_fg == neon.edge_styles["final"].stroke
    assert neon.edge_styles["not_in_path"].label_fg == "#929ba8"
    assert neon.node_styles["not_in_path"].ring == "#46505f"


@pytest.mark.ui
def test_builtin_frontier_settled_and_final_colors_are_distinct():
    for registered in ThemeManager.THEMES.values():
        frontier = QColor(registered.node_styles["frontier"].ring)
        settled = QColor(registered.node_styles["visited"].ring)
        final = QColor(registered.node_styles["final"].ring)

        assert frontier != final
        assert settled != final
        assert registered.edge_styles["relaxed"].stroke != registered.edge_styles["final"].stroke


@pytest.mark.ui
def test_all_themes_use_final_label_as_the_route_color():
    for registered in ThemeManager.THEMES.values():
        assert registered.edge_styles["final"].label_fg == registered.edge_styles["final"].stroke
        assert registered.edge_styles["not_in_path"].opacity < registered.edge_styles["final"].opacity


@pytest.mark.ui
def test_custom_qss_round_trips_and_appends_to_stylesheet():
    data = theme_to_dict(ThemeManager.THEMES["neon-dark"])
    data["id"] = "qss-layer"
    data["name"] = "QSS Layer"
    data["custom_qss"] = "QLabel#special { color: #abcdef; }"

    imported = theme_from_dict(data)

    assert imported.custom_qss == "QLabel#special { color: #abcdef; }"
    assert "/* Custom QSS */" in imported.qss()
    assert "QLabel#special { color: #abcdef; }" in imported.qss()
    assert theme_to_dict(imported)["custom_qss"] == data["custom_qss"]


@pytest.mark.ui
def test_parse_qss_theme_overrides_extracts_chrome_and_metrics():
    qss = """
    QMainWindow { background-color: #101010; color: #eeeeee; }
    QPushButton {
        background-color: #202020;
        border: 2px solid #404040;
        border-radius: 9px;
        padding: 7px;
        min-height: 34px;
    }
    QLineEdit {
        background-color: #303030;
        color: #aaaaaa;
        selection-background-color: #ff00aa;
        selection-color: #000000;
    }
    """

    parsed = parse_qss_theme_overrides(qss)

    assert parsed["theme"]["custom_qss"] == qss.strip()
    assert parsed["theme"]["base_bg"] == "#101010"
    assert parsed["theme"]["panel_bg"] == "#202020"
    assert parsed["theme"]["window_bg"] == "#303030"
    assert parsed["theme"]["text"] == "#eeeeee"
    assert parsed["theme"]["muted_text"] == "#aaaaaa"
    assert parsed["theme"]["button_border"] == "#404040"
    assert parsed["theme"]["highlight"] == "#ff00aa"
    assert parsed["app_style"]["border_radius"] == 9
    assert parsed["app_style"]["border_width"] == 2
    assert parsed["app_style"]["padding_x"] == 7
    assert parsed["app_style"]["control_min_height"] == 34


@pytest.mark.ui
def test_lerp_color_endpoints_and_midpoint_channels_include_alpha():
    start = QColor(0, 10, 20, 30)
    end = QColor(100, 110, 120, 130)

    assert lerp_color(start, end, 0).getRgb() == start.getRgb()
    assert lerp_color(start, end, 1).getRgb() == end.getRgb()
    assert lerp_color(start, end, 0.5).getRgb() == (50, 60, 70, 80)


@pytest.mark.ui
def test_qss_is_scoped_and_includes_expected_widgets():
    manager = ThemeManager()

    for theme_id in manager.theme_ids():
        qss = ThemeManager.THEMES[theme_id].qss()
        assert qss
        assert "#statusText" in qss
        assert "QPushButton" in qss
        assert "QWidget {" not in qss


@pytest.mark.ui
def test_palette_window_color_matches_theme_window_bg():
    manager = ThemeManager()

    for theme_id in manager.theme_ids():
        registered = ThemeManager.THEMES[theme_id]
        assert registered.palette().color(QPalette.ColorRole.Window) == QColor(registered.window_bg)


@pytest.mark.ui
def test_theme_manager_set_theme_emits_once_and_ignores_noops(qapp):
    manager = ThemeManager()
    spy = QSignalSpy(manager.theme_changed)

    manager.set_theme("midnight")

    assert len(spy) == 1
    assert manager.current.id == "midnight"

    manager.set_theme("midnight")
    assert len(spy) == 1

    manager.set_theme("nope")
    assert len(spy) == 1
    assert manager.current.id == "midnight"


@pytest.mark.ui
def test_load_from_config_maps_legacy_cyberpunk_alias(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"theme": "cyberpunk"}), encoding="utf-8")
    monkeypatch.setenv("DIJKSTRA_DASHBOARD_CONFIG", str(config_path))
    manager = ThemeManager()

    manager.load_from_config()

    assert manager.current.id == "neon-dark"


@pytest.mark.ui
def test_persistence_round_trip_loads_saved_theme():
    manager = ThemeManager()
    manager.set_theme("paper-light")
    reloaded = ThemeManager()

    reloaded.load_from_config()

    assert reloaded.current.id == "paper-light"


@pytest.mark.ui
def test_corrupt_config_file_falls_back_to_default(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{", encoding="utf-8")
    monkeypatch.setenv("DIJKSTRA_DASHBOARD_CONFIG", str(config_path))
    manager = ThemeManager()

    manager.load_from_config()

    assert manager.current.id == "neon-dark"


@pytest.mark.ui
def test_env_theme_override_survives_corrupt_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{", encoding="utf-8")
    monkeypatch.setenv("DIJKSTRA_DASHBOARD_CONFIG", str(config_path))
    monkeypatch.setenv("DIJKSTRA_DASHBOARD_THEME", "paper-light")
    manager = ThemeManager()

    manager.load_from_config()

    assert manager.current.id == "paper-light"


@pytest.mark.ui
def test_display_font_returns_requested_point_size(qapp):
    font = ThemeManager.THEMES["neon-dark"].display_font(13, QFont.Weight.Bold)

    assert font.pointSize() == 13
    assert isinstance(font.family(), str)
