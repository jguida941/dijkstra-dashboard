"""Phase 3 — animation layer + canvas feel.

Covers the AnimationCoordinator registry/finalize contract and the GraphView
canvas changes (fixed scene rect, incremental wheel zoom, fit-to-content).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QNativeGestureEvent, QPainterPath, QPointingDevice, QWheelEvent
from PyQt6.QtWidgets import QGraphicsScene, QPushButton

from dijkstra_dashboard.ui.animations import AnimationCoordinator
from dijkstra_dashboard.ui.graph_node import GraphNode
from dijkstra_dashboard.ui.graph_view import GraphView, ZOOM_OVERLAY_MARGIN, ZOOM_OVERLAY_PADDING
from dijkstra_dashboard.ui.theme import get_theme_manager


pytestmark = pytest.mark.ui


# ---------------------------------------------------------------------------
# AnimationCoordinator — registry / finalize / interval contract
# ---------------------------------------------------------------------------
def test_cancel_all_snaps_pop_scale_and_empties_registry(qapp):
    coord = AnimationCoordinator()
    node = GraphNode("A")

    coord.pop_scale(node, 300)
    assert coord._registry, "pop_scale must register a pending animation"

    node.setScale(1.5)  # simulate a mid-pop scale
    coord.cancel_all()

    assert node.scale() == 1.0            # finalize snapped to the exact end state
    assert coord._registry == {}          # registry flushed


def test_travel_dot_removed_from_scene_on_cancel(qapp):
    coord = AnimationCoordinator()
    scene = QGraphicsScene()
    path = QPainterPath(QPointF(0, 0))
    path.lineTo(QPointF(100, 0))

    baseline = len(scene.items())
    coord.travel_dot(scene, path, "#00e5ff", 300)
    assert len(scene.items()) == baseline + 1

    coord.cancel_all()
    assert len(scene.items()) == baseline  # finalize removed the dot
    assert coord._registry == {}


def test_run_stagger_cancel_fires_all_remaining_callbacks(qapp):
    coord = AnimationCoordinator()
    fired: list[int] = []
    callbacks = [lambda i=i: fired.append(i) for i in range(3)]

    coord.run_stagger(callbacks, step_ms=120)
    coord.cancel_all()

    assert sorted(fired) == [0, 1, 2]
    assert coord._registry == {}


def test_scaled_caps_to_step_interval_with_floor(qapp):
    coord = AnimationCoordinator()

    coord.set_interval(100)
    assert coord.scaled(500) == 90        # min(500, int(100 * 0.9))

    coord.set_interval(10)
    assert coord.scaled(500) == 30        # floor of 30ms


def test_animate_float_finalize_snaps_to_end(qapp):
    coord = AnimationCoordinator()
    seen: list[float] = []

    coord.animate_float("zoom", 1.0, 2.0, 120, lambda v: seen.append(v))
    coord.cancel_all()

    assert seen[-1] == pytest.approx(2.0)  # finalize applied the end value
    assert coord._registry == {}


def test_same_key_cancels_and_snaps_previous(qapp):
    coord = AnimationCoordinator()
    first: list[float] = []

    coord.animate_float("zoom", 0.0, 1.0, 200, lambda v: first.append(v))
    # Starting a new animation under the same key must cancel-and-snap the old one.
    coord.animate_float("zoom", 1.0, 3.0, 200, lambda v: None)

    assert first[-1] == pytest.approx(1.0)  # previous snapped to its end


# ---------------------------------------------------------------------------
# GraphView — scene rect decoupled from window (F10)
# ---------------------------------------------------------------------------
def test_scene_rect_is_fixed_big_rect(qapp):
    view = GraphView()
    rect = view.scene.sceneRect()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (-1500, -1000, 3000, 2000)


def test_resize_leaves_scene_rect_unchanged(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    before = view.scene.sceneRect()

    view.resize(1234, 987)
    qtbot.wait(10)

    after = view.scene.sceneRect()
    assert after == before
    assert (after.width(), after.height()) == (3000, 2000)


def test_zoom_overlay_keeps_clearance_from_view_edges(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)

    view._anchor_zoom_overlay()

    overlay = view.zoom_controls_widget.geometry()
    # Parented to the view (not the viewport) so panning cannot drag it along;
    # both geometries below are in view coordinates.
    viewport_geo = view.viewport().geometry()
    assert view.zoom_controls_widget.parent() is view
    assert viewport_geo.x() + viewport_geo.width() - (overlay.x() + overlay.width()) >= ZOOM_OVERLAY_MARGIN
    assert viewport_geo.y() + viewport_geo.height() - (overlay.y() + overlay.height()) >= ZOOM_OVERLAY_MARGIN

    for button in view.zoom_controls_widget.findChildren(QPushButton):
        button_bottom = view.zoom_controls_widget.y() + button.geometry().bottom()
        assert viewport_geo.y() + viewport_geo.height() - button_bottom >= ZOOM_OVERLAY_MARGIN
        assert button.geometry().top() >= ZOOM_OVERLAY_PADDING
        assert button.geometry().left() >= ZOOM_OVERLAY_PADDING
        assert view.zoom_controls_widget.height() - button.geometry().bottom() >= ZOOM_OVERLAY_PADDING


def test_zoom_overlay_stays_anchored_while_panning(qapp, qtbot):
    # The overlay must NOT ride along with the canvas: QGraphicsView scrolls the
    # viewport's child widgets, so the overlay is parented to the view itself.
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view._anchor_zoom_overlay()

    before = view.zoom_controls_widget.pos()
    # Pan exactly like the drag-pan handler does: scrollbar deltas.
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 120)
    view.verticalScrollBar().setValue(view.verticalScrollBar().value() + 80)

    assert view.zoom_controls_widget.pos() == before


def test_zoom_buttons_step_full_increment_even_mid_ease(qapp):
    # Two rapid + clicks must advance two full steps; the second click snaps the
    # in-flight ease before computing its target instead of reading a mid-tween
    # zoom_level.
    view = GraphView()
    view.reset_zoom()

    view.zoom_in()
    view.zoom_in()
    view.animator.cancel_all()  # finalize -> zoom_level lands on the target

    assert view.zoom_level == pytest.approx(1.4)


def test_zoom_buttons_never_move_opposite_past_clamp(qapp):
    # fit_to_content can leave zoom_level outside [0.2, 5.0]; +/- must then be
    # no-ops rather than snapping the wrong way to the clamp bound.
    view = GraphView()

    view.zoom_level = 6.0
    view.zoom_in()
    view.animator.cancel_all()
    assert view.zoom_level == pytest.approx(6.0)

    view.zoom_level = 0.1
    view.zoom_out()
    view.animator.cancel_all()
    assert view.zoom_level == pytest.approx(0.1)


def test_pinch_native_gesture_zooms(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view.reset_zoom()

    event = QNativeGestureEvent(
        Qt.NativeGestureType.ZoomNativeGesture,
        QPointingDevice.primaryPointingDevice(),
        QPointF(400, 300),
        QPointF(400, 300),
        QPointF(400, 300),
        0.5,
        0,
        0,
    )
    handled = view.viewportEvent(event)

    assert handled is True
    assert view.zoom_level == pytest.approx(1.5)
    assert view.transform().m11() == pytest.approx(1.5)


def test_delete_selection_keeps_viewport_zoom(qapp, qtbot):
    # In-place edits (delete/add edge/undo) must not re-fit and stomp the
    # user's zoom; only document loads reframe.
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view.reset_zoom()
    view.zoom_level = 2.0
    view.set_zoom()

    node = next(iter(view.nodes.values()))
    view._delete_items([], [node])

    assert view.transform().m11() == pytest.approx(2.0)
    assert view.zoom_level == pytest.approx(2.0)


def test_node_clamps_against_big_scene_rect(qapp):
    # A node can now sit far outside the old 800x600 viewport bounds.
    view = GraphView()
    node = next(iter(view.nodes.values()))

    node.setPos(QPointF(1400, 900))

    assert node.pos().x() == pytest.approx(1400)
    assert node.pos().y() == pytest.approx(900)


def test_edge_label_clamp_still_active_after_fit(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.fit_to_content()

    rect = view.scene.sceneRect()
    # Drive a node to the extreme corner so its edges would overflow without the clamp.
    node = next(iter(view.nodes.values()))
    node.setPos(QPointF(rect.right() - 25, rect.bottom() - 25))

    for edge in view.edges.values():
        edge.update_position()
        pos = edge.label.pos()
        assert rect.left() <= pos.x() <= rect.right()
        assert rect.top() <= pos.y() <= rect.bottom()


# ---------------------------------------------------------------------------
# GraphView — zoom (F7 incremental wheel, animated buttons, fit)
# ---------------------------------------------------------------------------
def test_wheel_zoom_scales_incrementally_and_syncs_zoom_level(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view.fit_to_content()

    before = view.transform().m11()
    assert view.zoom_level == pytest.approx(before)

    event = QWheelEvent(
        QPointF(400, 300),
        QPointF(400, 300),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    view.wheelEvent(event)

    after = view.transform().m11()
    assert after != pytest.approx(before)                 # zoom actually changed
    assert view.zoom_level == pytest.approx(after)        # zoom_level stays truthful
    assert 0.2 <= view.zoom_level <= 5.0


def test_wheel_zoom_clamped_to_bounds(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view.zoom_level = 4.9

    # A large positive angle would exceed 5.0 without the clamp.
    event = QWheelEvent(
        QPointF(400, 300),
        QPointF(400, 300),
        QPoint(0, 0),
        QPoint(0, 2400),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    view.wheelEvent(event)

    assert view.zoom_level == pytest.approx(5.0)


def test_fit_to_content_resyncs_zoom_level(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()

    view.fit_to_content()

    assert view.zoom_level == pytest.approx(view.transform().m11())


def test_reset_zoom_cancels_inflight_ease_and_lands_at_one(qapp):
    view = GraphView()
    view.zoom_in()  # starts an animated ease under key "zoom"
    assert "zoom" in view.animator._keyed

    view.reset_zoom()  # "100%" must win instantly

    assert view.zoom_level == 1.0
    assert "zoom" not in view.animator._keyed


def test_fit_to_content_is_noop_on_empty_scene(qapp):
    view = GraphView()
    view.scene.clear()
    view.nodes.clear()
    view.edges.clear()

    view.zoom_level = 1.0
    view.fit_to_content()  # must not raise

    assert view.zoom_level == 1.0


# ---------------------------------------------------------------------------
# GraphView — cancel_all wired into lifecycle (F8)
# ---------------------------------------------------------------------------
def test_set_graph_cancels_pending_animations(qapp):
    view = GraphView()
    node = next(iter(view.nodes.values()))
    view.animator.pop_scale(node, 300)
    assert view.animator._registry

    view.set_graph(view.get_graph())  # rebuild scene

    assert view.animator._registry == {}


def test_theme_switch_mid_travel_dot_does_not_crash(qapp):
    view = GraphView()
    edge = next(iter(view.edges.values()))
    baseline = len(view.scene.items())

    view.animator.travel_dot(view.scene, edge.curve_path(), "#00e5ff", 300)
    assert len(view.scene.items()) == baseline + 1

    # Theme change is connected to _on_theme_changed, which cancels first.
    get_theme_manager().set_theme("paper-light", persist=False)

    assert view.animator._registry == {}
    assert len(view.scene.items()) == baseline  # dot cleaned up


def test_clear_run_decorations_cancels_animations(qapp):
    view = GraphView()
    node = next(iter(view.nodes.values()))
    view.animator.pop_scale(node, 300)
    assert view.animator._registry

    view.clear_run_decorations()

    assert view.animator._registry == {}
    assert node.scale() == 1.0


@pytest.mark.ui
def test_lightning_items_removed_on_cancel(qapp):
    scene = QGraphicsScene()
    path = QPainterPath(QPointF(0, 0))
    path.lineTo(QPointF(120, 0))
    coordinator = AnimationCoordinator()
    baseline = len(scene.items())

    coordinator.lightning(scene, path, "#00e5ff", 400)
    assert len(scene.items()) == baseline + 2  # glow underlay + core bolt

    coordinator.cancel_all()
    assert len(scene.items()) == baseline
    assert coordinator._registry == {}


def test_relax_travel_path_follows_relaxation_direction(qapp):
    # For an undirected edge stored sorted (A,B), a relaxation FROM B TO A must
    # animate the bolt/comet B->A, not in the stored A->B orientation.
    view = GraphView()
    (a, b), item = next(iter(view.edges.items()))
    assert item.start_node.node_id == a  # undirected items are stored sorted

    # Relaxation source = b (the item's END node): the oriented path must start
    # nearer b and end nearer a.
    path = view._oriented_curve_path(item, b)
    start = path.pointAtPercent(0.0)
    end = path.pointAtPercent(1.0)

    def near(pt, node_id):
        return (pt - view.nodes[node_id].pos()).manhattanLength()

    assert near(start, b) < near(start, a)
    assert near(end, a) < near(end, b)

    # And the natural orientation (source = start node) is unchanged.
    natural = view._oriented_curve_path(item, a)
    assert near(natural.pointAtPercent(0.0), a) < near(natural.pointAtPercent(0.0), b)
