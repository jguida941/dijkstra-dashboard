from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsSimpleTextItem, QGraphicsDropShadowEffect, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QRadialGradient, QFontDatabase

class GraphNode(QGraphicsEllipseItem):
    def __init__(self, name, node_id=None, move_callback=None):
        super().__init__(-20, -20, 40, 40)
        self.name = name
        self.node_id = node_id or name
        self.move_callback = move_callback

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        # Set default appearance with gradient
        gradient = QRadialGradient(0, 0, 20)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(230, 230, 230))
        
        self.setPen(QPen(QColor(50, 50, 50), 2))
        self.setBrush(QBrush(gradient))
        
        # Add text label with better centering and font, attach as child
        self.label = QGraphicsSimpleTextItem(name, self)

        # Try to use Orbitron, fall back to system font if not available
        if "Orbitron" in QFontDatabase.families():
            self.label.setFont(QFont("Orbitron", 16, QFont.Weight.Bold))
        else:
            self.label.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        self.label.setBrush(QBrush(QColor("#ffffff")))
        self.label.setZValue(2)

        # Add text shadow effect
        text_shadow = QGraphicsDropShadowEffect()
        text_shadow.setBlurRadius(6)
        text_shadow.setColor(QColor(0, 0, 0, 180))
        text_shadow.setOffset(0, 0)
        self.label.setGraphicsEffect(text_shadow)

        # Center the text precisely
        text_rect = self.label.boundingRect()
        self.label.setPos(-text_rect.width()/2, -text_rect.height()/2 - 2)


        # Add glow effect
        self.glow_effect = QGraphicsDropShadowEffect()
        self.glow_effect.setColor(QColor(0, 255, 255, 100))
        self.glow_effect.setBlurRadius(20)
        self.glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self.glow_effect)
        self.setZValue(2)

        # Create pulse animation
        self.pulse_animation = QPropertyAnimation(self.glow_effect, b"blurRadius")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.pulse_animation.setStartValue(20)
        self.pulse_animation.setEndValue(40)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop

    def set_label(self, text):
        self.name = text
        self.label.setText(text)
        text_rect = self.label.boundingRect()
        self.label.setPos(-text_rect.width() / 2, -text_rect.height() / 2 - 2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Constrain node position to stay within scene bounds
            scene = self.scene()
            if scene:
                scene_rect = scene.sceneRect()
                node_radius = 25  # Node radius + padding
                min_x = scene_rect.left() + node_radius
                max_x = scene_rect.right() - node_radius
                min_y = scene_rect.top() + node_radius
                max_y = scene_rect.bottom() - node_radius

                new_pos = QPointF(value)
                new_pos.setX(max(min_x, min(new_pos.x(), max_x)))
                new_pos.setY(max(min_y, min(new_pos.y(), max_y)))
                return new_pos
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.move_callback is not None:
                self.move_callback(self, value)
        return super().itemChange(change, value)

    def highlight(self, is_final_path=False):
        # Change node color based on whether it's part of the final path
        gradient = QRadialGradient(0, 0, 20)
        if is_final_path:
            # Green for final path
            gradient.setColorAt(0, QColor(0, 255, 0, 200))
            gradient.setColorAt(1, QColor(0, 200, 0, 150))
            self.setPen(QPen(QColor(0, 150, 0), 3))
            self.glow_effect.setColor(QColor(0, 255, 0, 150))
        else:
            # Blue for visited nodes
            gradient.setColorAt(0, QColor(0, 255, 255, 200))
            gradient.setColorAt(1, QColor(0, 200, 255, 150))
            self.setPen(QPen(QColor(0, 150, 255), 3))
            self.glow_effect.setColor(QColor(0, 255, 255, 150))

        self.setBrush(QBrush(gradient))
        self.glow_effect.setBlurRadius(30)

        # Make label more visible during highlight
        self.label.setBrush(QBrush(QColor("#ffffff")))

        # Start pulse animation
        self.pulse_animation.start()

    def reset(self):
        # Stop pulse animation
        self.pulse_animation.stop()

        # Reset to default appearance
        gradient = QRadialGradient(0, 0, 20)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(230, 230, 230))

        self.setPen(QPen(QColor(50, 50, 50), 2))
        self.setBrush(QBrush(gradient))

        # Reset glow effect
        self.glow_effect.setColor(QColor(0, 255, 255, 100))
        self.glow_effect.setBlurRadius(20)

        # Reset label color
        self.label.setBrush(QBrush(QColor("#ffffff")))
    def set_state(self, state):
        if state == "idle":
            self.reset()
        elif state == "visited":
            self.highlight(is_final_path=False)
        elif state == "final":
            self.highlight(is_final_path=True)
        elif state == "unused":
            self.pulse_animation.stop()
            gradient = QRadialGradient(0, 0, 20)
            gradient.setColorAt(0, QColor(255, 0, 0, 180))
            gradient.setColorAt(1, QColor(150, 0, 0, 150))
            self.setPen(QPen(QColor(180, 0, 0), 2))
            self.setBrush(QBrush(gradient))
            self.glow_effect.setColor(QColor(255, 0, 0, 100))
            self.glow_effect.setBlurRadius(20)
            self.label.setBrush(QBrush(QColor("#ffcccc")))
