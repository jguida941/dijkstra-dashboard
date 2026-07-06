from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from dijkstra_dashboard.ui.theme import EDGE_STATE_ALIASES, EdgeStyle, current_theme


class WeightChip(QGraphicsItem):
    def __init__(self, text, edge):
        super().__init__()
        self.edge = edge
        self._text = str(text)
        self._style = current_theme().edge_style("default")
        self._accent = current_theme().accent
        self._font = current_theme().display_font(11, QFont.Weight.DemiBold)
        self._bounds: QRectF | None = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(3)

    def boundingRect(self):
        if self._bounds is None:
            metrics = QFontMetricsF(self._font)
            text_rect = metrics.tightBoundingRect(self._text or " ")
            width = max(1.0, text_rect.width()) + 16
            height = max(1.0, text_rect.height()) + 8
            self._bounds = QRectF(-width / 2, -height / 2, width, height)
        return self._bounds

    def paint(self, painter, option, widget=None):
        rect = self.boundingRect()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        painter.setBrush(QBrush(QColor(self._style.chip_bg)))

        if self.isSelected():
            painter.setPen(QPen(QColor(self._accent), 1.8))
        else:
            painter.setPen(QPen(QColor(self._style.chip_border), 1.2))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        painter.setPen(QPen(QColor(self._style.label_fg)))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)

    def set_text(self, text):
        text = str(text)
        if text == self._text:
            return
        self.prepareGeometryChange()
        self._text = text
        self._bounds = None
        self.update()

    def set_chip_style(self, style: EdgeStyle, accent: str):
        self._style = style
        self._accent = accent
        self.update()

    def refresh_theme(self):
        self.prepareGeometryChange()
        theme = current_theme()
        self._font = theme.display_font(11, QFont.Weight.DemiBold)
        self._bounds = None
        self.set_chip_style(theme.edge_style(self.edge._state), theme.accent)


class GraphEdge(QGraphicsPathItem):
    def __init__(
        self,
        start_node,
        end_node,
        weight,
        directed=False,
        bidirectional=False,
        curve_sign=1,
        curve_offset=8,
    ):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.weight = weight
        self.directed = directed
        self.bidirectional = bidirectional
        self.curve_sign = 1 if curve_sign >= 0 else -1
        self.curve_offset = float(curve_offset)
        self._label_in_scene = False
        self._state = "default"
        self._style = current_theme().edge_style("default")
        self._curve_path = QPainterPath()
        self._arrow_paths: list[QPainterPath] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.label = WeightChip(f"{weight}", self)

        self._apply_style(self._style)
        self.update_position()

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
        label_scene = self.label.scene()
        if label_scene is not None:
            label_scene.removeItem(self.label)
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
        self._label_in_scene = False

    def curve_path(self):
        return QPainterPath(self._curve_path)

    def update_position(self):
        start_pos = self.start_node.pos()
        end_pos = self.end_node.pos()

        direction = end_pos - start_pos
        length = math.hypot(direction.x(), direction.y())
        if length > 0:
            direction /= length

        start_radius = self.start_node.rect().width() / 2
        end_radius = self.end_node.rect().width() / 2
        arrow_size = 8
        start_clearance = start_radius + 1
        end_clearance = end_radius + 1

        if length > (start_clearance + end_clearance):
            start_anchor = start_pos + direction * start_clearance
            end_anchor = end_pos - direction * end_clearance
        else:
            start_anchor = start_pos
            end_anchor = end_pos

        mid = (start_anchor + end_anchor) / 2
        normal = QPointF(end_anchor.y() - start_anchor.y(), start_anchor.x() - end_anchor.x())
        normal_length = math.hypot(normal.x(), normal.y())

        if normal_length == 0:
            self._curve_path = QPainterPath(start_anchor)
            self._curve_path.lineTo(end_anchor)
            self._arrow_paths = []
            self.setPath(self._curve_path)
            self._position_label(mid, QPointF(0, -1))
            return

        normal /= normal_length
        control_point = mid + normal * (self.curve_offset * self.curve_sign)

        curve_path = QPainterPath()
        curve_path.moveTo(start_anchor)
        curve_path.quadTo(control_point, end_anchor)
        self._curve_path = curve_path
        self._arrow_paths = []

        if self.directed:
            self._arrow_paths.append(self._arrow_path_for(curve_path, 1.0, 0.96, direction, arrow_size))
            if self.bidirectional:
                reverse_direction = QPointF(-direction.x(), -direction.y())
                self._arrow_paths.append(
                    self._arrow_path_for(curve_path, 0.0, 0.04, reverse_direction, arrow_size)
                )

        combined_path = QPainterPath(curve_path)
        for arrow_path in self._arrow_paths:
            combined_path.addPath(arrow_path)
        self.setPath(combined_path)

        label_pos = curve_path.pointAtPercent(0.5)
        p1 = curve_path.pointAtPercent(0.48)
        p2 = curve_path.pointAtPercent(0.52)
        tangent = p2 - p1
        tangent_len = math.hypot(tangent.x(), tangent.y())

        if tangent_len > 0:
            normal_vec = QPointF(-tangent.y() / tangent_len, tangent.x() / tangent_len)
        else:
            normal_vec = normal

        bulge = control_point - mid
        if (normal_vec.x() * bulge.x() + normal_vec.y() * bulge.y()) < 0:
            normal_vec = QPointF(-normal_vec.x(), -normal_vec.y())

        self._position_label(label_pos + normal_vec * 15, normal_vec)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)

        if self._style.halo:
            painter.setPen(
                QPen(
                    QColor(self._style.halo),
                    self._style.width + 6,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPath(self._curve_path)

        stroke = QColor(self._style.stroke)
        painter.setPen(
            QPen(
                stroke,
                self._style.width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(self._curve_path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(stroke))
        for arrow_path in self._arrow_paths:
            painter.fillPath(arrow_path, QBrush(stroke))

        if self.isSelected():
            accent = QColor(current_theme().accent)
            painter.setPen(
                QPen(
                    accent,
                    self._style.width + 1,
                    Qt.PenStyle.DashLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPath(self._curve_path)

    def set_state(self, state):
        resolved = self._resolve_state(state)
        if resolved == self._state:
            return
        self._state = resolved
        self._style = current_theme().edge_style(resolved)
        self._apply_style(self._style)

    def refresh_theme(self):
        self._state = self._resolve_state(self._state)
        self._style = current_theme().edge_style(self._state)
        self.label.refresh_theme()
        self._apply_style(self._style)
        self.update_position()

    def set_weight(self, weight):
        self.weight = weight
        self.label.set_text(f"{weight}")
        self.update_position()

    def _apply_style(self, style: EdgeStyle):
        bounds_width = max(style.width, style.width + 6 if style.halo else style.width) + 4
        pen = QPen(QColor(style.stroke), bounds_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.label.set_chip_style(style, current_theme().accent)
        self.setZValue(style.z)
        self.setOpacity(style.opacity)
        self.label.setOpacity(style.opacity)
        self.update()
        self.label.update()

    def _resolve_state(self, state):
        theme = current_theme()
        resolved = EDGE_STATE_ALIASES.get(state, state)
        if resolved not in theme.edge_styles:
            return "default"
        return resolved

    def _arrow_path_for(self, curve_path, tip_percent, tail_percent, fallback_direction, arrow_size):
        tip = curve_path.pointAtPercent(tip_percent)
        tail = curve_path.pointAtPercent(tail_percent)
        direction = tip - tail
        direction_len = math.hypot(direction.x(), direction.y())
        if direction_len == 0:
            direction = QPointF(fallback_direction.x(), fallback_direction.y())
            direction_len = math.hypot(direction.x(), direction.y()) or 1.0
        direction /= direction_len

        side = QPointF(-direction.y(), direction.x())
        point_1 = tip - direction * arrow_size + side * (arrow_size * 0.6)
        point_2 = tip - direction * arrow_size - side * (arrow_size * 0.6)

        arrow_path = QPainterPath()
        arrow_path.moveTo(tip)
        arrow_path.lineTo(point_1)
        arrow_path.lineTo(point_2)
        arrow_path.closeSubpath()
        return arrow_path

    def _position_label(self, center, fallback_normal):
        text_rect = self.label.boundingRect()
        label_x = center.x()
        label_y = center.y()

        if text_rect.width() == 0 and text_rect.height() == 0:
            label_x += fallback_normal.x() * 15
            label_y += fallback_normal.y() * 15

        scene = self.scene()
        if scene:
            scene_rect = scene.sceneRect()
            padding = 10
            half_width = text_rect.width() / 2
            half_height = text_rect.height() / 2
            min_x = scene_rect.left() + padding + half_width
            max_x = scene_rect.right() - padding - half_width
            min_y = scene_rect.top() + padding + half_height
            max_y = scene_rect.bottom() - padding - half_height

            label_x = max(min_x, min(label_x, max_x))
            label_y = max(min_y, min(label_y, max_y))

        self.label.setPos(label_x, label_y)
