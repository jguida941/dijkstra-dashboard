from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from dijkstra_dashboard.ui.panels import DistanceTable, NarrationPanel, PseudocodePanel
from dijkstra_dashboard.ui.theme import current_theme


class InspectorPanel(QWidget):
    """Educational inspector: distance table + pseudocode + narration.

    Replaces StatusPanel. Reuses the #statusTitle / #legendLabel / #statusText
    objectNames so the existing QSS keeps styling the title, legend and log.
    Exposes table / pseudocode / narration for MainWindow to drive directly.
    """

    def __init__(self):
        super().__init__()
        self.base_title_size = 14
        self.base_text_size = 10

        self.table = DistanceTable()
        self.pseudocode = PseudocodePanel()
        self.narration = NarrationPanel()

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.title = QLabel("Algorithm Inspector")
        self.title.setObjectName("statusTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.legend = QLabel()
        self.legend.setObjectName("legendLabel")
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.legend)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(True)
        splitter.addWidget(self._section("Distances", self.table))
        splitter.addWidget(self._section("Pseudocode", self.pseudocode))
        splitter.addWidget(self._section("Narration", self.narration))
        splitter.setSizes([340, 420, 380])
        layout.addWidget(splitter, stretch=1)
        self.splitter = splitter

        self.setLayout(layout)
        self.refresh_theme(current_theme())

    def _section(self, title, panel):
        wrapper = QWidget()
        column = QVBoxLayout(wrapper)
        column.setContentsMargins(0, 0, 0, 0)
        header = QLabel(title)
        header.setObjectName("sectionHeader")
        column.addWidget(header)
        column.addWidget(panel, stretch=1)
        return wrapper

    # ---- Facade consumed by MainWindow --------------------------------
    def update_status(self, message, color="text"):
        self.narration.append_line(message, color)

    def clear_all(self):
        self.narration.clear()

    def refresh_theme(self, theme):
        self._rebuild_legend(theme)
        self.title.setFont(theme.display_font(self.base_title_size, QFont.Weight.Bold))
        self.legend.setFont(theme.display_font(self.base_text_size))
        self.table.refresh_theme(theme)
        self.pseudocode.refresh_theme(theme)
        self.narration.refresh_theme(theme)

    def _rebuild_legend(self, theme):
        entries = (
            ("Current", theme.node_style("current").ring),
            ("Frontier", theme.node_style("frontier").ring),
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
