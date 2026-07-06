import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsScene

import dijkstra_dashboard.ui.graph_edge as graph_edge_module
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


@pytest.mark.ui
def test_weight_chip_is_added_to_scene_with_edge(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(100, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)

    assert isinstance(edge.label, graph_edge_module.WeightChip)
    assert edge.label.scene() is scene


@pytest.mark.ui
def test_dispose_removes_edge_and_chip_from_scene(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(100, 0))
    scene.addItem(start)
    scene.addItem(end)
    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)

    edge.dispose()

    assert edge.scene() is None
    assert edge.label.scene() is None


@pytest.mark.ui
def test_curve_path_ends_at_anchor_not_arrow_vertex(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    start.setPos(QPointF(0, 0))
    end.setPos(QPointF(100, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5, directed=True)
    scene.addItem(edge)

    curve_end = edge.curve_path().pointAtPercent(1.0)
    expected_end = QPointF(79, 0)
    distance = ((curve_end.x() - expected_end.x()) ** 2 + (curve_end.y() - expected_end.y()) ** 2) ** 0.5
    assert distance < 1


@pytest.mark.ui
def test_edge_state_z_values_opacity_and_alias(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(100, 0))
    scene.addItem(start)
    scene.addItem(end)
    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)

    edge.set_state("final")
    assert edge.zValue() == 1

    edge.set_state("not_in_path")
    assert edge.opacity() < 1.0
    assert edge.label.opacity() == edge.opacity()

    edge.set_state("visited")
    assert edge._state == "relaxed"
