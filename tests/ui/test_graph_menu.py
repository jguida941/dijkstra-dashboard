"""Phase 6 (UI) — Graph menu, layout wiring, generate handler, File additions.

Confirm-discard prompts are suppressed by monkeypatching QMessageBox.question.
The generate path uses a stubbed dialog (F1). apply_layout is exercised both
snapped (animate=False) and animated (tiny duration + waitUntil).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, QSettings, Qt
from PyQt6.QtGui import QMouseEvent, QUndoStack
from PyQt6.QtWidgets import QDialog, QMessageBox

import dijkstra_dashboard.ui.main_window as mw_module
from dijkstra_dashboard.ui.graph_view import GraphView
from dijkstra_dashboard.ui.main_window import MainWindow, normalize_layout_positions


pytestmark = pytest.mark.ui

# Half of the F4 fixed extent (1400 x 900), plus a 1px float tolerance.
LAYOUT_HALF_W = 700.0 + 1.0
LAYOUT_HALF_H = 450.0 + 1.0


def _ini_settings(tmp_path):
    return QSettings(str(tmp_path / "mw.ini"), QSettings.Format.IniFormat)


def _menu(window, title):
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is not None and menu.title() == title:
            return menu
    return None


def _submenu(menu, title):
    for action in menu.actions():
        sub = action.menu()
        if sub is not None and sub.title() == title:
            return sub
    return None


def _action(menu, needle):
    for action in menu.actions():
        if needle in action.text():
            return action
    return None


def _mouse_event(kind, pos, button, buttons=None, modifiers=Qt.KeyboardModifier.NoModifier):
    buttons = button if buttons is None else buttons
    point = QPointF(*pos)
    return QMouseEvent(kind, point, point, button, buttons, modifiers)


# ---- menu structure --------------------------------------------------------
def test_graph_menu_between_view_and_help(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    titles = [a.menu().title() for a in window.menuBar().actions() if a.menu()]
    assert "Graph" in titles
    assert titles.index("View") < titles.index("Graph") < titles.index("Help")
    window.close()


def test_graph_menu_has_layout_and_examples_submenus(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    graph_menu = _menu(window, "Graph")
    assert graph_menu is not None
    assert _submenu(graph_menu, "Layout") is not None
    # The repo ships example json files, so the submenu exists and is populated.
    examples = _submenu(graph_menu, "Examples")
    assert examples is not None
    assert len(examples.actions()) >= 1
    window.close()


def test_main_layout_exposes_horizontal_and_vertical_splitters(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))

    assert window.main_splitter.orientation() == Qt.Orientation.Horizontal
    assert window.graph_splitter.orientation() == Qt.Orientation.Vertical
    assert window.main_splitter.count() == 2
    assert window.graph_splitter.count() == 2
    window.close()


def test_main_splitter_allows_inspector_to_collapse_for_full_graph(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    window.resize(1200, 800)
    window.main_splitter.setSizes([1200, 0])
    qapp.processEvents()

    assert window.main_splitter.isCollapsible(0) is False
    assert window.main_splitter.isCollapsible(1) is True
    assert window.main_splitter.sizes()[1] == 0
    window.close()


def test_snap_to_grid_action_and_dragged_position_rounding(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    graph_menu = _menu(window, "Graph")
    action = _action(graph_menu, "Snap to Grid")
    assert action is not None

    window.graph_view.set_grid_size(25)
    action.trigger()
    assert window.graph_view.snap_to_grid()

    node = window.graph_view.nodes["A"]
    node.setPos(QPointF(37, 63))

    assert node.pos().x() == pytest.approx(25)
    assert node.pos().y() == pytest.approx(75)
    assert window.graph_view.get_graph().get_node_position("A") == pytest.approx((25, 75))
    window.close()


def test_empty_canvas_left_drag_pans_view(qapp, qtbot, monkeypatch):
    view = GraphView()
    qtbot.addWidget(view)
    view.resize(420, 320)
    view.show()
    qtbot.waitExposed(view)
    view.centerOn(0, 0)
    monkeypatch.setattr(view, "itemAt", lambda *args, **kwargs: None)

    start_h = view.horizontalScrollBar().value()
    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            (210, 160),
            Qt.MouseButton.LeftButton,
        )
    )
    assert view._is_panning

    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            (130, 160),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )

    assert view.horizontalScrollBar().value() > start_h

    view.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            (130, 160),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
    )
    assert not view._is_panning


def test_cmd_click_toggles_node_group_selection(qapp, qtbot, monkeypatch):
    view = GraphView()
    qtbot.addWidget(view)
    node = view.nodes["A"]
    monkeypatch.setattr(view, "itemAt", lambda *args, **kwargs: node)

    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            (210, 160),
            Qt.MouseButton.LeftButton,
            modifiers=Qt.KeyboardModifier.MetaModifier,
        )
    )

    assert node.isSelected()
    assert view.pending_edge_start is None
    assert view._pending_before is None


def test_dragging_selected_node_moves_selected_group_and_commits_once(qapp, qtbot, monkeypatch):
    view = GraphView()
    qtbot.addWidget(view)
    view.undo_stack = QUndoStack()
    node_a = view.nodes["A"]
    node_b = view.nodes["B"]
    node_a.setSelected(True)
    node_b.setSelected(True)
    start_a = QPointF(node_a.pos())
    start_b = QPointF(node_b.pos())
    monkeypatch.setattr(view, "itemAt", lambda *args, **kwargs: node_a)

    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            (210, 160),
            Qt.MouseButton.LeftButton,
        )
    )
    assert set(view._drag_nodes) == {node_a, node_b}

    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            (250, 185),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    delta_a = node_a.pos() - start_a
    delta_b = node_b.pos() - start_b
    assert delta_a.x() == pytest.approx(delta_b.x())
    assert delta_a.y() == pytest.approx(delta_b.y())
    assert (delta_a.x(), delta_a.y()) != pytest.approx((0, 0))

    emitted = []
    view.graph_changed.connect(lambda: emitted.append(1))
    view.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            (250, 185),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
    )

    assert emitted == [1]
    assert view.undo_stack.index() == 1
    assert view.undo_stack.command(0).text() == "Move nodes"
    assert view._drag_nodes == []

    view.undo_stack.undo()
    assert view.nodes["A"].pos().x() == pytest.approx(start_a.x())
    assert view.nodes["A"].pos().y() == pytest.approx(start_a.y())
    assert view.nodes["B"].pos().x() == pytest.approx(start_b.x())
    assert view.nodes["B"].pos().y() == pytest.approx(start_b.y())


def test_file_menu_has_export_and_open_recent(qapp, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    file_menu = _menu(window, "File")
    texts = [a.text() for a in file_menu.actions()]
    assert any("PNG" in t for t in texts)
    assert any("SVG" in t for t in texts)
    assert _submenu(file_menu, "Open Recent") is not None
    window.close()


# ---- New Demo --------------------------------------------------------------
def test_new_demo_graph_loads_six_nodes(qapp, tmp_path, monkeypatch):
    window = MainWindow(settings=_ini_settings(tmp_path))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)

    graph_menu = _menu(window, "Graph")
    action = _action(graph_menu, "New Demo")
    assert action is not None
    action.trigger()

    assert len(window.graph_view.get_graph().get_nodes()) == 6
    window.close()


# ---- Generate Random (stubbed dialog, F1) ----------------------------------
def test_generate_random_replaces_graph_and_echoes_seed(qapp, tmp_path, monkeypatch):
    window = MainWindow(settings=_ini_settings(tmp_path))

    class StubDialog:
        def __init__(self, parent=None):
            self.resolved_seed = 42

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {
                "node_count": 5,
                "edge_density": 0.4,
                "weight_range": (1, 9),
                "seed": 42,
                "directed": False,
                "connected": True,
            }

    monkeypatch.setattr(mw_module, "RandomGraphDialog", StubDialog)

    messages = []
    monkeypatch.setattr(window.inspector, "update_status",
                        lambda msg, *a, **k: messages.append(msg))

    graph_menu = _menu(window, "Graph")
    action = _action(graph_menu, "Generate")
    assert action is not None
    action.trigger()

    assert len(window.graph_view.get_graph().get_nodes()) == 5
    assert any("seed 42" in m for m in messages)
    window.close()


def test_generate_random_cancelled_leaves_graph(qapp, tmp_path, monkeypatch):
    window = MainWindow(settings=_ini_settings(tmp_path))
    before = window.graph_view.get_graph().get_nodes()

    class StubDialog:
        def __init__(self, parent=None):
            self.resolved_seed = None

        def exec(self):
            return QDialog.DialogCode.Rejected

        def values(self):  # pragma: no cover - must not be reached on cancel
            raise AssertionError("values() must not run when dialog is cancelled")

    monkeypatch.setattr(mw_module, "RandomGraphDialog", StubDialog)

    graph_menu = _menu(window, "Graph")
    _action(graph_menu, "Generate").trigger()

    assert window.graph_view.get_graph().get_nodes() == before
    window.close()


# ---- apply_layout ----------------------------------------------------------
def test_apply_layout_animate_false_moves_nodes_edges_and_emits_once(qapp):
    view = GraphView()
    node_ids = list(view.nodes.keys())
    edge = next(iter(view.edges.values()))
    before = edge.curve_path().pointAtPercent(0.0)

    emitted = []
    view.graph_changed.connect(lambda: emitted.append(1))

    targets = {nid: (i * 40 - 100, 60.0) for i, nid in enumerate(node_ids)}
    view.apply_layout(targets, animate=False)

    for nid, (x, y) in targets.items():
        pos = view.nodes[nid].pos()
        assert pos.x() == pytest.approx(x)
        assert pos.y() == pytest.approx(y)
        model = view.get_graph().get_node_position(nid)
        assert model == pytest.approx((x, y))

    after = edge.curve_path().pointAtPercent(0.0)
    assert (after.x(), after.y()) != pytest.approx((before.x(), before.y()))
    assert len(emitted) == 1  # emit-once on finalize, never per node


def test_apply_layout_animated_completes_and_snaps(qapp, qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    node_ids = list(view.nodes.keys())
    targets = {nid: (i * 30 - 75, -40.0) for i, nid in enumerate(node_ids)}

    emitted = []
    view.graph_changed.connect(lambda: emitted.append(1))

    view.apply_layout(targets, animate=True, duration=40)
    qtbot.waitUntil(lambda: len(emitted) == 1, timeout=3000)

    for nid, (x, y) in targets.items():
        pos = view.nodes[nid].pos()
        assert pos.x() == pytest.approx(x)
        assert pos.y() == pytest.approx(y)
    assert len(emitted) == 1


# ---- F4: normalize_layout_positions ---------------------------------------
def test_normalize_layout_centers_on_origin_and_fits_extent():
    raw = {"a": (0, 0), "b": (400, 0), "c": (400, 300), "d": (0, 300)}
    norm = normalize_layout_positions(raw, extent_w=1400, extent_h=900)

    xs = [x for x, _y in norm.values()]
    ys = [y for _x, y in norm.values()]
    assert sum(xs) == pytest.approx(0.0, abs=1e-6)   # centered on the scene origin
    assert sum(ys) == pytest.approx(0.0, abs=1e-6)
    assert (max(xs) - min(xs)) <= 1400 + 1e-6        # inside the fixed extent
    assert (max(ys) - min(ys)) <= 900 + 1e-6


def test_normalize_layout_degenerate_graph_collapses_to_origin():
    # F4: never divide by a zero span (0/1-node); collapse to origin instead.
    assert normalize_layout_positions({"only": (123.0, -45.0)}) == {"only": (0.0, 0.0)}
    assert normalize_layout_positions({}) == {}


def test_circle_layout_action_runs_and_keeps_nodes_in_extent(qapp, qtbot, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    emitted = []
    window.graph_view.graph_changed.connect(lambda: emitted.append(1))

    layout_menu = _submenu(_menu(window, "Graph"), "Layout")
    _action(layout_menu, "Circle").trigger()
    qtbot.waitUntil(lambda: len(emitted) >= 1, timeout=3000)

    for nid in window.graph_view.get_graph().get_nodes():
        x, y = window.graph_view.get_graph().get_node_position(nid)
        assert abs(x) <= LAYOUT_HALF_W
        assert abs(y) <= LAYOUT_HALF_H
    window.close()


# ---- View menu zoom shortcuts ----------------------------------------------
def test_view_menu_zoom_shortcuts_wired(qapp, tmp_path):
    from PyQt6.QtGui import QKeySequence

    window = MainWindow(settings=_ini_settings(tmp_path))
    try:
        zoom_in_keys = window.zoom_in_action.shortcuts()
        assert QKeySequence("Ctrl+=") in zoom_in_keys
        assert window.reset_zoom_action.shortcut() == QKeySequence("Ctrl+0")
        assert window.fit_action.shortcut() == QKeySequence("Ctrl+Shift+0")
        # Zoom out uses the platform standard binding(s).
        assert window.zoom_out_action.shortcuts() == QKeySequence.keyBindings(
            QKeySequence.StandardKey.ZoomOut
        )
    finally:
        window.close()


def test_layout_ignores_snap_to_grid(qapp, tmp_path):
    # L1: a computed layout must land on its EXACT coordinates even with
    # Snap-to-Grid enabled (snapping is suspended during layout application).
    window = MainWindow(settings=_ini_settings(tmp_path))
    view = window.graph_view
    view.set_grid_size(40)
    view.set_snap_to_grid(True)

    node_ids = view.get_graph().get_nodes()
    # Deliberately off-grid targets (not multiples of 40).
    targets = {n: (float(17 + i * 53), float(29 - i * 11)) for i, n in enumerate(node_ids)}
    view.apply_layout(targets, animate=False)

    for n, (x, y) in targets.items():
        pos = view.nodes[n].pos()
        assert pos.x() == pytest.approx(x)
        assert pos.y() == pytest.approx(y)
    # Snapping is restored afterward for ordinary drags.
    assert view._suspend_snap is False
    window.close()
