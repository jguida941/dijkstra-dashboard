import pytest
from PyQt6.QtGui import QColor, QPalette

from dijkstra_dashboard.ui.controls_panel import ControlsPanel
from dijkstra_dashboard.ui.theme import current_theme


pytestmark = pytest.mark.ui


def test_set_algorithms_preserves_current_selection(qapp):
    panel = ControlsPanel()
    panel.set_algorithms([("dijkstra", "Dijkstra"), ("astar", "Astar")])
    panel.algorithm_combo.setCurrentIndex(1)
    assert panel.get_algorithm_name() == "astar"

    # Re-populate in a different order: selection (by key) must be preserved.
    panel.set_algorithms([("astar", "Astar"), ("dijkstra", "Dijkstra")])
    assert panel.get_algorithm_name() == "astar"


def test_set_timeline_enables_and_clear_timeline_disables(qapp):
    panel = ControlsPanel()
    assert not panel.timeline_slider.isEnabled()
    assert panel.position_label.text() == "0 / 0"

    panel.set_timeline(10)
    assert panel.timeline_slider.isEnabled()
    assert panel.timeline_slider.maximum() == 10
    assert panel.timeline_slider.value() == 0
    assert panel.position_label.text() == "0 / 10"

    panel.clear_timeline()
    assert not panel.timeline_slider.isEnabled()
    assert panel.timeline_slider.maximum() == 0
    assert panel.position_label.text() == "0 / 0"


def test_set_timeline_index_writes_without_emitting(qapp):
    panel = ControlsPanel()
    panel.set_timeline(10)

    emissions = []
    panel.timeline_slider.valueChanged.connect(emissions.append)
    panel.set_timeline_index(4)

    assert emissions == []  # blockSignals guard prevents the frame->slider->seek loop
    assert panel.timeline_slider.value() == 4
    assert panel.position_label.text() == "4 / 10"


def test_controls_panel_does_not_scale_top_bar_fonts(qapp):
    panel = ControlsPanel()
    base_selector = panel.algorithm_combo.font().pointSize()
    base_button = panel.run_button.font().pointSize()

    assert abs(base_selector - base_button) <= 1

    panel.refresh_theme(current_theme())

    assert panel.algorithm_combo.font().pointSize() == base_selector
    assert panel.run_button.font().pointSize() == base_button


def test_combo_popup_uses_theme_highlight(qapp):
    panel = ControlsPanel()
    theme = current_theme()
    panel.refresh_theme(theme)

    popup = panel.algorithm_combo.view()
    assert popup.palette().color(QPalette.ColorRole.Highlight).name() == QColor(theme.highlight).name()
    assert popup.palette().color(QPalette.ColorRole.HighlightedText).name() == QColor(theme.highlight_text).name()
    assert theme.highlight in popup.styleSheet()
