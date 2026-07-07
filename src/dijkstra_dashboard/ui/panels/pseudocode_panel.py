from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from dijkstra_dashboard.ui.theme import current_theme

TINT_ALPHA = 64  # ~25% accent wash for the secondary lines


class PseudocodePanel(QListWidget):
    """Monospace pseudocode with per-step line emphasis."""

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWordWrap(False)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        self._display_name = ""
        self._last_lines: list[int] = []

    def set_algorithm(self, display_name, pseudocode):
        self._display_name = display_name
        self._last_lines = []
        self.clear()
        for line in pseudocode:
            self.addItem(QListWidgetItem(line))
        self.highlight_step([])

    def highlight_step(self, lines):
        self._last_lines = list(lines)
        theme = current_theme()
        accent = QColor(theme.accent)
        tint = QColor(theme.accent)
        tint.setAlpha(TINT_ALPHA)
        contrast = QColor(theme.highlight_text)
        default_fg = QColor(theme.text)
        transparent = QColor(0, 0, 0, 0)

        emphasis = lines[0] if lines else None
        tinted = set(lines[1:]) if lines else set()

        for index in range(self.count()):
            item = self.item(index)
            if index == emphasis:
                item.setBackground(accent)
                item.setForeground(contrast)
            elif index in tinted:
                item.setBackground(tint)
                item.setForeground(default_fg)
            else:
                item.setBackground(transparent)
                item.setForeground(default_fg)

    def refresh_theme(self, theme):
        # Font family stays monospace; only re-resolve highlight colours.
        self.highlight_step(self._last_lines)
