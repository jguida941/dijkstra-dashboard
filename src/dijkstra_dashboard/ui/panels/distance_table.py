from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from dijkstra_dashboard.ui.theme import current_theme

INF = float("inf")

_COLUMNS = ("Node", "Distance", "Previous", "State")
_DISTANCE_HEADERS = {"bfs": "Distance (hops)", "astar": "g (tentative)"}

HIGHLIGHT_ALPHA = 46   # current-row wash
FLASH_ALPHA = 130      # changed-cell flash
FLASH_MS = 300


def _fmt(value) -> str:
    if value is None or value == INF:
        return "∞"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _distance_header(algorithm) -> str:
    return _DISTANCE_HEADERS.get(algorithm, "Distance")


def _state_text(frame, node_id) -> str:
    """Mirror the node-precedence from the view design, as display text."""
    distance = frame.distances.get(node_id, INF)
    if frame.is_final and frame.path and node_id in frame.path:
        return "final"
    if frame.is_final and frame.path:
        return "searched, not in path" if distance < INF else ""
    if frame.is_final:
        return "unreachable" if distance == INF else "not in path"
    if node_id == frame.current:
        return "current"
    if node_id in set(frame.visited):
        return "visited"
    if distance < INF:
        return "frontier"
    return ""


class DistanceTable(QTableWidget):
    """Per-node distance / previous / state, refolded from each RenderFrame."""

    def __init__(self):
        super().__init__(0, len(_COLUMNS))
        self.setHorizontalHeaderLabels(list(_COLUMNS))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self._node_ids: list[str] = []
        self._label_of = lambda node_id: node_id
        self._prev_values: dict[tuple[int, int], str] = {}
        self._current_row: int | None = None

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

        self.refresh_theme(current_theme())

    # ------------------------------------------------------------------
    def set_distance_header(self, algorithm):
        headers = list(_COLUMNS)
        headers[1] = _distance_header(algorithm)
        self.setHorizontalHeaderLabels(headers)

    def set_nodes(self, node_ids, label_of):
        self._node_ids = list(node_ids)
        self._label_of = label_of
        self._prev_values = {}
        self._current_row = None
        self._flash_timer.stop()

        self.setRowCount(len(self._node_ids))
        transparent = QColor(0, 0, 0, 0)
        for row, node_id in enumerate(self._node_ids):
            self._ensure_item(row, 0).setText(label_of(node_id))
            for col in (1, 2, 3):
                self._ensure_item(row, col).setText("")
            for col in range(len(_COLUMNS)):
                self._ensure_item(row, col).setBackground(transparent)

    def render_frame(self, frame, label_of):
        self._label_of = label_of
        theme = current_theme()
        highlight = self._alpha(theme, HIGHLIGHT_ALPHA)
        flash = self._alpha(theme, FLASH_ALPHA)
        transparent = QColor(0, 0, 0, 0)

        self._current_row = None
        new_values: dict[tuple[int, int], str] = {}
        for row, node_id in enumerate(self._node_ids):
            distance = frame.distances.get(node_id, INF)
            prev_id = frame.prev.get(node_id)
            prev_text = label_of(prev_id) if prev_id is not None else "—"
            texts = (_fmt(distance), prev_text, _state_text(frame, node_id))
            for offset, text in enumerate(texts):
                col = offset + 1
                self._ensure_item(row, col).setText(text)
                new_values[(row, col)] = text
            if node_id == frame.current:
                self._current_row = row

        # F12: repaint ALL cell backgrounds from the computed base first...
        for row in range(self.rowCount()):
            base = highlight if row == self._current_row else transparent
            for col in range(len(_COLUMNS)):
                self._ensure_item(row, col).setBackground(base)

        # ...then overlay flashes for cells whose value changed (forward only).
        self._flash_timer.stop()
        if frame.forward_step and self._prev_values:
            changed = [cell for cell, text in new_values.items()
                       if self._prev_values.get(cell) != text]
            for row, col in changed:
                self._ensure_item(row, col).setBackground(flash)
            if changed:
                self._flash_timer.start(FLASH_MS)

        self._prev_values = new_values

    def refresh_theme(self, theme):
        self.setFont(theme.display_font(10))
        self._clear_flash()

    # ------------------------------------------------------------------
    def _clear_flash(self):
        theme = current_theme()
        highlight = self._alpha(theme, HIGHLIGHT_ALPHA)
        transparent = QColor(0, 0, 0, 0)
        for row in range(self.rowCount()):
            base = highlight if row == self._current_row else transparent
            for col in range(len(_COLUMNS)):
                self._ensure_item(row, col).setBackground(base)

    def _ensure_item(self, row, col) -> QTableWidgetItem:
        item = self.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.setItem(row, col, item)
        return item

    @staticmethod
    def _alpha(theme, alpha) -> QColor:
        color = QColor(theme.accent)
        color.setAlpha(alpha)
        return color
