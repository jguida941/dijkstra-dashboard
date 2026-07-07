import pytest

from dijkstra_dashboard.core.algorithms import create_algorithm, list_algorithm_specs
from dijkstra_dashboard.core.algorithms.astar import AStarAlgorithm
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.errors import AlgorithmError
from dijkstra_dashboard.core.graph import Graph


@pytest.fixture
def positioned_graph():
    """Nodes on the x-axis: weights equal euclidean length except the A-C shortcut."""
    g = Graph()
    g.add_node("A", x=0, y=0)
    g.add_node("B", x=2, y=0)
    g.add_node("C", x=4, y=0)
    g.add_edge("A", "B", 2)
    g.add_edge("B", "C", 2)
    g.add_edge("A", "C", 10)
    return g


def test_astar_requires_target(sample_graph):
    algo = AStarAlgorithm()
    with pytest.raises(AlgorithmError):
        algo.solve(sample_graph, {"start": "A"})
    with pytest.raises(AlgorithmError):
        list(algo.iter_steps(sample_graph, {"start": "A"}))


def test_astar_degenerates_to_dijkstra_when_scale_zero(sample_graph):
    astar = AStarAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})
    dij = DijkstraAlgorithm().solve(sample_graph, {"start": "A", "target": "F"})

    # All nodes share position (0,0) -> heuristic scale 0 -> pure Dijkstra.
    assert astar.distances == dij.distances
    assert astar.path == dij.path

    steps = list(AStarAlgorithm().iter_steps(sample_graph, {"start": "A", "target": "F"}))
    assert (steps[-1].get("payload") or {}).get("heuristic_scale") == 0.0


def test_astar_optimal_on_positioned_graph(positioned_graph):
    astar = AStarAlgorithm().solve(positioned_graph, {"start": "A", "target": "C"})
    dij = DijkstraAlgorithm().solve(positioned_graph, {"start": "A", "target": "C"})

    assert astar.path == dij.path == ["A", "B", "C"]
    assert astar.distance == 4

    steps = list(AStarAlgorithm().iter_steps(positioned_graph, {"start": "A", "target": "C"}))
    assert (steps[-1].get("payload") or {}).get("heuristic_scale") == 1.0


def test_astar_visit_payloads_carry_h_and_f(positioned_graph):
    steps = list(AStarAlgorithm().iter_steps(positioned_graph, {"start": "A", "target": "C"}))
    visits = [s for s in steps if s["kind"] == "visit"]
    assert visits

    for s in visits:
        payload = s.get("payload") or {}
        assert "h" in payload and "f" in payload
        assert isinstance(payload["h"], float)
        assert isinstance(payload["f"], float)

    target_visits = [s for s in visits if s["node"] == "C"]
    assert target_visits
    assert target_visits[-1]["payload"]["h"] == 0.0  # h(target) == 0


def test_astar_line_map_and_registry(positioned_graph, sample_graph, disconnected_graph):
    cls = AStarAlgorithm
    all_steps = (
        list(cls().iter_steps(positioned_graph, {"start": "A", "target": "C"}))
        + list(cls().iter_steps(sample_graph, {"start": "A", "target": "F"}))
        + list(cls().iter_steps(disconnected_graph, {"start": "A", "target": "X"}))
    )

    seen = set()
    for s in all_steps:
        reason = (s.get("payload") or {}).get("reason")
        lines = cls.lines_for_step(s)
        assert lines, f"no lines for {(s['kind'], reason)}"
        assert all(0 <= i < len(cls.pseudocode) for i in lines)
        seen.add((s["kind"], reason))

    assert ("skip", "visited") in seen
    assert ("skip", "worse") in seen
    assert ("final", "target_found") in seen
    assert ("final", "unreachable") in seen

    algo = create_algorithm("astar")
    assert isinstance(algo, AStarAlgorithm)
    assert "astar" in {spec.name for spec in list_algorithm_specs()}


def test_astar_unknown_target_raises_algorithm_error(positioned_graph):
    # A missing target must surface as AlgorithmError (caught by the UI), not
    # a raw ValueError from the heuristic's position lookup.
    algo = AStarAlgorithm()
    with pytest.raises(AlgorithmError, match="Target node 'ZZZ' not found"):
        algo.solve(positioned_graph, {"start": "A", "target": "ZZZ"})
