from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation
from PyQt6.QtGui import QBrush, QColor, QFont, QPen
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsSimpleTextItem,
)

from dijkstra_dashboard.ui.theme import NODE_STATE_ALIASES, NodeStyle, current_theme


class GraphNode(QGraphicsEllipseItem):
    def __init__(self, name, node_id=None, move_callback=None):
        super().__init__(-20, -20, 40, 40)
        self.name = name
        self.node_id = node_id or name
        self.move_callback = move_callback
        self._state = "default"
        self._badge_text: str | None = None
        self._badge_master_visible = True
        self._badge_emphasis = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.label = QGraphicsSimpleTextItem(name, self)
        self.label.setZValue(2)

        self.badge = QGraphicsSimpleTextItem("", self)
        self.badge.setZValue(3)
        self.badge.setVisible(False)

        self.glow_effect = QGraphicsDropShadowEffect()
        self.glow_effect.setBlurRadius(20)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setEnabled(False)
        self.setGraphicsEffect(self.glow_effect)
        self.setZValue(2)

        self.pulse_animation = QPropertyAnimation(self.glow_effect, b"blurRadius")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.pulse_animation.setStartValue(20)
        self.pulse_animation.setEndValue(40)
        self.pulse_animation.setLoopCount(-1)

        self.refresh_theme()

    def set_label(self, text):
        self.name = text
        self.label.setText(text)
        self._recenter_label()
        self._recenter_badge()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene:
                scene_rect = scene.sceneRect()
                node_radius = 25
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

    def set_state(self, state):
        resolved = self._resolve_state(state)
        if resolved == self._state:
            return
        previous = self._state
        self._state = resolved
        if previous == "current" and resolved != "current":
            self.stop_pulse()
        self._apply_style(current_theme().node_style(resolved))
        self._sync_pulse()

    def refresh_theme(self):
        theme = current_theme()
        self.label.setFont(theme.display_font(16, QFont.Weight.Bold))
        self.badge.setFont(theme.display_font(9))
        self._apply_badge_brush()
        self._apply_style(theme.node_style(self._state))
        self._recenter_label()
        self._recenter_badge()
        self._sync_pulse()

    def stop_pulse(self):
        self.pulse_animation.stop()

    def set_distance_text(self, text: str | None):
        self._badge_text = text if text else None
        self.badge.setText(self._badge_text or "")
        self._recenter_badge()
        self._sync_badge_visibility()

    def set_badge_visible(self, visible: bool):
        self._badge_master_visible = bool(visible)
        self._sync_badge_visibility()

    def set_badge_emphasis(self, emphasized: bool):
        self._badge_emphasis = bool(emphasized)
        self._apply_badge_brush()

    def _apply_style(self, style: NodeStyle):
        theme = current_theme()
        self.setBrush(QBrush(QColor(style.fill)))
        self.setPen(QPen(QColor(style.ring), style.ring_width))
        self.label.setBrush(QBrush(QColor(style.text)))
        self.setOpacity(style.opacity)

        if style.glow and theme.glow_enabled:
            self.glow_effect.setColor(QColor(style.glow))
            self.glow_effect.setEnabled(True)
        else:
            self.glow_effect.setEnabled(False)

    def _sync_pulse(self):
        theme = current_theme()
        if self._state == "current" and theme.glow_enabled:
            self.pulse_animation.start()
        else:
            self.stop_pulse()

    def _resolve_state(self, state):
        theme = current_theme()
        resolved = NODE_STATE_ALIASES.get(state, state)
        if resolved not in theme.node_styles:
            return "default"
        return resolved

    def _recenter_label(self):
        text_rect = self.label.boundingRect()
        self.label.setPos(-text_rect.width() / 2, -text_rect.height() / 2 - 2)

    def _recenter_badge(self):
        badge_rect = self.badge.boundingRect()
        self.badge.setPos(-badge_rect.width() / 2, 22)

    def _sync_badge_visibility(self):
        self.badge.setVisible(self._badge_master_visible and self._badge_text is not None)

    def _apply_badge_brush(self):
        theme = current_theme()
        color = theme.accent if self._badge_emphasis else theme.muted_text
        self.badge.setBrush(QBrush(QColor(color)))
