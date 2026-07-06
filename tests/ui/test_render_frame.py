import pytest
from PyQt6.QtCore import Qt

from dijkstra_dashboard.ui.main_window import MainWindow


pytestmark = pytest.mark.ui


def _node_states(window):
    return {node_id: item._state for node_id, item in window.graph_view.nodes.items()}


def _edge_states(window):
    return {key: item._state for key, item in window.graph_view.edges.items()}


def _load(window, start="A", target="F", graph=None):
    graph = graph if graph is not None else window.graph_view.get_graph()
    assert window.playback.load_run(graph, "dijkstra", {"start": start, "target": target})


def test_first_step_marks_start_current_with_zero_badge(qapp):
    window = MainWindow()
    _load(window)
    window.playback.step_forward()  # k == 1: visit A

    node_a = window.graph_view.nodes["A"]
    assert node_a._state == "current"
    assert node_a._badge_text == "0"
    window.close()


def test_mid_run_settled_visited_and_frontier_finite_badge(qapp):
    window = MainWindow()
    _load(window)
    for _ in range(5):  # k == 5: visit C
        window.playback.step_forward()

    nodes = window.graph_view.nodes
    assert nodes["A"]._state == "visited"          # settled earlier
    assert nodes["C"]._state == "current"          # just visited
    assert nodes["B"]._state == "frontier"         # discovered, not settled
    assert nodes["B"]._badge_text == "5"           # finite distance badge
    assert nodes["E"]._state == "frontier"
    window.close()


def test_orientation_ghost_edge_stays_relaxed(qapp):
    # F1/F2: at k=6 the reverse-orientation skip (C,A) resolves to the SAME edge
    # item as the tree edge (A,C); item-level subtraction must keep it "relaxed".
    window = MainWindow()
    _load(window)
    for _ in range(6):  # k == 6: skip A via oriented tuple (C, A)
        window.playback.step_forward()

    edge_ac = window.graph_view._edge_item_for("A", "C")
    assert edge_ac._state == "relaxed"
    window.close()


def test_final_frame_highlights_path_nodes_and_edges(qapp):
    window = MainWindow()
    _load(window)
    window.playback.seek(window.playback.total)  # final frame

    nodes = window.graph_view.nodes
    for node_id in ("A", "C", "B", "F"):
        assert nodes[node_id]._state == "final"
    for node_id in ("D", "E"):
        assert nodes[node_id]._state == "not_in_path"

    assert window.graph_view._edge_item_for("A", "C")._state == "final"
    assert window.graph_view._edge_item_for("C", "B")._state == "final"
    assert window.graph_view._edge_item_for("B", "F")._state == "final"
    assert window.graph_view._edge_item_for("C", "D")._state == "not_in_path"
    window.close()


def test_unreachable_run_marks_target_and_dims_visited(qapp, disconnected_graph):
    window = MainWindow()
    window.graph_view.set_graph(disconnected_graph)
    _load(window, target="X", graph=disconnected_graph)
    window.playback.seek(window.playback.total)  # final frame, empty path

    nodes = window.graph_view.nodes
    assert nodes["X"]._state == "unreachable"
    assert nodes["A"]._state == "not_in_path"
    assert nodes["B"]._state == "not_in_path"
    window.close()


def test_view_scrub_equivalence_matches_fresh_forward(qapp):
    window = MainWindow()
    graph = window.graph_view.get_graph()

    _load(window)
    for _ in range(5):
        window.playback.step_forward()
    forward_nodes = _node_states(window)
    forward_edges = _edge_states(window)

    _load(window)
    window.playback.seek(5)
    assert _node_states(window) == forward_nodes
    assert _edge_states(window) == forward_edges
    window.close()


def test_render_frame_is_idempotent(qapp):
    window = MainWindow()
    frames = []
    window.playback.frame_changed.connect(frames.append)

    _load(window)
    for _ in range(5):
        window.playback.step_forward()

    before_nodes = _node_states(window)
    before_edges = _edge_states(window)

    window.graph_view.render_frame(frames[-1])  # re-render identical frame

    assert _node_states(window) == before_nodes
    assert _edge_states(window) == before_edges
    window.close()


def test_badges_visible_during_run_and_cleared(qapp):
    window = MainWindow()
    _load(window)
    window.playback.step_forward()

    node_a = window.graph_view.nodes["A"]
    assert node_a._badge_text == "0"
    assert node_a.badge.isVisible()

    window.graph_view.clear_run_decorations()
    assert node_a._badge_text is None
    assert not node_a.badge.isVisible()
    assert node_a._state == "default"
    window.close()


def test_timeline_slider_drag_drives_view(qapp):
    window = MainWindow()
    _load(window)

    window.controls_panel.timeline_slider.setValue(5)
    qapp.processEvents()

    assert window.controls_panel.position_label.text() == "5 / 19"
    assert window.graph_view.nodes["C"]._state == "current"
    window.close()


def test_run_button_end_to_end_reaches_finish(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.controls_panel.speed_slider.setValue(10)  # interval floored fast

    with qtbot.waitSignal(window.playback.run_finished, timeout=5000) as blocker:
        qtbot.mouseClick(window.controls_panel.run_button, Qt.MouseButton.LeftButton)

    assert blocker.args[0]["path"] == ("A", "C", "B", "F")
    assert window.status_panel.status_text.toPlainText() != ""
    window.close()
