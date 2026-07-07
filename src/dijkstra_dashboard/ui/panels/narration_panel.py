from __future__ import annotations

from PyQt6.QtGui import QFont, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit

from dijkstra_dashboard.ui.theme import current_theme


class NarrationPanel(QTextEdit):
    """Read-only running log of algorithm narration.

    Ports the Phase-1 StatusPanel replay-log pattern: each (message, role) is
    remembered so role colours can be re-resolved against a new theme on
    refresh_theme. Jump markers collapse onto the previous marker so scrubbing
    never floods the log.
    """

    MAX_LOG_LINES = 500

    def __init__(self):
        super().__init__()
        self.setObjectName("statusText")
        self.setReadOnly(True)
        self.setMinimumHeight(120)
        self._log: list[tuple[str, str]] = []
        self._last_is_jump = False
        self.refresh_theme(current_theme())

    def append_line(self, text, role="text"):
        self._log.append((text, role))
        self._trim()
        self._last_is_jump = False
        self._write_line(text, role, current_theme())

    def append_jump_marker(self, k):
        entry = (f"— jumped to step {k} —", "muted")
        if self._last_is_jump and self._log:
            self._log[-1] = entry
        else:
            self._log.append(entry)
            self._trim()
        self._last_is_jump = True
        self._render_all(current_theme())

    def clear(self):
        self._log.clear()
        self._last_is_jump = False
        super().clear()

    def refresh_theme(self, theme):
        self.setFont(theme.display_font(10))
        self._render_all(theme)

    # ------------------------------------------------------------------
    def _trim(self):
        if len(self._log) > self.MAX_LOG_LINES:
            del self._log[: -self.MAX_LOG_LINES]

    def _write_line(self, text, role, theme):
        cursor = self.textCursor()
        text_format = QTextCharFormat()
        color_role = "text" if role == "startup_help" else role
        text_format.setForeground(theme.color(color_role))
        if role == "startup_help":
            text_format.setFontPointSize(12)
        cursor.setCharFormat(text_format)
        cursor.insertText(text + "\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _render_all(self, theme):
        super().clear()
        for text, role in list(self._log):
            self._write_line(text, role, theme)
