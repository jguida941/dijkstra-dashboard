import pytest

from dijkstra_dashboard.ui.controls_panel import ControlsPanel


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


def test_selector_fonts_are_larger_and_scale(qapp):
    panel = ControlsPanel()
    base_selector = panel.algorithm_combo.font().pointSize()
    base_button = panel.run_button.font().pointSize()

    assert base_selector > base_button

    panel.set_font_scale(1.5)

    assert panel.algorithm_combo.font().pointSize() > base_selector
    assert panel.algorithm_combo.view().font().pointSize() == panel.algorithm_combo.font().pointSize()
