import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.theme import custom_theme_dir, get_theme_manager, theme_from_dict


@pytest.mark.ui
def test_main_window_boots_offscreen_with_notice_label_object_name(qapp):
    window = MainWindow()

    assert window.graph_view is not None
    assert window.inspector is not None
    assert window.notice_label.objectName() == "noticeLabel"

    window.close()


@pytest.mark.ui
def test_theme_change_updates_application_palette(qapp):
    window = MainWindow()
    manager = get_theme_manager()

    manager.set_theme("midnight", persist=False)
    qapp.processEvents()

    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor("#0f172a")

    window.close()


@pytest.mark.ui
def test_view_theme_menu_has_exclusive_three_theme_actions(qapp):
    window = MainWindow()

    view_menu = next(
        (action.menu() for action in window.menuBar().actions() if action.menu() and action.menu().title() == "View"),
        None,
    )
    assert view_menu is not None

    theme_menu = next(
        (action.menu() for action in view_menu.actions() if action.menu() and action.menu().title() == "Theme"),
        None,
    )
    assert theme_menu is not None

    actions = theme_menu.actions()
    assert len(actions) == 3
    assert all(action.isCheckable() for action in actions)
    assert len({action.actionGroup() for action in actions}) == 1
    assert actions[0].actionGroup().isExclusive()
    assert [action.text() for action in actions] == ["Neon Dark", "Midnight", "Paper Light"]
    assert actions[0].isChecked()

    window.close()


@pytest.mark.ui
def test_view_menu_groups_theme_actions_at_top(qapp):
    window = MainWindow()

    view_menu = next(
        (action.menu() for action in window.menuBar().actions() if action.menu() and action.menu().title() == "View"),
        None,
    )
    assert view_menu is not None

    actions = view_menu.actions()
    assert actions[0].menu() is not None
    assert actions[0].menu().title() == "Theme"
    assert actions[1].text() == "Edit Theme…"
    assert actions[2].text() == "Delete Custom Theme…"
    assert actions[3].isSeparator()

    window.close()


@pytest.mark.ui
def test_view_delete_custom_theme_action_removes_saved_theme(qapp, monkeypatch):
    manager = get_theme_manager()
    manager.save_custom_theme(theme_from_dict({"id": "menu-delete", "name": "Menu Delete"}))
    manager.set_theme("menu-delete", persist=False)
    window = MainWindow()

    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("Menu Delete (menu-delete)", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.delete_custom_theme()

    assert "menu-delete" not in manager.theme_ids()
    assert not (custom_theme_dir() / "menu-delete.json").exists()
    assert manager.current.id == "neon-dark"
    window.close()


@pytest.mark.ui
def test_switching_theme_mid_run_does_not_crash(qapp):
    window = MainWindow()
    graph = window.graph_view.get_graph()
    node_ids = graph.get_nodes()

    assert window.playback.load_run(
        graph, "dijkstra", {"start": node_ids[0], "target": node_ids[-1]}
    )
    window.playback.step_forward()
    window.playback.step_forward()

    # Start node is "current" for the opening steps; capture it to prove the
    # render state survives a theme swap through set_state re-application.
    start_state = window.graph_view.nodes[node_ids[0]]._state
    assert start_state == "current"

    get_theme_manager().set_theme("paper-light", persist=False)
    qapp.processEvents()
    window.playback.step_forward()

    assert window.graph_view.nodes[node_ids[0]]._state == "current"
    window.close()
