import pytest

from dijkstra_dashboard.core.graph import Graph


def test_add_node(empty_graph):
    node_id = empty_graph.add_node('A')
    assert node_id == 'A'
    assert 'A' in empty_graph.get_nodes()


def test_add_node_with_position(empty_graph):
    empty_graph.add_node('A', x=100, y=200)
    assert empty_graph.get_node_position('A') == (100.0, 200.0)


def test_add_duplicate_node_raises(empty_graph):
    empty_graph.add_node('A')
    with pytest.raises(ValueError, match="already exists"):
        empty_graph.add_node('A')


def test_remove_node_removes_edges(sample_graph):
    sample_graph.remove_node('A')
    assert 'A' not in sample_graph.get_nodes()
    edges = sample_graph.get_edges()
    assert not any(edge[0] == 'A' or edge[1] == 'A' for edge in edges)


def test_to_adjacency_dict_undirected(sample_graph):
    adjacency = sample_graph.to_adjacency_dict()
    assert ('B', 5) in adjacency['A']
    assert ('A', 5) in adjacency['B']


def test_set_directed_roundtrip(sample_graph):
    sample_graph.set_directed(True)
    assert sample_graph.directed is True
    sample_graph.set_directed(False)
    assert sample_graph.directed is False
