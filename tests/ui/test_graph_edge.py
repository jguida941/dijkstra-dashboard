from dataclasses import replace

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsScene

import dijkstra_dashboard.ui.graph_edge as graph_edge_module
from dijkstra_dashboard.ui.graph_edge import GraphEdge
from dijkstra_dashboard.ui.graph_node import GraphNode
from dijkstra_dashboard.ui.theme import get_theme_manager


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


@pytest.mark.ui
def test_weight_chip_trims_integral_floats(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    start.setPos(QPointF(0, 0))
    end.setPos(QPointF(120, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5.0)
    scene.addItem(edge)
    assert edge.label._text == "5"

    edge.set_weight(2.5)
    assert edge.label._text == "2.5"


@pytest.mark.ui
def test_transparent_weight_chip_renders_as_bare_number(qapp):
    get_theme_manager().set_theme("neon-dark", persist=False)
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(120, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)
    edge.set_state("final")

    assert edge.label._pill_visible() is False
    assert edge.label._style.chip_bg == "#00000000"
    assert edge.label._style.chip_border == "#00000000"


@pytest.mark.ui
def test_edge_halo_color_is_capped_to_translucent_glow(qapp):
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(120, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)
    edge._style = replace(edge._style, halo="#ff9966ff")

    assert edge._halo_paint_color().alpha() == 38
    assert edge._halo_width() == edge._style.width + 2

    edge.set_state("final")
    edge._style = replace(edge._style, halo="#ff9966ff")
    assert edge._halo_paint_color().alpha() == 90
    assert edge._halo_width() == edge._style.width + 6

    edge._style = replace(edge._style, halo="#4000e5ff")
    assert edge._halo_paint_color().alpha() == 0x40


@pytest.mark.ui
def test_active_route_edges_get_hot_center_highlight(qapp):
    get_theme_manager().set_theme("neon-dark", persist=False)
    scene = QGraphicsScene()
    start = GraphNode("A")
    end = GraphNode("B")
    end.setPos(QPointF(120, 0))
    scene.addItem(start)
    scene.addItem(end)

    edge = GraphEdge(start, end, 5)
    scene.addItem(edge)

    assert edge._core_highlight_width() == 0

    edge.set_state("relaxed")
    stroke = edge._style.stroke
    core = edge._core_highlight_color()
    assert 0 < edge._core_highlight_width() < edge._style.width
    assert core.alpha() == 235
    assert core.lightness() > QColor(stroke).lightness()

    edge.set_state("final")
    final_core = edge._core_highlight_color()
    assert 0 < edge._core_highlight_width() < edge._style.width
    assert final_core.lightness() > QColor(edge._style.stroke).lightness()
