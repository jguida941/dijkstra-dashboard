from PyQt6 import sip
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QPushButton, QHBoxLayout, QWidget, QInputDialog, QGraphicsSimpleTextItem, QSizePolicy
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPen, QResizeEvent
from .graph_node import GraphNode
from .graph_edge import GraphEdge, WeightChip
from .animations import AnimationCoordinator
from .undo import GraphSnapshotCommand
from .theme import current_theme, get_theme_manager
from dijkstra_dashboard.core.graph import Graph
import math

INF = float("inf")
IMPACT_FLASH_START = 0.84
FIT_MARGIN = 36.0


def format_distance(value):
    if value == INF:
        return "∞"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


class GraphView(QGraphicsView):
    graph_changed = pyqtSignal()
    message_changed = pyqtSignal(str)
    status_message = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Enhanced rendering settings
        self.setRenderHint(self.renderHints().Antialiasing)
        self.setRenderHint(self.renderHints().SmoothPixmapTransform)
        self.setViewportUpdateMode(self.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Make view expandable instead of fixed size
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)
        # Scene rect is decoupled from the window: one big fixed canvas so nodes
        # can be dragged well outside the current viewport. Set once, never
        # rewritten on resize.
        self.scene.setSceneRect(-1500, -1000, 3000, 2000)

        # Coordinator owns every transient tween (pops, travel dots, staggers,
        # zoom eases). Parented to the view; graphics items never own it.
        self.animator = AnimationCoordinator(self)

        self._apply_canvas_bg(current_theme())

        # Nodes handle their own left-drag movement. The view handles canvas
        # panning explicitly so hidden scrollbars still move predictably.
        self.setDragMode(self.DragMode.NoDrag)

        # Zoom settings
        self.zoom_level = 1.0
        self.zoom_step = 0.2  # 20% zoom step
        self._label_scale = 1.0
        self._snap_to_grid = False
        self._grid_size = 40.0
        self._snapping_node = False
        self._is_panning = False
        self._pan_button = Qt.MouseButton.NoButton
        self._pan_last_pos = None

        # Create zoom controls
        self.create_zoom_controls()

        # Store nodes and edges
        self.nodes = {}
        self.edges = {}
        self.graph = None
        self.pending_edge_start = None

        # Undo/redo (Phase 7): the stack is injected by MainWindow; the view is
        # constructible without one, and every mutation hook no-ops when it is
        # None (keeps stack-free tests untouched). ``_pending_before`` holds the
        # in-flight snapshot between _begin_mutation and _commit_mutation;
        # ``_drag_node`` marks a plain-left drag that spans press -> release.
        self.undo_stack = None
        self._pending_before = None
        self._drag_node = None

        get_theme_manager().theme_changed.connect(self._on_theme_changed)

        # Setup the graph
        self.setup_graph()

    def set_label_scale(self, scale):
        scale = max(1.0, min(1.6, float(scale)))
        if abs(scale - self._label_scale) < 0.01:
            return
        self._label_scale = scale
        self._apply_label_scale()

    def _apply_label_scale(self):
        for node in self.nodes.values():
            node.set_font_scale(self._label_scale)
        for edge in self.edges.values():
            edge.set_label_scale(self._label_scale)

    def create_zoom_controls(self):
        # Create a container widget for zoom controls
        controls_widget = QWidget()
        controls_widget.setObjectName("zoomOverlay")
        controls_layout = QHBoxLayout()
        controls_widget.setLayout(controls_layout)

        # Zoom out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.clicked.connect(self.zoom_out)

        # Zoom reset button
        zoom_reset_btn = QPushButton("100%")
        zoom_reset_btn.setFixedSize(50, 30)
        zoom_reset_btn.clicked.connect(self.reset_zoom)

        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.clicked.connect(self.zoom_in)

        # Add buttons to layout
        controls_layout.addWidget(zoom_out_btn)
        controls_layout.addWidget(zoom_reset_btn)
        controls_layout.addWidget(zoom_in_btn)
        controls_layout.setSpacing(5)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        # Add controls to the view
        controls_widget.setParent(self)
        controls_widget.move(10, 10)  # Position in top-left corner
        self.zoom_controls_widget = controls_widget

    def _apply_canvas_bg(self, theme):
        rect = self.scene.sceneRect()
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(theme.canvas_bg_top))
        gradient.setColorAt(1, QColor(theme.canvas_bg_bottom))
        self.setBackgroundBrush(QBrush(gradient))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self._snap_to_grid:
            return
        grid = max(5.0, float(self._grid_size))
        theme = current_theme()
        color = QColor(theme.button_border)
        color.setAlpha(90 if theme.dark else 120)
        painter.setPen(QPen(color, 1.0))
        left = math.floor(rect.left() / grid) * grid
        top = math.floor(rect.top() / grid) * grid
        x = left
        while x <= rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += grid
        y = top
        while y <= rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += grid

    def _on_theme_changed(self, theme):
        # Cancel -> snap every in-flight tween before restyling, then refresh.
        self.animator.cancel_all()
        self._apply_canvas_bg(theme)
        for node in self.nodes.values():
            node.refresh_theme()
        for edge in self.edges.values():
            edge.refresh_theme()

    def zoom_in(self):
        self._animate_zoom(min(5.0, self.zoom_level + self.zoom_step))

    def zoom_out(self):
        self._animate_zoom(max(0.2, self.zoom_level - self.zoom_step))

    def reset_zoom(self):
        # "100%" resets instantly (center-anchored). Cancel any in-flight +/- ease
        # first so the reset can't be overridden by a lingering zoom tween.
        self.animator.cancel("zoom")
        self.zoom_level = 1.0
        self.set_zoom()

    def _animate_zoom(self, target):
        def apply(value):
            self.zoom_level = value
            self.set_zoom()

        self.animator.animate_float("zoom", self.zoom_level, target, 120, apply)

    def set_zoom(self):
        # Reset transform then scale (center-anchored path for the +/-/100% buttons).
        self.resetTransform()
        self.scale(self.zoom_level, self.zoom_level)

    def wheelEvent(self, event):
        # Incremental zoom anchored under the cursor. NEVER resetTransform here:
        # that would drop the AnchorUnderMouse translation. Scale by the ratio
        # of the clamped new zoom to the current zoom, and keep zoom_level truthful.
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        new_zoom = max(0.2, min(5.0, self.zoom_level * (1.0015 ** event.angleDelta().y())))
        factor = new_zoom / self.zoom_level if self.zoom_level else 1.0
        self.scale(factor, factor)
        self.zoom_level = new_zoom
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        event.accept()

    def fit_to_content(self):
        # Fit the graph's bounding box (plus margin) into the viewport, then
        # resync zoom_level to the resulting scale. No-op on an empty scene.
        if not self.scene.items():
            return
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.fitInView(
            rect.adjusted(-FIT_MARGIN, -FIT_MARGIN, FIT_MARGIN, FIT_MARGIN),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.zoom_level = self.transform().m11()

    def set_tween_interval(self, ms):
        self.animator.set_interval(ms)

    def set_snap_to_grid(self, enabled):
        self._snap_to_grid = bool(enabled)
        self.viewport().update()

    def snap_to_grid(self):
        return self._snap_to_grid

    def set_grid_size(self, size):
        self._grid_size = max(5.0, float(size))
        if self._snap_to_grid:
            self.viewport().update()

    def grid_size(self):
        return self._grid_size

    def _snap_point(self, point):
        grid = max(5.0, float(self._grid_size))
        return QPointF(round(point.x() / grid) * grid, round(point.y() / grid) * grid)

    def _anchor_zoom_overlay(self):
        overlay = getattr(self, "zoom_controls_widget", None)
        if overlay is None:
            return
        overlay.adjustSize()
        margin = 28
        x = self.width() - overlay.width() - margin
        y = self.height() - overlay.height() - margin
        overlay.move(max(0, x), max(0, y))

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        # Scene rect is fixed (decoupled from the window); do NOT rewrite it here.
        # Re-apply the canvas gradient and re-anchor the zoom overlay bottom-right.
        self._apply_canvas_bg(current_theme())
        self._anchor_zoom_overlay()
        for edge in self.edges.values():
            edge.update_position()

    def _item_at_event(self, event):
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, QGraphicsSimpleTextItem):
            parent = item.parentItem()
            if isinstance(parent, GraphNode):
                return parent
        return item

    def _set_pan_cursor(self, active):
        if active:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.viewport().unsetCursor()

    def _start_pan(self, event):
        self._is_panning = True
        self._pan_button = event.button()
        self._pan_last_pos = event.position().toPoint()
        self._set_pan_cursor(True)
        event.accept()

    def _finish_pan(self):
        self._is_panning = False
        self._pan_button = Qt.MouseButton.NoButton
        self._pan_last_pos = None
        self._set_pan_cursor(False)

    def _should_start_pan(self, event, item):
        button = event.button()
        if button in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            # Preserve the existing Ctrl/Option + right-click node shortcut for
            # edge creation; every other right/middle drag pans the canvas.
            return not (
                button == Qt.MouseButton.RightButton
                and isinstance(item, GraphNode)
                and (
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                    or event.modifiers() & Qt.KeyboardModifier.AltModifier
                )
            )
        if button != Qt.MouseButton.LeftButton:
            return False
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            return False
        # Plain left-drag on empty space is the grab-the-canvas path. Left-drag
        # on nodes remains node movement, and edges/labels remain selectable.
        return item is None

    def mousePressEvent(self, event):
        self.setFocus()
        item = self._item_at_event(event)

        if event.button() == Qt.MouseButton.RightButton and isinstance(item, GraphNode) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            or event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self.handle_node_click(item)
            return

        if self._should_start_pan(event, item):
            self._start_pan(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if isinstance(item, GraphNode):
                if self.pending_edge_start is not None:
                    self.handle_node_click(item)
                    return
                if (
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                    or event.modifiers() & Qt.KeyboardModifier.AltModifier
                    or event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                ):
                    self.handle_node_click(item)
                    return
                # F8: a plain left press on a node (no modifiers, no pending
                # edge-start) falls through to a real drag -- snapshot now;
                # mouseReleaseEvent commits "Move node" iff it actually moved.
                self._begin_mutation()
                self._drag_node = item
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if not isinstance(item, GraphNode):
                    self.add_node_at(event.position().toPoint())
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_last_pos is not None:
            pos = event.position().toPoint()
            delta = pos - self._pan_last_pos
            self._pan_last_pos = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_panning and event.button() == self._pan_button:
            self._finish_pan()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self._drag_node is not None:
            node = self._drag_node
            self._drag_node = None
            if self._drag_moved(node):
                # ONE command per drag; F7: emit graph_changed exactly once here
                # (a moved node invalidates a loaded run -- positions feed A*).
                self._commit_mutation("Move node")
                self.graph_changed.emit()
            else:
                self._drop_pending()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        node_item = None
        if isinstance(item, GraphNode):
            node_item = item
        elif isinstance(item, QGraphicsSimpleTextItem):
            parent = item.parentItem()
            if isinstance(parent, GraphNode):
                node_item = parent

        if node_item is not None:
            self._rename_node(node_item)
            return

        edge_item = self._edge_from_item(item)
        if edge_item is not None:
            self._edit_edge_weight(edge_item)
            return

        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = self.scene.selectedItems()
            if not selected:
                return

            edges = []
            nodes = []
            for item in selected:
                if isinstance(item, GraphEdge):
                    edges.append(item)
                elif isinstance(item, GraphNode):
                    nodes.append(item)
                elif isinstance(item, WeightChip):
                    edges.append(item.edge)
                elif isinstance(item, QGraphicsSimpleTextItem):
                    # Check if it's an edge label
                    for edge in self.edges.values():
                        if edge.label is item:
                            edges.append(edge)
                            break

            if edges or nodes:
                QTimer.singleShot(0, lambda e=edges, n=nodes: self._delete_items(e, n))
            return
        super().keyPressEvent(event)

    def setup_graph(self):
        # Dynamically position nodes in a circle based on number of nodes
        node_names = ['A', 'B', 'C', 'D', 'E', 'F']
        # Use 35% of the smaller dimension for radius to fill more space
        view_size = min(self.width() or 800, self.height() or 600)
        radius = view_size * 0.35
        angle_offset = -math.pi / 2  # Start from top center
        node_positions = {}

        for i, name in enumerate(node_names):
            angle = angle_offset + 2 * math.pi * i / len(node_names)
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            node_positions[name] = QPointF(x, y)

        graph = Graph(directed=False)
        for name, pos in node_positions.items():
            graph.add_node(node_id=name, label=name, x=pos.x(), y=pos.y())

        # Add edges
        edges = [
            ('A', 'B', 5), ('A', 'C', 3), ('A', 'E', 11),
            ('B', 'C', 1), ('B', 'F', 2),
            ('C', 'D', 1), ('C', 'E', 5),
            ('D', 'E', 9), ('D', 'F', 3)
        ]

        for start, end, weight in edges:
            graph.add_edge(start, end, weight)

        self.set_graph(graph)

    def set_graph(self, graph):
        # Flush pending tweens BEFORE swapping the model: a mid-flight layout
        # finalize moves the OLD node items, and their itemChange writes
        # positions through _on_node_moved into self.graph — with the new graph
        # already assigned, old node ids would corrupt or crash it.
        self.animator.cancel_all()
        for node in self.nodes.values():
            node.stop_pulse()

        self.graph = graph
        self.pending_edge_start = None
        # Every node item is about to be rebuilt; forget any in-flight drag so a
        # release can't commit against a deleted node. (_pending_before is left
        # intact: several hooks call set_graph mid-mutation, then commit.)
        self._drag_node = None
        self._clear_message()

        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()

        # Add new nodes
        for node in self.graph.nodes():
            node_item = GraphNode(node.label, node_id=node.id, move_callback=self._on_node_moved)
            node_item.setPos(QPointF(node.x, node.y))
            self.nodes[node.id] = node_item
            self.scene.addItem(node_item)

        # Add edges
        if self.graph.directed:
            edge_pairs = {(edge.start, edge.end) for edge in self.graph.edges()}
            if self.graph.nodes():
                centroid_x = sum(node.x for node in self.graph.nodes()) / len(self.graph.nodes())
                centroid_y = sum(node.y for node in self.graph.nodes()) / len(self.graph.nodes())
            else:
                centroid_x = 0.0
                centroid_y = 0.0
            for edge in self.graph.edges():
                has_reverse = (edge.end, edge.start) in edge_pairs
                if has_reverse:
                    start_pos = self.nodes[edge.start].pos()
                    end_pos = self.nodes[edge.end].pos()
                    distance = math.hypot(end_pos.x() - start_pos.x(), end_pos.y() - start_pos.y())
                    # Use the same sign; reversed normals automatically curve the other way.
                    sign = 1
                    # Tighter curves - just enough to separate bidirectional edges
                    curve_offset = max(20, min(35, distance * 0.12))
                else:
                    start_pos = self.nodes[edge.start].pos()
                    end_pos = self.nodes[edge.end].pos()
                    mid = (start_pos + end_pos) / 2
                    normal = QPointF(end_pos.y() - start_pos.y(), start_pos.x() - end_pos.x())
                    to_center = QPointF(centroid_x - mid.x(), centroid_y - mid.y())
                    if normal.x() * to_center.x() + normal.y() * to_center.y() > 0:
                        sign = -1
                    else:
                        sign = 1
                    curve_offset = 8  # Subtle curve for single direction
                edge_item = GraphEdge(
                    self.nodes[edge.start],
                    self.nodes[edge.end],
                    edge.weight,
                    directed=True,
                    curve_sign=sign,
                    curve_offset=curve_offset,
                )
                self.edges[(edge.start, edge.end)] = edge_item
                self.scene.addItem(edge_item)
        else:
            for edge in self.graph.edges():
                edge_item = GraphEdge(
                    self.nodes[edge.start],
                    self.nodes[edge.end],
                    edge.weight,
                    directed=False,
                )
                self.edges[self._edge_key(edge.start, edge.end)] = edge_item
                self.scene.addItem(edge_item)

        self._apply_label_scale()
        self.graph_changed.emit()
        self.fit_to_content()

    def get_graph(self):
        return self.graph

    def get_node_items(self):
        if self.graph:
            return [(node.id, node.label) for node in self.graph.nodes()]
        return [(node_id, node.name) for node_id, node in self.nodes.items()]

    # ------------------------------------------------------------------
    # Undo/redo plumbing (Phase 7). A mutation hook captures a whole-graph
    # snapshot with _begin_mutation, applies its change, then either commits
    # (diff-guarded push) or drops the pending snapshot on any abort path.
    # ------------------------------------------------------------------
    def _begin_mutation(self):
        self._pending_before = self.graph.to_dict() if self.graph is not None else None

    def _commit_mutation(self, text):
        before = self._pending_before
        self._pending_before = None
        if before is None or self.graph is None or self.undo_stack is None:
            return
        after = self.graph.to_dict()
        if after == before:
            # Silent no-op (cancelled dialog, rejected rename): keep it off the
            # stack so undo never replays an unchanged snapshot.
            return
        self.undo_stack.push(
            GraphSnapshotCommand(text, before, after, self._restore_snapshot)
        )

    def _drop_pending(self):
        self._pending_before = None

    def _restore_snapshot(self, snapshot):
        # Rides the existing graph_changed pipeline (controller unload, combos
        # repopulate, decorations/animations clear) for free.
        self.set_graph(Graph.from_dict(snapshot))

    def _drag_moved(self, node):
        # A drag counts only if the node's live position differs from the
        # position stored in the before-snapshot (a plain click never moves it).
        if self._pending_before is None or self.graph is None or sip.isdeleted(node):
            return False
        stored = self._pending_before.get("nodes", {}).get(node.node_id)
        if stored is None:
            return False
        pos = node.pos()
        return pos.x() != stored.get("x") or pos.y() != stored.get("y")

    def add_node_at(self, view_pos):
        if not self.graph:
            return
        self._clear_message()
        self._begin_mutation()
        scene_pos = self.mapToScene(view_pos)

        # Constrain new node position to scene bounds
        scene_rect = self.scene.sceneRect()
        node_radius = 25
        x = max(scene_rect.left() + node_radius, min(scene_pos.x(), scene_rect.right() - node_radius))
        y = max(scene_rect.top() + node_radius, min(scene_pos.y(), scene_rect.bottom() - node_radius))

        node_id = self.graph.add_node(x=x, y=y)
        label = self.graph.get_node_label(node_id)
        node_item = GraphNode(label, node_id=node_id, move_callback=self._on_node_moved)
        node_item.setPos(QPointF(x, y))
        self.nodes[node_id] = node_item
        self.scene.addItem(node_item)
        self.graph_changed.emit()
        self._commit_mutation("Add node")

    def handle_node_click(self, node_item):
        node_id = node_item.node_id
        if self.pending_edge_start is None:
            self.pending_edge_start = node_id
            self.status_message.emit(
                f"Selected node {node_item.name} for edge start.", "text"
            )
            return

        if self.pending_edge_start == node_id:
            self.pending_edge_start = None
            self.status_message.emit("Edge start cleared.", "text")
            return

        weight, ok = QInputDialog.getDouble(
            self,
            "Edge Weight",
            "Weight:",
            1.0,
            -1e9,
            1e9,
            2,
        )
        if ok:
            # F8: snapshot wraps ONLY the accepted-dialog mutation; every error
            # path below drops the pending snapshot.
            self._begin_mutation()
            try:
                self._clear_message()
                updated = False
                try:
                    self.graph.update_edge(self.pending_edge_start, node_id, weight)
                    updated = True
                except ValueError as exc:
                    if "Edge not found" not in str(exc):
                        raise
                if not updated:
                    self.graph.add_edge(self.pending_edge_start, node_id, weight)
                direction = "->" if self.graph.directed else "--"
                start_label = self.graph.get_node_label(self.pending_edge_start)
                end_label = self.graph.get_node_label(node_id)
                action = "Updated" if updated else "Added"
                self.set_graph(self.graph)
                self.status_message.emit(
                    f"{action} edge {start_label} {direction} {end_label} ({weight}).",
                    "text",
                )
                self._commit_mutation("Update edge" if updated else "Add edge")
            except Exception as exc:
                self._drop_pending()
                self.status_message.emit(str(exc), "error")

        self.pending_edge_start = None

    def _on_node_moved(self, node_item, new_pos):
        node_id = node_item.node_id
        if self._snap_to_grid and not self._snapping_node:
            snapped = self._snap_point(new_pos)
            if snapped != new_pos:
                self._snapping_node = True
                try:
                    node_item.setPos(snapped)
                finally:
                    self._snapping_node = False
                new_pos = snapped
        if self.graph:
            self.graph.set_node_position(node_id, new_pos.x(), new_pos.y())
        for edge in self.edges.values():
            if edge.start_node is node_item or edge.end_node is node_item:
                edge.update_position()

    def _clear_message(self):
        self.message_changed.emit("")

    def label_lookup(self, node_id):
        if self.graph:
            try:
                label = self.graph.get_node_label(node_id)
            except Exception:
                return str(node_id)
            counts: dict[str, int] = {}
            for node in self.graph.nodes():
                counts[node.label] = counts.get(node.label, 0) + 1
            if counts.get(label, 0) > 1:
                return f"{label} ({node_id})"
            return label
        return str(node_id)

    def _edge_from_item(self, item):
        if isinstance(item, GraphEdge):
            return item
        if isinstance(item, WeightChip):
            return item.edge
        return None

    def _rename_node(self, node_item):
        if not self.graph:
            return
        self._clear_message()
        current = node_item.name
        label, ok = QInputDialog.getText(
            self,
            "Rename Node",
            "Label:",
            text=current,
        )
        if not ok:
            return
        label = label.strip()
        if not label:
            self.status_message.emit("Node label cannot be empty.", "error")
            return
        for node in self.graph.nodes():
            if node.label == label and node.id != node_item.node_id:
                self.status_message.emit(
                    f"Node label '{label}' is already in use.",
                    "error",
                )
                return
        # Snapshot begins only past validation, so cancel / empty / duplicate
        # rejections push nothing.
        self._begin_mutation()
        try:
            self.graph.rename_node(node_item.node_id, label)
            node_item.set_label(label)
            self.graph_changed.emit()
            self._commit_mutation("Rename node")
        except Exception as exc:
            self._drop_pending()
            self.status_message.emit(str(exc), "error")

    def _edit_edge_weight(self, edge_item):
        if not self.graph:
            return
        self._clear_message()
        weight, ok = QInputDialog.getDouble(
            self,
            "Edit Edge Weight",
            "Weight:",
            float(edge_item.weight),
            -1e9,
            1e9,
            2,
        )
        if not ok:
            return
        self._begin_mutation()
        try:
            if self.graph.directed and edge_item.bidirectional:
                self.graph.update_edge(edge_item.start_node.node_id, edge_item.end_node.node_id, weight)
                self.graph.update_edge(edge_item.end_node.node_id, edge_item.start_node.node_id, weight)
            else:
                self.graph.update_edge(edge_item.start_node.node_id, edge_item.end_node.node_id, weight)
            edge_item.set_weight(weight)
            self.graph_changed.emit()
            self._commit_mutation("Edit weight")
        except Exception as exc:
            self._drop_pending()
            self.status_message.emit(str(exc), "error")

    def _remove_node_item(self, node_item):
        if not self.graph:
            return
        self._clear_message()
        self._begin_mutation()
        # Flush pending tweens onto still-live items before any removal.
        self.animator.cancel_all()
        node_id = node_item.node_id
        edges_to_remove = [
            edge_key for edge_key, edge in self.edges.items()
            if edge.start_node.node_id == node_id or edge.end_node.node_id == node_id
        ]
        try:
            self.graph.remove_node(node_id)
        except Exception as exc:
            self._drop_pending()
            self.status_message.emit(str(exc), "error")
            return
        for edge_key in edges_to_remove:
            edge_item = self.edges.pop(edge_key, None)
            if edge_item:
                edge_item.dispose()
        self.nodes.pop(node_id, None)
        # Stop pulse before removal. The label carries no effect (Phase 1), so only
        # the node's own glow effect is cleared (sanctioned end-of-life).
        node_item.stop_pulse()
        node_item.setGraphicsEffect(None)
        if node_item.scene() is self.scene:
            self.scene.removeItem(node_item)
        self.graph_changed.emit()
        self._commit_mutation("Delete node")

    def _remove_edge_item(self, edge_item):
        if not self.graph:
            return
        self._clear_message()
        self._begin_mutation()
        self.animator.cancel_all()
        start_id = edge_item.start_node.node_id
        end_id = edge_item.end_node.node_id
        try:
            if self.graph.directed and edge_item.bidirectional:
                self.graph.remove_edge(start_id, end_id)
                self.graph.remove_edge(end_id, start_id)
            else:
                self.graph.remove_edge(start_id, end_id)
        except Exception as exc:
            self._drop_pending()
            self.status_message.emit(str(exc), "error")
            return
        if edge_item.bidirectional and self.graph.directed:
            edge_key = tuple(sorted([start_id, end_id]))
        else:
            edge_key = self._edge_key(start_id, end_id)
        edge_item = self.edges.pop(edge_key, edge_item)
        if edge_item:
            edge_item.dispose()
        self.graph_changed.emit()
        self._commit_mutation("Delete edge")

    def _delete_items(self, edges, nodes):
        if not self.graph:
            return
        self._clear_message()
        self._begin_mutation()
        self.animator.cancel_all()

        # Remove edges first to avoid stale references during node deletion.
        for edge_item in edges:
            start_id = edge_item.start_node.node_id
            end_id = edge_item.end_node.node_id
            try:
                if self.graph.directed and edge_item.bidirectional:
                    self.graph.remove_edge(start_id, end_id)
                    self.graph.remove_edge(end_id, start_id)
                else:
                    self.graph.remove_edge(start_id, end_id)
            except Exception:
                continue

        # Remove nodes (this also removes connected edges in the graph).
        for node_item in nodes:
            node_id = node_item.node_id
            if node_id not in self.graph.get_nodes():
                continue
            try:
                self.graph.remove_node(node_id)
            except Exception:
                continue

        # Rebuild the scene once to avoid deleting items mid-paint.
        self.set_graph(self.graph)
        # Diff-guarded: if every removal failed (nothing changed) nothing pushes.
        self._commit_mutation("Delete selection")

    def _edge_key(self, start, end):
        if self.graph and not self.graph.directed:
            return tuple(sorted([start, end]))
        return (start, end)

    def _edge_item_for(self, start, end):
        if not self.graph:
            return None
        if self.graph.directed:
            edge = self.edges.get((start, end))
            if edge:
                return edge
            fallback = self.edges.get(tuple(sorted([start, end])))
            if fallback and fallback.bidirectional:
                return fallback
            return None
        return self.edges.get(tuple(sorted([start, end])))

    def get_node_ids(self):
        if self.graph:
            return self.graph.get_nodes()
        return list(self.nodes.keys())

    # ------------------------------------------------------------------
    # Rendering — the view is a pure renderer of controller RenderFrames.
    # ------------------------------------------------------------------
    def render_frame(self, frame):
        """Render a controller frame.

        State is always written by the idempotent Phase-1 ``set_state`` pass, so
        scrubbing/seeking/loading is instantly correct. A forward step layers
        additive emphasis (pop, travel dot, or the final path stagger) on top.
        """
        if not frame.forward_step:
            # Scrub / seek / load: flush emphasis, then plain instant pass.
            self.animator.cancel_all()
            self._render_nodes(frame)
            self._render_edges(frame)
            return

        if frame.is_final and frame.path:
            # Dim non-path items instantly, then stagger the path into "final".
            if current_theme().animation.final_reveal == "instant":
                self._render_nodes(frame)
                self._render_edges(frame)
            else:
                self._render_final_staggered(frame)
            return

        # Ordinary forward step: instant state pass + additive emphasis.
        self._render_nodes(frame)
        self._render_edges(frame)
        self._animate_step_delta(frame)

    def _animate_step_delta(self, frame):
        step = frame.step
        if not step:
            return
        kind = step.get("kind")
        if kind == "visit":
            # A newly-settled current node gets a pop of emphasis.
            current = frame.current
            if current is not None and current in self.nodes:
                self.animator.pop_scale(self.nodes[current], self.animator.scaled(300))
        elif kind == "relax":
            # F1: the travel effect fires ONLY when the step carries an edge that
            # resolves to a live item (bellman-ford's source seed has edge=None).
            edge = step.get("edge")
            if edge is not None:
                item = self._edge_item_for(edge[0], edge[1])
                if item is not None:
                    theme = current_theme()
                    animation = theme.animation
                    duration = self.animator.scaled(round(340 / animation.motion_scale))
                    travel_color = (
                        animation.travel_color
                        or (
                            theme.warning
                            if animation.relax_effect == "lightning"
                            else theme.edge_style("relaxed").stroke
                        )
                    )
                    impact_color = animation.impact_color or travel_color
                    badge_flash_color = animation.badge_flash_color or impact_color
                    if animation.relax_effect == "lightning":
                        self.animator.lightning(
                            self.scene, item.curve_path(), travel_color, duration
                        )
                    elif animation.relax_effect == "comet":
                        self.animator.travel_dot(
                            self.scene, item.curve_path(), travel_color, duration
                        )
                    # The weight number flashes the travel/impact color while it passes.
                    chip = item.label
                    flash_color = badge_flash_color

                    def flash(progress, chip=chip, flash_color=flash_color):
                        if sip.isdeleted(chip):
                            return
                        chip.set_flash(None if progress >= 1.0 else flash_color)

                    self.animator.animate_color(("chip-flash", id(item)), duration, flash)
                    # Pop/flash the destination only near impact, when the
                    # travel animation visually reaches the receiving node.
                    target_item = self.nodes.get(step.get("node"))
                    if target_item is not None:
                        def impact_pop(progress, node=target_item):
                            if sip.isdeleted(node):
                                return
                            if progress < IMPACT_FLASH_START:
                                node.setScale(1.0)
                                return
                            local = (progress - IMPACT_FLASH_START) / (1.0 - IMPACT_FLASH_START)
                            if local <= 0.5:
                                node.setScale(1.0 + 0.12 * (local / 0.5))
                            else:
                                node.setScale(1.12 - 0.12 * ((local - 0.5) / 0.5))

                        self.animator.animate_color(
                            ("node-impact-pop", id(target_item)),
                            duration,
                            impact_pop,
                        )
                        if animation.impact_ring:
                            def flash_ring(progress, node=target_item, impact_color=impact_color):
                                if sip.isdeleted(node):
                                    return
                                node.set_ring_flash(
                                    impact_color if IMPACT_FLASH_START <= progress < 1.0 else None
                                )

                            self.animator.animate_color(
                                ("node-ring-flash", id(target_item)),
                                duration,
                                flash_ring,
                            )
                        if animation.impact_badge:
                            def flash_badge(progress, node=target_item, flash_color=badge_flash_color):
                                if sip.isdeleted(node):
                                    return
                                node.set_badge_flash(
                                    flash_color if IMPACT_FLASH_START <= progress < 1.0 else None
                                )

                            self.animator.animate_color(
                                ("node-badge-flash", id(target_item)),
                                duration,
                                flash_badge,
                            )

    def _render_final_staggered(self, frame):
        final_node_ids = set(frame.path)
        final_items = set()
        for start, end in zip(frame.path, frame.path[1:]):
            item = self._edge_item_for(start, end)
            if item is not None:
                final_items.add(item)

        # Badges reflect final distances for every node (never animated).
        for node_id, node_item in self.nodes.items():
            distance = frame.distances.get(node_id, INF)
            node_item.set_distance_text(format_distance(distance))
            node_item.set_badge_emphasis(False)
            if node_id not in final_node_ids:
                node_item.set_state("not_in_path" if distance < INF else "default")

        tree_items = self._items_for(frame.tree_edges)
        considered_items = self._items_for(frame.considered_edges) - tree_items

        # Non-path edges resolve before the stagger: searched/rejected edges keep
        # a blue-grey trace, untouched edges stay dark, path edges wait for final.
        for edge_item in self.edges.values():
            if edge_item in final_items:
                continue
            if edge_item in tree_items or edge_item in considered_items:
                edge_item.set_state("considered")
            else:
                edge_item.set_state("default")

        # Stagger the path node/edge "final" reveal source -> target.
        callbacks = []
        path = frame.path
        for index, node_id in enumerate(path):
            node_item = self.nodes.get(node_id)
            if node_item is not None:
                callbacks.append(lambda n=node_item: (not sip.isdeleted(n)) and n.set_state("final"))
            if index < len(path) - 1:
                item = self._edge_item_for(path[index], path[index + 1])
                if item is not None:
                    callbacks.append(lambda e=item: (not sip.isdeleted(e)) and e.set_state("final"))
        if callbacks:
            self.animator.run_stagger(callbacks, step_ms=self.animator.scaled(120))

    def _render_nodes(self, frame):
        visited = set(frame.visited)
        for node_id, node_item in self.nodes.items():
            distance = frame.distances.get(node_id, INF)
            if frame.is_final and frame.path and node_id in frame.path:
                state = "final"
            elif frame.is_final and frame.path:
                # Final target view has three tiers: answer path, searched but
                # not in the answer, and untouched.
                state = "not_in_path" if distance < INF else "default"
            elif frame.is_final:
                state = "unreachable" if distance == INF else "not_in_path"
            elif node_id == frame.current:
                state = "current"
            elif node_id in visited:
                state = "visited"
            elif distance < INF:
                state = "frontier"
            else:
                state = "default"
            node_item.set_state(state)
            node_item.set_distance_text(format_distance(distance))
            node_item.set_badge_emphasis(False)

    def _render_edges(self, frame):
        # F1/F2: resolve ORIENTED event tuples to edge ITEMS, then rank by item
        # identity. Item-level subtraction kills undirected orientation ghosts.
        final_items = set()
        if frame.is_final and frame.path:
            for start, end in zip(frame.path, frame.path[1:]):
                item = self._edge_item_for(start, end)
                if item is not None:
                    final_items.add(item)

        tree_items = self._items_for(frame.tree_edges)
        considered_items = self._items_for(frame.considered_edges) - tree_items

        for edge_item in self.edges.values():
            if frame.is_final and frame.path:
                if edge_item in final_items:
                    state = "final"
                elif edge_item in tree_items or edge_item in considered_items:
                    state = "considered"
                else:
                    state = "default"
            elif frame.is_final:
                start_distance = frame.distances.get(edge_item.start_node.node_id, INF)
                end_distance = frame.distances.get(edge_item.end_node.node_id, INF)
                if start_distance == INF and end_distance == INF:
                    state = "unreachable"
                else:
                    state = "not_in_path"
            elif edge_item in tree_items:
                state = "relaxed"
            elif edge_item in considered_items:
                state = "considered"
            else:
                state = "default"
            edge_item.set_state(state)

    def _items_for(self, oriented_edges):
        items = set()
        for start, end in oriented_edges:
            item = self._edge_item_for(start, end)
            if item is not None:
                items.add(item)
        return items

    def clear_run_decorations(self):
        self.animator.cancel_all()
        for node in self.nodes.values():
            node.set_state("default")
            node.set_distance_text(None)
            node.set_badge_emphasis(False)
        for edge in self.edges.values():
            edge.set_state("default")

    def set_badges_visible(self, visible):
        for node in self.nodes.values():
            node.set_badge_visible(bool(visible))

    def apply_layout(self, positions, animate=True, duration=600):
        """Move nodes to ``positions`` (node_id -> (x, y)).

        ``animate=True`` runs a single 0->1 tween through the AnimationCoordinator
        (key "layout"): each tick lerps every node's ``setPos``, which drives
        ``itemChange -> _on_node_moved`` so the model and edges stay synced for
        free. The coordinator's finalize (``apply(1.0)``) snaps every node to its
        exact target on natural finish OR on cancel. ``graph_changed`` is emitted
        EXACTLY ONCE after the tween finishes — positions feed A*'s heuristic, so
        the run must invalidate, but a per-tick emit would unload it 60x/s — then
        ``fit_to_content()`` reframes. ``animate=False`` snaps directly.
        """
        targets = {
            node_id: (float(x), float(y))
            for node_id, (x, y) in positions.items()
            if node_id in self.nodes
        }
        if not targets:
            return

        # One command per layout: snapshot before positions move, commit once the
        # positions land (immediately for animate=False, in the finalize below for
        # the tween). Diff-guarded, so a layout that changes nothing pushes nothing.
        self._begin_mutation()

        if not animate:
            for node_id, (x, y) in targets.items():
                item = self.nodes.get(node_id)
                if item is not None and not sip.isdeleted(item):
                    item.setPos(QPointF(x, y))
            self.fit_to_content()
            self.graph_changed.emit()
            self._commit_mutation("Apply layout")
            return

        starts = {}
        for node_id in targets:
            pos = self.nodes[node_id].pos()
            starts[node_id] = (pos.x(), pos.y())

        completed = {"done": False}

        def complete_once():
            # Completion rides the tween's apply(1.0), which the coordinator
            # guarantees on BOTH natural finish and cancellation (finalize) —
            # so a theme switch / scrub / set_graph mid-layout still commits
            # the mutation, invalidates the run, and stays undoable. The flag
            # dedupes the natural-finish case (last tick + finalize both land
            # on progress 1.0).
            if completed["done"]:
                return
            completed["done"] = True
            self.fit_to_content()
            self.graph_changed.emit()
            self._commit_mutation("Apply layout")

        def apply(progress):
            for node_id, (end_x, end_y) in targets.items():
                item = self.nodes.get(node_id)
                if item is None or sip.isdeleted(item):
                    continue
                start_x, start_y = starts[node_id]
                item.setPos(QPointF(
                    start_x + (end_x - start_x) * progress,
                    start_y + (end_y - start_y) * progress,
                ))
            if progress >= 1.0:
                complete_once()

        self.animator.animate_float("layout", 0.0, 1.0, duration, apply)

    def get_edge_weight(self, start, end):
        edge = self._edge_item_for(start, end)
        if edge:
            return edge.weight
        return 0
