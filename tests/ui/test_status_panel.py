import pytest
from PyQt6.QtGui import QColor

from dijkstra_dashboard.ui.status_panel import StatusPanel
from dijkstra_dashboard.ui.theme import ThemeManager, get_theme_manager


def _first_fragment_color(panel):
    block = panel.status_text.document().firstBlock()
    iterator = block.begin()
    fragment = iterator.fragment()
    return fragment.charFormat().foreground().color()


@pytest.mark.ui
def test_status_log_replays_in_new_theme_colors(qapp):
    panel = StatusPanel()
    panel.update_status("hello", "text")

    manager = get_theme_manager()
    manager.set_theme("paper-light", persist=False)
    panel.refresh_theme(manager.current)

    assert "hello" in panel.status_text.toPlainText()
    assert _first_fragment_color(panel) == QColor(ThemeManager.THEMES["paper-light"].text)


@pytest.mark.ui
def test_status_clear_also_clears_replay_log(qapp):
    panel = StatusPanel()
    panel.update_status("old line", "accent")
    panel.clear()

    panel.refresh_theme(get_theme_manager().current)

    assert panel.status_text.toPlainText().strip() == ""
