"""Phase 6 (UI) — RecentFiles (QSettings-backed MRU list).

Injected QSettings (tmp .ini) per F3/Trap4 — the user's real settings are never
touched. Contract: max 8, most-recent-first, dedupe by absolute path, plus the
MainWindow "Open Recent" submenu rebuild.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings

from dijkstra_dashboard.ui.recent_files import RecentFiles


def _settings(tmp_path):
    return QSettings(str(tmp_path / "recent.ini"), QSettings.Format.IniFormat)


def test_add_keeps_max_eight_most_recent_first(tmp_path):
    recents = RecentFiles(_settings(tmp_path))
    for i in range(9):
        recents.add(str(tmp_path / f"g{i}.json"))

    listed = recents.list()
    assert len(listed) == 8
    assert listed[0].endswith("g8.json")          # most recent at front
    assert all(not p.endswith("g0.json") for p in listed)  # oldest evicted


def test_dedupe_moves_existing_to_front(tmp_path):
    recents = RecentFiles(_settings(tmp_path))
    a = str(tmp_path / "a.json")
    b = str(tmp_path / "b.json")
    recents.add(a)
    recents.add(b)
    recents.add(a)  # re-adding a moves it to front, no duplicate

    listed = recents.list()
    assert len(listed) == 2
    assert listed[0].endswith("a.json")
    assert listed[1].endswith("b.json")


def test_remove_and_clear(tmp_path):
    recents = RecentFiles(_settings(tmp_path))
    a = str(tmp_path / "a.json")
    b = str(tmp_path / "b.json")
    recents.add(a)
    recents.add(b)

    recents.remove(a)
    listed = recents.list()
    assert len(listed) == 1
    assert listed[0].endswith("b.json")

    recents.clear()
    assert recents.list() == []


def test_persists_over_same_ini(tmp_path):
    settings = _settings(tmp_path)
    recents = RecentFiles(settings)
    recents.add(str(tmp_path / "a.json"))
    settings.sync()

    reopened = RecentFiles(_settings(tmp_path))
    assert len(reopened.list()) == 1
    assert reopened.list()[0].endswith("a.json")


@pytest.mark.ui
def test_mainwindow_open_recent_submenu_reflects_recents(qapp, tmp_path):
    from dijkstra_dashboard.ui.main_window import MainWindow

    window = MainWindow(settings=_settings(tmp_path))

    file_menu = next(
        m.menu() for m in window.menuBar().actions()
        if m.menu() is not None and m.menu().title() == "File"
    )
    recent_menu = next(
        (a.menu() for a in file_menu.actions()
         if a.menu() is not None and a.menu().title() == "Open Recent"),
        None,
    )
    assert recent_menu is not None

    window.recents.add(str(tmp_path / "one.json"))
    window.recents.add(str(tmp_path / "two.json"))
    window._rebuild_recent_menu()

    data = [a.data() for a in recent_menu.actions() if a.data()]
    assert [d.rsplit("/", 1)[-1] for d in data] == ["two.json", "one.json"]  # MRU first

    window.close()
