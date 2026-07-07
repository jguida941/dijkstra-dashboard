import json

import pytest
from PyQt6.QtTest import QSignalSpy

from dijkstra_dashboard.ui.theme import ThemeManager, custom_theme_dir, theme_from_dict


def _make_custom(theme_id="my-custom", name="My Custom", **overrides):
    data = {"id": theme_id, "name": name}
    data.update(overrides)
    return theme_from_dict(data)


@pytest.mark.ui
def test_save_custom_theme_writes_json_under_hermetic_config_dir():
    manager = ThemeManager()
    theme = _make_custom(accent="#abcdef")

    path = manager.save_custom_theme(theme)

    # Written as <config dir>/themes/<id>.json inside the tmp hermetic dir.
    assert path == custom_theme_dir() / "my-custom.json"
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["id"] == "my-custom"
    assert saved["accent"] == "#abcdef"
    # Registered on the saving manager immediately.
    assert "my-custom" in manager.theme_ids()


@pytest.mark.ui
def test_fresh_manager_load_custom_themes_exposes_saved_id():
    saver = ThemeManager()
    saver.save_custom_theme(_make_custom(theme_id="fresh-one", name="Fresh One"))

    fresh = ThemeManager()
    assert "fresh-one" not in fresh.theme_ids()

    fresh.load_custom_themes()
    assert "fresh-one" in fresh.theme_ids()
    assert fresh.THEMES["fresh-one"].name == "Fresh One"


@pytest.mark.ui
def test_load_from_config_resolves_persisted_custom_id_after_custom_load():
    saver = ThemeManager()
    saver.save_custom_theme(_make_custom(theme_id="persisted", name="Persisted"))
    saver.set_theme("persisted", persist=True)

    fresh = ThemeManager()
    # Boot order: custom themes load BEFORE load_from_config so the id resolves.
    fresh.load_custom_themes()
    fresh.load_from_config()

    assert fresh.current.id == "persisted"


@pytest.mark.ui
def test_load_from_config_falls_back_when_custom_not_loaded_first():
    saver = ThemeManager()
    saver.save_custom_theme(_make_custom(theme_id="persisted2", name="Persisted Two"))
    saver.set_theme("persisted2", persist=True)

    fresh = ThemeManager()
    fresh.load_from_config()  # custom NOT loaded -> unknown id -> neon fallback

    assert fresh.current.id == "neon-dark"


@pytest.mark.ui
def test_register_new_theme_emits_themes_changed(qapp):
    manager = ThemeManager()
    spy = QSignalSpy(manager.themes_changed)

    manager.register_theme(_make_custom(theme_id="reg-new", name="Reg New"))

    assert len(spy) == 1
    assert "reg-new" in manager.theme_ids()


@pytest.mark.ui
def test_register_replacing_existing_id_does_not_re_emit_themes_changed(qapp):
    manager = ThemeManager()
    manager.register_theme(_make_custom(theme_id="dup", name="Dup"))
    spy = QSignalSpy(manager.themes_changed)

    manager.register_theme(_make_custom(theme_id="dup", name="Dup v2", accent="#101010"))

    # Value-only replacement of an already-registered id: no menu-rebuild signal.
    assert len(spy) == 0
    assert manager.THEMES["dup"].name == "Dup v2"


@pytest.mark.ui
def test_register_replacing_active_theme_reapplies_via_theme_changed(qapp):
    manager = ThemeManager()
    manager.register_theme(_make_custom(theme_id="live", name="Live", accent="#111111"))
    manager.set_theme("live", persist=False)
    spy = QSignalSpy(manager.theme_changed)

    # Replacing the currently-active theme must re-apply (set_theme no-ops on the
    # same id) so live-preview edits actually refresh.
    manager.register_theme(_make_custom(theme_id="live", name="Live", accent="#222222"))

    assert len(spy) == 1
    assert manager.current.accent == "#222222"


@pytest.mark.ui
def test_unregister_custom_theme_removes_and_emits(qapp):
    manager = ThemeManager()
    manager.register_theme(_make_custom(theme_id="temp", name="Temp"))
    spy = QSignalSpy(manager.themes_changed)

    manager.unregister_theme("temp")

    assert "temp" not in manager.theme_ids()
    assert len(spy) == 1


@pytest.mark.ui
def test_unregister_builtin_is_refused():
    manager = ThemeManager()

    with pytest.raises(ValueError):
        manager.unregister_theme("neon-dark")

    assert "neon-dark" in manager.theme_ids()


@pytest.mark.ui
def test_delete_custom_theme_removes_file_registry_and_falls_back_when_active():
    manager = ThemeManager()
    theme = _make_custom(theme_id="delete-me", name="Delete Me")
    path = manager.save_custom_theme(theme)
    manager.set_theme("delete-me", persist=False)

    manager.delete_custom_theme("delete-me")

    assert not path.exists()
    assert "delete-me" not in manager.theme_ids()
    assert manager.current.id == "neon-dark"


@pytest.mark.ui
def test_delete_custom_theme_refuses_builtin():
    manager = ThemeManager()

    with pytest.raises(ValueError):
        manager.delete_custom_theme("neon-dark")

    assert "neon-dark" in manager.theme_ids()


@pytest.mark.ui
def test_load_custom_themes_skips_invalid_files():
    seed = ThemeManager()
    seed.save_custom_theme(_make_custom(theme_id="valid-one", name="Valid One"))
    directory = custom_theme_dir()
    (directory / "broken.json").write_text("{ not json", encoding="utf-8")
    (directory / "noid.json").write_text(json.dumps({"name": "No Id"}), encoding="utf-8")

    fresh = ThemeManager()
    fresh.load_custom_themes()  # must not raise

    assert set(fresh.theme_ids()) == {"neon-dark", "midnight", "paper-light", "valid-one"}


@pytest.mark.ui
def test_load_custom_themes_never_overrides_builtin_id():
    directory = custom_theme_dir()
    directory.mkdir(parents=True, exist_ok=True)
    hijack = {"id": "neon-dark", "name": "Hijacked", "accent": "#000000"}
    (directory / "neon-dark.json").write_text(json.dumps(hijack), encoding="utf-8")

    manager = ThemeManager()
    manager.load_custom_themes()

    assert manager.THEMES["neon-dark"] == ThemeManager.BUILTIN_THEMES["neon-dark"]
    assert manager.THEMES["neon-dark"].name == "Neon Dark"


@pytest.mark.ui
def test_registry_is_per_instance_not_shared():
    a = ThemeManager()
    b = ThemeManager()

    a.register_theme(_make_custom(theme_id="only-in-a", name="Only In A"))

    assert "only-in-a" in a.theme_ids()
    assert "only-in-a" not in b.theme_ids()
    # Built-ins remain untouched by instance registration.
    assert "only-in-a" not in ThemeManager.BUILTIN_THEMES
