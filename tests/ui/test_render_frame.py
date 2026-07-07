import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.theme import get_theme_manager


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


def test_relax_impact_flash_lands_only_near_destination(qapp, monkeypatch):
    get_theme_manager().set_theme("neon-dark", persist=False)
    window = MainWindow()
    captured = {}

    monkeypatch.setattr(window.graph_view.animator, "lightning", lambda *args, **kwargs: None)
    monkeypatch.setattr(window.graph_view.animator, "travel_dot", lambda *args, **kwargs: None)

    def fake_animate_color(key, duration, apply_fn):
        captured[key] = apply_fn
        apply_fn(0.0)

    monkeypatch.setattr(window.graph_view.animator, "animate_color", fake_animate_color)

    _load(window)
    window.playback.step_forward()  # visit A
    window.playback.step_forward()  # relax A -> B

    node_b = window.graph_view.nodes["B"]
    state_ring = QColor(node_b._style.ring)
    muted_badge = QColor(node_b.badge.brush().color())
    ring_flash = next(fn for key, fn in captured.items() if key[0] == "node-ring-flash")
    badge_flash = next(fn for key, fn in captured.items() if key[0] == "node-badge-flash")

    ring_flash(0.5)
    badge_flash(0.5)
    assert node_b.pen().color() == state_ring
    assert node_b.badge.brush().color() == muted_badge

    ring_flash(0.9)
    badge_flash(0.9)
    assert node_b.pen().color() == QColor("#ffb020")
    assert node_b.badge.brush().color() == QColor("#ffb020")

    ring_flash(1.0)
    badge_flash(1.0)
    assert node_b.pen().color() == state_ring
    assert node_b.badge.brush().color() == muted_badge
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
    for edge_key, edge_item in window.graph_view.edges.items():
        if edge_key not in {("A", "C"), ("B", "C"), ("B", "F")}:
            assert edge_item._state == "considered"
    window.close()


def test_final_frame_keeps_untouched_subgraph_dark(qapp):
    from dijkstra_dashboard.core.graph import Graph

    graph = Graph()
    graph.add_node("A", x=0, y=0)
    graph.add_node("B", x=80, y=0)
    graph.add_node("X", x=0, y=80)
    graph.add_node("Y", x=80, y=80)
    graph.add_edge("A", "B", 1)
    graph.add_edge("X", "Y", 1)

    window = MainWindow()
    window.graph_view.set_graph(graph)
    _load(window, start="A", target="B", graph=graph)
    window.playback.seek(window.playback.total)

    assert window.graph_view._edge_item_for("A", "B")._state == "final"
    assert window.graph_view._edge_item_for("X", "Y")._state == "default"
    assert window.graph_view.nodes["X"]._state == "default"
    assert window.graph_view.nodes["Y"]._state == "default"
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
    assert window.inspector.narration.toPlainText() != ""
    window.close()


# ---------------------------------------------------------------------------
# Phase 3 — animation layer integration (additive emphasis over instant states)
# ---------------------------------------------------------------------------
def test_forward_visit_registers_pop_and_lands_current(qapp, qtbot):
    window = MainWindow()
    window.graph_view.set_tween_interval(60)  # tiny tweens
    _load(window)

    window.playback.step_forward()  # visit A -> current + pop emphasis

    assert len(window.graph_view.animator._registry) == 1  # a pop is pending

    qtbot.waitUntil(lambda: not window.graph_view.animator._registry, timeout=2000)

    node_a = window.graph_view.nodes["A"]
    assert node_a._state == "current"          # state snapped instantly
    assert node_a.scale() == pytest.approx(1.0)  # pop finalized back to 1.0
    window.close()


def test_forward_steps_land_exact_states_and_clean_scene(qapp, qtbot):
    window = MainWindow()
    window.graph_view.set_tween_interval(60)
    _load(window)

    scene = window.graph_view.scene
    baseline_items = len(scene.items())

    for _ in range(5):  # visits + relaxes: pops and travel dots fire
        window.playback.step_forward()

    qtbot.waitUntil(lambda: not window.graph_view.animator._registry, timeout=3000)

    nodes = window.graph_view.nodes
    assert nodes["A"]._state == "visited"
    assert nodes["C"]._state == "current"
    assert nodes["B"]._state == "frontier"
    assert all(node.scale() == pytest.approx(1.0) for node in nodes.values())
    assert len(scene.items()) == baseline_items  # travel dots removed on finish
    window.close()


def test_forward_into_final_staggers_then_lands_final_states(qapp, qtbot):
    window = MainWindow()
    window.graph_view.set_tween_interval(60)
    _load(window)

    for _ in range(window.playback.total):  # drive to the final frame (forward)
        window.playback.step_forward()

    qtbot.waitUntil(lambda: not window.graph_view.animator._registry, timeout=4000)

    nodes = window.graph_view.nodes
    for node_id in ("A", "C", "B", "F"):
        assert nodes[node_id]._state == "final"
    for node_id in ("D", "E"):
        assert nodes[node_id]._state == "not_in_path"
    assert window.graph_view._edge_item_for("A", "C")._state == "final"
    assert window.graph_view._edge_item_for("B", "F")._state == "final"
    window.close()


def test_scrub_renders_instant_states_with_no_pending_animation(qapp):
    window = MainWindow()
    window.graph_view.set_tween_interval(60)
    _load(window)

    window.playback.seek(5)  # forward_step=False -> cancel_all + instant pass

    nodes = window.graph_view.nodes
    assert nodes["A"]._state == "visited"
    assert nodes["C"]._state == "current"
    assert nodes["B"]._state == "frontier"
    assert len(window.graph_view.animator._registry) == 0  # scrub queues nothing
    window.close()


def test_bellman_ford_first_edge_free_relax_no_crash(qapp, qtbot):
    # F1: bellman-ford seeds the source with an edge=None relax; travel_dot must
    # NOT fire for it and the forward step must not crash with animations enabled.
    window = MainWindow()
    window.graph_view.set_tween_interval(60)
    graph = window.graph_view.get_graph()
    assert window.playback.load_run(graph, "bellman-ford", {"start": "A", "target": "F"})

    window.playback.step_forward()  # first step: edge-free relax of the source
    qtbot.wait(150)

    node_a = window.graph_view.nodes["A"]
    assert node_a._badge_text == "0"     # source distance seeded, state pass ran
    window.close()
