"""In-app theme editor with debounced live preview and custom-theme persistence.

The dialog seeds a plain working dict from ``theme_to_dict(current_theme())`` and
never mutates a (frozen) ``Theme`` directly: every edit updates the dict, and a
200 ms debounce rebuilds a throwaway preview theme (registered under the reserved
``custom-preview`` id) and applies it live. Cancel restores the pre-open theme and
drops the preview; Save persists a real custom theme and switches to it.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from PyQt6.QtCore import QRegularExpression, QTimer
from PyQt6.QtGui import QColor, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    EDGE_STATES,
    FINAL_REVEALS,
    NODE_STATES,
    PREVIEW_THEME_ID,
    RELAX_EFFECTS,
    current_theme,
    get_theme_manager,
    parse_qss_theme_overrides,
    theme_from_dict,
    theme_to_dict,
)

#: #RRGGBB or #AARRGGBB (case-insensitive).
_HEX_PATTERN = r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$"
_HEX_RE = re.compile(_HEX_PATTERN)

_PREVIEW_DEBOUNCE_MS = 200

_CATEGORIES = (
    "Canvas & Chrome",
    "Node states",
    "Edge states",
    "Qt style",
    "Effects",
    "Import / Export",
)

#: Chrome color fields (label, working-dict key). None of these carry alpha.
_CHROME_FIELDS = (
    ("Canvas top", "canvas_bg_top"),
    ("Canvas bottom", "canvas_bg_bottom"),
    ("Window", "window_bg"),
    ("Panel", "panel_bg"),
    ("Base", "base_bg"),
    ("Text", "text"),
    ("Muted text", "muted_text"),
    ("Accent", "accent"),
    ("Success", "success"),
    ("Error", "error"),
    ("Warning", "warning"),
    ("Button bg", "button_bg"),
    ("Button text", "button_text"),
    ("Button border", "button_border"),
    ("Highlight", "highlight"),
    ("Highlight text", "highlight_text"),
)

_APP_STYLE_GROUPS = (
    (
        "Borders & Shape",
        (
            ("Border radius", "border_radius", 0, 32),
            ("Small radius", "small_radius", 0, 24),
            ("Border width", "border_width", 0, 6),
        ),
    ),
    (
        "Spacing",
        (
            ("Button padding Y", "padding_y", 0, 24),
            ("Button padding X", "padding_x", 0, 32),
            ("Input padding Y", "input_padding_y", 0, 24),
            ("Input padding X", "input_padding_x", 0, 32),
        ),
    ),
    (
        "Controls",
        (
            ("Control min height", "control_min_height", 18, 80),
            ("Checkbox size", "checkbox_size", 8, 32),
            ("Slider groove height", "slider_groove_height", 1, 24),
            ("Slider handle size", "slider_handle_size", 6, 40),
            ("Scrollbar width", "scrollbar_width", 4, 32),
            ("Splitter handle width", "splitter_handle_width", 1, 24),
        ),
    ),
)


class _ColorRow(QWidget):
    """A color swatch button + validated hex line-edit for one color field."""

    def __init__(self, path, value, alpha, on_change, parent=None):
        super().__init__(parent)
        self._path = path
        self._alpha = alpha
        self._on_change = on_change  # callback(path, hex_text)
        self._invalid = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._swatch = QPushButton()
        self._swatch.setFixedWidth(40)
        self._swatch.setFlat(True)
        self._swatch.clicked.connect(self._open_picker)
        self._edit = QLineEdit()
        self._edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(_HEX_PATTERN), self._edit)
        )
        self._edit.editingFinished.connect(self._on_edit_finished)
        layout.addWidget(self._swatch)
        layout.addWidget(self._edit)

        self.set_value(value)

    # -- display -------------------------------------------------------
    def set_value(self, value):
        text = value if isinstance(value, str) else ""
        self._edit.blockSignals(True)
        self._edit.setText(text)
        self._edit.blockSignals(False)
        self._paint_swatch(text)
        self.mark_invalid(False)

    def _paint_swatch(self, text):
        color = QColor(text) if _HEX_RE.match(text or "") else QColor("#00000000")
        # Draw the opaque view of the color; the border keeps it visible on any bg.
        opaque = QColor(color.red(), color.green(), color.blue())
        self._swatch.setStyleSheet(
            f"background-color: {opaque.name()}; border: 1px solid #808080; border-radius: 3px;"
        )

    def mark_invalid(self, invalid):
        self._invalid = bool(invalid)
        self._edit.setStyleSheet("border: 1px solid #ff2d55;" if invalid else "")

    def is_invalid(self):
        return self._invalid

    # -- input ---------------------------------------------------------
    def _open_picker(self):
        text = self._edit.text().strip()
        initial = QColor(text) if _HEX_RE.match(text) else QColor("#ffffffff")
        options = (
            QColorDialog.ColorDialogOption.ShowAlphaChannel
            if self._alpha
            else QColorDialog.ColorDialogOption(0)
        )
        chosen = QColorDialog.getColor(initial, self, "Select color", options)
        if not chosen.isValid():
            return
        fmt = QColor.NameFormat.HexArgb if self._alpha else QColor.NameFormat.HexRgb
        self._on_change(self._path, chosen.name(fmt))

    def _on_edit_finished(self):
        self._on_change(self._path, self._edit.text().strip())


class ThemeEditorDialog(QDialog):
    """Modal editor over a working copy of the current theme, with live preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Theme")
        self.setModal(True)

        self._manager = get_theme_manager()
        self._original_id = self._manager.current.id
        self._seed = theme_to_dict(current_theme())
        self._working = copy.deepcopy(self._seed)
        self._saved = False

        # Per-path widget registries so reset/refresh can repaint every control.
        self._color_rows: dict[tuple, _ColorRow] = {}
        self._spins: dict[tuple, QDoubleSpinBox] = {}
        self._combos: dict[tuple, QComboBox] = {}
        self._none_checks: dict[tuple, QCheckBox] = {}
        self._glow_enabled_check: QCheckBox | None = None
        self._json_paste: QPlainTextEdit | None = None
        self._qss_paste: QPlainTextEdit | None = None
        self._qss_preview: QPlainTextEdit | None = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._apply_preview)

        self._build_ui()
        self._refresh_all_widgets()

    # ------------------------------------------------------------------
    # Working-dict access helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _walk(container, path):
        node = container
        for key in path:
            node = node[key]
        return node

    def _get(self, path):
        return self._walk(self._working, path)

    def _assign(self, path, value):
        node = self._working
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    # ------------------------------------------------------------------
    # Edit API (also the programmatic hook used by tests)
    # ------------------------------------------------------------------
    def _set_color(self, path, value):
        """Raw setter into the working dict (marks dirty + schedules preview)."""
        self._set_value(path, value)

    def _set_value(self, path, value):
        self._assign(path, value)
        self._mark_dirty()

    def _edit_hex(self, path, text):
        """Validated hex entry: commit on match, else mark the field and keep the dict."""
        text = (text or "").strip()
        row = self._color_rows.get(path)
        if not _HEX_RE.match(text):
            if row is not None:
                row.mark_invalid(True)
            return False
        self._set_value(path, text)
        if row is not None:
            row.set_value(text)
        return True

    def _mark_dirty(self):
        self._preview_timer.start()

    def _on_qss_paste_changed(self):
        self._sync_qss_paste_to_working(parse=False, show_errors=False)

    def _sync_qss_paste_to_working(self, parse=False, show_errors=False):
        if self._qss_paste is None:
            return True
        text = self._qss_paste.toPlainText().strip()
        if text == self._working.get("custom_qss", "") and not parse:
            return True

        if parse and text:
            try:
                overrides = parse_qss_theme_overrides(text)
            except ValueError as exc:
                if show_errors:
                    self._show_error(f"Could not import pasted QSS: {exc}")
                return False
            for key, value in overrides.get("theme", {}).items():
                self._working[key] = value
            for key, value in overrides.get("app_style", {}).items():
                self._working["app_style"][key] = value
        else:
            self._working["custom_qss"] = text

        self._mark_dirty()
        return True

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------
    def _apply_preview(self):
        self._sync_qss_paste_to_working(parse=False, show_errors=False)
        preview_data = dict(self._working)
        preview_data["id"] = PREVIEW_THEME_ID
        try:
            preview = theme_from_dict(preview_data)
        except Exception:
            return  # a transiently-invalid working state simply skips this tick.
        self._manager.register_theme(preview)
        self._manager.set_theme(PREVIEW_THEME_ID, persist=False)
        self._refresh_export_views()

    def _flush_preview(self):
        """Test hook: apply any pending preview synchronously."""
        self._preview_timer.stop()
        self._apply_preview()

    def _drop_preview(self):
        if PREVIEW_THEME_ID in self._manager.theme_ids():
            try:
                self._manager.unregister_theme(PREVIEW_THEME_ID)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Slug / naming
    # ------------------------------------------------------------------
    def _slugify(self, name):
        base = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "custom"
        reserved = set(self._manager.BUILTIN_THEMES) | {PREVIEW_THEME_ID}
        return f"{base}-2" if base in reserved else base

    def _current_slug(self):
        return self._slugify(self._name_edit.text())

    def _on_name_changed(self, text):
        slug = self._current_slug()
        self._slug_label.setText(f"id: {slug}")
        self._working["name"] = text
        self._working["id"] = slug

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)

        # Top row: name + derived id slug + note.
        top = QHBoxLayout()
        top.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit(self._seed.get("name", ""))
        self._name_edit.textChanged.connect(self._on_name_changed)
        top.addWidget(self._name_edit, stretch=1)
        self._slug_label = QLabel()
        top.addWidget(self._slug_label)
        note = QLabel("(Based on current theme)")
        note.setEnabled(False)
        top.addWidget(note)
        outer.addLayout(top)

        # Body: category list on the left, scrolling form on the right.
        body = QHBoxLayout()
        self._category_list = QListWidget()
        self._category_list.addItems(_CATEGORIES)
        self._category_list.setMaximumWidth(160)
        body.addWidget(self._category_list)

        self._stack = QStackedWidget()
        for name in _CATEGORIES:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self._build_category_page(name))
            self._stack.addWidget(scroll)
        body.addWidget(self._stack, stretch=1)
        outer.addLayout(body, stretch=1)

        self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._category_list.setCurrentRow(0)

        # Inline error label (never a modal box).
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ff2d55;")
        self._error_label.setWordWrap(True)
        outer.addWidget(self._error_label)

        # Buttons.
        buttons = QHBoxLayout()
        reset_button = QPushButton("Reset section")
        reset_button.clicked.connect(self._reset_section)
        buttons.addWidget(reset_button)
        delete_button = QPushButton("Delete saved theme")
        delete_button.clicked.connect(self._delete_saved_theme)
        buttons.addWidget(delete_button)
        self._delete_button = delete_button
        buttons.addStretch(1)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save)
        buttons.addWidget(save_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        outer.addLayout(buttons)

        # Seed the slug label from the initial name.
        self._on_name_changed(self._name_edit.text())
        self._refresh_delete_button()

    def _build_category_page(self, name):
        if name == "Canvas & Chrome":
            return self._build_chrome_page()
        if name == "Node states":
            return self._build_node_page()
        if name == "Edge states":
            return self._build_edge_page()
        if name == "Qt style":
            return self._build_qt_style_page()
        if name == "Effects":
            return self._build_effects_page()
        if name == "Import / Export":
            return self._build_import_export_page()
        return self._build_effects_page()

    def _build_chrome_page(self):
        page = QWidget()
        form = QFormLayout(page)
        for label, key in _CHROME_FIELDS:
            form.addRow(label, self._color_row((key,), alpha=False))
        return page

    def _build_node_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        for state in NODE_STATES:
            group = QGroupBox(self._node_state_label(state))
            form = QFormLayout(group)
            form.addRow("Fill", self._color_row(("node_styles", state, "fill"), alpha=False))
            form.addRow("Ring", self._color_row(("node_styles", state, "ring"), alpha=False))
            form.addRow("Text", self._color_row(("node_styles", state, "text"), alpha=False))
            form.addRow("Ring width", self._num_spin(("node_styles", state, "ring_width"), 0.0, 12.0, 0.5))
            form.addRow("Glow", self._nullable_color_row(("node_styles", state, "glow")))
            form.addRow("Opacity", self._num_spin(("node_styles", state, "opacity"), 0.12, 1.0, 0.05))
            layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_edge_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        for state in EDGE_STATES:
            group = QGroupBox(self._edge_state_label(state))
            form = QFormLayout(group)
            form.addRow("Stroke", self._color_row(("edge_styles", state, "stroke"), alpha=False))
            form.addRow("Label", self._color_row(("edge_styles", state, "label_fg"), alpha=False))
            form.addRow("Chip bg", self._color_row(("edge_styles", state, "chip_bg"), alpha=True))
            form.addRow("Chip border", self._color_row(("edge_styles", state, "chip_border"), alpha=True))
            form.addRow("Width", self._num_spin(("edge_styles", state, "width"), 0.0, 12.0, 0.5))
            form.addRow("Z", self._num_spin(("edge_styles", state, "z"), -5.0, 5.0, 0.1))
            form.addRow("Halo", self._nullable_color_row(("edge_styles", state, "halo")))
            form.addRow("Opacity", self._num_spin(("edge_styles", state, "opacity"), 0.12, 1.0, 0.05))
            layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_qt_style_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        for title, rows in _APP_STYLE_GROUPS:
            group = QGroupBox(title)
            form = QFormLayout(group)
            for label, key, low, high in rows:
                form.addRow(label, self._int_spin(("app_style", key), low, high))
            layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _node_state_label(self, state):
        return {
            "default": "Unseen node",
            "frontier": "Frontier node",
            "current": "Current node",
            "visited": "Settled node",
            "final": "Final answer node",
            "not_in_path": "Searched off-path node",
            "unreachable": "Unreachable node",
        }.get(state, state)

    def _edge_state_label(self, state):
        return {
            "default": "Untouched edge",
            "considered": "Searched / rejected edge",
            "relaxed": "Current best edge",
            "final": "Final answer edge",
            "not_in_path": "Off-path edge",
            "unreachable": "Unreachable edge",
        }.get(state, state)

    def _build_effects_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        glow_group = QGroupBox("Glow")
        glow_layout = QFormLayout(glow_group)
        self._glow_enabled_check = QCheckBox("Enable glow effects")
        self._glow_enabled_check.toggled.connect(
            lambda checked: self._set_value(("glow_enabled",), bool(checked))
        )
        glow_layout.addRow("Enabled", self._glow_enabled_check)
        explain = QLabel(
            "Gates node glow and the current-node pulse. Per-state glow/halo "
            "colors still apply per node and edge above."
        )
        explain.setWordWrap(True)
        explain.setEnabled(False)
        glow_layout.addRow(explain)
        layout.addWidget(glow_group)

        animation_group = QGroupBox("Graph animations")
        animation_layout = QFormLayout(animation_group)
        animation_layout.addRow(
            "Relax effect",
            self._choice_combo(
                ("animation", "relax_effect"),
                tuple(
                    ({"lightning": "Lightning bolt", "comet": "Comet dot", "none": "None"}[value], value)
                    for value in RELAX_EFFECTS
                ),
            ),
        )
        animation_layout.addRow(
            "Final reveal",
            self._choice_combo(
                ("animation", "final_reveal"),
                tuple(
                    ({"stagger": "Stagger path", "instant": "Instant"}[value], value)
                    for value in FINAL_REVEALS
                ),
            ),
        )
        animation_layout.addRow(
            "Impact ring",
            self._bool_check(("animation", "impact_ring"), "Flash the receiving node ring"),
        )
        animation_layout.addRow(
            "Impact badge",
            self._bool_check(("animation", "impact_badge"), "Flash the receiving distance badge"),
        )
        animation_layout.addRow(
            "Travel color",
            self._nullable_color_row(("animation", "travel_color")),
        )
        animation_layout.addRow(
            "Impact ring color",
            self._nullable_color_row(("animation", "impact_color")),
        )
        animation_layout.addRow(
            "Badge flash color",
            self._nullable_color_row(("animation", "badge_flash_color")),
        )
        animation_layout.addRow(
            "Motion speed",
            self._num_spin(("animation", "motion_scale"), 0.25, 2.0, 0.05),
        )
        layout.addWidget(animation_group)
        layout.addStretch(1)
        return page

    def _build_import_export_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        file_group = QGroupBox("File")
        file_layout = QHBoxLayout(file_group)
        import_button = QPushButton("Import JSON...")
        import_button.clicked.connect(self._import_json_file)
        file_layout.addWidget(import_button)
        import_qss_button = QPushButton("Import QSS...")
        import_qss_button.clicked.connect(self._import_qss_file)
        file_layout.addWidget(import_qss_button)
        export_json_button = QPushButton("Export JSON...")
        export_json_button.clicked.connect(self._export_json_file)
        file_layout.addWidget(export_json_button)
        export_qss_button = QPushButton("Export QSS...")
        export_qss_button.clicked.connect(self._export_qss_file)
        file_layout.addWidget(export_qss_button)
        file_layout.addStretch(1)
        layout.addWidget(file_group)

        paste_group = QGroupBox("Paste JSON theme")
        paste_layout = QVBoxLayout(paste_group)
        self._json_paste = QPlainTextEdit()
        self._json_paste.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._json_paste.setPlaceholderText(
            "Paste an exported Dijkstra Dashboard theme JSON here."
        )
        paste_layout.addWidget(self._json_paste, stretch=1)
        paste_buttons = QHBoxLayout()
        apply_button = QPushButton("Apply pasted JSON")
        apply_button.clicked.connect(self._apply_pasted_json)
        paste_buttons.addWidget(apply_button)
        load_current_button = QPushButton("Load current JSON")
        load_current_button.clicked.connect(self._load_current_json_into_paste)
        paste_buttons.addWidget(load_current_button)
        copy_json_button = QPushButton("Copy JSON")
        copy_json_button.clicked.connect(self._copy_json)
        paste_buttons.addWidget(copy_json_button)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._json_paste.clear)
        paste_buttons.addWidget(clear_button)
        paste_buttons.addStretch(1)
        paste_layout.addLayout(paste_buttons)
        layout.addWidget(paste_group, stretch=1)

        qss_paste_group = QGroupBox("Paste Qt stylesheet")
        qss_paste_layout = QVBoxLayout(qss_paste_group)
        self._qss_paste = QPlainTextEdit()
        self._qss_paste.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._qss_paste.setPlaceholderText(
            "Paste a Qt stylesheet (QSS) here. It is saved with this theme. Use Import pasted QSS to copy its colors into editable fields."
        )
        self._qss_paste.textChanged.connect(self._on_qss_paste_changed)
        qss_paste_layout.addWidget(self._qss_paste, stretch=1)
        qss_paste_buttons = QHBoxLayout()
        apply_qss_button = QPushButton("Import pasted QSS")
        apply_qss_button.clicked.connect(self._apply_pasted_qss)
        qss_paste_buttons.addWidget(apply_qss_button)
        load_qss_button = QPushButton("Load generated QSS")
        load_qss_button.clicked.connect(self._load_current_qss_into_paste)
        qss_paste_buttons.addWidget(load_qss_button)
        clear_qss_button = QPushButton("Clear custom QSS")
        clear_qss_button.clicked.connect(self._clear_custom_qss)
        qss_paste_buttons.addWidget(clear_qss_button)
        qss_paste_buttons.addStretch(1)
        qss_paste_layout.addLayout(qss_paste_buttons)
        layout.addWidget(qss_paste_group, stretch=1)

        qss_group = QGroupBox("Generated QSS preview")
        qss_layout = QVBoxLayout(qss_group)
        self._qss_preview = QPlainTextEdit()
        self._qss_preview.setReadOnly(True)
        self._qss_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        qss_layout.addWidget(self._qss_preview, stretch=1)
        qss_buttons = QHBoxLayout()
        refresh_button = QPushButton("Refresh QSS")
        refresh_button.clicked.connect(self._refresh_export_views)
        qss_buttons.addWidget(refresh_button)
        copy_button = QPushButton("Copy QSS")
        copy_button.clicked.connect(self._copy_qss)
        qss_buttons.addWidget(copy_button)
        qss_buttons.addStretch(1)
        qss_layout.addLayout(qss_buttons)
        layout.addWidget(qss_group, stretch=1)

        return page

    # -- widget factories (register into the per-path maps) ------------
    def _color_row(self, path, alpha):
        row = _ColorRow(path, self._get(path), alpha, self._edit_hex)
        self._color_rows[path] = row
        return row

    def _nullable_color_row(self, path):
        container = QWidget()
        line = QHBoxLayout(container)
        line.setContentsMargins(0, 0, 0, 0)
        value = self._get(path)
        row = _ColorRow(path, value, alpha=True, on_change=self._edit_hex)
        self._color_rows[path] = row
        none_check = QCheckBox("none")
        none_check.setChecked(value is None)
        row.setEnabled(value is not None)
        none_check.toggled.connect(lambda checked, p=path: self._on_none_toggled(p, checked))
        self._none_checks[path] = none_check
        line.addWidget(row, stretch=1)
        line.addWidget(none_check)
        return container

    def _on_none_toggled(self, path, checked):
        row = self._color_rows.get(path)
        if checked:
            if row is not None:
                row.setEnabled(False)
            self._set_value(path, None)
        else:
            seed_value = self._walk(self._seed, path)
            restored = seed_value if isinstance(seed_value, str) else self._nullable_color_fallback(path)
            if row is not None:
                row.set_value(restored)
                row.setEnabled(True)
            self._set_value(path, restored)

    def _nullable_color_fallback(self, path):
        if path and path[-1] == "halo":
            color = QColor(self._working.get("accent", "#00e5ff"))
            state = path[-2] if len(path) >= 2 else ""
            color.setAlpha(90 if state in {"relaxed", "final"} else 38)
            return color.name(QColor.NameFormat.HexArgb)
        if path and path[-1] == "glow":
            color = QColor(self._working.get("accent", "#00e5ff"))
            color.setAlpha(128)
            return color.name(QColor.NameFormat.HexArgb)
        return self._working.get("warning", "#ffb020")

    def _num_spin(self, path, low, high, step):
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.setValue(float(self._get(path)))
        spin.valueChanged.connect(lambda v, p=path: self._set_value(p, float(v)))
        self._spins[path] = spin
        return spin

    def _int_spin(self, path, low, high):
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(1)
        spin.setDecimals(0)
        spin.setValue(float(self._get(path)))
        spin.valueChanged.connect(lambda v, p=path: self._set_value(p, int(round(v))))
        self._spins[path] = spin
        return spin

    def _choice_combo(self, path, choices):
        combo = QComboBox()
        for label, value in choices:
            combo.addItem(label, userData=value)
        value = self._get(path)
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))
        combo.currentIndexChanged.connect(lambda _idx, p=path, c=combo: self._on_choice_changed(p, c))
        self._combos[path] = combo
        return combo

    def _on_choice_changed(self, path, combo):
        value = combo.currentData()
        if value is not None:
            self._set_value(path, value)

    def _bool_check(self, path, label):
        check = QCheckBox(label)
        check.setChecked(bool(self._get(path)))
        check.toggled.connect(lambda checked, p=path: self._set_value(p, bool(checked)))
        self._none_checks[path] = check
        return check

    # ------------------------------------------------------------------
    # Refresh / reset
    # ------------------------------------------------------------------
    def _refresh_all_widgets(self):
        for path, spin in self._spins.items():
            spin.blockSignals(True)
            spin.setValue(float(self._get(path)))
            spin.blockSignals(False)
        for path, combo in self._combos.items():
            combo.blockSignals(True)
            index = combo.findData(self._get(path))
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)
        for path, row in self._color_rows.items():
            value = self._get(path)
            row.set_value(value)
            if path in self._none_checks:
                check = self._none_checks[path]
                if isinstance(check, QCheckBox) and check.text() == "none":
                    check.blockSignals(True)
                    check.setChecked(value is None)
                    check.blockSignals(False)
                    row.setEnabled(value is not None)
        for path, check in self._none_checks.items():
            if path in self._color_rows:
                continue
            check.blockSignals(True)
            check.setChecked(bool(self._get(path)))
            check.blockSignals(False)
        if self._glow_enabled_check is not None:
            self._glow_enabled_check.blockSignals(True)
            self._glow_enabled_check.setChecked(bool(self._get(("glow_enabled",))))
            self._glow_enabled_check.blockSignals(False)
        if self._qss_paste is not None:
            self._qss_paste.blockSignals(True)
            self._qss_paste.setPlainText(self._working.get("custom_qss", ""))
            self._qss_paste.blockSignals(False)
        self._refresh_export_views()

    def _select_category(self, name):
        self._category_list.setCurrentRow(_CATEGORIES.index(name))

    def _reset_section(self):
        row = self._category_list.currentRow()
        if row < 0:
            return
        self._reset_category(_CATEGORIES[row])

    def _reset_category(self, name):
        if name == "Canvas & Chrome":
            for _label, key in _CHROME_FIELDS:
                self._working[key] = copy.deepcopy(self._seed[key])
        elif name == "Node states":
            self._working["node_styles"] = copy.deepcopy(self._seed["node_styles"])
        elif name == "Edge states":
            self._working["edge_styles"] = copy.deepcopy(self._seed["edge_styles"])
        elif name == "Qt style":
            self._working["app_style"] = copy.deepcopy(self._seed["app_style"])
        elif name == "Effects":
            self._working["glow_enabled"] = self._seed["glow_enabled"]
            self._working["animation"] = copy.deepcopy(self._seed["animation"])
        elif name == "Import / Export":
            self._refresh_export_views()
            return
        self._refresh_all_widgets()
        self._mark_dirty()

    # ------------------------------------------------------------------
    # Import / export
    # ------------------------------------------------------------------
    def _save_ready_theme_data(self):
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("Theme name cannot be empty.")
        data = copy.deepcopy(self._working)
        data["id"] = self._current_slug()
        data["name"] = name
        # Normalize through the validator so exported JSON is complete and stable.
        return theme_to_dict(theme_from_dict(data))

    def _save_ready_theme(self):
        return theme_from_dict(self._save_ready_theme_data())

    def _load_theme_data(self, data, source="theme JSON"):
        try:
            theme = theme_from_dict(data)
        except Exception as exc:
            self._show_error(f"Could not import {source}: {exc}")
            return False

        self._working = theme_to_dict(theme)
        self._name_edit.blockSignals(True)
        self._name_edit.setText(theme.name)
        self._name_edit.blockSignals(False)
        self._slug_label.setText(f"id: {self._current_slug()}")
        self._refresh_all_widgets()
        self._mark_dirty()
        self._show_error("")
        return True

    def _import_json_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Theme", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            return
        try:
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
        except Exception as exc:
            self._show_error(f"Could not read theme JSON: {exc}")
            return
        self._load_theme_data(data, Path(filename).name)

    def _export_json_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Theme JSON", f"{self._current_slug()}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        try:
            data = self._save_ready_theme_data()
            path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        except Exception as exc:
            self._show_error(f"Could not export JSON: {exc}")

    def _export_qss_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Generated QSS", f"{self._current_slug()}.qss",
            "Qt Stylesheets (*.qss);;All Files (*)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".qss":
            path = path.with_suffix(".qss")
        try:
            path.write_text(self._save_ready_theme().qss(), encoding="utf-8")
        except Exception as exc:
            self._show_error(f"Could not export QSS: {exc}")

    def _import_qss_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Qt Stylesheet", "", "Qt Stylesheets (*.qss);;All Files (*)"
        )
        if not filename:
            return False
        try:
            text = Path(filename).read_text(encoding="utf-8")
        except Exception as exc:
            self._show_error(f"Could not read QSS: {exc}")
            return False
        if self._qss_paste is not None:
            self._qss_paste.setPlainText(text)
        return self._apply_pasted_qss()

    def _apply_pasted_json(self):
        if self._json_paste is None:
            return False
        text = self._json_paste.toPlainText().strip()
        if not text:
            self._show_error("Paste a theme JSON first.")
            return False
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self._show_error(f"Invalid JSON: {exc}")
            return False
        return self._load_theme_data(data, "pasted JSON")

    def _load_current_json_into_paste(self):
        if self._json_paste is None:
            return
        try:
            data = self._save_ready_theme_data()
        except Exception as exc:
            self._show_error(str(exc))
            return
        self._json_paste.setPlainText(json.dumps(data, indent=2, ensure_ascii=True))

    def _apply_pasted_qss(self):
        if self._qss_paste is None:
            return False
        if not self._qss_paste.toPlainText().strip():
            self._show_error("Paste a Qt stylesheet first.")
            return False
        if not self._sync_qss_paste_to_working(parse=True, show_errors=True):
            return False
        self._refresh_all_widgets()
        self._show_error("")
        return True

    def _load_current_qss_into_paste(self):
        if self._qss_paste is None:
            return
        try:
            self._qss_paste.setPlainText(self._save_ready_theme().qss())
        except Exception as exc:
            self._show_error(str(exc))

    def _clear_custom_qss(self):
        self._working["custom_qss"] = ""
        if self._qss_paste is not None:
            self._qss_paste.clear()
        self._refresh_export_views()
        self._mark_dirty()
        self._show_error("")

    def _refresh_export_views(self):
        if self._qss_preview is None:
            return
        try:
            self._qss_preview.setPlainText(self._save_ready_theme().qss())
        except Exception:
            self._qss_preview.setPlainText("")

    def _copy_qss(self):
        if self._qss_preview is None:
            return
        QApplication.clipboard().setText(self._qss_preview.toPlainText())

    def _copy_json(self):
        try:
            data = self._save_ready_theme_data()
        except Exception as exc:
            self._show_error(str(exc))
            return
        QApplication.clipboard().setText(json.dumps(data, indent=2, ensure_ascii=True))

    def _refresh_delete_button(self):
        current_id = self._seed.get("id")
        can_delete = (
            isinstance(current_id, str)
            and current_id in self._manager.theme_ids()
            and current_id not in self._manager.BUILTIN_THEMES
            and current_id != PREVIEW_THEME_ID
        )
        self._delete_button.setEnabled(can_delete)

    def _delete_saved_theme(self):
        theme_id = self._seed.get("id")
        if (
            not isinstance(theme_id, str)
            or theme_id in self._manager.BUILTIN_THEMES
            or theme_id == PREVIEW_THEME_ID
            or theme_id not in self._manager.theme_ids()
        ):
            self._show_error("Only saved custom themes can be deleted.")
            return
        self._preview_timer.stop()
        self._manager.delete_custom_theme(theme_id)
        self._saved = True
        self.accept()

    # ------------------------------------------------------------------
    # Save / cancel / close
    # ------------------------------------------------------------------
    def _show_error(self, message):
        self._error_label.setText(message)

    def _on_save(self):
        name = self._name_edit.text().strip()
        if not name:
            self._show_error("Theme name cannot be empty.")
            return
        # Save must not re-import QSS over manual palette edits. "Import pasted
        # QSS" is the explicit one-shot bridge from QSS into editable fields;
        # saving only persists the raw stylesheet layer.
        if not self._sync_qss_paste_to_working(parse=False, show_errors=False):
            return
        slug = self._current_slug()
        save_data = dict(self._working)
        save_data["id"] = slug
        save_data["name"] = name
        try:
            theme = theme_from_dict(save_data)
        except Exception as exc:  # pragma: no cover - defensive
            self._show_error(str(exc))
            return

        self._preview_timer.stop()
        self._manager.save_custom_theme(theme)   # writes <slug>.json + registers
        self._manager.set_theme(slug, persist=True)
        self._drop_preview()
        self._saved = True
        self.accept()

    def _restore_original(self):
        if self._saved:
            return
        self._preview_timer.stop()
        if (
            self._manager.current.id != self._original_id
            and self._original_id in self._manager.theme_ids()
        ):
            self._manager.set_theme(self._original_id, persist=False)
        self._drop_preview()

    def reject(self):
        self._restore_original()
        super().reject()

    def closeEvent(self, event):
        self._restore_original()
        super().closeEvent(event)
