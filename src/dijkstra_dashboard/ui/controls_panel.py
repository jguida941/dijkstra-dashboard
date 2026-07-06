from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton, QSlider, QLabel, QCheckBox
from PyQt6.QtCore import Qt

class ControlsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Start node selection
        self.start_combo = QComboBox()
        self.start_combo.addItems(['A', 'B', 'C', 'D', 'E', 'F'])
        self.start_combo.setCurrentText('A')
        layout.addWidget(self.start_combo)
        
        # Target node selection
        self.target_combo = QComboBox()
        self.target_combo.addItems(['A', 'B', 'C', 'D', 'E', 'F'])
        self.target_combo.setCurrentText('F')
        layout.addWidget(self.target_combo)

        # Directed mode toggle
        self.directed_toggle = QCheckBox("Directed")
        layout.addWidget(self.directed_toggle)
        
        # Run button
        self.run_button = QPushButton("Run Visualization")
        layout.addWidget(self.run_button)

        # Step button
        self.step_button = QPushButton("Step")
        layout.addWidget(self.step_button)

        # Play/Pause button
        self.play_button = QPushButton("Play")
        layout.addWidget(self.play_button)

        # Reset button
        self.reset_button = QPushButton("Reset")
        layout.addWidget(self.reset_button)

        # Speed slider
        speed_label = QLabel("Speed")
        layout.addWidget(speed_label)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(120)
        layout.addWidget(self.speed_slider)

        # Help button
        self.help_button = QPushButton("Controls")
        layout.addWidget(self.help_button)

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

    def get_start_node_id(self):
        return self.start_combo.currentData() or self.start_combo.currentText()

    def get_target_node_id(self):
        return self.target_combo.currentData() or self.target_combo.currentText()
