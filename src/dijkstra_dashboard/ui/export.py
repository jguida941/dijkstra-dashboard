"""Scene export — pure PNG / SVG rasterisers for the graph view.

Sizing follows F2: the source rectangle is the scene's *items* bounding rect
grown by 60px (enough to cover the node glow blur, ~40px), NEVER the fixed
3000x2000 ``sceneRect``. The output pixel/point size derives from that source
size; ``scene.render`` maps the source onto a target of matching size.

Graphics effects (the node drop-shadow glow) are left untouched — the Phase-1
``setGraphicsEffect(None)`` trap is not repeated here. QtSvg rasterises the glow
inside the SVG, which is accepted.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QImage, QPainter

try:  # QtSvg is an optional PyQt6 component; degrade gracefully when absent.
    from PyQt6.QtSvg import QSvgGenerator

    HAS_SVG = True
except ImportError:  # pragma: no cover - exercised only where QtSvg is missing
    QSvgGenerator = None  # type: ignore[assignment]
    HAS_SVG = False


#: Margin added around the items bounding rect (covers the ~40px glow blur).
EXPORT_MARGIN = 60.0


def _source_rect(scene) -> QRectF:
    """The items bounding rect grown by :data:`EXPORT_MARGIN` on every side."""
    return scene.itemsBoundingRect().adjusted(
        -EXPORT_MARGIN, -EXPORT_MARGIN, EXPORT_MARGIN, EXPORT_MARGIN
    )


def export_scene_png(scene, path, scale: float = 2.0) -> bool:
    """Render ``scene`` to a PNG at ``path``; return True on success.

    The image is ``source.size() * scale`` pixels, filled transparent, then the
    source rect is rendered onto it. Returns False for an empty scene (no items).
    """
    if not scene.items():
        return False
    source = _source_rect(scene)
    if source.isEmpty():
        return False

    width = max(1, int(round(source.width() * scale)))
    height = max(1, int(round(source.height() * scale)))

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    target = QRectF(0.0, 0.0, float(width), float(height))
    scene.render(painter, target, source)
    painter.end()

    return bool(image.save(str(path), "PNG"))


def export_scene_svg(scene, path) -> bool:
    """Render ``scene`` to an SVG at ``path``; return True on success.

    Returns False when QtSvg is unavailable (:data:`HAS_SVG` is False) or the
    scene is empty. Size and viewBox use the same items-based source rect.
    """
    if not HAS_SVG:
        return False
    if not scene.items():
        return False
    source = _source_rect(scene)
    if source.isEmpty():
        return False

    width = max(1, int(round(source.width())))
    height = max(1, int(round(source.height())))

    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(QSize(width, height))
    generator.setViewBox(QRectF(0.0, 0.0, float(width), float(height)))
    generator.setTitle("Dijkstra Graph")
    generator.setDescription("Exported from the Dijkstra Path Visualizer.")

    painter = QPainter(generator)
    if not painter.isActive():
        # Qt could not open the output device (missing directory, permissions).
        return False
    scene.render(painter, QRectF(0.0, 0.0, float(width), float(height)), source)
    painter.end()

    return os.path.exists(str(path)) and os.path.getsize(str(path)) > 0
