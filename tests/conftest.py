import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from dijkstra_dashboard.core.graph import Graph


@pytest.fixture
def sample_graph():
    """Standard 6-node test graph."""
    g = Graph()
    for name in ['A', 'B', 'C', 'D', 'E', 'F']:
        g.add_node(name)
    g.add_edge('A', 'B', 5)
    g.add_edge('A', 'C', 3)
    g.add_edge('A', 'E', 11)
    g.add_edge('B', 'C', 1)
    g.add_edge('B', 'F', 2)
    g.add_edge('C', 'D', 1)
    g.add_edge('C', 'E', 5)
    g.add_edge('D', 'E', 9)
    g.add_edge('D', 'F', 3)
    return g


@pytest.fixture
def empty_graph():
    return Graph()


@pytest.fixture
def disconnected_graph():
    g = Graph()
    g.add_node('A')
    g.add_node('B')
    g.add_node('X')
    g.add_edge('A', 'B', 1)
    return g


@pytest.fixture
def negative_weight_graph():
    g = Graph()
    for name in ['A', 'B', 'C']:
        g.add_node(name)
    g.add_edge('A', 'B', 4)
    g.add_edge('B', 'C', -2)
    g.add_edge('A', 'C', 5)
    return g
