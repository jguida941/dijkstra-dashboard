"""Phase 6 (UI) — PNG / SVG scene export (pure functions).

Covers ui/export.py: sizing from the ITEMS bounding rect (not the fixed
3000x2000 scene rect), transparent PNG fill, and the guarded QtSvg path.
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene

from dijkstra_dashboard.ui.export import HAS_SVG, export_scene_png, export_scene_svg


pytestmark = pytest.mark.ui


def _scene_with_items():
    scene = QGraphicsScene()
    # A deliberately huge scene rect: export must NOT size from it.
    scene.setSceneRect(-1500, -1000, 3000, 2000)
    first = QGraphicsEllipseItem(-20, -20, 40, 40)
    first.setPos(0, 0)
    scene.addItem(first)
    second = QGraphicsEllipseItem(-20, -20, 40, 40)
    second.setPos(200, 120)
    scene.addItem(second)
    return scene


def test_export_png_writes_non_empty_file(qapp, tmp_path):
    scene = _scene_with_items()
    out = tmp_path / "graph.png"

    assert export_scene_png(scene, str(out)) is True
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_png_sizes_from_items_rect_scaled(qapp, tmp_path):
    # F2: source = itemsBoundingRect +/- 60; image size = source.size() * scale.
    scene = _scene_with_items()
    out = tmp_path / "graph.png"

    export_scene_png(scene, str(out), scale=2.0)

    image = QImage(str(out))
    source = scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
    assert image.width() == round(source.width() * 2.0)
    assert image.height() == round(source.height() * 2.0)
    # The fixed 3000x2000 scene rect would give 6000x4000 at scale 2 — never that.
    assert image.width() < 6000
    assert image.height() < 4000


def test_export_png_empty_scene_returns_false(qapp, tmp_path):
    scene = QGraphicsScene()
    scene.setSceneRect(-1500, -1000, 3000, 2000)
    out = tmp_path / "empty.png"

    assert export_scene_png(scene, str(out)) is False


def test_has_svg_true_in_this_env(qapp):
    assert HAS_SVG is True


def test_export_svg_writes_xml_file(qapp, tmp_path):
    scene = _scene_with_items()
    out = tmp_path / "graph.svg"

    assert export_scene_svg(scene, str(out)) is True
    assert out.exists()
    data = out.read_bytes()
    assert len(data) > 0
    assert data.lstrip().startswith(b"<?xml")
