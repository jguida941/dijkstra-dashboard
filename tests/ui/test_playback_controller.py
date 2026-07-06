import pytest

from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.ui.playback_controller import PlaybackController


pytestmark = pytest.mark.ui


def _capture(controller):
    events = {"loaded": [], "frames": [], "finished": [], "errors": [], "playing": []}
    controller.run_loaded.connect(events["loaded"].append)
    controller.frame_changed.connect(events["frames"].append)
    controller.run_finished.connect(events["finished"].append)
    controller.run_error.connect(events["errors"].append)
    controller.playing_changed.connect(events["playing"].append)
    return events


def _load(graph, start="A", target="F"):
    controller = PlaybackController()
    events = _capture(controller)
    assert controller.load_run(graph, "dijkstra", {"start": start, "target": target})
    return controller, events


def _frame_after_forward(graph, k, start="A", target="F"):
    controller, events = _load(graph, start, target)
    for _ in range(k):
        controller.step_forward()
    return events["frames"][-1]


def _assert_replay_equal(left, right):
    assert left.distances == right.distances
    assert left.prev == right.prev
    assert left.visited == right.visited
    assert left.current == right.current
    assert left.tree_edges == right.tree_edges
    assert left.considered_edges == right.considered_edges


def test_load_run_emits_meta_and_initial_frame(qapp, sample_graph):
    controller = PlaybackController()
    events = _capture(controller)
    expected_total = len(
        list(DijkstraAlgorithm().iter_steps(sample_graph, {"start": "A", "target": "F"}))
    )

    assert controller.load_run(sample_graph, "dijkstra", {"start": "A", "target": "F"})

    # F4: the original meta keys survive as a subset; load_run additively appends
    # "constraints" (and, for A*, an optional "heuristic_scale").
    assert len(events["loaded"]) == 1
    loaded = events["loaded"][0]
    original = {
        "algorithm": "dijkstra",
        "start": "A",
        "target": "F",
        "total": expected_total,
        "directed": False,
    }
    assert original.items() <= loaded.items()
    assert loaded["constraints"] == {"non_negative": True}
    assert "heuristic_scale" not in loaded
    frame = events["frames"][-1]
    assert frame.index == 0
    assert frame.total == expected_total
    assert frame.step is None
    assert frame.distances == {node: float("inf") for node in sample_graph.get_nodes()}
    assert frame.visited == ()
    assert frame.current is None
    assert frame.prev == {}
    assert frame.tree_edges == frozenset()
    assert frame.considered_edges == frozenset()
    assert frame.path == ()
    assert not frame.is_final
    assert not frame.forward_step


def test_step_forward_to_completion_emits_one_summary(qapp, sample_graph):
    controller, events = _load(sample_graph)

    for _ in range(controller.total):
        controller.step_forward()

    assert [frame.index for frame in events["frames"]] == list(range(controller.total + 1))
    assert len(events["finished"]) == 1
    assert not controller.is_playing

    summary = events["finished"][0]
    assert summary["path"] == ("A", "C", "B", "F")
    assert summary["distance"] == 6
    assert summary["visited_order"] == ("A", "C", "B", "D", "F")
    assert summary["visits"] == 5
    assert summary["relaxations"] == 7
    assert summary["skips"] == 6
    assert summary["comparisons"] == 13
    assert summary["error"] is None


def test_scrub_refold_matches_fresh_forward_frames(qapp, sample_graph):
    controller, events = _load(sample_graph)
    total = controller.total

    for k in {1, total // 2, total}:
        controller.seek(total)
        controller.seek(0)
        controller.seek(k)
        _assert_replay_equal(events["frames"][-1], _frame_after_forward(sample_graph, k))


def test_step_back_from_mid_matches_fresh_previous_frame(qapp, sample_graph):
    controller, events = _load(sample_graph)
    mid = controller.total // 2
    controller.seek(mid)

    controller.step_back()

    _assert_replay_equal(events["frames"][-1], _frame_after_forward(sample_graph, mid - 1))


def test_seek_total_finished_dedup_resets_after_leaving_final(qapp, sample_graph):
    controller, events = _load(sample_graph)

    controller.seek(controller.total)
    controller.seek(controller.total)
    assert len(events["finished"]) == 1

    controller.seek(controller.total - 1)
    controller.seek(controller.total)
    assert len(events["finished"]) == 2


def test_unreachable_target_loads_without_error(qapp, disconnected_graph):
    controller, events = _load(disconnected_graph, target="X")

    controller.seek(controller.total)

    assert events["frames"][-1].path == ()
    assert events["finished"][0]["path"] == ()
    assert events["errors"] == []


def test_negative_weights_reject_load_and_unload(qapp, negative_weight_graph):
    controller = PlaybackController()
    events = _capture(controller)

    assert not controller.load_run(negative_weight_graph, "dijkstra", {"start": "A", "target": "C"})

    assert events["errors"] == ["Dijkstra does not support negative weights."]
    assert not controller.is_loaded


def test_play_timer_runs_to_completion_and_pauses(qapp, qtbot, sample_graph):
    controller, events = _load(sample_graph)
    controller.set_interval(50)

    with qtbot.waitSignal(controller.run_finished, timeout=4000) as blocker:
        controller.play()

    assert blocker.args[0]["path"] == ("A", "C", "B", "F")
    assert events["playing"] == [True, False]
    assert not controller.is_playing


def test_start_equals_target_finishes_with_zero_distance(qapp, sample_graph):
    controller, events = _load(sample_graph, start="A", target="A")

    controller.seek(controller.total)

    assert events["frames"][-1].path == ("A",)
    assert events["finished"][0]["path"] == ("A",)
    assert events["finished"][0]["distance"] == 0.0
