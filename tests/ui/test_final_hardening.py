"""Regressions pinned from the final adversarial pass: cross-feature
interactions between animated layouts, graph replacement, undo, and export."""

import pytest

from dijkstra_dashboard.core.graph import Graph
from dijkstra_dashboard.ui.export import export_scene_svg
from dijkstra_dashboard.ui.main_window import MainWindow


def _small_graph(ids):
    g = Graph()
    for i, n in enumerate(ids):
        g.add_node(node_id=n, label=n, x=float(i * 60), y=0.0)
    g.add_edge(ids[0], ids[1], 1)
    return g


@pytest.mark.ui
def test_set_graph_during_animated_layout_does_not_crash(qapp):
    window = MainWindow()
    gv = window.graph_view
    ids = gv.get_graph().get_nodes()
    targets = {n: (100.0 + i * 40, 120.0) for i, n in enumerate(ids)}
    gv.apply_layout(targets, animate=True, duration=400)

    gv.set_graph(_small_graph(["X", "Y"]))
    qapp.processEvents()

    assert set(gv.nodes) == {"X", "Y"}
    window.close()


@pytest.mark.ui
def test_cancelled_layout_still_commits_and_invalidates(qapp):
    window = MainWindow()
    gv = window.graph_view
    graph = gv.get_graph()
    ids = graph.get_nodes()
    assert window.playback.load_run(graph, "dijkstra", {"start": ids[0], "target": ids[-1]})
    window.undo_stack.clear()

    targets = {n: (float(i * 50), 200.0) for i, n in enumerate(ids)}
    gv.apply_layout(targets, animate=True, duration=500)
    gv.animator.cancel_all()  # what a theme switch / scrub does mid-layout
    qapp.processEvents()

    assert not window.playback.is_loaded, "layout completion must invalidate the run"
    assert window.undo_stack.count() == 1, "cancelled layout must still be undoable"
    assert graph.get_node_position(ids[0]) == targets[ids[0]]
    window.close()


@pytest.mark.ui
def test_svg_export_reports_failure_on_bad_path(qapp):
    window = MainWindow()
    assert export_scene_svg(window.graph_view.scene, "/tmp/no-such-dir-ddash-final/out.svg") is False
    window.close()
