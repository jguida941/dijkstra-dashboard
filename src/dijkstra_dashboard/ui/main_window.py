import json
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QFileDialog, QMessageBox, QLabel, QComboBox, QSlider, QLineEdit,
                             QTextEdit, QPlainTextEdit, QAbstractSpinBox, QDialog, QSplitter,
                             QInputDialog)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QActionGroup, QShortcut, QKeySequence, QUndoStack
from .graph_view import GraphView
from .controls_panel import ControlsPanel
from .inspector_panel import InspectorPanel
from .narration import DISPLAY_NAMES, comparison_line, describe_step, describe_summary, run_header
from .playback_controller import PlaybackController
from .theme import PREVIEW_THEME_ID, current_theme, get_theme_manager, make_app_icon
from .theme_editor import ThemeEditorDialog
from .random_graph_dialog import RandomGraphDialog
from .recent_files import RecentFiles
from .export import export_scene_png, export_scene_svg, HAS_SVG
from dijkstra_dashboard.core.graph import Graph
from dijkstra_dashboard.core.algorithms import get_algorithm_class, list_algorithm_specs
from dijkstra_dashboard.core.samples import default_demo_graph
from dijkstra_dashboard.core.generate import random_graph
from dijkstra_dashboard.core.layouts import circle_layout, grid_layout, spring_layout


#: Fixed layout extent (F4): target positions are centered on the scene origin
#: and scaled to fit this box — comfortably inside the 3000x2000 scene rect and
#: clear of the +/-25px node clamp margin. Never derived from a degenerate
#: (0/1-node) itemsBoundingRect.
LAYOUT_EXTENT_W = 1400.0
LAYOUT_EXTENT_H = 900.0


def normalize_layout_positions(raw, extent_w=LAYOUT_EXTENT_W, extent_h=LAYOUT_EXTENT_H):
    """Center a layout's positions on the origin and scale to a fixed extent.

    Uses the layout's own coordinate spread (never itemsBoundingRect), so a
    degenerate 0/1-node graph collapses to the origin instead of dividing by a
    zero span. The result fits within ``extent_w x extent_h`` centered on (0, 0).
    """
    if not raw:
        return {}
    xs = [x for x, _y in raw.values()]
    ys = [y for _x, y in raw.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    span_x = max_x - min_x
    span_y = max_y - min_y
    scale_x = extent_w / span_x if span_x > 1e-9 else 1.0
    scale_y = extent_h / span_y if span_y > 1e-9 else 1.0
    scale = min(scale_x, scale_y)
    return {
        node_id: ((x - center_x) * scale, (y - center_y) * scale)
        for node_id, (x, y) in raw.items()
    }

class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.setWindowTitle("Dijkstra Path Visualizer")
        self.setMinimumSize(1000, 700)
        self.graph_path = None

        # Recent files (F3): tests inject an isolated tmp-ini QSettings; the app
        # passes None and gets a bare QSettings() (org/app set in __main__).
        self.settings = settings if settings is not None else QSettings()
        self.recents = RecentFiles(self.settings)
        # Examples ship only in a source checkout; scanned once at startup.
        self._example_paths = self._scan_examples()

        # Inspector wiring state (cached per run; never re-read the combo mid-run).
        self._algo_class = None
        self._algo_name = None
        self._total_steps = 0
        self._header_written = False
        self._graph_version = 0
        self._summaries = {}

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.main_splitter)
        
        # Left panel (graph and controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_splitter = QSplitter(Qt.Orientation.Vertical)
        self.graph_splitter.setChildrenCollapsible(False)
        left_layout.addWidget(self.graph_splitter)
        
        # Create and add controls panel
        self.controls_panel = ControlsPanel()
        controls_wrapper = QWidget()
        controls_layout = QVBoxLayout(controls_wrapper)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self.controls_panel)

        self.notice_label = QLabel("")
        self.notice_label.setObjectName("noticeLabel")
        self.notice_label.setVisible(False)
        controls_layout.addWidget(self.notice_label)

        # Right panel (status)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Create and add the educational inspector (distances + pseudocode + narration)
        self.inspector = InspectorPanel()
        right_layout.addWidget(self.inspector)

        # Create and add graph view
        self.graph_view = GraphView()
        # Undo/redo (Phase 7): one stack per window, injected into the view. Every
        # editing mutation pushes a whole-graph snapshot command; document-replacing
        # actions (New / Demo / Generate / Open) clear it instead.
        self.undo_stack = QUndoStack(self)
        self.graph_view.undo_stack = self.undo_stack
        self.graph_splitter.addWidget(controls_wrapper)
        self.graph_splitter.addWidget(self.graph_view)
        self.graph_splitter.setStretchFactor(0, 0)
        self.graph_splitter.setStretchFactor(1, 1)
        self.graph_splitter.setSizes([120, 720])

        # Playback controller owns the trace + replay state; the view renders frames.
        self.playback = PlaybackController(parent=self)

        self.controls_panel.set_algorithms(
            [(spec.name, DISPLAY_NAMES.get(spec.name, spec.name.capitalize()))
             for spec in list_algorithm_specs()]
        )
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        if self.graph_view.get_graph():
            self._set_directed_toggle(self.graph_view.get_graph().directed)
        self.inspector.update_status(
            "Add node: Shift+click empty space\n"
            "Add edge: Ctrl/Option/Shift+click two nodes\n"
            "Directed arrows: selection order sets direction\n"
            "Remove: select node/edge, press Delete\n"
            "Pan: right-drag"
        )

        # Add panels to movable splitters.
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([760, 360])
        self._restore_splitter_layout()
        self.main_splitter.splitterMoved.connect(self._save_splitter_layout)
        self.graph_splitter.splitterMoved.connect(self._save_splitter_layout)

        # Menu actions
        self.setup_menus()
        self._setup_shortcuts()

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
        self.graph_view.status_message.connect(self.inspector.update_status)

        # Playback controller drives all run rendering / status.
        self.playback.run_loaded.connect(self.on_run_loaded)
        self.playback.frame_changed.connect(self.on_frame_changed)
        self.playback.playing_changed.connect(self.on_playing_changed)
        self.playback.run_error.connect(self.on_run_error)
        self.playback.run_finished.connect(self.on_run_finished)

        manager = get_theme_manager()
        manager.theme_changed.connect(self.apply_theme)
        manager.theme_changed.connect(self.inspector.refresh_theme)
        manager.theme_changed.connect(self.controls_panel.refresh_theme)
        self.apply_theme(current_theme())

        self.on_speed_changed(self.controls_panel.speed_slider.value())

    def on_graph_changed(self):
        # Every mutation path emits graph_changed exactly once (F5). The handler
        # must be idempotent and cheap (F6): drop the stale run and reset the view.
        self._graph_version += 1
        self._header_written = False
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        # F6: keep the Directed toggle in sync with the model so undo/redo of a
        # directedness change restores the checkbox (blockSignals-guarded helper,
        # so this never re-triggers on_directed_toggled).
        graph = self.graph_view.get_graph()
        if graph is not None:
            self._set_directed_toggle(graph.directed)
        self.playback.unload()
        self.graph_view.clear_run_decorations()
        self.controls_panel.clear_timeline()
        self.inspector.clear_run_views()

    def _set_directed_toggle(self, value):
        toggle = self.controls_panel.directed_toggle
        blocked = toggle.blockSignals(True)
        toggle.setChecked(bool(value))
        toggle.blockSignals(blocked)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Explanatory text tracks the window size (clamped by each component).
        scale = event.size().width() / 1280.0
        if hasattr(self, "inspector"):
            self.inspector.set_font_scale(scale)
        if hasattr(self, "controls_panel"):
            self.controls_panel.set_font_scale(scale)
        if hasattr(self, "graph_view"):
            self.graph_view.set_label_scale(scale)

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

        # "Open Recent" is rebuilt from RecentFiles after every mutation.
        self.recent_menu = file_menu.addMenu("Open Recent")
        self._rebuild_recent_menu()

        save_action = QAction("Save Graph", self)
        save_action.triggered.connect(self.save_graph)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Graph As...", self)
        save_as_action.triggered.connect(self.save_graph_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()
        export_png_action = QAction("Export as PNG...", self)
        export_png_action.triggered.connect(self.export_png)
        file_menu.addAction(export_png_action)

        export_svg_action = QAction("Export as SVG...", self)
        export_svg_action.triggered.connect(self.export_svg)
        # SVG export needs QtSvg; disable the action when the import failed.
        export_svg_action.setEnabled(HAS_SVG)
        file_menu.addAction(export_svg_action)

        # Edit menu sits between File and View. These are auto enable/disable +
        # auto-labelled undo/redo actions with window-level Ctrl+Z / Ctrl+Y
        # shortcuts; no Phase-4 focus guard is needed (no plain-key collision).
        edit_menu = self.menuBar().addMenu("Edit")
        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        redo_action = self.undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        view_menu = self.menuBar().addMenu("View")
        self.theme_menu = view_menu.addMenu("Theme")
        manager = get_theme_manager()
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.theme_actions = {}
        self._rebuild_theme_menu()

        manager.theme_changed.connect(self._sync_theme_actions)
        # Custom themes register/unregister at runtime (editor save/preview) — the
        # Theme submenu rebuilds so new entries appear and stale ones disappear.
        manager.themes_changed.connect(self._rebuild_theme_menu)

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

        view_menu.addSeparator()
        self.show_labels_action = QAction("Show Distance Labels", self)
        self.show_labels_action.setCheckable(True)
        self.show_labels_action.setChecked(True)
        self.show_labels_action.toggled.connect(self.graph_view.set_badges_visible)
        view_menu.addAction(self.show_labels_action)

        view_menu.addSeparator()
        edit_theme_action = QAction("Edit Theme…", self)
        edit_theme_action.triggered.connect(self.open_theme_editor)
        view_menu.addAction(edit_theme_action)

        delete_theme_action = QAction("Delete Custom Theme…", self)
        delete_theme_action.triggered.connect(self.delete_custom_theme)
        view_menu.addAction(delete_theme_action)

        # Graph menu sits between View and Help.
        graph_menu = self.menuBar().addMenu("Graph")

        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_graph)
        graph_menu.addAction(new_action)

        new_demo_action = QAction("New Demo Graph", self)
        new_demo_action.triggered.connect(self.new_demo_graph)
        graph_menu.addAction(new_demo_action)

        generate_action = QAction("Generate Random...", self)
        generate_action.triggered.connect(self.generate_random_graph)
        graph_menu.addAction(generate_action)

        graph_menu.addSeparator()
        self.snap_to_grid_action = QAction("Snap to Grid", self)
        self.snap_to_grid_action.setCheckable(True)
        self.snap_to_grid_action.toggled.connect(self.on_snap_to_grid_toggled)
        graph_menu.addAction(self.snap_to_grid_action)

        grid_size_action = QAction("Grid Size...", self)
        grid_size_action.triggered.connect(self.set_grid_size)
        graph_menu.addAction(grid_size_action)
        self._restore_grid_settings()

        graph_menu.addSeparator()

        layout_menu = graph_menu.addMenu("Layout")
        for label, name in (("Circle", "circle"), ("Grid", "grid"), ("Spring", "spring")):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked, n=name: self._apply_named_layout(n))
            layout_menu.addAction(action)

        self._build_examples_submenu(graph_menu)

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

    def _restore_splitter_layout(self):
        main_state = self.settings.value("layout/main_splitter")
        graph_state = self.settings.value("layout/graph_splitter")
        if main_state is not None:
            self.main_splitter.restoreState(main_state)
        if graph_state is not None:
            self.graph_splitter.restoreState(graph_state)

    def _save_splitter_layout(self, *_args):
        self.settings.setValue("layout/main_splitter", self.main_splitter.saveState())
        self.settings.setValue("layout/graph_splitter", self.graph_splitter.saveState())

    def _restore_grid_settings(self):
        try:
            size = int(float(self.settings.value("graph/grid_size", self.graph_view.grid_size())))
        except (TypeError, ValueError):
            size = int(self.graph_view.grid_size())
        self.graph_view.set_grid_size(size)

        raw = self.settings.value("graph/snap_to_grid", False)
        enabled = raw if isinstance(raw, bool) else str(raw).lower() in {"1", "true", "yes"}
        blocked = self.snap_to_grid_action.blockSignals(True)
        self.snap_to_grid_action.setChecked(enabled)
        self.snap_to_grid_action.blockSignals(blocked)
        self.graph_view.set_snap_to_grid(enabled)

    def _rebuild_theme_menu(self):
        # Rebuild the Theme submenu from the manager's live registry, reusing the
        # one shared exclusive action group. The reserved live-preview id is never
        # listed. Called at setup and whenever the registry changes.
        manager = get_theme_manager()
        for action in self.theme_actions.values():
            self.theme_action_group.removeAction(action)
            action.deleteLater()
        self.theme_menu.clear()
        self.theme_actions = {}
        for theme_id in manager.theme_ids():
            if theme_id == PREVIEW_THEME_ID:
                continue
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
            self.theme_menu.addAction(action)
            self.theme_actions[theme_id] = action

    def _sync_theme_actions(self, theme):
        # Tolerates a current id with no action (e.g. the live-preview theme while
        # the editor is open): in that case no entry ends up checked.
        for theme_id, action in self.theme_actions.items():
            blocked = action.blockSignals(True)
            action.setChecked(theme_id == theme.id)
            action.blockSignals(blocked)

    def open_theme_editor(self):
        dialog = ThemeEditorDialog(self)
        dialog.exec()

    def delete_custom_theme(self):
        manager = get_theme_manager()
        choices = [
            theme_id for theme_id in manager.theme_ids()
            if theme_id not in manager.BUILTIN_THEMES and theme_id != PREVIEW_THEME_ID
        ]
        if not choices:
            QMessageBox.information(self, "Delete Custom Theme", "No custom themes to delete.")
            return

        labels = [f"{manager.THEMES[theme_id].name} ({theme_id})" for theme_id in choices]
        selected, ok = QInputDialog.getItem(
            self,
            "Delete Custom Theme",
            "Theme:",
            labels,
            0,
            False,
        )
        if not ok or not selected:
            return
        theme_id = choices[labels.index(selected)]
        if QMessageBox.question(
            self,
            "Delete Custom Theme",
            f"Delete '{manager.THEMES[theme_id].name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        manager.delete_custom_theme(theme_id)

    def _setup_shortcuts(self):
        # WindowShortcut transport controls; guards inside each handler bail when
        # an editable widget (combo/slider/line/text/spin) holds focus (F11).
        bindings = (
            (Qt.Key.Key_Space, self._sc_toggle),
            (Qt.Key.Key_Left, self._sc_back),
            (Qt.Key.Key_Right, self._sc_forward),
            (Qt.Key.Key_Home, self._sc_home),
            (Qt.Key.Key_End, self._sc_end),
        )
        self._shortcuts = []
        for key, handler in bindings:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _editing_focus(self):
        editable = (QComboBox, QSlider, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)
        widget = QApplication.focusWidget()
        while widget is not None:
            if isinstance(widget, editable):
                return True
            widget = widget.parentWidget()
        return False

    def _sc_toggle(self):
        if self._editing_focus():
            return
        self.toggle_playback()

    def _sc_forward(self):
        if self._editing_focus():
            return
        self.step_visualization()

    def _sc_back(self):
        if self._editing_focus():
            return
        if self.playback.is_loaded:
            self.step_back()

    def _sc_home(self):
        if self._editing_focus():
            return
        if self.playback.is_loaded:
            self.playback.seek(0)

    def _sc_end(self):
        if self._editing_focus():
            return
        if self.playback.is_loaded:
            self.playback.seek(self.playback.total)

    def _load_run(self):
        """Load the current graph/params into the controller. Returns True on load."""
        start_node = self.controls_panel.get_start_node_id()
        target_node = self.controls_panel.get_target_node_id()
        graph = self.graph_view.get_graph()
        if graph is None:
            return False
        algorithm_name = self.controls_panel.get_algorithm_name()
        # F5: clear the inspector BEFORE loading; the run header is written from
        # on_run_loaded once the controller emits meta.
        self._header_written = False
        self.inspector.clear_all()
        if not self.playback.load_run(
            graph, algorithm_name, {"start": start_node, "target": target_node}
        ):
            return False
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
        self.inspector.clear_all()
        self._header_written = False
        self._algo_class = None
        self._algo_name = None
        self.controls_panel.play_button.setText("Play")

    def on_speed_changed(self, value):
        interval_ms = 1100 - (value * 100)
        self.playback.set_interval(interval_ms)
        self.graph_view.set_tween_interval(interval_ms)

    def on_timeline_changed(self, value):
        self.playback.seek(value)

    def on_run_loaded(self, meta):
        self.controls_panel.set_timeline(meta["total"])

        algorithm_name = meta["algorithm"]
        self._algo_name = algorithm_name
        # Cache the running algorithm CLASS; never re-read the combo mid-run (trap 3).
        self._algo_class = get_algorithm_class(algorithm_name)
        self._total_steps = meta["total"]
        label_of = self.graph_view.label_lookup

        graph = self.graph_view.get_graph()
        node_ids = graph.get_nodes() if graph is not None else []
        self.inspector.table.set_nodes(node_ids, label_of)
        self.inspector.table.set_distance_header(algorithm_name)

        display = DISPLAY_NAMES.get(algorithm_name, algorithm_name)
        self.inspector.pseudocode.set_algorithm(display, list(self._algo_class.pseudocode))

        self.inspector.narration.append_line(run_header(meta, label_of), "accent")
        self._header_written = True

        if meta["total"] > 10_000:
            self.inspector.narration.append_line(
                f"Large run ({meta['total']} steps) — narration only for manual steps; "
                "use the timeline.",
                "muted",
            )

    def on_frame_changed(self, frame):
        self.graph_view.render_frame(frame)
        self.controls_panel.set_timeline_index(frame.index)

        label_of = self.graph_view.label_lookup
        self.inspector.table.render_frame(frame, label_of)

        if frame.step is not None and self._algo_class is not None:
            self.inspector.pseudocode.highlight_step(self._algo_class.lines_for_step(frame.step))
        else:
            self.inspector.pseudocode.highlight_step([])

        if frame.forward_step:
            # F6: runs over 10k steps skip ALL per-step narration (manual + autoplay).
            if self._total_steps <= 10_000 and frame.step is not None:
                sentence, role = describe_step(frame.step, label_of, self._algo_name)
                self.inspector.narration.append_line(sentence, role)
        elif frame.index > 0 and self._header_written:
            # F5: no jump marker for the initial load frame (index 0) or before a header.
            self.inspector.narration.append_jump_marker(frame.index)

    def on_playing_changed(self, playing):
        self.controls_panel.play_button.setText("Pause" if playing else "Play")

    def on_run_error(self, message):
        self.inspector.update_status(message, "error")
        self.on_message_changed(message)

    def on_run_finished(self, summary):
        label_of = self.graph_view.label_lookup
        for text, role in describe_summary(summary, label_of):
            self.inspector.narration.append_line(text, role)
        if not summary.get("path"):
            self.on_message_changed("No path found.")

        # Cross-algorithm comparison for the same graph/start/target key.
        key = (self._graph_version, summary.get("start"), summary.get("target"))
        algorithm = summary.get("algorithm")
        bucket = self._summaries.setdefault(key, {})
        previous = None
        for other_algo, other_summary in bucket.items():
            if other_algo != algorithm:
                previous = other_summary
        bucket[algorithm] = summary
        if previous is not None:
            self.inspector.narration.append_line(
                comparison_line(summary, previous, label_of), "muted"
            )

    def on_directed_toggled(self, checked):
        graph = self.graph_view.get_graph()
        if not graph:
            return
        # Snapshot around the directedness change so undo restores the prior edge
        # set + mode (and, via F6, the checkbox). Diff-guarded, so a no-op toggle
        # pushes nothing.
        self.graph_view._begin_mutation()
        graph.set_directed(bool(checked))
        self.graph_view.set_graph(graph)
        self.graph_view._commit_mutation("Toggle directed")
        if self.inspector:
            if checked:
                self.inspector.update_status(
                    "Directed mode enabled (edges use node order; add reverse edges if needed)."
                )
            else:
                self.inspector.update_status("Undirected mode enabled (one weight per edge).")

    def on_snap_to_grid_toggled(self, enabled):
        self.graph_view.set_snap_to_grid(enabled)
        self.settings.setValue("graph/snap_to_grid", bool(enabled))

    def set_grid_size(self):
        value, ok = QInputDialog.getInt(
            self,
            "Grid Size",
            "Grid spacing:",
            int(self.graph_view.grid_size()),
            5,
            200,
            5,
        )
        if ok:
            self.graph_view.set_grid_size(value)
            self.settings.setValue("graph/grid_size", value)
            self.inspector.update_status(f"Grid size set to {value}.")

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
            "- Drag empty canvas, right-drag, or middle-drag: pan\n"
            "- Zoom: use +/- buttons or 100%\n\n"
            "Playback:\n"
            "- Algorithm selector: choose which algorithm to replay\n"
            "- Run: reload the trace and play from the start\n"
            "- Step: advance one step (loads the run if needed)\n"
            "- ⏮ Back: rewind one step\n"
            "- Play/Pause: toggle playback\n"
            "- Timeline scrubber: drag to jump to any step\n"
            "- Speed slider: adjust playback speed\n\n"
            "Keyboard shortcuts:\n"
            "- Space: play/pause\n"
            "- Left / Right: step back / forward\n"
            "- Home / End: jump to the start / final step",
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
        self._load_graph_from_path(path)

    def _load_graph_from_path(self, path):
        """Shared loader for Open / Open Recent / Examples.

        On success: load the graph, sync the directed toggle, record the path in
        recents and rebuild the submenu. On failure: report and DROP the path
        from recents (a stale/broken entry should not linger).
        """
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            graph = Graph.from_dict(data)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            self.recents.remove(path)
            self._rebuild_recent_menu()
            return False

        self.graph_view.set_graph(graph)
        # F9: fresh document -> the edit history no longer applies. Cleared only
        # on this success path; a failed load (above) keeps history intact.
        self.undo_stack.clear()
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self._set_directed_toggle(graph.directed)
        self.graph_path = path
        self.recents.add(path)
        self._rebuild_recent_menu()
        if self.inspector:
            self.inspector.update_status(f"Loaded graph: {path}")
        return True

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

        self.recents.add(path)
        self._rebuild_recent_menu()
        if self.inspector:
            self.inspector.update_status(f"Saved graph: {path}")

    # ------------------------------------------------------------------
    # Recent files + examples menus
    # ------------------------------------------------------------------
    def _scan_examples(self):
        # Examples ship only in a SOURCE CHECKOUT (repo /examples), never in an
        # installed wheel. __file__ is .../src/dijkstra_dashboard/ui/main_window.py,
        # so parents[3] is the repo root. Absent dir -> no submenu, no crash.
        examples_dir = Path(__file__).resolve().parents[3] / "examples"
        if not examples_dir.is_dir():
            return []
        return sorted(examples_dir.glob("*.json"))

    def _build_examples_submenu(self, graph_menu):
        # Submenu is hidden entirely when the checkout has no example json.
        if not self._example_paths:
            return
        examples_menu = graph_menu.addMenu("Examples")
        for example_path in self._example_paths:
            action = QAction(example_path.stem, self)
            action.setData(str(example_path))
            action.triggered.connect(
                lambda _checked, p=str(example_path): self._load_graph_from_path(p)
            )
            examples_menu.addAction(action)

    def _rebuild_recent_menu(self):
        menu = getattr(self, "recent_menu", None)
        if menu is None:
            return
        menu.clear()
        paths = self.recents.list()
        for path in paths:
            action = QAction(path, self)
            action.setData(path)
            action.triggered.connect(
                lambda _checked, p=path: self._load_graph_from_path(p)
            )
            menu.addAction(action)
        menu.addSeparator()
        clear_action = QAction("Clear Menu", self)
        clear_action.setEnabled(bool(paths))
        clear_action.triggered.connect(self._clear_recent_files)
        menu.addAction(clear_action)

    def _clear_recent_files(self):
        self.recents.clear()
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # Graph menu handlers
    # ------------------------------------------------------------------
    def _confirm_discard(self):
        answer = QMessageBox.question(self, "Discard Graph", "Discard the current graph?")
        return answer == QMessageBox.StandardButton.Yes

    def new_graph(self):
        if not self._confirm_discard():
            return
        directed = self.controls_panel.directed_toggle.isChecked()
        graph = Graph(directed=directed)
        self.graph_view.set_graph(graph)
        self.undo_stack.clear()  # F9: fresh document
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self.graph_path = None
        if self.inspector:
            self.inspector.update_status("New empty graph.")

    def new_demo_graph(self):
        if not self._confirm_discard():
            return
        graph = default_demo_graph()
        self.graph_view.set_graph(graph)
        self.undo_stack.clear()  # F9: fresh document
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self._set_directed_toggle(graph.directed)
        self.graph_path = None
        if self.inspector:
            self.inspector.update_status("Loaded demo graph.")

    def generate_random_graph(self):
        dialog = RandomGraphDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        kwargs = dialog.values()
        try:
            graph = random_graph(**kwargs)
        except Exception as exc:
            QMessageBox.critical(self, "Generate Error", str(exc))
            return

        self.graph_view.set_graph(graph)
        self.undo_stack.clear()  # F9: fresh document
        self.controls_panel.set_nodes(self.graph_view.get_node_items())
        self._set_directed_toggle(graph.directed)
        self.graph_path = None
        if self.inspector:
            # Seed is always echoed (resolved once, so every run is reproducible).
            self.inspector.update_status(
                f"Generated {kwargs['node_count']}-node graph "
                f"(density {kwargs['edge_density']}, seed {dialog.resolved_seed})."
            )

    def _apply_named_layout(self, name):
        graph = self.graph_view.get_graph()
        if graph is None:
            return
        node_ids = graph.get_nodes()
        if not node_ids:
            return
        if name == "circle":
            raw = circle_layout(node_ids)
        elif name == "grid":
            raw = grid_layout(node_ids)
        elif name == "spring":
            edges = [(start, end) for start, end, _weight in graph.get_edges()]
            # Pin the seed for determinism (spring is randomized).
            raw = spring_layout(node_ids, edges, iterations=60, seed=1)
        else:
            return
        positions = normalize_layout_positions(raw)
        self.graph_view.apply_layout(positions, animate=True)

    # ------------------------------------------------------------------
    # Export handlers
    # ------------------------------------------------------------------
    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as PNG", "", "PNG Image (*.png);;All Files (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path = f"{path}.png"
        if export_scene_png(self.graph_view.scene, path):
            if self.inspector:
                self.inspector.update_status(f"Exported PNG: {path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export PNG (empty graph?).")

    def export_svg(self):
        if not HAS_SVG:
            QMessageBox.warning(self, "Export Error", "SVG export is unavailable (QtSvg missing).")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as SVG", "", "SVG Image (*.svg);;All Files (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".svg"):
            path = f"{path}.svg"
        if export_scene_svg(self.graph_view.scene, path):
            if self.inspector:
                self.inspector.update_status(f"Exported SVG: {path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export SVG (empty graph?).")
