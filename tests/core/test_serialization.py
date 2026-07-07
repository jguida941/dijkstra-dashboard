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

def test_validation_error_message_lists_reasons():
    # The load dialog shows str(exc); a bare "Graph validation failed." hides
    # WHY. The message must name the failing edge and its reason.
    data = {
        "version": 1,
        "directed": False,
        "nodes": {
            "A": {"label": "A", "x": 0, "y": 0},
            "B": {"label": "B", "x": 10, "y": 0},
        },
        "edges": [
            {"id": "A--B", "start": "A", "end": "B", "weight": float("inf")},
        ],
    }
    with pytest.raises(Exception) as excinfo:
        dict_to_graph(data)
    message = str(excinfo.value)
    assert "finite" in message
    assert message != "Graph validation failed."
