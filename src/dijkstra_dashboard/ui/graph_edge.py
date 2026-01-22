from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsDropShadowEffect, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QColor, QFont, QPainterPath, QBrush, QPolygonF, QFontDatabase
import math

class GraphEdge(QGraphicsPathItem):
    def __init__(self, start_node, end_node, weight, directed=False, bidirectional=False,
                 curve_sign=1, curve_offset=8):
        super().__init__()
        self.setZValue(0)
        self.start_node = start_node
        self.end_node = end_node
        self.weight = weight
        self.directed = directed
        self.bidirectional = bidirectional
        self.curve_sign = 1 if curve_sign >= 0 else -1
        self.curve_offset = float(curve_offset)
        self._label_in_scene = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # Set default appearance
        self.setPen(QPen(QColor(100, 100, 100), 2))

        # Add weight label (just the weight value)
        self.label = QGraphicsSimpleTextItem(f"{weight}")
        self.label.setZValue(3)
        # Try to use Orbitron, fall back to system font if not available
        if "Orbitron" in QFontDatabase.families():
            self.label.setFont(QFont("Orbitron", 14, QFont.Weight.ExtraBold))
        else:
            self.label.setFont(QFont("Arial", 14, QFont.Weight.ExtraBold))
        self.label.setBrush(QBrush(QColor("#ffffff")))
        # Add glow effect to the label itself for better pop
        self.label_glow = QGraphicsDropShadowEffect()
        self.label_glow.setBlurRadius(15)
        self.label_glow.setColor(QColor(0, 255, 255, 150))
        self.label_glow.setOffset(0)
        self.label.setGraphicsEffect(self.label_glow)

        # Add edge glow effect
        self.glow_effect = QGraphicsDropShadowEffect()
        self.glow_effect.setBlurRadius(10)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setColor(QColor(0, 255, 255, 100))
        self.setGraphicsEffect(self.glow_effect)

        # Update position when nodes move
        self.update_position()

        self.set_state("default")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
            scene = self.scene()
            if scene and not self._label_in_scene:
                scene.addItem(self.label)
                self._label_in_scene = True
            elif scene is None:
                self._label_in_scene = False
        return super().itemChange(change, value)

    def dispose(self):
        self.label.setGraphicsEffect(None)
        self.setGraphicsEffect(None)
        label_scene = self.label.scene()
        if label_scene is not None:
            label_scene.removeItem(self.label)
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
        self._label_in_scene = False

    def update_position(self):
        # Calculate control points for curved edge
        start_pos = self.start_node.pos()
        end_pos = self.end_node.pos()

        direction = end_pos - start_pos
        length = (direction.x() ** 2 + direction.y() ** 2) ** 0.5
        if length > 0:
            direction /= length

        start_radius = self.start_node.rect().width() / 2
        end_radius = self.end_node.rect().width() / 2
        arrow_size = 8
        # Minimal clearance - arrows should nearly touch nodes
        start_clearance = start_radius + 1
        end_clearance = end_radius + 1

        if length > (start_clearance + end_clearance):
            start_anchor = start_pos + direction * start_clearance
            end_anchor = end_pos - direction * end_clearance
        else:
            start_anchor = start_pos
            end_anchor = end_pos

        # Calculate midpoint and control points
        mid = (start_anchor + end_anchor) / 2
        normal = QPointF(end_anchor.y() - start_anchor.y(), start_anchor.x() - end_anchor.x())
        normal_length = (normal.x() ** 2 + normal.y() ** 2) ** 0.5
        if normal_length > 0:
            normal /= normal_length
            # Offset the curve - use curve_sign for direction
            control_point = mid + normal * (self.curve_offset * self.curve_sign)

            # Create curved path
            path = QPainterPath()
            path.moveTo(start_anchor)
            path.quadTo(control_point, end_anchor)

            if self.directed:
                # Add arrow at the end using path tangent
                end_tip = path.pointAtPercent(1.0)
                end_tail = path.pointAtPercent(0.96)
                end_dir = end_tip - end_tail
                end_len = (end_dir.x() ** 2 + end_dir.y() ** 2) ** 0.5
                if end_len == 0:
                    end_dir = QPointF(direction.x(), direction.y())
                    end_len = (end_dir.x() ** 2 + end_dir.y() ** 2) ** 0.5 or 1.0
                end_dir /= end_len
                end_side = QPointF(-end_dir.y(), end_dir.x())
                arrow_p1 = end_tip - end_dir * arrow_size + end_side * (arrow_size * 0.6)
                arrow_p2 = end_tip - end_dir * arrow_size - end_side * (arrow_size * 0.6)

                arrow_path = QPainterPath()
                arrow_path.moveTo(end_tip)
                arrow_path.lineTo(arrow_p1)
                arrow_path.lineTo(arrow_p2)
                arrow_path.closeSubpath()

                combined_path = QPainterPath(path)
                combined_path.addPath(arrow_path)
                if self.bidirectional:
                    start_tip = path.pointAtPercent(0.0)
                    start_tail = path.pointAtPercent(0.04)
                    start_dir = start_tip - start_tail
                    start_len = (start_dir.x() ** 2 + start_dir.y() ** 2) ** 0.5
                    if start_len == 0:
                        start_dir = QPointF(-direction.x(), -direction.y())
                        start_len = (start_dir.x() ** 2 + start_dir.y() ** 2) ** 0.5 or 1.0
                    start_dir /= start_len
                    start_side = QPointF(-start_dir.y(), start_dir.x())
                    start_p1 = start_tip - start_dir * arrow_size + start_side * (arrow_size * 0.6)
                    start_p2 = start_tip - start_dir * arrow_size - start_side * (arrow_size * 0.6)
                    start_arrow = QPainterPath()
                    start_arrow.moveTo(start_tip)
                    start_arrow.lineTo(start_p1)
                    start_arrow.lineTo(start_p2)
                    start_arrow.closeSubpath()
                    combined_path.addPath(start_arrow)
                self.setPath(combined_path)
            else:
                self.setPath(path)

            # Position weight label near the curve midpoint
            text_rect = self.label.boundingRect()
            label_pos = path.pointAtPercent(0.5)

            # Calculate tangent by getting two nearby points on the curve
            p1 = path.pointAtPercent(0.48)
            p2 = path.pointAtPercent(0.52)
            tangent = p2 - p1
            tangent_len = math.sqrt(tangent.x() ** 2 + tangent.y() ** 2)

            if tangent_len > 0:
                # Normal is perpendicular to tangent
                normal_vec = QPointF(-tangent.y() / tangent_len, tangent.x() / tangent_len)
            else:
                normal_vec = normal

            # Make sure normal points toward the curve bulge (same side as control point)
            bulge = control_point - mid
            if (normal_vec.x() * bulge.x() + normal_vec.y() * bulge.y()) < 0:
                normal_vec = QPointF(-normal_vec.x(), -normal_vec.y())

            # Use smaller offset to keep labels closer to edges
            label_offset = 15
            label_pos += normal_vec * label_offset

            # Calculate label position centered on the offset point
            label_x = label_pos.x() - text_rect.width() / 2
            label_y = label_pos.y() - text_rect.height() / 2

            # Clamp label position to stay within scene bounds with padding
            scene = self.scene()
            if scene:
                scene_rect = scene.sceneRect()
                padding = 10
                min_x = scene_rect.left() + padding
                max_x = scene_rect.right() - text_rect.width() - padding
                min_y = scene_rect.top() + padding
                max_y = scene_rect.bottom() - text_rect.height() - padding

                label_x = max(min_x, min(label_x, max_x))
                label_y = max(min_y, min(label_y, max_y))

            self.label.setPos(label_x, label_y)
        else:
            # Fallback to straight line if nodes are too close
            self.setPath(QPainterPath(QLineF(start_anchor, end_anchor)))
            text_rect = self.label.boundingRect()
            label_x = mid.x() - text_rect.width() / 2
            label_y = mid.y() - text_rect.height() / 2

            # Clamp label position to stay within scene bounds
            scene = self.scene()
            if scene:
                scene_rect = scene.sceneRect()
                padding = 10
                min_x = scene_rect.left() + padding
                max_x = scene_rect.right() - text_rect.width() - padding
                min_y = scene_rect.top() + padding
                max_y = scene_rect.bottom() - text_rect.height() - padding

                label_x = max(min_x, min(label_x, max_x))
                label_y = max(min_y, min(label_y, max_y))

            self.label.setPos(label_x, label_y)

    def highlight(self, is_final_path=False):
        if is_final_path:
            self.setZValue(1)
            color = QColor("#00ff00")
            self.setPen(QPen(color, 3))  # Bright green
            self.glow_effect.setColor(QColor(0, 255, 0, 150))
            self.glow_effect.setBlurRadius(25)
            self.label.setBrush(QBrush(QColor("#66ff66")))
            self.label_glow.setColor(QColor(0, 255, 0, 160))
            self.label_glow.setBlurRadius(12)
        else:
            self.setZValue(0.5)
            color = QColor("#00ffff")
            self.setPen(QPen(color, 2))  # Cyan
            self.glow_effect.setColor(QColor(0, 255, 255, 120))
            self.glow_effect.setBlurRadius(15)
            self.label.setBrush(QBrush(QColor("#55ffff")))
            self.label_glow.setColor(QColor(0, 255, 255, 160))
            self.label_glow.setBlurRadius(12)

    def reset(self):
        self.setZValue(0)
        color = QColor(100, 100, 100)
        self.setPen(QPen(color, 2))
        self.label.setBrush(QBrush(QColor("#ffffff")))
        self.glow_effect.setColor(QColor(0, 255, 255, 100))
        self.glow_effect.setBlurRadius(10)
        self.label_glow.setColor(QColor(0, 255, 255, 150))
        self.label_glow.setBlurRadius(15)

    def set_state(self, state):
        if state == "final":
            self.setZValue(1)
            color = QColor("#00ff00")
            self.setPen(QPen(color, 3))  # Bright green
            self.glow_effect.setColor(QColor(0, 255, 0, 180))
            self.glow_effect.setBlurRadius(25)
            self.label.setBrush(QBrush(QColor("#00ff00")))  # Green for used edge
        elif state == "visited":
            self.setZValue(0.5)
            color = QColor("#00ffff")
            self.setPen(QPen(color, 2))  # Cyan
            self.glow_effect.setColor(QColor(0, 255, 255, 120))
            self.glow_effect.setBlurRadius(15)
            self.label.setBrush(QBrush(QColor("#00ffff")))
        elif state == "idle":
            self.setZValue(0)
            color = QColor("#ff0044")
            self.setPen(QPen(color, 2))  # Neon red
            self.glow_effect.setColor(QColor(255, 0, 80, 200))
            self.glow_effect.setBlurRadius(30)
            self.label.setBrush(QBrush(QColor("#ff3333")))  # Red for unused edge cost
            self.label_glow.setColor(QColor(255, 0, 80, 200))
            self.label_glow.setBlurRadius(10)
        elif state == "unused":
            self.setZValue(0)
            color = QColor("#ff0044")
            self.setPen(QPen(color, 2))
            self.glow_effect.setColor(QColor(255, 0, 80, 180))
            self.glow_effect.setBlurRadius(24)
            self.label.setBrush(QBrush(QColor("#ff3333")))
            self.label_glow.setColor(QColor(255, 0, 80, 200))
            self.label_glow.setBlurRadius(10)
        elif state == "default":
            self.setZValue(0)
            color = QColor(100, 100, 100)
            self.setPen(QPen(color, 2))  # Neutral gray
            self.glow_effect.setColor(QColor(0, 255, 255, 80))
            self.glow_effect.setBlurRadius(8)
            self.label.setBrush(QBrush(QColor("#bbbbbb")))
            self.label_glow.setColor(QColor(0, 255, 255, 150))
            self.label_glow.setBlurRadius(15)

    def set_cost_label_color(self, color):
        if self.label:
            self.label.setBrush(QBrush(color))
            glow_color = QColor(color)
            glow_color.setAlpha(160)
            self.label_glow.setColor(glow_color)
            self.label_glow.setBlurRadius(10)
            self.label.update()

    def set_weight(self, weight):
        self.weight = weight
        self.label.setText(f"{weight}")
        self.update_position()
