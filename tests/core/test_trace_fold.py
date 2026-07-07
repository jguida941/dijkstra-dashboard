import pytest

from dijkstra_dashboard.core.algorithms import runner
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.algorithms.runner import apply_step, apply_steps, init_state


GOLDEN_TRACE = [
    ("visit", "A", None, None),
    ("relax", "B", ("A", "B"), None),
    ("relax", "C", ("A", "C"), None),
    ("relax", "E", ("A", "E"), None),
    ("visit", "C", None, None),
    ("skip", "A", ("C", "A"), "visited"),
    ("relax", "B", ("C", "B"), None),
    ("relax", "D", ("C", "D"), None),
    ("relax", "E", ("C", "E"), None),
    ("visit", "B", None, None),
    ("skip", "A", ("B", "A"), "visited"),
    ("skip", "C", ("B", "C"), "visited"),
    ("relax", "F", ("B", "F"), None),
    ("visit", "D", None, None),
    ("skip", "C", ("D", "C"), "visited"),
    ("skip", "E", ("D", "E"), "worse"),
    ("skip", "F", ("D", "F"), "worse"),
    ("visit", "F", None, None),
    ("final", "F", None, "target_found"),
]


def _signature(step):
    return (
        step["kind"],
        step["node"],
        step["edge"],
        (step.get("payload") or {}).get("reason"),
    )


def _steps(graph, target="F", mode="delta"):
    return list(DijkstraAlgorithm().iter_steps(graph, {"start": "A", "target": target}, mode=mode))


def test_dijkstra_golden_step_trace(sample_graph):
    assert [_signature(step) for step in _steps(sample_graph)] == GOLDEN_TRACE


def test_skips_are_state_neutral_and_paths_match_solve(sample_graph):
    steps = _steps(sample_graph)
    fold = apply_steps(steps, sample_graph.get_nodes())
    result = DijkstraAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})

    assert fold.distances == result.distances
    assert runner.build_paths(fold.prev, "A", fold.distances) == result.paths


def test_result_from_steps_matches_solve_for_reachable_and_unreachable(
    sample_graph, disconnected_graph
):
    reachable_steps = _steps(sample_graph)
    reachable = runner.result_from_steps(
        reachable_steps, sample_graph.get_nodes(), "A", "F", "single_path"
    )
    assert reachable.path == ["A", "C", "B", "F"]
    assert reachable.distance == 6
    assert reachable.visited_order == ["A", "C", "B", "D", "F"]
    assert reachable.steps is None

    unreachable_steps = _steps(disconnected_graph, target="X")
    unreachable = runner.result_from_steps(
        unreachable_steps, disconnected_graph.get_nodes(), "A", "X", "single_path"
    )
    assert unreachable.path == []
    assert unreachable.distance == float("inf")


def test_start_distance_after_first_visit(sample_graph):
    fold = apply_steps(_steps(sample_graph)[:1], sample_graph.get_nodes())
    assert fold.distances["A"] == 0.0


def test_apply_steps_prefix_matches_incremental(sample_graph):
    steps = _steps(sample_graph)
    for k in range(len(steps) + 1):
        prefix_fold = apply_steps(steps[:k], sample_graph.get_nodes())
        incremental = init_state(sample_graph.get_nodes())
        for step in steps[:k]:
            apply_step(incremental, step)

        assert prefix_fold.distances == incremental.distances
        assert prefix_fold.prev == incremental.prev
        assert prefix_fold.visited == incremental.visited
        assert prefix_fold.current == incremental.current
        assert prefix_fold.touched_edges == incremental.touched_edges


def test_snapshot_visit_payloads_match_fold_prefix(sample_graph):
    steps = _steps(sample_graph, mode="snapshot")
    prefix = []
    for step in steps:
        prefix.append(step)
        if step["kind"] == "visit":
            fold = apply_steps(prefix, sample_graph.get_nodes())
            assert step["payload"]["distances"] == fold.distances


def test_visit_with_node_none_is_safe_noop():
    state = init_state(["A"])
    apply_step(
        state,
        {
            "kind": "visit",
            "node": None,
            "edge": None,
            "old_distance": None,
            "new_distance": 0.0,
            "payload": {"marker": True},
        },
    )

    assert state.distances == {"A": float("inf")}
    assert state.visited == []
    assert state.current is None
    assert state.payload == {"marker": True}
