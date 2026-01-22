from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsDropShadowEffect, QPushButton, QHBoxLayout, QWidget, QInputDialog, QGraphicsSimpleTextItem, QSizePolicy
from PyQt6.QtCore import Qt, QPointF, QTimer, QRectF, QPoint, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QLinearGradient, QWheelEvent, QMouseEvent, QResizeEvent
from .graph_node import GraphNode
from .graph_edge import GraphEdge
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm
from dijkstra_dashboard.core.algorithms.runner import apply_step, init_state
from dijkstra_dashboard.core.errors import AlgorithmError
from dijkstra_dashboard.core.graph import Graph
import math

class GraphView(QGraphicsView):
    graph_changed = pyqtSignal()
    message_changed = pyqtSignal(str)
    playback_finished = pyqtSignal()

    def __init__(self, status_panel=None):
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
        # Initial scene rect - will be updated on resize
        self.scene.setSceneRect(-400, -300, 800, 600)
        
        # Enhanced background with gradient
        gradient = QLinearGradient(0, 0, 0, 600)
        gradient.setColorAt(0, QColor(10, 10, 10))
        gradient.setColorAt(1, QColor(20, 20, 20))
        self.setBackgroundBrush(QBrush(gradient))
        
        # Enable node dragging; use right-click drag for panning
        self.setDragMode(self.DragMode.NoDrag)
        
        # Zoom settings
        self.zoom_level = 1.0
        self.zoom_step = 0.2  # 20% zoom step
        
        # Create zoom controls
        self.create_zoom_controls()
        
        # Store nodes and edges
        self.nodes = {}
        self.edges = {}
        self.graph = None
        self.pending_edge_start = None
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_step)
        self.animation_timer.setInterval(500)
        self.current_path = []
        self.steps = []
        self.step_index = 0
        self.visited_order = []
        self.final_visited_order = []
        self.step_state = None
        self.ready_params = None
        self.finalized = False
        
        # Status panel reference
        self.status_panel = status_panel
        
        # Setup the graph
        self.setup_graph()
        
    def create_zoom_controls(self):
        # Create a container widget for zoom controls
        controls_widget = QWidget()
        controls_layout = QHBoxLayout()
        controls_widget.setLayout(controls_layout)
        
        # Zoom out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        # Zoom reset button
        zoom_reset_btn = QPushButton("100%")
        zoom_reset_btn.setFixedSize(50, 30)
        zoom_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        zoom_reset_btn.clicked.connect(self.reset_zoom)
        
        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
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
        
    def zoom_in(self):
        self.zoom_level += self.zoom_step
        self.set_zoom()
        
    def zoom_out(self):
        self.zoom_level = max(0.2, self.zoom_level - self.zoom_step)
        self.set_zoom()
        
    def reset_zoom(self):
        self.zoom_level = 1.0
        self.set_zoom()
        
    def set_zoom(self):
        # Reset transform
        self.resetTransform()
        # Apply new zoom level
        self.scale(self.zoom_level, self.zoom_level)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        # Update scene rect to match view size, centered at origin
        w = event.size().width()
        h = event.size().height()
        self.scene.setSceneRect(-w / 2, -h / 2, w, h)
        # Update edge label positions since scene bounds changed
        for edge in self.edges.values():
            edge.update_position()

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, QGraphicsSimpleTextItem):
                parent = item.parentItem()
                if isinstance(parent, GraphNode):
                    item = parent
            if isinstance(item, GraphNode) and (
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
                or event.modifiers() & Qt.KeyboardModifier.AltModifier
            ):
                self.handle_node_click(item)
                return
            self.setDragMode(self.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, QGraphicsSimpleTextItem):
                parent = item.parentItem()
                if isinstance(parent, GraphNode):
                    item = parent
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
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if not isinstance(item, GraphNode):
                    self.add_node_at(event.position().toPoint())
                    return

        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.setDragMode(self.DragMode.NoDrag)
        super().mouseReleaseEvent(event)

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
        self.graph = graph
        self.pending_edge_start = None
        self._clear_message()
        self._invalidate_steps()

        # Clear old scene
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

        self.graph_changed.emit()

    def get_graph(self):
        return self.graph

    def get_node_items(self):
        if self.graph:
            return [(node.id, node.label) for node in self.graph.nodes()]
        return [(node_id, node.name) for node_id, node in self.nodes.items()]

    def add_node_at(self, view_pos):
        if not self.graph:
            return
        self._clear_message()
        self._invalidate_steps()
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

    def handle_node_click(self, node_item):
        node_id = node_item.node_id
        if self.pending_edge_start is None:
            self.pending_edge_start = node_id
            if self.status_panel:
                self.status_panel.update_status(
                    f"Selected node {node_item.name} for edge start."
                )
            return

        if self.pending_edge_start == node_id:
            self.pending_edge_start = None
            if self.status_panel:
                self.status_panel.update_status("Edge start cleared.")
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
                self.set_graph(self.graph)
                if self.status_panel:
                    direction = "->" if self.graph.directed else "--"
                    start_label = self.graph.get_node_label(self.pending_edge_start)
                    end_label = self.graph.get_node_label(node_id)
                    action = "Updated" if updated else "Added"
                    self.status_panel.update_status(
                        f"{action} edge {start_label} {direction} {end_label} ({weight})."
                    )
            except Exception as exc:
                if self.status_panel:
                    self.status_panel.update_status(str(exc), "#ff5555")

        self.pending_edge_start = None

    def _on_node_moved(self, node_item, new_pos):
        node_id = node_item.node_id
        if self.graph:
            self.graph.set_node_position(node_id, new_pos.x(), new_pos.y())
        for edge in self.edges.values():
            if edge.start_node is node_item or edge.end_node is node_item:
                edge.update_position()

    def _clear_message(self):
        self.message_changed.emit("")

    def _highlight_no_path(self):
        for node in self.nodes.values():
            node.set_state("unused")
        for edge in self.edges.values():
            edge.set_state("unused")
            edge.set_cost_label_color(QColor("red"))

    def _invalidate_steps(self):
        self.animation_timer.stop()
        self.current_path = []
        self.steps = []
        self.step_index = 0
        self.visited_order = []
        self.final_visited_order = []
        self.step_state = None
        self.ready_params = None
        self.finalized = False

    def _label_lookup(self, node_id):
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
        if isinstance(item, QGraphicsSimpleTextItem):
            for edge in self.edges.values():
                if edge.label is item:
                    return edge
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
            if self.status_panel:
                self.status_panel.update_status("Node label cannot be empty.", "#ff5555")
            return
        for node in self.graph.nodes():
            if node.label == label and node.id != node_item.node_id:
                if self.status_panel:
                    self.status_panel.update_status(
                        f"Node label '{label}' is already in use.",
                        "#ff5555",
                    )
                return
        try:
            self.graph.rename_node(node_item.node_id, label)
            node_item.set_label(label)
            self._invalidate_steps()
            self.graph_changed.emit()
        except Exception as exc:
            if self.status_panel:
                self.status_panel.update_status(str(exc), "#ff5555")

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
        try:
            if self.graph.directed and edge_item.bidirectional:
                self.graph.update_edge(edge_item.start_node.node_id, edge_item.end_node.node_id, weight)
                self.graph.update_edge(edge_item.end_node.node_id, edge_item.start_node.node_id, weight)
            else:
                self.graph.update_edge(edge_item.start_node.node_id, edge_item.end_node.node_id, weight)
            edge_item.set_weight(weight)
            self._invalidate_steps()
        except Exception as exc:
            if self.status_panel:
                self.status_panel.update_status(str(exc), "#ff5555")

    def _remove_node_item(self, node_item):
        if not self.graph:
            return
        self._clear_message()
        node_id = node_item.node_id
        edges_to_remove = [
            edge_key for edge_key, edge in self.edges.items()
            if edge.start_node.node_id == node_id or edge.end_node.node_id == node_id
        ]
        try:
            self.graph.remove_node(node_id)
        except Exception as exc:
            if self.status_panel:
                self.status_panel.update_status(str(exc), "#ff5555")
            return
        for edge_key in edges_to_remove:
            edge_item = self.edges.pop(edge_key, None)
            if edge_item:
                edge_item.dispose()
        self.nodes.pop(node_id, None)
        # Stop animation and clear graphics effects on node before removal
        if hasattr(node_item, 'pulse_animation'):
            node_item.pulse_animation.stop()
        if hasattr(node_item, 'label') and node_item.label:
            node_item.label.setGraphicsEffect(None)
        node_item.setGraphicsEffect(None)
        if node_item.scene() is self.scene:
            self.scene.removeItem(node_item)
        self._invalidate_steps()

    def _remove_edge_item(self, edge_item):
        if not self.graph:
            return
        self._clear_message()
        start_id = edge_item.start_node.node_id
        end_id = edge_item.end_node.node_id
        try:
            if self.graph.directed and edge_item.bidirectional:
                self.graph.remove_edge(start_id, end_id)
                self.graph.remove_edge(end_id, start_id)
            else:
                self.graph.remove_edge(start_id, end_id)
        except Exception as exc:
            if self.status_panel:
                self.status_panel.update_status(str(exc), "#ff5555")
            return
        if edge_item.bidirectional and self.graph.directed:
            edge_key = tuple(sorted([start_id, end_id]))
        else:
            edge_key = self._edge_key(start_id, end_id)
        edge_item = self.edges.pop(edge_key, edge_item)
        if edge_item:
            edge_item.dispose()
        self._invalidate_steps()

    def _delete_items(self, edges, nodes):
        if not self.graph:
            return
        self._clear_message()

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
            
    def prepare_visualization(self, start_node, target_node, force=False):
        if (not force and self.ready_params == (start_node, target_node)
                and self.steps and self.step_index < len(self.steps)):
            return True

        # Reset all nodes and edges to default state
        self.reset()
        self.visited_order = []
        self.final_visited_order = []
        self.ready_params = (start_node, target_node)
        self.finalized = False

        if not self.graph:
            return False

        algorithm = DijkstraAlgorithm()
        try:
            result = algorithm.solve(self.graph, {
                "start": start_node,
                "target": target_node,
            })
        except AlgorithmError as exc:
            if self.status_panel:
                self.status_panel.update_status(str(exc), "#ff5555")
            return False

        self.current_path = result.path or []
        self.steps = list(algorithm.iter_steps(self.graph, {
            "start": start_node,
            "target": target_node,
        }))
        self.step_index = 0
        self.final_visited_order = result.visited_order
        self.step_state = init_state(self.graph.get_nodes())
        self.finalized = False

        if not self.current_path:
            self._highlight_no_path()
            self.message_changed.emit("No path found.")
            if self.status_panel:
                self.status_panel.update_status("No path found.", "#ff5555")
            return False

        return True

    def start_visualization(self, start_node, target_node):
        if not self.prepare_visualization(start_node, target_node, force=True):
            return
        self.start_playback()

    def start_playback(self):
        if not self.steps:
            return
        if not self.animation_timer.isActive():
            self.animation_timer.start()

    def pause_playback(self):
        if self.animation_timer.isActive():
            self.animation_timer.stop()

    def step_once(self, start_node, target_node):
        self.pause_playback()
        if not self.prepare_visualization(start_node, target_node, force=False):
            return
        if self.steps:
            self.animate_step()

    def set_animation_interval(self, interval_ms):
        self.animation_timer.setInterval(max(50, int(interval_ms)))

    def animate_step(self):
        if self.step_index >= len(self.steps):
            self._finalize_visualization()
            return

        step = self.steps[self.step_index]
        kind = step.get("kind")

        if self.step_state is not None:
            apply_step(self.step_state, step)
            self.visited_order = list(self.step_state.visited)

        if kind == "visit":
            node_id = step.get("node")
            if node_id in self.nodes:
                self.nodes[node_id].highlight(is_final_path=False)
                if node_id not in self.visited_order:
                    self.visited_order.append(node_id)
        elif kind == "relax":
            edge_key = step.get("edge") or (None, None)
            start, end = edge_key
            if start and end:
                edge = self._edge_item_for(start, end)
                if edge:
                    edge.highlight(is_final_path=False)

        # Update status panel
        if self.status_panel:
            self.status_panel.show_path(
                self.current_path,
                self.get_total_distance(),
                self.visited_order,
                self.get_edge_weight,
                self._label_lookup,
            )

        self.step_index += 1
        if self.step_index >= len(self.steps):
            self._finalize_visualization()

    def _finalize_visualization(self):
        if self.finalized:
            return
        if not self.current_path:
            return
        self.finalized = True

        # After animation completes, highlight the final path in green
        for edge in self.edges.values():
            edge.set_state("unused")
            edge.set_cost_label_color(QColor("red"))

        for node in self.nodes.values():
            node.set_state("unused")

        for i in range(len(self.current_path) - 1):
            current = self.current_path[i]
            next_node = self.current_path[i + 1]
            self.nodes[current].set_state("final")
            edge = self._edge_item_for(current, next_node)
            if edge:
                edge.highlight(is_final_path=True)
                edge.set_cost_label_color(QColor("lime"))

        # Highlight the last node in the final path
        self.nodes[self.current_path[-1]].set_state("final")

        self.animation_timer.stop()
        self.playback_finished.emit()

        # Final status update once animation is fully complete
        if self.status_panel:
            visited_order = self.final_visited_order or self.current_path
            self.status_panel.show_path(
                self.current_path,
                self.get_total_distance(),
                visited_order,
                self.get_edge_weight,
                self._label_lookup,
            )

    def get_total_distance(self):
        total = 0
        for i in range(len(self.current_path) - 1):
            current = self.current_path[i]
            next_node = self.current_path[i + 1]
            edge = self._edge_item_for(current, next_node)
            if edge:
                total += edge.weight
        return total

    def get_edge_weight(self, start, end):
        edge = self._edge_item_for(start, end)
        if edge:
            return edge.weight
        return 0

    def reset(self):
        # Stop any ongoing animation
        self.animation_timer.stop()
        self.current_path = []
        self.steps = []
        self.step_index = 0
        self.visited_order = []
        self.final_visited_order = []
        self.step_state = None
        self.pending_edge_start = None
        self._clear_message()
        self.ready_params = None
        self.finalized = False

        # Reset all nodes and edges
        for node in self.nodes.values():
            node.reset()
        for edge in self.edges.values():
            edge.reset()

        # Clear status panel
        if self.status_panel:
            self.status_panel.clear()
