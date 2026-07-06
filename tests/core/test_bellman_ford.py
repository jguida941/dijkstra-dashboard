import pytest

from dijkstra_dashboard.core.algorithms import create_algorithm, list_algorithm_specs
from dijkstra_dashboard.core.algorithms.bellman_ford import BellmanFordAlgorithm
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.errors import AlgorithmError
from dijkstra_dashboard.core.graph import Graph


@pytest.fixture
def directed_bf_graph():
    g = Graph(directed=True)
    for name in ["A", "B", "C"]:
        g.add_node(name)
    g.add_edge("A", "B", 4)
    g.add_edge("B", "C", -2)
    g.add_edge("A", "C", 5)
    return g


@pytest.fixture
def negative_cycle_graph():
    g = Graph(directed=True)
    for name in ["A", "B"]:
        g.add_node(name)
    g.add_edge("A", "B", 1)
    g.add_edge("B", "A", -3)
    return g


def test_bf_directed_negative_edge_ok(directed_bf_graph):
    result = BellmanFordAlgorithm().solve(directed_bf_graph, {"start": "A", "target": "C"})
    assert result.distance == 2
    assert result.path == ["A", "B", "C"]
    assert result.distances["C"] == 2


def test_bf_directed_negative_cycle_raises_but_iter_completes(negative_cycle_graph):
    algo = BellmanFordAlgorithm()

    with pytest.raises(AlgorithmError):
        algo.solve(negative_cycle_graph, {"start": "A", "target": "B"})

    # iter_steps stays fully replayable: it completes and the last step flags the cycle.
    steps = list(algo.iter_steps(negative_cycle_graph, {"start": "A", "target": "B"}))
    assert steps[-1]["kind"] == "final"
    assert (steps[-1].get("payload") or {}).get("negative_cycle") is True


def test_bf_undirected_negative_edge_is_negative_cycle(negative_weight_graph):
    algo = BellmanFordAlgorithm()

    with pytest.raises(AlgorithmError):
        algo.solve(negative_weight_graph, {"start": "A", "target": "C"})

    # Negative cycle is a run-level outcome, still surfaced when target is None.
    steps = list(algo.iter_steps(negative_weight_graph, {"start": "A"}))
    assert (steps[-1].get("payload") or {}).get("negative_cycle") is True


def test_bf_early_convergence_matches_dijkstra(sample_graph):
    algo = BellmanFordAlgorithm()
    steps = list(algo.iter_steps(sample_graph, {"start": "A", "target": "F"}))
    result = algo.solve(sample_graph, {"start": "A", "target": "F"})
    dij = DijkstraAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})

    assert result.distances == dij.distances
    final = steps[-1]
    assert final["kind"] == "final"
    assert "converged_at_pass" in (final.get("payload") or {})


def test_bf_pass_markers_have_none_node_and_empty_visited(sample_graph):
    algo = BellmanFordAlgorithm()
    result = algo.solve(sample_graph, {"start": "A", "target": "F"})

    # Pass markers carry node=None, so the fold's visited list stays empty for BF.
    assert result.visited_order == []

    steps = list(algo.iter_steps(sample_graph, {"start": "A", "target": "F"}))
    pass_markers = [s for s in steps if s["kind"] == "visit"]
    assert pass_markers
    assert all(s["node"] is None for s in pass_markers)
    assert all("pass" in (s.get("payload") or {}) for s in pass_markers)


def test_bf_line_map_and_registry(sample_graph, negative_cycle_graph, disconnected_graph):
    cls = BellmanFordAlgorithm
    all_steps = (
        list(cls().iter_steps(sample_graph, {"start": "A", "target": "F"}))
        + list(cls().iter_steps(negative_cycle_graph, {"start": "A", "target": "B"}))
        + list(cls().iter_steps(disconnected_graph, {"start": "A", "target": "X"}))
    )

    seen = set()
    for s in all_steps:
        reason = (s.get("payload") or {}).get("reason")
        lines = cls.lines_for_step(s)
        assert lines, f"no lines for {(s['kind'], reason)}"
        assert all(0 <= i < len(cls.pseudocode) for i in lines)
        seen.add((s["kind"], reason))

    assert ("visit", None) in seen
    assert ("final", "target_found") in seen
    assert ("final", "unreachable") in seen
    assert ("final", None) in seen  # negative-cycle final

    algo = create_algorithm("bellman-ford")
    assert isinstance(algo, BellmanFordAlgorithm)
    assert "bellman-ford" in {spec.name for spec in list_algorithm_specs()}
