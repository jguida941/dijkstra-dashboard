import json

import pytest

from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.theme import (
    PREVIEW_THEME_ID,
    ThemeManager,
    custom_theme_dir,
    get_theme_manager,
    theme_to_dict,
)
import dijkstra_dashboard.ui.theme_editor as theme_editor_module
from dijkstra_dashboard.ui.theme_editor import ThemeEditorDialog


def _theme_menu(window):
    view_menu = next(
        m.menu()
        for m in window.menuBar().actions()
        if m.menu() and m.menu().title() == "View"
    )
    return next(
        a.menu()
        for a in view_menu.actions()
        if a.menu() and a.menu().title() == "Theme"
    )


@pytest.mark.ui
def test_dialog_seeds_name_and_known_hex_from_current_theme(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        assert dialog._name_edit.text() == "Neon Dark"
        # A known chrome hex from the current theme lands in the working copy.
        assert dialog._working["accent"] == "#00e5ff"
    finally:
        dialog.reject()


@pytest.mark.ui
def test_slug_derived_from_name_and_builtin_collision_suffixed(qapp):
    dialog = ThemeEditorDialog()
    try:
        dialog._name_edit.setText("My Neon")
        assert dialog._current_slug() == "my-neon"
        # Collision with a built-in id gets a -2 suffix (never clobbers a built-in).
        dialog._name_edit.setText("Neon Dark")
        assert dialog._current_slug() == "neon-dark-2"
    finally:
        dialog.reject()


@pytest.mark.ui
def test_model_edit_plus_flush_reflects_in_live_preview(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        dialog._set_color(("node_styles", "visited", "fill"), "#112233")
        dialog._flush_preview()

        assert manager.current.id == PREVIEW_THEME_ID
        assert manager.current.node_styles["visited"].fill == "#112233"
    finally:
        dialog.reject()


@pytest.mark.ui
def test_animation_edit_plus_flush_reflects_in_live_preview(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        dialog._set_value(("animation", "relax_effect"), "comet")
        dialog._set_value(("animation", "final_reveal"), "instant")
        dialog._set_value(("animation", "impact_ring"), False)
        dialog._set_value(("animation", "travel_color"), "#ffaa00")
        dialog._set_value(("animation", "impact_color"), "#ff5500")
        dialog._flush_preview()

        assert manager.current.id == PREVIEW_THEME_ID
        assert manager.current.animation.relax_effect == "comet"
        assert manager.current.animation.final_reveal == "instant"
        assert manager.current.animation.impact_ring is False
        assert manager.current.animation.travel_color == "#ffaa00"
        assert manager.current.animation.impact_color == "#ff5500"
    finally:
        dialog.reject()


@pytest.mark.ui
def test_app_style_edit_plus_flush_reflects_in_live_preview_and_qss(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        dialog._set_value(("app_style", "border_radius"), 14)
        dialog._set_value(("app_style", "scrollbar_width"), 18)
        dialog._flush_preview()

        assert manager.current.id == PREVIEW_THEME_ID
        assert manager.current.app_style.border_radius == 14
        assert manager.current.app_style.scrollbar_width == 18
        assert "border-radius: 14px" in manager.current.qss()
        assert "width: 18px" in manager.current.qss()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_pasted_json_import_updates_working_theme_and_export_preview(qapp):
    manager = get_theme_manager()
    manager.set_theme("midnight", persist=False)
    data = theme_to_dict(manager.current)
    data["id"] = "pasted"
    data["name"] = "Pasted"
    data["accent"] = "#123456"
    data["app_style"]["border_radius"] = 11

    dialog = ThemeEditorDialog()
    try:
        dialog._json_paste.setPlainText(json.dumps(data))
        assert dialog._apply_pasted_json() is True

        assert dialog._name_edit.text() == "Pasted"
        assert dialog._working["accent"] == "#123456"
        assert dialog._working["app_style"]["border_radius"] == 11
        assert "border-radius: 11px" in dialog._qss_preview.toPlainText()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_pasted_qss_import_updates_working_theme_and_export_preview(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)
    qss = """
    QMainWindow { background-color: #111111; color: #eeeeee; }
    QPushButton {
        background-color: #222222;
        border: 2px solid #444444;
        border-radius: 12px;
        padding: 8px;
    }
    QLineEdit {
        selection-background-color: #ff00aa;
        selection-color: #000000;
    }
    """

    dialog = ThemeEditorDialog()
    try:
        dialog._qss_paste.setPlainText(qss)
        assert dialog._apply_pasted_qss() is True

        assert dialog._working["custom_qss"] == qss.strip()
        assert dialog._working["base_bg"] == "#111111"
        assert dialog._working["button_bg"] == "#222222"
        assert dialog._working["button_border"] == "#444444"
        assert dialog._working["highlight"] == "#ff00aa"
        assert dialog._working["app_style"]["border_radius"] == 12
        assert "/* Custom QSS */" in dialog._qss_preview.toPlainText()
        assert "QMainWindow { background-color: #111111; color: #eeeeee; }" in dialog._qss_preview.toPlainText()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_clear_custom_qss_removes_saved_stylesheet_layer(qapp):
    dialog = ThemeEditorDialog()
    try:
        dialog._working["custom_qss"] = "QLabel { color: #abcdef; }"
        dialog._qss_paste.setPlainText(dialog._working["custom_qss"])

        dialog._clear_custom_qss()

        assert dialog._working["custom_qss"] == ""
        assert dialog._qss_paste.toPlainText() == ""
        assert "QLabel { color: #abcdef; }" not in dialog._qss_preview.toPlainText()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_import_qss_file_parses_stylesheet(qapp, tmp_path, monkeypatch):
    qss_path = tmp_path / "theme.qss"
    qss_path.write_text(
        "QPushButton { background-color: #222222; border: 3px solid #555555; }",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        theme_editor_module.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(qss_path), ""),
    )

    dialog = ThemeEditorDialog()
    try:
        assert dialog._import_qss_file() is True

        assert dialog._working["custom_qss"] == qss_path.read_text(encoding="utf-8")
        assert dialog._working["base_bg"] == "#222222"
        assert dialog._working["button_border"] == "#555555"
        assert dialog._working["app_style"]["border_width"] == 3
    finally:
        dialog.reject()


@pytest.mark.ui
def test_cancel_restores_original_theme_and_unregisters_preview(qapp):
    manager = get_theme_manager()
    manager.set_theme("midnight", persist=False)

    dialog = ThemeEditorDialog()
    dialog._set_color(("accent",), "#010203")
    dialog._flush_preview()
    assert manager.current.id == PREVIEW_THEME_ID

    dialog.reject()

    assert manager.current.id == "midnight"
    assert PREVIEW_THEME_ID not in manager.theme_ids()


@pytest.mark.ui
def test_save_creates_file_grows_menu_and_switches_current(qapp):
    window = MainWindow()
    manager = get_theme_manager()
    theme_menu = _theme_menu(window)
    before = len(theme_menu.actions())

    dialog = ThemeEditorDialog()
    dialog._name_edit.setText("Sunset Blaze")
    dialog._set_color(("accent",), "#ff8800")
    dialog._flush_preview()
    dialog._on_save()

    assert (custom_theme_dir() / "sunset-blaze.json").exists()
    assert manager.current.id == "sunset-blaze"
    assert len(theme_menu.actions()) == before + 1
    assert PREVIEW_THEME_ID not in manager.theme_ids()
    # The reserved preview id never appears in the Theme menu.
    assert all(a.data() != PREVIEW_THEME_ID for a in theme_menu.actions())
    window.close()


@pytest.mark.ui
def test_theme_editor_delete_saved_custom_theme_removes_file_and_accepts(qapp):
    manager = get_theme_manager()
    dialog = ThemeEditorDialog()
    dialog._name_edit.setText("Delete From Studio")
    dialog._on_save()
    assert (custom_theme_dir() / "delete-from-studio.json").exists()

    delete_dialog = ThemeEditorDialog()
    try:
        assert delete_dialog._delete_button.isEnabled()
        delete_dialog._delete_saved_theme()

        assert delete_dialog.result() == int(delete_dialog.DialogCode.Accepted)
        assert not (custom_theme_dir() / "delete-from-studio.json").exists()
        assert "delete-from-studio" not in manager.theme_ids()
        assert manager.current.id == "neon-dark"
    finally:
        if delete_dialog.result() != int(delete_dialog.DialogCode.Accepted):
            delete_dialog.reject()


@pytest.mark.ui
def test_saved_theme_survives_reload_through_load_custom_themes(qapp):
    dialog = ThemeEditorDialog()
    dialog._name_edit.setText("Persisted Custom")
    dialog._set_color(("accent",), "#ff8800")
    dialog._on_save()

    fresh = ThemeManager()
    fresh.load_custom_themes()
    assert "persisted-custom" in fresh.theme_ids()
    assert fresh.THEMES["persisted-custom"].accent == "#ff8800"


@pytest.mark.ui
def test_invalid_hex_rejected_field_marked_and_dict_unchanged(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        original = dialog._working["accent"]
        ok = dialog._edit_hex(("accent",), "not-a-hex")

        assert ok is False
        assert dialog._working["accent"] == original
        assert dialog._color_rows[("accent",)].is_invalid()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_valid_hex_commits_and_clears_invalid_mark(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        assert dialog._edit_hex(("accent",), "#ABCDEF") is True
        assert dialog._working["accent"] == "#ABCDEF"
        assert not dialog._color_rows[("accent",)].is_invalid()
    finally:
        dialog.reject()


@pytest.mark.ui
def test_reset_section_restores_category_from_seed(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        seed_accent = dialog._seed["accent"]
        dialog._set_color(("accent",), "#000000")
        assert dialog._working["accent"] == "#000000"

        dialog._select_category("Canvas & Chrome")
        dialog._reset_section()

        assert dialog._working["accent"] == seed_accent
    finally:
        dialog.reject()


@pytest.mark.ui
def test_reset_effects_restores_animation_settings(qapp):
    manager = get_theme_manager()
    manager.set_theme("neon-dark", persist=False)

    dialog = ThemeEditorDialog()
    try:
        seed = dialog._seed["animation"]["relax_effect"]
        dialog._set_value(("animation", "relax_effect"), "none")
        assert dialog._working["animation"]["relax_effect"] == "none"

        dialog._select_category("Effects")
        dialog._reset_section()

        assert dialog._working["animation"]["relax_effect"] == seed
    finally:
        dialog.reject()


@pytest.mark.ui
def test_empty_name_on_save_is_rejected_inline(qapp):
    dialog = ThemeEditorDialog()
    try:
        dialog._name_edit.setText("   ")
        dialog._on_save()
        # Dialog stays open (not accepted) and surfaces an inline error.
        assert dialog.result() != int(dialog.DialogCode.Accepted)
        assert dialog._error_label.text()
    finally:
        dialog.reject()
