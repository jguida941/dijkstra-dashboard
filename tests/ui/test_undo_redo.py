"""Phase 7 — snapshot-based undo/redo.

Whole-graph snapshots ride a QUndoStack. Every editing mutation captures a
before/after ``to_dict`` pair and pushes a :class:`GraphSnapshotCommand`; undo /
redo restore by rebuilding the view through ``set_graph`` (which already unloads
the run, repopulates combos and clears decorations). Document-replacing actions
(New / New Demo / Generate / Open) clear the stack instead of pushing.

Binding folds exercised here:
  F6 — undo of a directedness change restores the Directed checkbox.
  F7 — a completed node drag emits ``graph_changed`` exactly once on release.
  F8 — snapshots begin only for the real-drag / accepted-dialog branches; every
       cancel / reject / modifier path pushes nothing.
  F9 — the stack is cleared only after a successful document replacement.
"""
from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings
from PyQt6.QtGui import QKeySequence, QMouseEvent, QUndoStack
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

import dijkstra_dashboard.ui.main_window as mw_module
from dijkstra_dashboard.ui.graph_view import GraphView
from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.undo import GraphSnapshotCommand


pytestmark = pytest.mark.ui


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _view_with_stack(qtbot):
    view = GraphView()
    qtbot.addWidget(view)
    view.undo_stack = QUndoStack()
    return view


def _ini_settings(tmp_path):
    return QSettings(str(tmp_path / "mw.ini"), QSettings.Format.IniFormat)


def _window(qtbot, tmp_path):
    window = MainWindow(settings=_ini_settings(tmp_path))
    qtbot.addWidget(window)
    return window


def _menu(window, title):
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is not None and menu.title() == title:
            return menu
    return None


def _action(menu, needle):
    for action in menu.actions():
        if needle in action.text():
            return action
    return None


def _left_event(kind, modifiers, pos=QPointF(5.0, 5.0)):
    from PyQt6.QtCore import Qt
    return QMouseEvent(
        kind,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        modifiers,
    )


def _edge_weight(view, start, end):
    for s, e, w in view.get_graph().get_edges():
        if {s, e} == {start, end}:
            return w
    return None


# --------------------------------------------------------------------------
# GraphSnapshotCommand — first-redo guard (unit)
# --------------------------------------------------------------------------
def test_snapshot_command_first_redo_is_noop(qapp):
    calls = []
    cmd = GraphSnapshotCommand("X", {"before": 1}, {"after": 2}, calls.append)

    cmd.redo()  # pushed-time redo must NOT re-apply (mutation already happened)
    assert calls == []

    cmd.undo()
    assert calls[-1] == {"before": 1}

    cmd.redo()  # real redo restores the after snapshot
    assert calls[-1] == {"after": 2}


# --------------------------------------------------------------------------
# Add node
# --------------------------------------------------------------------------
def test_add_node_undo_removes_then_redo_restores(qtbot):
    view = _view_with_stack(qtbot)
    before_ids = set(view.get_graph().get_nodes())

    view.add_node_at(QPoint(220, 160))
    after_ids = set(view.get_graph().get_nodes())
    new_id = (after_ids - before_ids).pop()
    label = view.get_graph().get_node_label(new_id)

    assert view.undo_stack.index() == 1
    assert new_id in view.nodes

    view.undo_stack.undo()
    assert new_id not in view.get_graph().get_nodes()
    assert new_id not in view.nodes

    view.undo_stack.redo()
    assert new_id in view.get_graph().get_nodes()
    assert new_id in view.nodes
    assert view.get_graph().get_node_label(new_id) == label  # label preserved


# --------------------------------------------------------------------------
# Edit edge weight
# --------------------------------------------------------------------------
def test_edit_weight_undo_restores_model_and_chip(qtbot, monkeypatch):
    view = _view_with_stack(qtbot)
    edge_item = view._edge_item_for("A", "B")
    old = edge_item.weight

    monkeypatch.setattr(QInputDialog, "getDouble", lambda *a, **k: (42.0, True))
    view._edit_edge_weight(edge_item)

    assert view.undo_stack.index() == 1
    assert _edge_weight(view, "A", "B") == 42.0
    assert view._edge_item_for("A", "B").weight == 42.0

    view.undo_stack.undo()
    assert _edge_weight(view, "A", "B") == old
    # The rebuilt edge item (and its weight chip) reflect the restored weight.
    assert view._edge_item_for("A", "B").weight == old


def test_edit_weight_same_value_pushes_nothing(qtbot, monkeypatch):
    # Trap #2: a silent no-op mutation (unchanged weight) must not pollute the
    # stack -- _commit_mutation diffs before/after.
    view = _view_with_stack(qtbot)
    edge_item = view._edge_item_for("A", "B")
    same = edge_item.weight

    monkeypatch.setattr(QInputDialog, "getDouble", lambda *a, **k: (same, True))
    view._edit_edge_weight(edge_item)

    assert view.undo_stack.count() == 0
    assert view._pending_before is None


# --------------------------------------------------------------------------
# Node drag — programmatic path (design test #3)
# --------------------------------------------------------------------------
def test_programmatic_drag_one_command_and_undo_restores(qtbot):
    view = _view_with_stack(qtbot)
    node = view.nodes["A"]
    start = node.pos()

    view._begin_mutation()
    node.setPos(QPointF(start.x() + 60, start.y() + 45))
    view._commit_mutation("Move node")

    assert view.undo_stack.index() == 1
    assert view.undo_stack.command(0).text() == "Move node"

    view.undo_stack.undo()
    restored = view.nodes["A"].pos()
    assert restored.x() == pytest.approx(start.x())
    assert restored.y() == pytest.approx(start.y())
    # Edges follow: an incident edge is rebuilt against the restored node item.
    incident = view._edge_item_for("A", "B")
    assert incident.start_node is view.nodes["A"] or incident.end_node is view.nodes["A"]


# --------------------------------------------------------------------------
# Delete selection (design test #4)
# --------------------------------------------------------------------------
def test_delete_selection_single_command_restores_both(qtbot):
    view = _view_with_stack(qtbot)
    before_nodes = sorted(view.get_graph().get_nodes())
    before_edges = sorted(tuple(sorted((s, e))) for s, e, _w in view.get_graph().get_edges())

    node_item = view.nodes["A"]
    edge_item = view._edge_item_for("C", "D")
    view._delete_items([edge_item], [node_item])

    assert view.undo_stack.index() == 1  # exactly one "Delete selection" command
    assert view.undo_stack.command(0).text() == "Delete selection"
    assert "A" not in view.get_graph().get_nodes()

    view.undo_stack.undo()
    assert sorted(view.get_graph().get_nodes()) == before_nodes
    restored_edges = sorted(tuple(sorted((s, e))) for s, e, _w in view.get_graph().get_edges())
    assert restored_edges == before_edges
    assert view._edge_item_for("C", "D") is not None


# --------------------------------------------------------------------------
# Undo rides the graph_changed pipeline: a loaded run is invalidated
# --------------------------------------------------------------------------
def test_undo_during_loaded_run_unloads_controller(qtbot, tmp_path):
    window = _window(qtbot, tmp_path)
    window.graph_view.add_node_at(QPoint(240, 180))
    assert window.undo_stack.index() == 1

    assert window._load_run()
    assert window.playback.is_loaded

    window.undo_stack.undo()
    assert not window.playback.is_loaded  # graph_changed ride unloaded the run


# --------------------------------------------------------------------------
# F9 — document-replacing actions clear the stack
# --------------------------------------------------------------------------
def test_new_demo_clears_undo_stack(qtbot, tmp_path, monkeypatch):
    window = _window(qtbot, tmp_path)
    window.graph_view.add_node_at(QPoint(240, 180))
    assert window.undo_stack.count() == 1

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    _action(_menu(window, "Graph"), "New Demo").trigger()

    assert window.undo_stack.count() == 0


def test_generate_clears_undo_stack(qtbot, tmp_path, monkeypatch):
    window = _window(qtbot, tmp_path)
    window.graph_view.add_node_at(QPoint(240, 180))
    assert window.undo_stack.count() == 1

    class StubDialog:
        def __init__(self, parent=None):
            self.resolved_seed = 7

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {
                "node_count": 5,
                "edge_density": 0.4,
                "weight_range": (1, 9),
                "seed": 7,
                "directed": False,
                "connected": True,
            }

    monkeypatch.setattr(mw_module, "RandomGraphDialog", StubDialog)
    _action(_menu(window, "Graph"), "Generate").trigger()

    assert window.undo_stack.count() == 0


def test_load_graph_from_path_clears_undo_stack(qtbot, tmp_path):
    window = _window(qtbot, tmp_path)
    payload = window.graph_view.get_graph().to_dict()
    path = tmp_path / "g.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    window.graph_view.add_node_at(QPoint(240, 180))
    assert window.undo_stack.count() == 1

    assert window._load_graph_from_path(str(path))
    assert window.undo_stack.count() == 0


def test_failed_load_keeps_undo_stack(qtbot, tmp_path, monkeypatch):
    window = _window(qtbot, tmp_path)
    window.graph_view.add_node_at(QPoint(240, 180))
    assert window.undo_stack.count() == 1

    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    assert window._load_graph_from_path(str(bad)) is False
    assert window.undo_stack.count() == 1  # failed load keeps history intact


# --------------------------------------------------------------------------
# Rename — rejected paths push nothing (F8)
# --------------------------------------------------------------------------
def test_rename_duplicate_pushes_nothing(qtbot, monkeypatch):
    view = _view_with_stack(qtbot)
    # 'B' already exists, so renaming 'A' -> 'B' is rejected as a duplicate.
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("B", True))
    view._rename_node(view.nodes["A"])

    assert view.undo_stack.count() == 0
    assert view._pending_before is None


def test_rename_cancel_pushes_nothing(qtbot, monkeypatch):
    view = _view_with_stack(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    view._rename_node(view.nodes["A"])

    assert view.undo_stack.count() == 0
    assert view._pending_before is None


def test_rename_success_pushes_and_undo_restores(qtbot, monkeypatch):
    view = _view_with_stack(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Zed", True))
    view._rename_node(view.nodes["A"])

    assert view.undo_stack.index() == 1
    assert view.get_graph().get_node_label("A") == "Zed"

    view.undo_stack.undo()
    assert view.get_graph().get_node_label("A") == "A"


# --------------------------------------------------------------------------
# First-redo no-op correctness (design test #8, trap #1)
# --------------------------------------------------------------------------
def test_first_redo_is_no_op(qtbot, monkeypatch):
    view = _view_with_stack(qtbot)
    calls = []
    original = view._restore_snapshot
    monkeypatch.setattr(view, "_restore_snapshot",
                        lambda snap: (calls.append(1), original(snap))[1])

    before_ids = set(view.get_graph().get_nodes())
    view.add_node_at(QPoint(220, 160))
    new_id = (set(view.get_graph().get_nodes()) - before_ids).pop()

    # push() fired redo() once, but the first redo is a guarded no-op: restore
    # never ran, and the live graph already equals the after-snapshot.
    assert view.undo_stack.index() == 1
    assert calls == []
    assert new_id in view.get_graph().get_nodes()

    view.undo_stack.undo()
    assert calls == [1]
    view.undo_stack.redo()
    assert calls == [1, 1]


# --------------------------------------------------------------------------
# mousePressEvent — snapshot discipline (F8)
# --------------------------------------------------------------------------
def test_modifier_click_edge_start_pushes_nothing(qtbot, monkeypatch):
    from PyQt6.QtCore import Qt
    view = _view_with_stack(qtbot)
    node = view.nodes["A"]
    monkeypatch.setattr(view, "itemAt", lambda *a, **k: node)

    view.mousePressEvent(_left_event(QEvent.Type.MouseButtonPress,
                                     Qt.KeyboardModifier.ControlModifier))

    assert view.pending_edge_start == node.node_id  # edge-start selection
    assert view._pending_before is None             # no drag snapshot begun
    assert view.undo_stack.count() == 0


def test_plain_left_press_begins_drag_snapshot(qtbot, monkeypatch):
    from PyQt6.QtCore import Qt
    view = _view_with_stack(qtbot)
    node = view.nodes["A"]
    monkeypatch.setattr(view, "itemAt", lambda *a, **k: node)

    view.mousePressEvent(_left_event(QEvent.Type.MouseButtonPress,
                                     Qt.KeyboardModifier.NoModifier))

    assert view._pending_before is not None
    assert view._drag_node is node
    assert view.undo_stack.count() == 0  # nothing pushed until release


# --------------------------------------------------------------------------
# mouseReleaseEvent — F7 emit-once + commit / drop
# --------------------------------------------------------------------------
def test_drag_release_emits_graph_changed_once_and_commits(qtbot):
    from PyQt6.QtCore import Qt
    view = _view_with_stack(qtbot)
    node = view.nodes["A"]
    start = node.pos()

    view._begin_mutation()
    view._drag_node = node
    node.setPos(QPointF(start.x() + 55, start.y() + 35))

    emitted = []
    view.graph_changed.connect(lambda: emitted.append(1))
    view.mouseReleaseEvent(_left_event(QEvent.Type.MouseButtonRelease,
                                       Qt.KeyboardModifier.NoModifier))

    assert emitted == [1]                       # F7: exactly once on release
    assert view.undo_stack.index() == 1
    assert view.undo_stack.command(0).text() == "Move node"
    assert view._drag_node is None

    view.undo_stack.undo()
    restored = view.nodes["A"].pos()
    assert restored.x() == pytest.approx(start.x())
    assert restored.y() == pytest.approx(start.y())


def test_click_without_move_drops_pending(qtbot):
    from PyQt6.QtCore import Qt
    view = _view_with_stack(qtbot)
    node = view.nodes["A"]

    view._begin_mutation()
    view._drag_node = node  # pressed but never moved

    emitted = []
    view.graph_changed.connect(lambda: emitted.append(1))
    view.mouseReleaseEvent(_left_event(QEvent.Type.MouseButtonRelease,
                                       Qt.KeyboardModifier.NoModifier))

    assert emitted == []
    assert view.undo_stack.count() == 0
    assert view._pending_before is None
    assert view._drag_node is None


# --------------------------------------------------------------------------
# Toggle directed — undo restores mode AND checkbox (F6)
# --------------------------------------------------------------------------
def test_toggle_directed_undo_restores_mode_and_checkbox(qtbot, tmp_path):
    window = _window(qtbot, tmp_path)
    assert window.graph_view.get_graph().directed is False
    assert window.controls_panel.directed_toggle.isChecked() is False

    window.controls_panel.directed_toggle.setChecked(True)
    assert window.graph_view.get_graph().directed is True
    assert window.undo_stack.index() == 1

    window.undo_stack.undo()
    assert window.graph_view.get_graph().directed is False
    assert window.controls_panel.directed_toggle.isChecked() is False  # F6

    window.undo_stack.redo()
    assert window.graph_view.get_graph().directed is True
    assert window.controls_panel.directed_toggle.isChecked() is True


# --------------------------------------------------------------------------
# Edit menu wiring
# --------------------------------------------------------------------------
def test_edit_menu_between_file_and_view_with_undo_redo(qtbot, tmp_path):
    window = _window(qtbot, tmp_path)
    titles = [a.menu().title() for a in window.menuBar().actions() if a.menu()]
    assert "Edit" in titles
    assert titles.index("File") < titles.index("Edit") < titles.index("View")

    edit_menu = _menu(window, "Edit")
    texts = [a.text() for a in edit_menu.actions()]
    assert any("Undo" in t for t in texts)
    assert any("Redo" in t for t in texts)

    undo_action = _action(edit_menu, "Undo")
    redo_action = _action(edit_menu, "Redo")
    assert undo_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Undo)
    assert redo_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Redo)


# --------------------------------------------------------------------------
# Overlapping animated layouts: each tween commits against ITS OWN snapshot
# --------------------------------------------------------------------------
def test_overlapping_layouts_push_two_correct_commands(qapp, qtbot):
    view = _view_with_stack(qtbot)
    original = view.graph.to_dict()
    node_ids = list(view.nodes.keys())

    first = {node_id: (float(60 * i), 0.0) for i, node_id in enumerate(node_ids)}
    second = {node_id: (0.0, float(60 * i)) for i, node_id in enumerate(node_ids)}

    # Start layout 2 while layout 1's tween is still in flight. Layout 1 must
    # finalize + commit against its own snapshot; layout 2 gets a fresh one.
    view.apply_layout(first, animate=True, duration=200)
    view.apply_layout(second, animate=True, duration=200)
    view.animator.cancel_all()  # finalize -> both layouts land + commit

    assert view.undo_stack.count() == 2
    for node_id, (x, y) in second.items():
        assert view.graph.to_dict()["nodes"][node_id]["x"] == pytest.approx(x)
        assert view.graph.to_dict()["nodes"][node_id]["y"] == pytest.approx(y)

    view.undo_stack.undo()
    for node_id, (x, y) in first.items():
        assert view.graph.to_dict()["nodes"][node_id]["x"] == pytest.approx(x)
        assert view.graph.to_dict()["nodes"][node_id]["y"] == pytest.approx(y)

    view.undo_stack.undo()
    assert view.graph.to_dict() == original
