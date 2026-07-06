from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPen, QPixmap

from dijkstra_dashboard import config


NODE_STATES = ("default", "frontier", "current", "visited", "final", "not_in_path", "unreachable")
EDGE_STATES = ("default", "considered", "relaxed", "final", "not_in_path", "unreachable")
NODE_STATE_ALIASES = {"idle": "default", "unused": "not_in_path"}
EDGE_STATE_ALIASES = {"idle": "default", "unused": "not_in_path", "visited": "relaxed"}
RELAX_EFFECTS = ("lightning", "comet", "none")
FINAL_REVEALS = ("stagger", "instant")

#: Reserved id used for the theme editor's throwaway live-preview theme. It is
#: registered/unregistered by the editor and never shown in the Theme menu.
PREVIEW_THEME_ID = "custom-preview"

#: Scalar (non-collection) Theme fields, split by how they round-trip through a
#: JSON dict. font_pref (tuple), node_styles and edge_styles are handled apart.
_THEME_STR_FIELDS = (
    "canvas_bg_top", "canvas_bg_bottom", "window_bg", "panel_bg", "base_bg",
    "text", "muted_text", "accent", "success", "error", "warning",
    "button_bg", "button_text", "button_border", "highlight", "highlight_text",
)
_THEME_BOOL_FIELDS = ("dark", "glow_enabled")

_font_family_cache: dict[tuple[str, ...], str] = {}
_theme_manager: ThemeManager | None = None


@dataclass(frozen=True)
class NodeStyle:
    fill: str
    ring: str
    ring_width: float
    text: str
    glow: str | None = None
    opacity: float = 1.0


@dataclass(frozen=True)
class EdgeStyle:
    stroke: str
    width: float
    label_fg: str
    chip_bg: str
    chip_border: str
    halo: str | None = None
    opacity: float = 1.0
    z: float = 0.0


@dataclass(frozen=True)
class AnimationStyle:
    relax_effect: str
    impact_ring: bool
    impact_badge: bool
    final_reveal: str
    motion_scale: float = 1.0


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    dark: bool
    canvas_bg_top: str
    canvas_bg_bottom: str
    window_bg: str
    panel_bg: str
    base_bg: str
    text: str
    muted_text: str
    accent: str
    success: str
    error: str
    warning: str
    button_bg: str
    button_text: str
    button_border: str
    highlight: str
    highlight_text: str
    font_pref: tuple[str, ...]
    glow_enabled: bool
    node_styles: dict[str, NodeStyle]
    edge_styles: dict[str, EdgeStyle]
    animation: AnimationStyle

    def node_style(self, state: str) -> NodeStyle:
        resolved = NODE_STATE_ALIASES.get(state, state)
        if resolved not in self.node_styles:
            resolved = "default"
        return self.node_styles[resolved]

    def edge_style(self, state: str) -> EdgeStyle:
        resolved = EDGE_STATE_ALIASES.get(state, state)
        if resolved not in self.edge_styles:
            resolved = "default"
        return self.edge_styles[resolved]

    def color(self, role: str) -> QColor:
        if role.startswith("#"):
            return QColor(role)
        value = getattr(self, role, self.text)
        if not isinstance(value, str):
            value = self.text
        return QColor(value)

    def palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.window_bg))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.text))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.base_bg))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(self.panel_bg))
        palette.setColor(QPalette.ColorRole.Text, QColor(self.text))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.button_bg))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.button_text))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(self.error))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self.highlight))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(self.highlight_text))
        palette.setColor(QPalette.ColorRole.Link, QColor(self.accent))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(self.panel_bg))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(self.text))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.muted_text))
        for role in (
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.WindowText,
        ):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(self.muted_text))
        return palette

    def qss(self) -> str:
        hover_bg = _color_name(lerp_color(QColor(self.button_bg), QColor(self.accent), 0.18))
        pressed_bg = _color_name(lerp_color(QColor(self.button_bg), QColor(self.accent), 0.32))
        disabled_bg = _color_name(lerp_color(QColor(self.button_bg), QColor(self.muted_text), 0.12))
        slider_groove = _color_name(lerp_color(QColor(self.base_bg), QColor(self.button_border), 0.55))
        menu_selected = _color_name(lerp_color(QColor(self.panel_bg), QColor(self.accent), 0.22))
        checkbox_bg = _color_name(lerp_color(QColor(self.base_bg), QColor(self.panel_bg), 0.5))
        zoom_hover = _color_name(lerp_color(QColor(self.panel_bg), QColor(self.accent), 0.16))
        zoom_pressed = _color_name(lerp_color(QColor(self.panel_bg), QColor(self.accent), 0.28))
        notice_bg = _color_name(lerp_color(QColor(self.panel_bg), QColor(self.error), 0.22))
        notice_border = _color_name(lerp_color(QColor(self.panel_bg), QColor(self.error), 0.5))

        return f"""
QPushButton {{
    background-color: {self.button_bg};
    color: {self.button_text};
    border: 1px solid {self.button_border};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPushButton:hover {{
    background-color: {hover_bg};
    border-color: {self.accent};
}}
QPushButton:pressed {{
    background-color: {pressed_bg};
}}
QPushButton:disabled {{
    background-color: {disabled_bg};
    color: {self.muted_text};
    border-color: {self.button_border};
}}
QComboBox {{
    background-color: {self.button_bg};
    color: {self.button_text};
    border: 1px solid {self.button_border};
    border-radius: 5px;
    padding: 4px 8px;
}}
QComboBox:hover {{
    border-color: {self.accent};
}}
QComboBox QAbstractItemView {{
    background-color: {self.panel_bg};
    color: {self.text};
    border: 1px solid {self.button_border};
    selection-background-color: {self.highlight};
    selection-color: {self.highlight_text};
}}
QSlider::groove:horizontal {{
    background-color: {slider_groove};
    height: 5px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {self.accent};
    border: 1px solid {self.highlight_text};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QCheckBox {{
    color: {self.text};
    spacing: 6px;
}}
QCheckBox::indicator {{
    background-color: {checkbox_bg};
    border: 1px solid {self.button_border};
    border-radius: 3px;
    width: 14px;
    height: 14px;
}}
QCheckBox::indicator:checked {{
    background-color: {self.accent};
    border-color: {self.accent};
}}
QMenuBar, QMenu {{
    background-color: {self.panel_bg};
    color: {self.text};
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background-color: {menu_selected};
    color: {self.text};
}}
QToolTip {{
    background-color: {self.panel_bg};
    color: {self.text};
    border: 1px solid {self.button_border};
    padding: 4px;
}}
#noticeLabel {{
    background-color: {notice_bg};
    border: 1px solid {notice_border};
    border-radius: 4px;
    padding: 6px 10px;
    color: {self.text};
}}
#statusTitle {{
    color: {self.accent};
}}
#legendLabel {{
    color: {self.muted_text};
}}
#statusText {{
    color: {self.text};
    background-color: {self.base_bg};
    border: 1px solid {self.button_border};
}}
#zoomOverlay QPushButton {{
    background-color: {self.panel_bg};
    color: {self.button_text};
    border: 1px solid {self.button_border};
    border-radius: 4px;
    padding: 3px 6px;
}}
#zoomOverlay QPushButton:hover {{
    background-color: {zoom_hover};
    border-color: {self.accent};
}}
#zoomOverlay QPushButton:pressed {{
    background-color: {zoom_pressed};
}}
"""

    def display_font(self, point_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
        family = _resolve_font_family(self.font_pref)
        font = QFont(family, point_size)
        font.setWeight(weight)
        return font


def lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    if t <= 0:
        return QColor(a)
    if t >= 1:
        return QColor(b)
    red = round(a.red() + (b.red() - a.red()) * t)
    green = round(a.green() + (b.green() - a.green()) * t)
    blue = round(a.blue() + (b.blue() - a.blue()) * t)
    alpha = round(a.alpha() + (b.alpha() - a.alpha()) * t)
    return QColor(red, green, blue, alpha)


def make_app_icon(theme: Theme) -> QIcon:
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    points = (QPointF(28, 82), QPointF(64, 42), QPointF(100, 72))
    painter.setPen(QPen(QColor(theme.muted_text), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(points[0], points[1])
    painter.drawLine(points[1], points[2])

    painter.setPen(Qt.PenStyle.NoPen)
    for point, color in zip(points, (theme.accent, theme.success, theme.muted_text)):
        painter.setBrush(QBrush(QColor(color)))
        painter.drawEllipse(point, 15, 15)
    painter.end()

    return QIcon(pixmap)


def _resolve_font_family(font_pref: tuple[str, ...]) -> str:
    key = tuple(font_pref)
    if key not in _font_family_cache:
        families = set(QFontDatabase.families())
        fallback = key[-1] if key else ""
        _font_family_cache[key] = next((family for family in key if family in families), fallback)
    return _font_family_cache[key]


def _reset_font_cache_for_tests() -> None:
    _font_family_cache.clear()


def _color_name(color: QColor) -> str:
    if color.alpha() == 255:
        return color.name(QColor.NameFormat.HexRgb)
    return color.name(QColor.NameFormat.HexArgb)


def _theme_id(theme_id: str) -> str:
    return ThemeManager.LEGACY_THEME_ALIASES.get(theme_id, theme_id)


def _build_themes() -> dict[str, Theme]:
    return {
        "neon-dark": Theme(
            id="neon-dark",
            name="Neon Dark",
            dark=True,
            canvas_bg_top="#050507",
            canvas_bg_bottom="#0b0b12",
            window_bg="#16161d",
            panel_bg="#1a1a24",
            base_bg="#101018",
            text="#e8e8f0",
            muted_text="#8888a0",
            accent="#00e5ff",
            success="#4dd8ff",
            error="#ff2d55",
            warning="#ffb020",
            button_bg="#232330",
            button_text="#e8e8f0",
            button_border="#33334a",
            highlight="#00b8cc",
            highlight_text="#001018",
            font_pref=("Orbitron", "Arial"),
            glow_enabled=True,
            node_styles={
                "default": NodeStyle(fill="#1e1e30", ring="#5c5c7a", ring_width=2, text="#e8e8f0"),
                "frontier": NodeStyle(fill="#123a44", ring="#00e5ff", ring_width=2, text="#ffffff", glow="#5000e5ff"),
                "current": NodeStyle(fill="#00e5ff", ring="#ffffff", ring_width=3, text="#001018", glow="#a000e5ff"),
                "visited": NodeStyle(fill="#0d6d86", ring="#00e5ff", ring_width=3, text="#eaffff", glow="#6000e5ff"),
                "final": NodeStyle(fill="#0a4a5c", ring="#00ffff", ring_width=3, text="#e6ffff", glow="#8000ffff"),
                "not_in_path": NodeStyle(fill="#111923", ring="#46505f", ring_width=2, text="#a5afbd", opacity=0.72),
                "unreachable": NodeStyle(fill="#3a1020", ring="#ff2d55", ring_width=2.5, text="#ffb3c2", glow="#40ff2d55"),
            },
            # Neon chips are BARE numbers (fully transparent pill) — the pill
            # chrome only appears while a chip is selected.
            edge_styles={
                "default": EdgeStyle(stroke="#4a4a62", width=2, label_fg="#cfcfe0", chip_bg="#00000000", chip_border="#00000000", z=0),
                "considered": EdgeStyle(stroke="#2f4a55", width=2.5, label_fg="#8fb8c2", chip_bg="#00000000", chip_border="#00000000", z=0.2),
                "relaxed": EdgeStyle(stroke="#00e5ff", width=2.5, label_fg="#aef4ff", chip_bg="#00000000", chip_border="#00000000", halo="#5500e5ff", z=0.5),
                "final": EdgeStyle(stroke="#00ffff", width=3.5, label_fg="#00ffff", chip_bg="#00000000", chip_border="#00000000", halo="#6000ffff", z=1),
                "not_in_path": EdgeStyle(stroke="#3f4652", width=2, label_fg="#929ba8", chip_bg="#00000000", chip_border="#00000000", opacity=0.62, z=0),
                "unreachable": EdgeStyle(stroke="#ff2d55", width=2, label_fg="#ffb3c2", chip_bg="#00000000", chip_border="#00000000", z=0),
            },
            animation=AnimationStyle(
                relax_effect="lightning",
                impact_ring=True,
                impact_badge=True,
                final_reveal="stagger",
                motion_scale=1.0,
            ),
        ),
        "midnight": Theme(
            id="midnight",
            name="Midnight",
            dark=True,
            canvas_bg_top="#0f172a",
            canvas_bg_bottom="#1e293b",
            window_bg="#0f172a",
            panel_bg="#1e293b",
            base_bg="#0b1120",
            text="#e2e8f0",
            muted_text="#94a3b8",
            accent="#3b82f6",
            success="#67e8f9",
            error="#f87171",
            warning="#fbbf24",
            button_bg="#1e293b",
            button_text="#e2e8f0",
            button_border="#334155",
            highlight="#2563eb",
            highlight_text="#eff6ff",
            font_pref=("Helvetica Neue", "Arial"),
            glow_enabled=False,
            node_styles={
                "default": NodeStyle(fill="#1e293b", ring="#475569", ring_width=2, text="#e2e8f0"),
                "frontier": NodeStyle(fill="#172554", ring="#60a5fa", ring_width=2, text="#dbeafe"),
                "current": NodeStyle(fill="#3b82f6", ring="#dbeafe", ring_width=3, text="#0b1120"),
                "visited": NodeStyle(fill="#1e3a8a", ring="#3b82f6", ring_width=2.5, text="#dbeafe"),
                "final": NodeStyle(fill="#123a44", ring="#38d5ff", ring_width=3, text="#eafcff", glow="#5538d5ff"),
                "not_in_path": NodeStyle(fill="#18212f", ring="#4b5565", ring_width=2, text="#a8b3c2", opacity=0.55),
                "unreachable": NodeStyle(fill="#450a0a", ring="#f87171", ring_width=2, text="#fecaca"),
            },
            edge_styles={
                "default": EdgeStyle(stroke="#475569", width=2, label_fg="#cbd5e1", chip_bg="#e61e293b", chip_border="#475569", z=0),
                "considered": EdgeStyle(stroke="#7c8faa", width=2, label_fg="#cbd5e1", chip_bg="#e61e293b", chip_border="#7c8faa", z=0.2),
                "relaxed": EdgeStyle(stroke="#60a5fa", width=2.5, label_fg="#dbeafe", chip_bg="#e6172554", chip_border="#60a5fa", z=0.5),
                "final": EdgeStyle(stroke="#38d5ff", width=3.5, label_fg="#38d5ff", chip_bg="#e6123a44", chip_border="#38d5ff", halo="#4038d5ff", z=1),
                "not_in_path": EdgeStyle(stroke="#4b5565", width=1.6, label_fg="#9aa6b6", chip_bg="#d918212f", chip_border="#4b5565", opacity=0.5, z=0),
                "unreachable": EdgeStyle(stroke="#f87171", width=2, label_fg="#fecaca", chip_bg="#e6450a0a", chip_border="#f87171", z=0),
            },
            animation=AnimationStyle(
                relax_effect="comet",
                impact_ring=True,
                impact_badge=True,
                final_reveal="stagger",
                motion_scale=0.95,
            ),
        ),
        "paper-light": Theme(
            id="paper-light",
            name="Paper Light",
            dark=False,
            canvas_bg_top="#ffffff",
            canvas_bg_bottom="#f4f4f5",
            window_bg="#fafafa",
            panel_bg="#ffffff",
            base_bg="#ffffff",
            text="#18181b",
            muted_text="#71717a",
            accent="#0072B2",
            success="#0072B2",
            error="#D55E00",
            warning="#E69F00",
            button_bg="#f4f4f5",
            button_text="#18181b",
            button_border="#d4d4d8",
            highlight="#0072B2",
            highlight_text="#ffffff",
            font_pref=("Helvetica Neue", "Arial"),
            glow_enabled=False,
            node_styles={
                "default": NodeStyle(fill="#ffffff", ring="#a1a1aa", ring_width=2, text="#18181b"),
                "frontier": NodeStyle(fill="#eaf5fc", ring="#56B4E9", ring_width=2, text="#0c4a6e"),
                "current": NodeStyle(fill="#0072B2", ring="#18181b", ring_width=3, text="#ffffff"),
                "visited": NodeStyle(fill="#d0e6f2", ring="#0072B2", ring_width=2.5, text="#093a5c"),
                "final": NodeStyle(fill="#dff4ff", ring="#0072B2", ring_width=3, text="#07344d"),
                "not_in_path": NodeStyle(fill="#f3f4f6", ring="#9ca3af", ring_width=2, text="#4b5563", opacity=0.55),
                "unreachable": NodeStyle(fill="#fbe3d6", ring="#D55E00", ring_width=2, text="#7c2d12"),
            },
            edge_styles={
                "default": EdgeStyle(stroke="#a1a1aa", width=2, label_fg="#3f3f46", chip_bg="#e6ffffff", chip_border="#d4d4d8", z=0),
                "considered": EdgeStyle(stroke="#56B4E9", width=2, label_fg="#0c4a6e", chip_bg="#e6eaf5fc", chip_border="#56B4E9", z=0.2),
                "relaxed": EdgeStyle(stroke="#0072B2", width=2.5, label_fg="#093a5c", chip_bg="#e6d0e6f2", chip_border="#0072B2", z=0.5),
                "final": EdgeStyle(stroke="#0072B2", width=3.5, label_fg="#0072B2", chip_bg="#e6dff4ff", chip_border="#0072B2", z=1),
                "not_in_path": EdgeStyle(stroke="#9ca3af", width=1.5, label_fg="#6b7280", chip_bg="#e6f3f4f6", chip_border="#d1d5db", opacity=0.5, z=0),
                "unreachable": EdgeStyle(stroke="#D55E00", width=2, label_fg="#7c2d12", chip_bg="#e6fbe3d6", chip_border="#D55E00", z=0),
            },
            animation=AnimationStyle(
                relax_effect="comet",
                impact_ring=True,
                impact_badge=True,
                final_reveal="instant",
                motion_scale=0.9,
            ),
        ),
    }


class _ThemesRegistry:
    """Descriptor backing ``ThemeManager.THEMES``.

    Historically ``THEMES`` was a plain class-level dict, read both as
    ``ThemeManager.THEMES["neon-dark"]`` (class access, all over the tests) and
    as ``self.THEMES`` / ``manager.THEMES`` (instance access, in the engine).
    Phase 9 makes the registry per-instance mutable (custom themes register into
    one manager without leaking into others), so this descriptor preserves BOTH
    long-standing access patterns:

    * class access returns the immutable built-in registry, so every existing
      ``ThemeManager.THEMES[...]`` call site keeps resolving the built-ins;
    * instance access returns that manager's live registry (built-ins plus any
      runtime-registered custom themes).

    Read-only: rebinding is refused so nobody silently swaps the registry out.
    """

    def __get__(self, obj, objtype=None):
        if obj is None:
            return objtype.BUILTIN_THEMES
        return obj._themes

    def __set__(self, obj, value):
        raise AttributeError("ThemeManager.THEMES is read-only")


class ThemeManager(QObject):
    theme_changed = pyqtSignal(object)
    #: Emitted (no args) when the set of registered theme ids changes, so the
    #: View > Theme menu can rebuild. NOT emitted for value-only replacements of
    #: an already-registered id (e.g. repeated live-preview edits).
    themes_changed = pyqtSignal()
    LEGACY_THEME_ALIASES = {"cyberpunk": "neon-dark"}
    #: Immutable source of the shipped themes. Instances copy this into a private
    #: per-instance registry; class-level ``THEMES`` access returns this dict.
    BUILTIN_THEMES = _build_themes()
    THEMES = _ThemesRegistry()

    def __init__(self) -> None:
        super().__init__()
        # Per-instance copy so register/unregister never mutate the built-ins or
        # bleed across managers. Class-level THEMES still exposes BUILTIN_THEMES.
        self._themes: dict[str, Theme] = dict(self.BUILTIN_THEMES)
        self._current = self._themes["neon-dark"]

    def register_theme(self, theme: Theme) -> None:
        """Insert or replace ``theme`` in this manager's registry.

        A genuinely new id emits ``themes_changed`` (menu rebuild). Replacing the
        currently-active theme (the live-preview case, where ``set_theme`` would
        no-op on the same id) re-applies it via ``theme_changed`` so listeners
        refresh their palette/canvas.
        """
        is_new = theme.id not in self._themes
        self._themes[theme.id] = theme
        if self._current.id == theme.id and self._current is not theme:
            self._current = theme
            self.theme_changed.emit(self._current)
        if is_new:
            self.themes_changed.emit()

    def unregister_theme(self, theme_id: str) -> None:
        """Remove a custom theme from the registry. Built-in ids are refused."""
        if theme_id in self.BUILTIN_THEMES:
            raise ValueError(f"Cannot unregister built-in theme: {theme_id}")
        if theme_id in self._themes:
            del self._themes[theme_id]
            self.themes_changed.emit()

    def save_custom_theme(self, theme: Theme) -> Path:
        """Persist ``theme`` as ``<id>.json`` under the custom theme dir and register it."""
        directory = custom_theme_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{theme.id}.json"
        tmp = path.with_name(f"{path.name}.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(theme_to_dict(theme), handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        tmp.replace(path)  # atomic-enough: never leaves a half-written file behind.
        self.register_theme(theme)
        return path

    def load_custom_themes(self) -> None:
        """Register every valid custom theme JSON on disk. Invalid files are skipped."""
        directory = custom_theme_dir()
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                theme = theme_from_dict(data)
            except Exception:
                continue  # corrupt/invalid file: skip silently, never crash boot.
            # A custom file must never shadow a shipped built-in palette.
            if theme.id in self.BUILTIN_THEMES:
                continue
            self.register_theme(theme)

    @property
    def current(self) -> Theme:
        return self._current

    def theme_ids(self) -> list[str]:
        return list(self.THEMES.keys())

    def set_theme(self, theme_id: str, persist: bool = True) -> None:
        resolved = _theme_id(theme_id)
        if resolved not in self.THEMES or resolved == self._current.id:
            return

        self._current = self.THEMES[resolved]
        self.theme_changed.emit(self._current)

        if persist:
            try:
                data = config.load_config()
                data["theme"] = resolved
                config.save_config(data)
            except Exception:
                pass

    def load_from_config(self) -> None:
        try:
            data = config.resolve_config()
            theme_id = data.get("theme", "neon-dark")
        except Exception:
            # A corrupt/unreadable config file must not swallow the env override.
            try:
                theme_id = config.env_config().get("theme", "neon-dark")
            except Exception:
                theme_id = "neon-dark"

        resolved = _theme_id(theme_id)
        if resolved not in self.THEMES:
            resolved = "neon-dark"
        self._current = self.THEMES[resolved]


def custom_theme_dir() -> Path:
    """Directory holding persisted custom themes: ``<config dir>/themes``.

    Derived from ``config.get_config_path()`` so the hermetic-config test fixture
    (which points the config env var at a tmp dir) isolates it for free.
    """
    return config.get_config_path().parent / "themes"


def theme_to_dict(theme: Theme) -> dict:
    """Full JSON-able dict for a Theme (the inverse of ``theme_from_dict``)."""
    return {
        "id": theme.id,
        "name": theme.name,
        "dark": theme.dark,
        "canvas_bg_top": theme.canvas_bg_top,
        "canvas_bg_bottom": theme.canvas_bg_bottom,
        "window_bg": theme.window_bg,
        "panel_bg": theme.panel_bg,
        "base_bg": theme.base_bg,
        "text": theme.text,
        "muted_text": theme.muted_text,
        "accent": theme.accent,
        "success": theme.success,
        "error": theme.error,
        "warning": theme.warning,
        "button_bg": theme.button_bg,
        "button_text": theme.button_text,
        "button_border": theme.button_border,
        "highlight": theme.highlight,
        "highlight_text": theme.highlight_text,
        "font_pref": list(theme.font_pref),
        "glow_enabled": theme.glow_enabled,
        "node_styles": {state: asdict(style) for state, style in theme.node_styles.items()},
        "edge_styles": {state: asdict(style) for state, style in theme.edge_styles.items()},
        "animation": asdict(theme.animation),
    }


def _pick_str(data: dict, key: str, default: str) -> str:
    value = data.get(key, default)
    return value if isinstance(value, str) else default


def _pick_bool(data: dict, key: str, default: bool) -> bool:
    if key in data and isinstance(data[key], bool):
        return data[key]
    return default


def _pick_num(data: dict, key: str, default: float) -> float:
    # Pass real numbers through unchanged (preserving int-ness for exact
    # round-trips); reject bools and non-numbers back to the neon default.
    if key in data:
        value = data[key]
        if not isinstance(value, bool) and isinstance(value, (int, float)):
            return value
    return default


def _pick_nullable_str(data: dict, key: str, default):
    # An explicit ``null`` is honored (glow/halo "none"), distinct from a missing
    # key which defaults to the neon value.
    if key in data:
        value = data[key]
        if value is None or isinstance(value, str):
            return value
    return default


def _pick_choice(data: dict, key: str, default: str, choices: tuple[str, ...]) -> str:
    value = data.get(key, default)
    return value if isinstance(value, str) and value in choices else default


def theme_from_dict(data) -> Theme:
    """Validating inverse of ``theme_to_dict``.

    Missing fields default from the neon-dark built-in (per-field for chrome,
    per-state-per-field for node/edge styles). Unknown keys are ignored. A
    non-dict, or a missing/blank id or name, raises ValueError. Ids are literal
    (no alias resolution here).
    """
    if not isinstance(data, dict):
        raise ValueError("theme data must be a dict")

    theme_id = data.get("id")
    if not isinstance(theme_id, str) or not theme_id.strip():
        raise ValueError("theme data requires a non-empty 'id'")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("theme data requires a non-empty 'name'")

    default = ThemeManager.BUILTIN_THEMES["neon-dark"]

    node_data = data.get("node_styles")
    if not isinstance(node_data, dict):
        node_data = {}
    node_styles: dict[str, NodeStyle] = {}
    for state in NODE_STATES:
        base = default.node_styles[state]
        raw = node_data.get(state)
        if not isinstance(raw, dict):
            raw = {}
        node_styles[state] = NodeStyle(
            fill=_pick_str(raw, "fill", base.fill),
            ring=_pick_str(raw, "ring", base.ring),
            ring_width=_pick_num(raw, "ring_width", base.ring_width),
            text=_pick_str(raw, "text", base.text),
            glow=_pick_nullable_str(raw, "glow", base.glow),
            opacity=_pick_num(raw, "opacity", base.opacity),
        )

    edge_data = data.get("edge_styles")
    if not isinstance(edge_data, dict):
        edge_data = {}
    edge_styles: dict[str, EdgeStyle] = {}
    for state in EDGE_STATES:
        base = default.edge_styles[state]
        raw = edge_data.get(state)
        if not isinstance(raw, dict):
            raw = {}
        edge_styles[state] = EdgeStyle(
            stroke=_pick_str(raw, "stroke", base.stroke),
            width=_pick_num(raw, "width", base.width),
            label_fg=_pick_str(raw, "label_fg", base.label_fg),
            chip_bg=_pick_str(raw, "chip_bg", base.chip_bg),
            chip_border=_pick_str(raw, "chip_border", base.chip_border),
            halo=_pick_nullable_str(raw, "halo", base.halo),
            opacity=_pick_num(raw, "opacity", base.opacity),
            z=_pick_num(raw, "z", base.z),
        )

    animation_data = data.get("animation")
    if not isinstance(animation_data, dict):
        animation_data = {}
    motion_scale = _pick_num(animation_data, "motion_scale", default.animation.motion_scale)
    motion_scale = max(0.25, min(2.0, float(motion_scale)))
    animation = AnimationStyle(
        relax_effect=_pick_choice(animation_data, "relax_effect", default.animation.relax_effect, RELAX_EFFECTS),
        impact_ring=_pick_bool(animation_data, "impact_ring", default.animation.impact_ring),
        impact_badge=_pick_bool(animation_data, "impact_badge", default.animation.impact_badge),
        final_reveal=_pick_choice(animation_data, "final_reveal", default.animation.final_reveal, FINAL_REVEALS),
        motion_scale=motion_scale,
    )

    font_raw = data.get("font_pref")
    if isinstance(font_raw, (list, tuple)) and font_raw and all(isinstance(x, str) for x in font_raw):
        font_pref = tuple(font_raw)
    else:
        font_pref = default.font_pref

    chrome = {field: _pick_str(data, field, getattr(default, field)) for field in _THEME_STR_FIELDS}
    chrome.update({field: _pick_bool(data, field, getattr(default, field)) for field in _THEME_BOOL_FIELDS})

    return Theme(
        id=theme_id,
        name=name,
        font_pref=font_pref,
        node_styles=node_styles,
        edge_styles=edge_styles,
        animation=animation,
        **chrome,
    )


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def current_theme() -> Theme:
    return get_theme_manager().current


def _reset_theme_manager_for_tests() -> None:
    global _theme_manager
    _theme_manager = None
