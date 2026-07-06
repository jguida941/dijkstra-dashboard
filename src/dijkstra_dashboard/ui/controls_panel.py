from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QSlider, QLabel, QCheckBox
from PyQt6.QtCore import Qt

class ControlsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # ---- Row 1: algorithm + endpoints + transport controls ----
        row1 = QHBoxLayout()
        row1.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Algorithm selection (objectName-free, non-editable)
        self.algorithm_combo = QComboBox()
        row1.addWidget(self.algorithm_combo)

        # Start node selection
        self.start_combo = QComboBox()
        self.start_combo.addItems(['A', 'B', 'C', 'D', 'E', 'F'])
        self.start_combo.setCurrentText('A')
        row1.addWidget(self.start_combo)

        # Target node selection
        self.target_combo = QComboBox()
        self.target_combo.addItems(['A', 'B', 'C', 'D', 'E', 'F'])
        self.target_combo.setCurrentText('F')
        row1.addWidget(self.target_combo)

        # Directed mode toggle
        self.directed_toggle = QCheckBox("Directed")
        row1.addWidget(self.directed_toggle)

        # Run button
        self.run_button = QPushButton("Run Visualization")
        row1.addWidget(self.run_button)

        # Step Back button
        self.step_back_button = QPushButton("⏮ Step Back")
        row1.addWidget(self.step_back_button)

        # Step button
        self.step_button = QPushButton("Step")
        row1.addWidget(self.step_button)

        # Play/Pause button
        self.play_button = QPushButton("Play")
        row1.addWidget(self.play_button)

        # Reset button
        self.reset_button = QPushButton("Reset")
        row1.addWidget(self.reset_button)

        # Help button
        self.help_button = QPushButton("Controls")
        row1.addWidget(self.help_button)

        layout.addLayout(row1)

        # ---- Row 2: timeline scrubber + position + speed ----
        row2 = QHBoxLayout()

        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setEnabled(False)
        row2.addWidget(self.timeline_slider, stretch=1)

        self.position_label = QLabel("0 / 0")
        row2.addWidget(self.position_label)

        speed_label = QLabel("Speed")
        row2.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(120)
        row2.addWidget(self.speed_slider)

        layout.addLayout(row2)

        self.setLayout(layout)

    def set_nodes(self, nodes):
        current_start = self.start_combo.currentData() or self.start_combo.currentText()
        current_target = self.target_combo.currentData() or self.target_combo.currentText()

        self.start_combo.clear()
        self.target_combo.clear()

        label_counts = {}
        for _node_id, label in nodes:
            label_counts[label] = label_counts.get(label, 0) + 1

        for node_id, label in nodes:
            display_label = label
            if label_counts.get(label, 0) > 1:
                display_label = f"{label} ({node_id})"
            self.start_combo.addItem(display_label, userData=node_id)
            self.target_combo.addItem(display_label, userData=node_id)

        if nodes:
            start_index = self.start_combo.findData(current_start)
            if start_index >= 0:
                self.start_combo.setCurrentIndex(start_index)
            else:
                self.start_combo.setCurrentIndex(0)

            target_index = self.target_combo.findData(current_target)
            if target_index >= 0:
                self.target_combo.setCurrentIndex(target_index)
            else:
                self.target_combo.setCurrentIndex(len(nodes) - 1)

    def set_algorithms(self, items):
        current = self.algorithm_combo.currentData()

        self.algorithm_combo.clear()
        for key, display in items:
            self.algorithm_combo.addItem(display, userData=key)

        if items:
            index = self.algorithm_combo.findData(current)
            if index >= 0:
                self.algorithm_combo.setCurrentIndex(index)
            else:
                self.algorithm_combo.setCurrentIndex(0)

    def get_algorithm_name(self):
        return self.algorithm_combo.currentData()

    def set_timeline(self, total):
        blocked = self.timeline_slider.blockSignals(True)
        self.timeline_slider.setRange(0, total)
        self.timeline_slider.setValue(0)
        self.timeline_slider.blockSignals(blocked)
        self.timeline_slider.setEnabled(True)
        self.position_label.setText(f"0 / {total}")

    def clear_timeline(self):
        blocked = self.timeline_slider.blockSignals(True)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setValue(0)
        self.timeline_slider.blockSignals(blocked)
        self.timeline_slider.setEnabled(False)
        self.position_label.setText("0 / 0")

    def set_timeline_index(self, k):
        blocked = self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(k)
        self.timeline_slider.blockSignals(blocked)
        self.position_label.setText(f"{k} / {self.timeline_slider.maximum()}")

    def get_start_node_id(self):
        return self.start_combo.currentData() or self.start_combo.currentText()

    def get_target_node_id(self):
        return self.target_combo.currentData() or self.target_combo.currentText()
