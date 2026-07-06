from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QResizeEvent, QTextCharFormat
from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from dijkstra_dashboard.ui.theme import current_theme


class StatusPanel(QWidget):
    MAX_LOG_LINES = 500

    def __init__(self):
        super().__init__()
        self.base_title_size = 14
        self.base_text_size = 10
        self._log: list[tuple[str, str]] = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.title = QLabel("Dijkstra Visualizer")
        self.title.setObjectName("statusTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.legend = QLabel()
        self.legend.setObjectName("legendLabel")
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.legend)

        self.status_text = QTextEdit()
        self.status_text.setObjectName("statusText")
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        layout.addWidget(self.status_text)

        self.setLayout(layout)
        self.refresh_theme(current_theme())

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._apply_scaled_fonts(event.size().width())

    def update_status(self, message, color="text"):
        self._log.append((message, color))
        if len(self._log) > self.MAX_LOG_LINES:
            del self._log[: -self.MAX_LOG_LINES]
        self._write_line(message, color)

    def _write_line(self, message, color):
        cursor = self.status_text.textCursor()
        text_format = QTextCharFormat()
        text_format.setForeground(current_theme().color(color))
        cursor.setCharFormat(text_format)
        cursor.insertText(message + "\n")
        self.status_text.setTextCursor(cursor)
        self.status_text.ensureCursorVisible()

    def clear(self):
        self._log.clear()
        self.status_text.clear()

    def refresh_theme(self, theme):
        self._rebuild_legend(theme)
        width = self.width() or 300
        self._apply_scaled_fonts(width)
        # Replay scrollback so role colors re-resolve against the new theme.
        self.status_text.clear()
        for message, color in list(self._log):
            self._write_line(message, color)

    def show_path(self, path, distance, visited_order, weight_lookup=None, label_lookup=None):
        self.clear()

        if not path:
            self.update_status("No path found.", "error")
            return

        if weight_lookup is None:
            weight_lookup = lambda _start, _end: 0
        if label_lookup is None:
            label_lookup = lambda node_id: node_id

        start_label = label_lookup(path[0])
        end_label = label_lookup(path[-1])
        self.update_status(f"✅ Shortest path from {start_label} to {end_label} found!\n", "success")

        self.update_status("Visited Order:", "accent")
        self.update_status(" → ".join(label_lookup(node_id) for node_id in visited_order), "text")

        self.update_status("\nShortest Path:", "accent")
        self.update_status(" → ".join(label_lookup(node_id) for node_id in path), "text")

        self.update_status(f"\nTotal Distance: {distance}", "accent")

        self.update_status("\nPath Details:", "accent")
        total = 0
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            weight = weight_lookup(current, next_node)
            total += weight
            current_label = label_lookup(current)
            next_label = label_lookup(next_node)
            self.update_status(f"{current_label} → {next_label} ({weight})", "text")
        self.update_status(f"Total: {total}", "accent")

    def _apply_scaled_fonts(self, width):
        theme = current_theme()
        scale = max(0.8, min(1.5, width / 300))
        title_size = int(self.base_title_size * scale)
        text_size = int(self.base_text_size * scale)

        self.title.setFont(theme.display_font(title_size, QFont.Weight.Bold))
        self.legend.setFont(theme.display_font(text_size))
        self.status_text.setFont(theme.display_font(text_size))

    def _rebuild_legend(self, theme):
        entries = (
            ("Current", theme.node_style("current").ring),
            ("Visited", theme.node_style("visited").ring),
            ("Final path", theme.node_style("final").ring),
            ("Not in path", theme.node_style("not_in_path").ring),
            ("Unreachable", theme.node_style("unreachable").ring),
        )
        self.legend.setText(
            "  ".join(
                f'<span style="color: {color};">&#9679;</span> {label}' for label, color in entries
            )
        )
