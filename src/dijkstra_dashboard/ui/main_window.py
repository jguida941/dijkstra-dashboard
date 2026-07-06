import json

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QLabel
from PyQt6.QtGui import QAction, QActionGroup
from .graph_view import GraphView
from .controls_panel import ControlsPanel
from .status_panel import StatusPanel
from .playback_controller import PlaybackController
from .theme import current_theme, get_theme_manager, make_app_icon
from dijkstra_dashboard.core.graph import Graph
from dijkstra_dashboard.core.algorithms import list_algorithm_specs

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dijkstra Path Visualizer")
        self.setMinimumSize(1000, 700)
        self.graph_path = None

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel (graph and controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Create and add controls panel
        self.controls_panel = ControlsPanel()
        left_layout.addWidget(self.controls_panel)

        self.notice_label = QLabel("")
        self.notice_label.setObjectName("noticeLabel")
        self.notice_label.setVisible(False)
        left_layout.addWidget(self.notice_label)

        # Right panel (status)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Create and add status panel
        self.status_panel = StatusPanel()
        right_layout.addWidget(self.status_panel)

        # Create and add graph view
        self.graph_view = GraphView()
        left_layout.addWidget(self.graph_view)

        # Playback controller owns the trace + replay state; the view renders frames.
        self.playback = PlaybackController(parent=self)

        self.controls_panel.set_algorithms(
            [(spec.name, spec.name.capitalize()) for spec in list_algorithm_specs()]
        )
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        if self.graph_view.get_graph():
            self._set_directed_toggle(self.graph_view.get_graph().directed)
        self.status_panel.update_status(
            "Shift+click empty space to add a node. "
            "Ctrl/Option/Shift+click two nodes to add an edge weight. "
            "Directed mode uses selection order for arrows. "
            "Select a node/edge and press Delete to remove. "
            "Right-drag to pan."
        )

        # Add panels to main layout
        main_layout.addWidget(left_panel, stretch=2)
        main_layout.addWidget(right_panel, stretch=1)

        # Menu actions
        self.setup_menus()

        # Connect signals
        self.controls_panel.run_button.clicked.connect(self.start_visualization)
        self.controls_panel.reset_button.clicked.connect(self.reset_visualization)
        self.controls_panel.step_button.clicked.connect(self.step_visualization)
        self.controls_panel.step_back_button.clicked.connect(self.step_back)
        self.controls_panel.play_button.clicked.connect(self.toggle_playback)
        self.controls_panel.speed_slider.valueChanged.connect(self.on_speed_changed)
        self.controls_panel.timeline_slider.valueChanged.connect(self.on_timeline_changed)
        self.controls_panel.help_button.clicked.connect(self.show_controls_help)
        self.controls_panel.directed_toggle.toggled.connect(self.on_directed_toggled)
        self.graph_view.graph_changed.connect(self.on_graph_changed)
        self.graph_view.message_changed.connect(self.on_message_changed)
        self.graph_view.status_message.connect(self.status_panel.update_status)

        # Playback controller drives all run rendering / status.
        self.playback.run_loaded.connect(self.on_run_loaded)
        self.playback.frame_changed.connect(self.on_frame_changed)
        self.playback.playing_changed.connect(self.on_playing_changed)
        self.playback.run_error.connect(self.on_run_error)
        self.playback.run_finished.connect(self.on_run_finished)

        manager = get_theme_manager()
        manager.theme_changed.connect(self.apply_theme)
        manager.theme_changed.connect(self.status_panel.refresh_theme)
        self.apply_theme(current_theme())

        self.on_speed_changed(self.controls_panel.speed_slider.value())

    def on_graph_changed(self):
        # Every mutation path emits graph_changed exactly once (F5). The handler
        # must be idempotent and cheap (F6): drop the stale run and reset the view.
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self.playback.unload()
        self.graph_view.clear_run_decorations()
        self.controls_panel.clear_timeline()

    def _set_directed_toggle(self, value):
        toggle = self.controls_panel.directed_toggle
        blocked = toggle.blockSignals(True)
        toggle.setChecked(bool(value))
        toggle.blockSignals(blocked)

    def on_message_changed(self, message):
        message = message.strip()
        if message:
            self.notice_label.setText(message)
            self.notice_label.setVisible(True)
        else:
            self.notice_label.setVisible(False)

    def setup_menus(self):
        file_menu = self.menuBar().addMenu("File")

        open_action = QAction("Open Graph...", self)
        open_action.triggered.connect(self.open_graph)
        file_menu.addAction(open_action)

        save_action = QAction("Save Graph", self)
        save_action.triggered.connect(self.save_graph)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Graph As...", self)
        save_as_action.triggered.connect(self.save_graph_as)
        file_menu.addAction(save_as_action)

        view_menu = self.menuBar().addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        manager = get_theme_manager()
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.theme_actions = {}
        for theme_id in manager.theme_ids():
            theme = manager.THEMES[theme_id]
            action = QAction(theme.name, self)
            action.setCheckable(True)
            action.setData(theme_id)
            action.setChecked(theme_id == manager.current.id)
            action.triggered.connect(
                lambda checked, selected_theme_id=theme_id: manager.set_theme(selected_theme_id, persist=True)
                if checked else None
            )
            self.theme_action_group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[theme_id] = action

        manager.theme_changed.connect(self._sync_theme_actions)

        view_menu.addSeparator()
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.triggered.connect(self.graph_view.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.triggered.connect(self.graph_view.zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.triggered.connect(self.graph_view.reset_zoom)
        view_menu.addAction(reset_zoom_action)

        fit_action = QAction("Fit to Graph", self)
        fit_action.triggered.connect(self.graph_view.fit_to_content)
        view_menu.addAction(fit_action)

        help_menu = self.menuBar().addMenu("Help")
        controls_action = QAction("Controls...", self)
        controls_action.triggered.connect(self.show_controls_help)
        help_menu.addAction(controls_action)

    def apply_theme(self, theme):
        app = QApplication.instance()
        if app is not None:
            app.setPalette(theme.palette())
            app.setStyleSheet(theme.qss())
        self.setWindowIcon(make_app_icon(theme))

    def _sync_theme_actions(self, theme):
        for theme_id, action in self.theme_actions.items():
            blocked = action.blockSignals(True)
            action.setChecked(theme_id == theme.id)
            action.blockSignals(blocked)

    def _disambiguated_labels(self, graph, start_node, target_node):
        label_counts: dict[str, int] = {}
        for node in graph.nodes():
            label_counts[node.label] = label_counts.get(node.label, 0) + 1
        start_label = graph.get_node_label(start_node)
        target_label = graph.get_node_label(target_node)
        if label_counts.get(start_label, 0) > 1:
            start_label = f"{start_label} ({start_node})"
        if label_counts.get(target_label, 0) > 1:
            target_label = f"{target_label} ({target_node})"
        return start_label, target_label

    def _announce_run(self, graph, start_node, target_node, algorithm_name):
        start_label, target_label = self._disambiguated_labels(graph, start_node, target_node)
        algo_display = self.controls_panel.algorithm_combo.currentText() or algorithm_name
        self.status_panel.clear()
        self.status_panel.update_status(
            f"Running {algo_display} from {start_label} to {target_label}"
        )

    def _load_run(self):
        """Load the current graph/params into the controller. Returns True on load."""
        start_node = self.controls_panel.get_start_node_id()
        target_node = self.controls_panel.get_target_node_id()
        graph = self.graph_view.get_graph()
        if graph is None:
            return False
        algorithm_name = self.controls_panel.get_algorithm_name()
        if not self.playback.load_run(
            graph, algorithm_name, {"start": start_node, "target": target_node}
        ):
            return False
        self._announce_run(graph, start_node, target_node, algorithm_name)
        return True

    def _ensure_loaded(self):
        if self.playback.is_loaded:
            return True
        return self._load_run()

    def start_visualization(self):
        # Run always reloads from scratch, then plays (Q9).
        if self._load_run():
            self.playback.play()

    def step_visualization(self):
        if self._ensure_loaded():
            self.playback.step_forward()

    def step_back(self):
        self.playback.step_back()

    def toggle_playback(self):
        # Play toggles; loads first if needed, but never autoplays on load.
        if self._ensure_loaded():
            self.playback.toggle()

    def reset_visualization(self):
        self.playback.unload()
        self.graph_view.clear_run_decorations()
        self.controls_panel.clear_timeline()
        self.status_panel.clear()
        self.controls_panel.play_button.setText("Play")

    def on_speed_changed(self, value):
        interval_ms = 1100 - (value * 100)
        self.playback.set_interval(interval_ms)
        self.graph_view.set_tween_interval(interval_ms)

    def on_timeline_changed(self, value):
        self.playback.seek(value)

    def on_run_loaded(self, meta):
        self.controls_panel.set_timeline(meta["total"])

    def on_frame_changed(self, frame):
        self.graph_view.render_frame(frame)
        self.controls_panel.set_timeline_index(frame.index)

    def on_playing_changed(self, playing):
        self.controls_panel.play_button.setText("Pause" if playing else "Play")

    def on_run_error(self, message):
        self.status_panel.update_status(message, "error")
        self.on_message_changed(message)

    def on_run_finished(self, summary):
        path = summary.get("path")
        if path:
            self.status_panel.show_path(
                list(path),
                summary.get("distance"),
                list(summary.get("visited_order", ())),
                self.graph_view.get_edge_weight,
                self.graph_view.label_lookup,
            )
            self.status_panel.update_status(
                f"Visits: {summary['visits']} · "
                f"Relaxations: {summary['relaxations']} · "
                f"Comparisons: {summary['comparisons']}",
                "text",
            )
        else:
            self.on_message_changed("No path found.")
            self.status_panel.update_status("No path found.", "error")

    def on_directed_toggled(self, checked):
        graph = self.graph_view.get_graph()
        if not graph:
            return
        graph.set_directed(bool(checked))
        self.graph_view.set_graph(graph)
        if self.status_panel:
            if checked:
                self.status_panel.update_status(
                    "Directed mode enabled (edges use node order; add reverse edges if needed)."
                )
            else:
                self.status_panel.update_status("Undirected mode enabled (one weight per edge).")

    def show_controls_help(self):
        QMessageBox.information(
            self,
            "Controls",
            "Graph editing:\n"
            "- Shift + click empty space: add node\n"
            "- Ctrl/Option/Shift + click two nodes: add edge (weight prompt)\n"
            "- Directed toggle: edges are one-way\n"
            "- Undirected: edges are bidirectional with one weight\n"
            "- Two-way different weights: enable Directed and add A → B then B → A\n"
            "- Drag node: move\n"
            "- Double-click node: rename\n"
            "- Double-click edge/weight: edit weight\n"
            "- Select node/edge + Delete: remove\n"
            "- Right-drag: pan\n"
            "- Zoom: use +/- buttons or 100%\n\n"
            "Playback:\n"
            "- Algorithm selector: choose which algorithm to replay\n"
            "- Run Visualization: reload the trace and play from the start\n"
            "- Step: advance one step (loads the run if needed)\n"
            "- Step Back: rewind one step\n"
            "- Play/Pause: toggle playback\n"
            "- Timeline scrubber: drag to jump to any step\n"
            "- Speed slider: adjust playback speed",
        )

    def open_graph(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Graph",
            "",
            "Graph JSON (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            graph = Graph.from_dict(data)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            return

        self.graph_view.set_graph(graph)
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self._set_directed_toggle(graph.directed)
        self.graph_path = path
        if self.status_panel:
            self.status_panel.update_status(f"Loaded graph: {path}")

    def save_graph(self):
        if not self.graph_path:
            self.save_graph_as()
            return
        self._write_graph(self.graph_path)

    def save_graph_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Graph As",
            "",
            "Graph JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path = f"{path}.json"
        self._write_graph(path)
        self.graph_path = path

    def _write_graph(self, path):
        graph = self.graph_view.get_graph()
        if graph is None:
            QMessageBox.warning(self, "Save Error", "No graph to save.")
            return

        try:
            data = graph.to_dict()
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=True)
                handle.write("\n")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            return

        if self.status_panel:
            self.status_panel.update_status(f"Saved graph: {path}")
