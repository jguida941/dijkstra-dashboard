"""Snapshot-based undo command for the graph view.

The editor takes whole-graph ``to_dict`` snapshots and restores by rebuilding
the view through ``set_graph`` (which already unloads the run, repopulates the
combos and clears decorations). A single command type carries the before/after
pair; the view supplies the restore callback.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtGui import QUndoCommand


class GraphSnapshotCommand(QUndoCommand):
    """Restore whole-graph snapshots on undo/redo.

    ``QUndoStack.push`` fires ``redo()`` synchronously at push time, but the
    mutation has ALREADY been applied to the live graph by that point, so the
    first ``redo()`` must be a no-op -- re-applying ``after`` would rebuild the
    scene and double-emit ``graph_changed``. The standard ``_first`` guard makes
    the pushed-time redo inert; every later redo restores ``after`` for real.
    """

    def __init__(self, text: str, before: dict, after: dict,
                 restore: Callable[[dict], None]) -> None:
        super().__init__(text)
        self._before = before
        self._after = after
        self._restore = restore
        self._first = True

    def redo(self) -> None:
        if self._first:
            self._first = False
            return
        self._restore(self._after)

    def undo(self) -> None:
        self._restore(self._before)
