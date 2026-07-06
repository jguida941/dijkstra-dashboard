import pytest

from dijkstra_dashboard.core.graph import Graph
from dijkstra_dashboard.core.serialization import graph_to_dict, dict_to_graph


def test_serialization_roundtrip(sample_graph):
    data = graph_to_dict(sample_graph)
    restored = dict_to_graph(data)

    assert restored.get_nodes() == sample_graph.get_nodes()
    assert set(restored.get_edges()) == set(sample_graph.get_edges())
    assert restored.directed == sample_graph.directed


def test_dict_to_graph_invalid_version():
    data = {
        "version": 999,
        "directed": False,
        "nodes": {},
        "edges": [],
    }
    with pytest.raises(Exception):
        dict_to_graph(data)
