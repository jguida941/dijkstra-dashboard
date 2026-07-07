import pytest
from PyQt6.QtGui import QColor

from dijkstra_dashboard.ui.graph_node import GraphNode
from dijkstra_dashboard.ui.theme import ThemeManager, current_theme, get_theme_manager


@pytest.mark.ui
def test_set_state_applies_theme_fill(qapp):
    node = GraphNode("A")

    node.set_state("visited")

    assert node.brush().color() == QColor(ThemeManager.THEMES["neon-dark"].node_styles["visited"].fill)


@pytest.mark.ui
def test_current_state_is_idempotent_and_does_not_restart_pulse(qapp, monkeypatch):
    node = GraphNode("A")
    calls = []

    class PulseSpy:
        def __init__(self):
            self.starts = 0
            self.stops = 0

        def start(self):
            self.starts += 1

        def stop(self):
            self.stops += 1

    pulse = PulseSpy()
    original_apply = node._apply_style

    def apply_spy(style):
        calls.append(style)
        original_apply(style)

    monkeypatch.setattr(node, "_apply_style", apply_spy)
    node.pulse_animation = pulse

    node.set_state("current")
    node.set_state("current")

    assert len(calls) == 1
    assert pulse.starts == 1


@pytest.mark.ui
def test_not_in_path_opacity_and_unused_alias(qapp):
    node = GraphNode("A")

    node.set_state("unused")

    assert node._state == "not_in_path"
    assert node.opacity() < 1.0


@pytest.mark.ui
def test_refresh_theme_preserves_state_and_reapplies_colors(qapp):
    node = GraphNode("A")
    node.set_state("visited")

    get_theme_manager().set_theme("midnight", persist=False)
    node.refresh_theme()

    assert node._state == "visited"
    assert node.brush().color() == QColor(current_theme().node_styles["visited"].fill)


@pytest.mark.ui
def test_distance_badge_text_visibility_and_master_toggle(qapp):
    node = GraphNode("A")

    node.set_distance_text("3")
    assert node.badge.isVisible()

    node.set_badge_visible(False)
    assert not node.badge.isVisible()

    node.set_badge_visible(True)
    assert node.badge.isVisible()

    node.set_distance_text(None)
    assert not node.badge.isVisible()


@pytest.mark.ui
def test_ring_flash_temporarily_overrides_and_restores_state_ring(qapp):
    node = GraphNode("A")
    node.set_state("frontier")
    state_ring = QColor(current_theme().node_style("frontier").ring)

    node.set_ring_flash(current_theme().warning)
    assert node.pen().color() == QColor(current_theme().warning)
    assert node.pen().widthF() > current_theme().node_style("frontier").ring_width

    node.set_ring_flash(None)
    assert node.pen().color() == state_ring


@pytest.mark.ui
def test_badge_flash_temporarily_overrides_and_restores_muted_color(qapp):
    node = GraphNode("A")
    node.set_distance_text("3")
    muted = QColor(current_theme().muted_text)

    node.set_badge_flash("#ffb020")
    assert node.badge.brush().color() == QColor("#ffb020")

    node.set_badge_flash(None)
    assert node.badge.brush().color() == muted
