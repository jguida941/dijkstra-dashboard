import pytest
from PyQt6.QtGui import QColor

from dijkstra_dashboard.ui.panels.narration_panel import NarrationPanel
from dijkstra_dashboard.ui.theme import ThemeManager, get_theme_manager


def _first_fragment_color(panel):
    block = panel.document().firstBlock()
    iterator = block.begin()
    fragment = iterator.fragment()
    return fragment.charFormat().foreground().color()


@pytest.mark.ui
def test_narration_log_replays_in_new_theme_colors(qapp):
    panel = NarrationPanel()
    panel.append_line("hello", "text")

    manager = get_theme_manager()
    manager.set_theme("paper-light", persist=False)
    panel.refresh_theme(manager.current)

    assert "hello" in panel.toPlainText()
    assert _first_fragment_color(panel) == QColor(ThemeManager.THEMES["paper-light"].text)


@pytest.mark.ui
def test_narration_clear_also_clears_replay_log(qapp):
    panel = NarrationPanel()
    panel.append_line("old line", "accent")
    panel.clear()

    panel.refresh_theme(get_theme_manager().current)

    assert panel.toPlainText().strip() == ""


@pytest.mark.ui
def test_consecutive_jump_markers_collapse_to_one(qapp):
    panel = NarrationPanel()
    panel.append_line("Visit A (d=0).", "accent")
    panel.append_jump_marker(3)
    panel.append_jump_marker(7)

    text = panel.toPlainText()
    assert text.count("jumped to step") == 1
    assert "jumped to step 7" in text
    assert "Visit A (d=0)." in text
