"""Tests for core.samples (default demo graph) and core.generate (seeded random graphs)."""

import math

import pytest

from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.generate import random_graph
from dijkstra_dashboard.core.graph import Graph
from dijkstra_dashboard.core.samples import default_demo_graph

DEMO_RADIUS = 210.0  # 35% of the nominal 600px minimum view dimension


def _reachable_from(graph, start):
    """Tiny BFS reachability helper over Graph.get_neighbors."""
    seen = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop(0)
        for neighbor, _weight in graph.get_neighbors(current):
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append(neighbor)
    return seen


# ---------------------------------------------------------------------------
# default_demo_graph
# ---------------------------------------------------------------------------

class TestDefaultDemoGraph:
    def test_node_and_edge_counts(self):
        g = default_demo_graph()
        assert sorted(g.get_nodes()) == ['A', 'B', 'C', 'D', 'E', 'F']
        assert len(g.get_nodes()) == 6
        assert len(g.get_edges()) == 9
        assert g.directed is False

    def test_known_edge_weight(self):
        g = default_demo_graph()
        weights = {frozenset((s, e)): w for s, e, w in g.get_edges()}
        assert weights[frozenset(('A', 'B'))] == 5

    def test_positions_nonzero_on_demo_radius(self):
        g = default_demo_graph()
        for node_id in g.get_nodes():
            x, y = g.get_node_position(node_id)
            assert (x, y) != (0.0, 0.0)
            assert math.hypot(x, y) == pytest.approx(DEMO_RADIUS)

    def test_deterministic_across_calls(self):
        assert default_demo_graph().to_dict() == default_demo_graph().to_dict()


# ---------------------------------------------------------------------------
# random_graph
# ---------------------------------------------------------------------------

class TestRandomGraph:
    def test_same_seed_is_identical(self):
        a = random_graph(10, 0.4, seed=42)
        b = random_graph(10, 0.4, seed=42)
        assert a.to_dict() == b.to_dict()

    def test_different_seeds_differ(self):
        a = random_graph(12, 0.3, seed=1)
        b = random_graph(12, 0.3, seed=2)
        assert a.to_dict() != b.to_dict()

    def test_connected_graph_is_fully_reachable(self):
        g = random_graph(15, 0.2, seed=7, connected=True)
        first = g.get_nodes()[0]
        assert _reachable_from(g, first) == set(g.get_nodes())

    @pytest.mark.parametrize("node_count", [1, 51])
    def test_node_count_validation(self, node_count):
        with pytest.raises(ValueError):
            random_graph(node_count, 0.5, seed=0)

    @pytest.mark.parametrize("edge_density", [-0.1, 1.1])
    def test_edge_density_validation(self, edge_density):
        with pytest.raises(ValueError):
            random_graph(5, edge_density, seed=0)

    @pytest.mark.parametrize("weight_range", [(5, 2), (0, 9)])
    def test_weight_range_validation(self, weight_range):
        with pytest.raises(ValueError):
            random_graph(5, 0.5, weight_range=weight_range, seed=0)

    def test_weights_are_integers_within_range(self):
        g = random_graph(10, 0.6, weight_range=(3, 7), seed=99)
        for _start, _end, weight in g.get_edges():
            assert float(weight).is_integer()
            assert 3 <= weight <= 7

    def test_directed_flag_round_trips(self):
        g = random_graph(8, 0.5, seed=5, directed=True)
        assert g.directed is True
        assert Graph.from_dict(g.to_dict()).directed is True

        u = random_graph(8, 0.5, seed=5, directed=False)
        assert u.directed is False
        assert Graph.from_dict(u.to_dict()).directed is False

    def test_density_zero_connected_is_pure_spanning_tree(self):
        g = random_graph(10, 0.0, seed=3, connected=True)
        assert len(g.get_edges()) == 9

    def test_density_one_undirected_fills_pool(self):
        g = random_graph(8, 1.0, seed=11, directed=False, connected=True)
        assert len(g.get_edges()) == 8 * 7 // 2

    def test_positions_on_circle(self):
        g = random_graph(6, 0.5, seed=13)
        for node_id in g.get_nodes():
            x, y = g.get_node_position(node_id)
            assert (x, y) != (0.0, 0.0)
            assert math.hypot(x, y) == pytest.approx(DEMO_RADIUS)

    def test_labels_extend_past_alphabet(self):
        g = random_graph(30, 0.1, seed=17)
        nodes = g.get_nodes()
        assert nodes[0] == 'A'
        assert nodes[25] == 'Z'
        assert nodes[26] == 'A1'
        assert nodes[27] == 'B1'
        assert g.get_node_label('A1') == 'A1'


# ---------------------------------------------------------------------------
# Fold-compat smoke: dijkstra over a seeded graph
# ---------------------------------------------------------------------------

class TestDijkstraSmoke:
    def test_dijkstra_solves_seeded_graph(self):
        g = random_graph(12, 0.4, seed=21, connected=True)
        start = g.get_nodes()[0]
        result = DijkstraAlgorithm().solve(g, {"start": start})
        assert result.distances[start] == 0
        assert set(result.distances) == set(g.get_nodes())
        for node in g.get_nodes():
            assert result.distances[node] != float('inf')
            assert result.paths[node][0] == start
            assert result.paths[node][-1] == node
