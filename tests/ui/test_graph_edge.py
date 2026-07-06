import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsScene

from dijkstra_dashboard.ui.graph_edge import GraphEdge
from dijkstra_dashboard.ui.graph_node import GraphNode


@pytest.mark.ui
def test_coincident_nodes_fallback_no_raise(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    start.setPos(QPointF(100, 100))
    end.setPos(QPointF(100, 100))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 7)
    scene.addItem(edge)

    edge.update_position()
