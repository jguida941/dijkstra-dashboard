"""Transient animation layer for the graph view.

The :class:`AnimationCoordinator` owns every short-lived tween (node pops,
travel dots, staggered path reveals, zoom eases). Two invariants make the layer
safe next to the idempotent ``set_state`` renderer:

* Every animation registers a *finalize* closure that snaps its target to the
  exact end state. ``finished`` and cancellation both run that finalize exactly
  once, then deregister -- the scene is never left half-painted.
* Every per-tick callback that touches a graphics item guards
  ``sip.isdeleted(item)`` (animations are parented to the coordinator, never to
  the graphics items, which cannot own ``QObject`` children).

Animations are additive emphasis only; ``set_state`` remains the single writer
of node/edge visual state.
"""
from __future__ import annotations

import math
import random
from typing import Callable

from PyQt6 import sip
from PyQt6.QtCore import Qt, QPointF, QVariantAnimation, QEasingCurve, QObject
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem


class AnimationCoordinator(QObject):
    """Owns and flushes every transient tween in the graph view."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # anim -> finalize closure (snaps the item to its exact end state).
        self._registry: dict[QVariantAnimation, Callable[[], None]] = {}
        # key -> current anim, for "restart replaces + snaps the old one".
        self._keyed: dict[object, QVariantAnimation] = {}
        self._interval_ms: int = 500
        self._bolt_counter: int = 0

    # -- interval bookkeeping ------------------------------------------------
    def set_interval(self, ms: int) -> None:
        """Remember the playback step interval (drives :meth:`scaled`)."""
        self._interval_ms = max(1, int(ms))

    def scaled(self, base_ms: int) -> int:
        """Cap a base duration so a tween never outlives the step interval."""
        capped = min(int(base_ms), int(self._interval_ms * 0.9))
        return max(30, capped)

    # -- registry plumbing ---------------------------------------------------
    def _register(self, anim: QVariantAnimation, finalize: Callable[[], None],
                  key: object | None = None) -> None:
        self._registry[anim] = finalize
        if key is not None:
            self._keyed[key] = anim
        anim.finished.connect(lambda: self._finish(anim, key))

    def _finish(self, anim: QVariantAnimation, key: object | None = None) -> None:
        """Run an animation's finalize exactly once, then deregister it."""
        finalize = self._registry.pop(anim, None)
        if finalize is None:
            return  # already finalized (e.g. via cancel_all)
        if key is not None and self._keyed.get(key) is anim:
            self._keyed.pop(key, None)
        finalize()
        anim.deleteLater()

    def cancel(self, key: object) -> None:
        """Cancel-and-snap only the animation registered under ``key`` (if any)."""
        self._cancel_key(key)

    def _cancel_key(self, key: object) -> None:
        """Cancel-and-snap the animation currently registered under ``key``."""
        old = self._keyed.pop(key, None)
        if old is None:
            return
        finalize = self._registry.pop(old, None)
        old.stop()
        if finalize is not None:
            finalize()
        old.deleteLater()

    def cancel_all(self) -> None:
        """Flush every pending animation: snap to end, remove dots, clear."""
        pending = list(self._registry.items())
        self._registry.clear()
        self._keyed.clear()
        for anim, finalize in pending:
            anim.stop()
            finalize()
            anim.deleteLater()

    # -- primitives ----------------------------------------------------------
    def animate_color(self, key: object, duration: int,
                      apply_fn: Callable[[float], None]) -> QVariantAnimation:
        """Tween a normalized 0->1 progress under ``key``; caller lerps in ``apply_fn``.

        Starting a new animation under the same key cancels-and-snaps the old one.
        """
        self._cancel_key(key)
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(max(1, int(duration)))
        anim.valueChanged.connect(lambda value: apply_fn(float(value)))
        self._register(anim, lambda: apply_fn(1.0), key=key)
        anim.start()
        return anim

    def pop_scale(self, node, duration: int) -> QVariantAnimation:
        """Bump ``node`` scale 1.0 -> 1.12 -> 1.0 (OutBack). Finalize snaps to 1.0."""
        anim = QVariantAnimation(self)
        anim.setDuration(max(1, int(duration)))
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.5, 1.12)
        anim.setKeyValueAt(1.0, 1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)

        def on_tick(value) -> None:
            if not sip.isdeleted(node):
                node.setScale(float(value))

        def finalize() -> None:
            if not sip.isdeleted(node):
                node.setScale(1.0)

        anim.valueChanged.connect(on_tick)
        self._register(anim, finalize)
        anim.start()
        return anim

    def travel_dot(self, scene, curve_path, color, duration: int) -> QVariantAnimation:
        """Ride a small dot along ``curve_path``; removed on finish AND on cancel."""
        dot = QGraphicsEllipseItem(-4.0, -4.0, 8.0, 8.0)
        dot.setBrush(QBrush(QColor(color)))
        dot.setPen(QPen(Qt.PenStyle.NoPen))
        dot.setZValue(4)
        dot.setPos(curve_path.pointAtPercent(0.0))
        scene.addItem(dot)

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(max(1, int(duration)))

        def on_tick(value) -> None:
            if not sip.isdeleted(dot) and dot.scene() is not None:
                dot.setPos(curve_path.pointAtPercent(float(value)))

        def finalize() -> None:
            if not sip.isdeleted(dot) and dot.scene() is not None:
                dot.scene().removeItem(dot)

        anim.valueChanged.connect(on_tick)
        self._register(anim, finalize)
        anim.start()
        return anim

    def lightning(self, scene, curve_path, color, duration: int) -> QVariantAnimation:
        """A flickering jagged bolt that sweeps source->target along ``curve_path``.

        Two scene items (glow underlay + bright core) share a jittered polyline
        whose head advances with the tween and whose tail trails ~30% behind —
        the direction of travel is unmistakable. Both items are removed on
        finish AND on cancel via one finalize.
        """
        core_color = QColor(color)
        glow_color = QColor(color)
        glow_color.setAlpha(70)

        halo_item = QGraphicsPathItem()
        halo_item.setPen(QPen(glow_color, 7.0, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        halo_item.setZValue(4.4)
        bolt_item = QGraphicsPathItem()
        bolt_item.setPen(QPen(core_color, 2.2, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        bolt_item.setZValue(4.5)
        scene.addItem(halo_item)
        scene.addItem(bolt_item)

        self._bolt_counter += 1
        rng = random.Random(self._bolt_counter)
        segments = 12

        def on_tick(value) -> None:
            for item in (halo_item, bolt_item):
                if sip.isdeleted(item) or item.scene() is None:
                    return
            head = min(1.0, float(value))
            tail = max(0.0, head - 0.30)
            points = []
            for i in range(segments + 1):
                p = tail + (head - tail) * (i / segments)
                base = curve_path.pointAtPercent(p)
                # Perpendicular jitter, zero at the ends so the bolt stays
                # anchored to the nodes; re-rolled every tick = flicker.
                angle = math.radians(curve_path.angleAtPercent(p) + 90.0)
                amp = 5.5 * math.sin(math.pi * i / segments) * (rng.random() * 2.0 - 1.0)
                points.append(QPointF(base.x() + math.cos(angle) * amp,
                                      base.y() - math.sin(angle) * amp))
            jag = QPainterPath(points[0])
            for pt in points[1:]:
                jag.lineTo(pt)
            halo_item.setPath(jag)
            bolt_item.setPath(jag)

        def finalize() -> None:
            for item in (halo_item, bolt_item):
                if not sip.isdeleted(item) and item.scene() is not None:
                    item.scene().removeItem(item)

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(max(1, int(duration)))
        anim.valueChanged.connect(on_tick)
        self._register(anim, finalize)
        anim.start()
        return anim

    def run_stagger(self, callbacks, step_ms: int = 120) -> QVariantAnimation | None:
        """Fire ``callbacks[i]`` at ``i * step_ms`` via one animation.

        Cancellation (or natural finish) executes ALL remaining callbacks
        instantly, in order.
        """
        callbacks = list(callbacks)
        count = len(callbacks)
        if count == 0:
            return None

        step = max(1, int(step_ms))
        duration = max(1, count * step)
        fired: set[int] = set()

        def fire_up_to(elapsed_ms: float) -> None:
            for index in range(count):
                if index not in fired and index * step <= elapsed_ms:
                    fired.add(index)
                    callbacks[index]()

        def finalize() -> None:
            for index in range(count):
                if index not in fired:
                    fired.add(index)
                    callbacks[index]()

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration)
        anim.valueChanged.connect(lambda value: fire_up_to(float(value) * duration))
        self._register(anim, finalize)
        anim.start()
        return anim

    def animate_float(self, key: object, start: float, end: float, duration: int,
                     apply_fn: Callable[[float], None]) -> QVariantAnimation:
        """Generic float tween under ``key`` (e.g. zoom). Finalize applies ``end``."""
        self._cancel_key(key)
        anim = QVariantAnimation(self)
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.setDuration(max(1, int(duration)))
        anim.valueChanged.connect(lambda value: apply_fn(float(value)))
        self._register(anim, lambda: apply_fn(float(end)), key=key)
        anim.start()
        return anim
