import importlib

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from dijkstra_dashboard.core.algorithms import get_algorithm_class
from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.theme import ThemeManager, get_theme_manager


pytestmark = pytest.mark.ui


NODE_ORDER = ["A", "B", "C", "D", "E", "F"]


def _row(node_id):
    return NODE_ORDER.index(node_id)


def _select_algo(window, name):
    combo = window.controls_panel.algorithm_combo
    combo.setCurrentIndex(combo.findData(name))


def _load(window):
    assert window._load_run()


# --------------------------------------------------------------------------
def test_inspector_present_and_status_panel_gone(qapp):
    window = MainWindow()
    assert window.inspector is not None
    assert not hasattr(window, "status_panel")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("dijkstra_dashboard.ui.status_panel")
    window.close()


def test_startup_narration_help_is_scannable(qapp):
    window = MainWindow()
    lines = window.inspector.narration.toPlainText().strip().splitlines()

    assert lines == [
        "Add node: Shift+click empty space",
        "Add edge: Ctrl/Option/Shift+click two nodes",
        "Directed arrows: selection order sets direction",
        "Remove: select node/edge, press Delete",
        "Pan: right-drag",
    ]
    window.close()


def test_table_start_row_shows_zero_and_current(qapp):
    window = MainWindow()
    _load(window)
    window.playback.step_forward()  # k=1: visit A

    table = window.inspector.table
    assert table.item(_row("A"), 1).text() == "0"       # distance column
    assert table.item(_row("A"), 3).text() == "current"  # state column
    window.close()


def test_pseudocode_highlight_matches_lines_for_step(qapp):
    window = MainWindow()
    _load(window)
    frames = []
    window.playback.frame_changed.connect(frames.append)
    window.playback.step_forward()  # k=1: visit A

    expected = get_algorithm_class("dijkstra").lines_for_step(frames[-1].step)
    assert window.inspector.pseudocode._last_lines == expected
    assert expected  # sanity: a visit maps to real lines
    window.close()


def test_forward_step_flashes_changed_distance_but_seek_does_not(qapp):
    forward = MainWindow()
    _load(forward)
    forward.playback.step_forward()  # k=1: visit A
    forward.playback.step_forward()  # k=2: relax A->B (B: inf -> 5, B not current)
    flashed = forward.inspector.table.item(_row("B"), 1).background().color()
    assert flashed.alpha() > 0
    forward.close()

    scrub = MainWindow()
    _load(scrub)
    scrub.playback.seek(2)  # same distances, but a non-forward jump
    quiet = scrub.inspector.table.item(_row("B"), 1).background().color()
    assert quiet.alpha() == 0
    scrub.close()


def test_narration_accumulates_manual_steps_and_single_jump_marker(qapp):
    window = MainWindow()
    _load(window)
    for _ in range(3):  # visit A, relax A->B, relax A->C
        window.playback.step_forward()

    text = window.inspector.narration.toPlainText()
    assert "Visit A (d=0)." in text
    assert "Relax A→B" in text
    assert "Relax A→C" in text

    window.playback.seek(5)
    window.playback.seek(8)
    text = window.inspector.narration.toPlainText()
    assert text.count("jumped to step") == 1
    assert "jumped to step 8" in text
    window.close()


def test_run_to_end_summary_then_comparison_on_second_algorithm(qapp):
    window = MainWindow()
    _load(window)
    window.playback.seek(window.playback.total)

    text = window.inspector.narration.toPlainText()
    assert "Path: A → C → B → F (cost 6)" in text
    assert "Visits 5 · Relaxations 7 · Skips 6 · Comparisons 13" in text
    assert window.inspector.table.item(_row("D"), 3).text() == "searched, not in path"
    assert window.inspector.table.item(_row("E"), 3).text() == "searched, not in path"

    _select_algo(window, "bfs")
    _load(window)
    window.playback.seek(window.playback.total)

    lines = window.inspector.narration.toPlainText().splitlines()
    comparison = [ln for ln in lines if "|" in ln and "Dijkstra" in ln and "BFS" in ln]
    assert comparison, "expected a comparison line after the second algorithm run"
    window.close()


def test_right_arrow_keyclick_advances_frame(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    qapp.processEvents()
    _load(window)
    window.graph_view.setFocus()  # move focus off the (editable) combo
    qapp.processEvents()

    frames = []
    window.playback.frame_changed.connect(frames.append)
    qtbot.keyClick(window.graph_view, Qt.Key.Key_Right)

    assert frames, "Right arrow did not emit a frame"
    assert frames[-1].index == 1
    assert frames[-1].forward_step
    window.close()


def test_space_keyclick_toggles_play_state(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    qapp.processEvents()
    _load(window)
    window.graph_view.setFocus()
    qapp.processEvents()

    assert not window.playback.is_playing
    qtbot.keyClick(window.graph_view, Qt.Key.Key_Space)
    assert window.playback.is_playing
    qtbot.keyClick(window.graph_view, Qt.Key.Key_Space)
    assert not window.playback.is_playing
    window.playback.pause()
    window.close()


def test_space_ignored_when_editable_combo_focused(qapp, qtbot):
    # F11: a Space keypress while an editable combo holds focus must not toggle
    # (or load) playback — the shortcut handler bails on editable focus.
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    qapp.processEvents()

    window.controls_panel.start_combo.setFocus()
    qapp.processEvents()
    assert isinstance(QApplication.focusWidget(), type(window.controls_panel.start_combo))

    qtbot.keyClick(window.controls_panel.start_combo, Qt.Key.Key_Space)
    assert not window.playback.is_loaded
    assert not window.playback.is_playing
    window.close()


def test_badges_toggle_hides_node_badge(qapp):
    window = MainWindow()
    _load(window)
    window.playback.step_forward()  # A shows badge "0"

    node_a = window.graph_view.nodes["A"]
    assert node_a.badge.isVisible()

    window.show_labels_action.setChecked(False)
    assert not node_a.badge.isVisible()
    window.close()


def test_theme_switch_recolors_narration_without_crash(qapp):
    window = MainWindow()
    _load(window)
    window.playback.step_forward()

    get_theme_manager().set_theme("paper-light", persist=False)
    qapp.processEvents()

    narration = window.inspector.narration
    assert narration.toPlainText().strip() != ""
    block = narration.document().firstBlock()
    color = block.begin().fragment().charFormat().foreground().color()
    from PyQt6.QtGui import QColor
    assert color == QColor(ThemeManager.THEMES["paper-light"].accent)
    window.close()


def test_algorithm_switch_swaps_pseudocode_and_table_header(qapp):
    window = MainWindow()
    _load(window)  # dijkstra
    table = window.inspector.table
    assert table.horizontalHeaderItem(1).text() == "Distance"

    _select_algo(window, "bfs")
    _load(window)

    assert table.horizontalHeaderItem(1).text() == "Distance (hops)"
    pseudocode = window.inspector.pseudocode
    bfs_pseudo = get_algorithm_class("bfs").pseudocode
    assert pseudocode.count() == len(bfs_pseudo)
    assert pseudocode.item(0).text() == bfs_pseudo[0]
    window.close()


@pytest.mark.ui
def test_graph_change_clears_stale_table_rows(qapp):
    window = MainWindow()
    graph = window.graph_view.get_graph()
    node_ids = graph.get_nodes()
    assert window.playback.load_run(graph, "dijkstra",
                                    {"start": node_ids[0], "target": node_ids[-1]})
    window.playback.step_forward()
    assert window.inspector.table.rowCount() > 0

    from dijkstra_dashboard.core.graph import Graph
    fresh = Graph()
    fresh.add_node(node_id="X", label="X", x=0, y=0)
    fresh.add_node(node_id="Y", label="Y", x=50, y=0)
    fresh.add_edge("X", "Y", 1)
    window.graph_view.set_graph(fresh)
    qapp.processEvents()

    assert window.inspector.table.rowCount() == 0
    window.close()


@pytest.mark.ui
def test_inspector_fonts_scale_with_window(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    qapp.processEvents()

    node = window.graph_view.nodes["A"]
    edge = window.graph_view.edges[("A", "B")]
    base_narration = window.inspector.narration.font().pointSize()
    base_badge = node.badge.font().pointSize()
    base_edge_label = edge.label._font.pointSize()

    window.resize(1800, 950)
    qapp.processEvents()

    assert window.inspector.narration.font().pointSize() > base_narration
    assert node.badge.font().pointSize() > base_badge
    assert edge.label._font.pointSize() > base_edge_label
    assert window.inspector.table.font().pointSize() > 0
    window.close()
