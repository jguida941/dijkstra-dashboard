import pytest

from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.errors import AlgorithmError


def test_dijkstra_simple_path(sample_graph):
    algo = DijkstraAlgorithm()
    result = algo.solve(sample_graph, {"start": "A", "target": "F"})
    assert result.path == ['A', 'C', 'B', 'F']
    assert result.distance == 6


def test_dijkstra_unreachable_target(disconnected_graph):
    algo = DijkstraAlgorithm()
    result = algo.solve(disconnected_graph, {"start": "A", "target": "X"})
    assert result.path == []
    assert result.distance == float("inf")


def test_dijkstra_negative_weight_raises(negative_weight_graph):
    algo = DijkstraAlgorithm()
    with pytest.raises(AlgorithmError):
        algo.solve(negative_weight_graph, {"start": "A", "target": "C"})


def test_dijkstra_iter_steps_final(sample_graph):
    algo = DijkstraAlgorithm()
    steps = list(algo.iter_steps(sample_graph, {"start": "A", "target": "F"}))
    assert steps[-1]["kind"] == "final"
