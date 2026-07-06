"""RecentFiles — a small QSettings-backed most-recently-used path list.

Signal-less by design: MainWindow rebuilds its "Open Recent" submenu after each
mutation. The backing :class:`~PyQt6.QtCore.QSettings` is injected (production
passes a bare ``QSettings()`` with org/app already set in ``__main__``; tests
pass an isolated tmp ``.ini`` so the user's real settings are never touched).
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QSettings

#: Settings key holding the MRU list.
RECENT_KEY = "recent_files"
#: Maximum retained entries.
MAX_RECENT = 8


class RecentFiles:
    def __init__(self, settings: QSettings, key: str = RECENT_KEY,
                 max_items: int = MAX_RECENT) -> None:
        self._settings = settings
        self._key = key
        self._max = max_items

    def list(self) -> list[str]:
        """Return the stored paths, most-recent-first."""
        value = self._settings.value(self._key, [])
        if value is None:
            return []
        # QSettings/IniFormat collapses a one-element list back to a bare str.
        if isinstance(value, str):
            items = [value] if value else []
        else:
            items = list(value)
        return [str(item) for item in items if item]

    def add(self, path: str) -> None:
        """Insert ``path`` at the front (dedup by absolute path), cap at max."""
        target = os.path.abspath(path)
        items = [p for p in self.list() if os.path.abspath(p) != target]
        items.insert(0, target)
        del items[self._max:]
        self._settings.setValue(self._key, items)

    def remove(self, path: str) -> None:
        """Drop ``path`` (matched by absolute path) if present."""
        target = os.path.abspath(path)
        items = [p for p in self.list() if os.path.abspath(p) != target]
        self._settings.setValue(self._key, items)

    def clear(self) -> None:
        """Remove every entry."""
        self._settings.setValue(self._key, [])
