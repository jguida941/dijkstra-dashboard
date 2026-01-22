import json

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor, QAction
from .graph_view import GraphView
from .controls_panel import ControlsPanel
from .status_panel import StatusPanel
from dijkstra_dashboard.core.graph import Graph

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dijkstra Path Visualizer")
        self.setMinimumSize(1000, 700)
        self.graph_path = None
        
        # Set dark theme
        self.set_dark_theme()

        # Menu actions
        self.setup_menus()

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
        self.notice_label.setVisible(False)
        self.notice_label.setStyleSheet(
            "background-color: #5a1a1a; color: #ffffff; padding: 6px 10px; "
            "border: 1px solid #aa3333; border-radius: 4px;"
        )
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
        self.graph_view.status_panel = self.status_panel
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

        # Connect signals
        self.controls_panel.run_button.clicked.connect(self.start_visualization)
        self.controls_panel.reset_button.clicked.connect(self.reset_visualization)
        self.controls_panel.step_button.clicked.connect(self.step_visualization)
        self.controls_panel.play_button.clicked.connect(self.toggle_playback)
        self.controls_panel.speed_slider.valueChanged.connect(self.on_speed_changed)
        self.controls_panel.help_button.clicked.connect(self.show_controls_help)
        self.controls_panel.directed_toggle.toggled.connect(self.on_directed_toggled)
        self.graph_view.graph_changed.connect(self.on_graph_changed)
        self.graph_view.message_changed.connect(self.on_message_changed)
        self.graph_view.playback_finished.connect(self.on_playback_finished)

        self.on_speed_changed(self.controls_panel.speed_slider.value())

    def on_graph_changed(self):
        self.controls_panel.set_nodes(self.graph_view.get_node_items())

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

        help_menu = self.menuBar().addMenu("Help")
        controls_action = QAction("Controls...", self)
        controls_action.triggered.connect(self.show_controls_help)
        help_menu.addAction(controls_action)

    def set_dark_theme(self):
        # Set dark palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        self.setPalette(palette)

    def start_visualization(self):
        start_node = self.controls_panel.get_start_node_id()
        target_node = self.controls_panel.get_target_node_id()
        graph = self.graph_view.get_graph()
        if graph:
            label_counts: dict[str, int] = {}
            for node in graph.nodes():
                label_counts[node.label] = label_counts.get(node.label, 0) + 1
            start_label = graph.get_node_label(start_node)
            target_label = graph.get_node_label(target_node)
            if label_counts.get(start_label, 0) > 1:
                start_label = f"{start_label} ({start_node})"
            if label_counts.get(target_label, 0) > 1:
                target_label = f"{target_label} ({target_node})"
        else:
            start_label = start_node
            target_label = target_node

        # Clear status panel
        self.status_panel.clear()
        self.status_panel.update_status(
            f"Starting visualization from {start_label} to {target_label}"
        )

        # Run visualization
        self.graph_view.start_visualization(start_node, target_node)
        self.controls_panel.play_button.setText("Pause")
        # Delay status panel update until animation completes
        pass

    def step_visualization(self):
        start_node = self.controls_panel.get_start_node_id()
        target_node = self.controls_panel.get_target_node_id()
        self.graph_view.step_once(start_node, target_node)
        self.controls_panel.play_button.setText("Play")

    def toggle_playback(self):
        if self.graph_view.animation_timer.isActive():
            self.graph_view.pause_playback()
            self.controls_panel.play_button.setText("Play")
            return

        start_node = self.controls_panel.get_start_node_id()
        target_node = self.controls_panel.get_target_node_id()
        if self.graph_view.prepare_visualization(start_node, target_node, force=False):
            self.graph_view.start_playback()
            self.controls_panel.play_button.setText("Pause")

    def reset_visualization(self):
        self.graph_view.reset()
        self.status_panel.clear()
        self.controls_panel.play_button.setText("Play")

    def on_speed_changed(self, value):
        interval_ms = 1100 - (value * 100)
        self.graph_view.set_animation_interval(interval_ms)

    def on_playback_finished(self):
        self.controls_panel.play_button.setText("Play")

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
            "- Run Visualization: restart and play\n"
            "- Step: advance one step\n"
            "- Play/Pause: toggle playback\n"
            "- Speed slider: adjust animation speed",
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
