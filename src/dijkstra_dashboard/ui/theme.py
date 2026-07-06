from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPen, QPixmap

from dijkstra_dashboard import config


NODE_STATES = ("default", "frontier", "current", "visited", "final", "not_in_path", "unreachable")
EDGE_STATES = ("default", "considered", "relaxed", "final", "not_in_path", "unreachable")
NODE_STATE_ALIASES = {"idle": "default", "unused": "not_in_path"}
EDGE_STATE_ALIASES = {"idle": "default", "unused": "not_in_path", "visited": "relaxed"}

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
            success="#39ff14",
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
                "final": NodeStyle(fill="#124a1a", ring="#39ff14", ring_width=3, text="#eaffe6", glow="#8039ff14"),
                "not_in_path": NodeStyle(fill="#38101c", ring="#ff0044", ring_width=2, text="#ff9fb4", glow="#38ff0044", opacity=0.95),
                "unreachable": NodeStyle(fill="#3a1020", ring="#ff2d55", ring_width=2.5, text="#ffb3c2", glow="#40ff2d55"),
            },
            # Neon chips are BARE numbers (fully transparent pill) — the pill
            # chrome only appears while a chip is selected.
            edge_styles={
                "default": EdgeStyle(stroke="#4a4a62", width=2, label_fg="#cfcfe0", chip_bg="#00000000", chip_border="#00000000", z=0),
                "considered": EdgeStyle(stroke="#3f6a72", width=2, label_fg="#9fd7de", chip_bg="#00000000", chip_border="#00000000", z=0.2),
                "relaxed": EdgeStyle(stroke="#00e5ff", width=3, label_fg="#aef4ff", chip_bg="#00000000", chip_border="#00000000", halo="#5500e5ff", z=0.5),
                "final": EdgeStyle(stroke="#39ff14", width=3.5, label_fg="#b6ff9e", chip_bg="#00000000", chip_border="#00000000", halo="#6039ff14", z=1),
                "not_in_path": EdgeStyle(stroke="#ff0044", width=2, label_fg="#ff4d6b", chip_bg="#00000000", chip_border="#00000000", opacity=0.9, z=0),
                "unreachable": EdgeStyle(stroke="#ff2d55", width=2, label_fg="#ffb3c2", chip_bg="#00000000", chip_border="#00000000", z=0),
            },
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
            success="#4ade80",
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
                "final": NodeStyle(fill="#78350f", ring="#fbbf24", ring_width=3, text="#fef3c7"),
                "not_in_path": NodeStyle(fill="#1e293b", ring="#475569", ring_width=2, text="#e2e8f0", opacity=0.4),
                "unreachable": NodeStyle(fill="#450a0a", ring="#f87171", ring_width=2, text="#fecaca"),
            },
            edge_styles={
                "default": EdgeStyle(stroke="#475569", width=2, label_fg="#cbd5e1", chip_bg="#e61e293b", chip_border="#475569", z=0),
                "considered": EdgeStyle(stroke="#7c8faa", width=2, label_fg="#cbd5e1", chip_bg="#e61e293b", chip_border="#7c8faa", z=0.2),
                "relaxed": EdgeStyle(stroke="#60a5fa", width=2.5, label_fg="#dbeafe", chip_bg="#e6172554", chip_border="#60a5fa", z=0.5),
                "final": EdgeStyle(stroke="#f59e0b", width=3.5, label_fg="#fef3c7", chip_bg="#e6451a03", chip_border="#f59e0b", halo="#40f59e0b", z=1),
                "not_in_path": EdgeStyle(stroke="#475569", width=1.5, label_fg="#cbd5e1", chip_bg="#e61e293b", chip_border="#475569", opacity=0.45, z=0),
                "unreachable": EdgeStyle(stroke="#f87171", width=2, label_fg="#fecaca", chip_bg="#e6450a0a", chip_border="#f87171", z=0),
            },
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
            success="#009E73",
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
                "final": NodeStyle(fill="#d4efe6", ring="#009E73", ring_width=3, text="#065f46"),
                "not_in_path": NodeStyle(fill="#ffffff", ring="#a1a1aa", ring_width=2, text="#18181b", opacity=0.45),
                "unreachable": NodeStyle(fill="#fbe3d6", ring="#D55E00", ring_width=2, text="#7c2d12"),
            },
            edge_styles={
                "default": EdgeStyle(stroke="#a1a1aa", width=2, label_fg="#3f3f46", chip_bg="#e6ffffff", chip_border="#d4d4d8", z=0),
                "considered": EdgeStyle(stroke="#56B4E9", width=2, label_fg="#0c4a6e", chip_bg="#e6eaf5fc", chip_border="#56B4E9", z=0.2),
                "relaxed": EdgeStyle(stroke="#0072B2", width=2.5, label_fg="#093a5c", chip_bg="#e6d0e6f2", chip_border="#0072B2", z=0.5),
                "final": EdgeStyle(stroke="#009E73", width=3.5, label_fg="#065f46", chip_bg="#e6d4efe6", chip_border="#009E73", z=1),
                "not_in_path": EdgeStyle(stroke="#a1a1aa", width=1.5, label_fg="#3f3f46", chip_bg="#e6ffffff", chip_border="#d4d4d8", opacity=0.4, z=0),
                "unreachable": EdgeStyle(stroke="#D55E00", width=2, label_fg="#7c2d12", chip_bg="#e6fbe3d6", chip_border="#D55E00", z=0),
            },
        ),
    }


class ThemeManager(QObject):
    theme_changed = pyqtSignal(object)
    LEGACY_THEME_ALIASES = {"cyberpunk": "neon-dark"}
    THEMES = _build_themes()

    def __init__(self) -> None:
        super().__init__()
        self._current = self.THEMES["neon-dark"]

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
