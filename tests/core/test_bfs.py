import pytest

from dijkstra_dashboard.core.algorithms import create_algorithm, list_algorithm_specs
from dijkstra_dashboard.core.algorithms.bfs import BreadthFirstSearchAlgorithm
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.algorithms.runner import result_from_steps


def _steps(graph, start="A", target="F"):
    return list(
        BreadthFirstSearchAlgorithm().iter_steps(graph, {"start": start, "target": target})
    )


def test_bfs_fewest_hops_path(sample_graph):
    result = BreadthFirstSearchAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})
    assert result.path == ["A", "B", "F"]
    assert result.distance == 2


def test_bfs_contrasts_with_dijkstra_and_ignores_weights(sample_graph):
    bfs = BreadthFirstSearchAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})
    dij = DijkstraAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})

    # Dijkstra follows the cheap-by-weight route.
    assert dij.path == ["A", "C", "B", "F"]
    assert dij.distance == 6

    # BFS ignores weights: fewest hops, a genuinely different path.
    assert bfs.path == ["A", "B", "F"]
    assert bfs.path != dij.path
    assert bfs.distance == 2  # hop count, not a weight sum


def test_bfs_unreachable(disconnected_graph):
    result = BreadthFirstSearchAlgorithm().solve(disconnected_graph, {"start": "A", "target": "X"})
    assert result.path == []
    assert result.distance == float("inf")


def test_bfs_fold_matches_solve(sample_graph):
    steps = _steps(sample_graph)
    folded = result_from_steps(steps, sample_graph.get_nodes(), "A", "F", "single_path")
    solved = BreadthFirstSearchAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})

    assert folded.distances == solved.distances
    assert folded.path == solved.path
    assert folded.distance == solved.distance


def test_bfs_golden_kinds_prefix(sample_graph):
    steps = _steps(sample_graph)
    prefix = [(s["kind"], s["node"]) for s in steps[:5]]
    assert prefix == [
        ("visit", "A"),
        ("relax", "B"),
        ("relax", "C"),
        ("relax", "E"),
        ("visit", "B"),
    ]


def test_bfs_emits_no_worse_skips(sample_graph):
    steps = _steps(sample_graph)
    skip_reasons = {
        (s.get("payload") or {}).get("reason") for s in steps if s["kind"] == "skip"
    }
    assert skip_reasons == {"visited"}


def test_bfs_line_map_covers_emitted_steps(sample_graph, disconnected_graph):
    cls = BreadthFirstSearchAlgorithm
    all_steps = _steps(sample_graph, "A", "F") + _steps(disconnected_graph, "A", "X")

    seen = set()
    for s in all_steps:
        reason = (s.get("payload") or {}).get("reason")
        lines = cls.lines_for_step(s)
        assert lines, f"no lines for {(s['kind'], reason)}"
        assert all(0 <= i < len(cls.pseudocode) for i in lines)
        seen.add((s["kind"], reason))

    assert ("final", "target_found") in seen
    assert ("final", "unreachable") in seen


def test_bfs_registered():
    algo = create_algorithm("bfs")
    assert isinstance(algo, BreadthFirstSearchAlgorithm)
    assert "bfs" in {spec.name for spec in list_algorithm_specs()}
