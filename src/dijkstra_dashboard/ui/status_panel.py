from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QFontDatabase, QResizeEvent

class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.base_title_size = 14
        self.base_text_size = 10
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Determine font family
        if "Orbitron" in QFontDatabase.families():
            self.font_family = "Orbitron"
        else:
            self.font_family = "Arial"

        # Title (removed "AI Enhanced Mode")
        self.title = QLabel("Dijkstra Visualizer")
        self.title.setFont(QFont(self.font_family, self.base_title_size, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #00ffff;")
        layout.addWidget(self.title)

        # Legend
        self.legend = QLabel("🔵 Visited  🟢 Final Path  🔴 Not in Path")
        self.legend.setFont(QFont(self.font_family, self.base_text_size))
        self.legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.legend.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.legend)

        # Status text area
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont(self.font_family, self.base_text_size))
        self.status_text.setMinimumHeight(200)
        self.status_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.status_text)

        self.setLayout(layout)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        # Scale fonts based on panel width
        width = event.size().width()
        scale = max(0.8, min(1.5, width / 300))  # Scale between 0.8x and 1.5x

        title_size = int(self.base_title_size * scale)
        text_size = int(self.base_text_size * scale)

        self.title.setFont(QFont(self.font_family, title_size, QFont.Weight.Bold))
        self.legend.setFont(QFont(self.font_family, text_size))
        self.status_text.setFont(QFont(self.font_family, text_size))

    def update_status(self, message, color="#ffffff"):
        cursor = self.status_text.textCursor()
        format = QTextCharFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(message + "\n")
        self.status_text.setTextCursor(cursor)
        self.status_text.ensureCursorVisible()

    def clear(self):
        self.status_text.clear()

    def show_path(self, path, distance, visited_order, weight_lookup=None, label_lookup=None):
        self.status_text.clear()

        if not path:
            self.update_status("No path found.", "#ff5555")
            return

        if weight_lookup is None:
            weight_lookup = lambda _start, _end: 0
        if label_lookup is None:
            label_lookup = lambda node_id: node_id

        # Add summary header
        start_label = label_lookup(path[0])
        end_label = label_lookup(path[-1])
        self.update_status(f"✅ Shortest path from {start_label} to {end_label} found!\n", "#00ff00")

        # Show visited order
        self.update_status("Visited Order:", "#00ffff")
        self.update_status(" → ".join(label_lookup(node_id) for node_id in visited_order), "#ffffff")

        # Show final path
        self.update_status("\nShortest Path:", "#00ffff")
        self.update_status(" → ".join(label_lookup(node_id) for node_id in path), "#ffffff")

        # Show total distance
        self.update_status(f"\nTotal Distance: {distance}", "#00ffff")

        # Show path steps with weights
        self.update_status("\nPath Details:", "#00ffff")
        total = 0
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            weight = weight_lookup(current, next_node)
            total += weight
            current_label = label_lookup(current)
            next_label = label_lookup(next_node)
            self.update_status(f"{current_label} → {next_label} ({weight})", "#ffffff")
        self.update_status(f"Total: {total}", "#00ffff")
