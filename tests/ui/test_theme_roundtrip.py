import json

import pytest

from dijkstra_dashboard.ui.theme import ThemeManager, theme_from_dict, theme_to_dict


@pytest.mark.ui
@pytest.mark.parametrize("theme_id", ["neon-dark", "midnight", "paper-light"])
def test_round_trip_equals_builtin(theme_id):
    original = ThemeManager.THEMES[theme_id]
    rebuilt = theme_from_dict(theme_to_dict(original))
    assert rebuilt == original


@pytest.mark.ui
def test_to_dict_is_json_serializable_and_survives_disk_round_trip():
    original = ThemeManager.THEMES["midnight"]
    data = theme_to_dict(original)
    # font_pref is emitted as a JSON-able list (not a tuple).
    assert isinstance(data["font_pref"], list)
    reloaded = json.loads(json.dumps(data))
    assert theme_from_dict(reloaded) == original


@pytest.mark.ui
def test_from_dict_fills_missing_style_fields_from_neon_defaults():
    neon = ThemeManager.THEMES["neon-dark"]
    sparse = {
        "id": "sparse",
        "name": "Sparse",
        "node_styles": {"visited": {"fill": "#123456"}},
    }
    theme = theme_from_dict(sparse)

    assert theme.id == "sparse"
    assert theme.name == "Sparse"
    # Provided field kept verbatim.
    assert theme.node_styles["visited"].fill == "#123456"
    # Sibling fields of the SAME state default from neon.
    assert theme.node_styles["visited"].ring == neon.node_styles["visited"].ring
    assert theme.node_styles["visited"].glow == neon.node_styles["visited"].glow
    # Untouched states/edges default entirely from neon.
    assert theme.node_styles["current"] == neon.node_styles["current"]
    assert theme.edge_styles["relaxed"] == neon.edge_styles["relaxed"]
    # Missing chrome fields default from neon.
    assert theme.accent == neon.accent
    assert theme.dark == neon.dark
    assert theme.font_pref == neon.font_pref
    assert theme.animation == neon.animation


@pytest.mark.ui
def test_from_dict_rejects_non_dict():
    with pytest.raises(ValueError):
        theme_from_dict(["not", "a", "dict"])


@pytest.mark.ui
def test_from_dict_rejects_missing_or_blank_id():
    with pytest.raises(ValueError):
        theme_from_dict({"name": "No Id"})
    with pytest.raises(ValueError):
        theme_from_dict({"id": "   ", "name": "Blank Id"})


@pytest.mark.ui
def test_from_dict_rejects_missing_or_blank_name():
    with pytest.raises(ValueError):
        theme_from_dict({"id": "has-id"})
    with pytest.raises(ValueError):
        theme_from_dict({"id": "has-id", "name": "   "})


@pytest.mark.ui
def test_from_dict_ignores_unknown_keys():
    neon = ThemeManager.THEMES["neon-dark"]
    data = theme_to_dict(neon)
    data["totally_unknown"] = {"nested": [1, 2, 3]}
    data["node_styles"]["visited"]["bogus_field"] = "xyz"
    data["edge_styles"]["relaxed"]["also_bogus"] = 99

    theme = theme_from_dict(data)

    # Unknown keys silently dropped; result is identical to the built-in.
    assert theme == neon


@pytest.mark.ui
def test_from_dict_honors_explicit_null_glow_and_halo():
    data = {
        "id": "no-glow",
        "name": "No Glow",
        "node_styles": {"current": {"glow": None}},
        "edge_styles": {"relaxed": {"halo": None}},
    }
    theme = theme_from_dict(data)

    assert theme.node_styles["current"].glow is None
    assert theme.edge_styles["relaxed"].halo is None


@pytest.mark.ui
def test_from_dict_validates_animation_choices_and_clamps_motion_scale():
    neon = ThemeManager.THEMES["neon-dark"]
    data = {
        "id": "bad-animation",
        "name": "Bad Animation",
        "animation": {
            "relax_effect": "teleport",
            "final_reveal": "spiral",
            "impact_ring": False,
            "impact_badge": False,
            "motion_scale": 99,
        },
    }

    theme = theme_from_dict(data)

    assert theme.animation.relax_effect == neon.animation.relax_effect
    assert theme.animation.final_reveal == neon.animation.final_reveal
    assert theme.animation.impact_ring is False
    assert theme.animation.impact_badge is False
    assert theme.animation.motion_scale == 2.0


@pytest.mark.ui
def test_from_dict_round_trips_theme_studio_app_style_and_animation_colors():
    data = {
        "id": "studio",
        "name": "Studio",
        "animation": {
            "travel_color": "#ffaa00",
            "impact_color": "#ff5500",
            "badge_flash_color": "#ffee66",
        },
        "app_style": {
            "border_radius": 99,
            "small_radius": 7,
            "border_width": 3,
            "padding_y": 9,
            "slider_handle_size": 18,
        },
    }

    theme = theme_from_dict(data)
    saved = theme_to_dict(theme)
    rebuilt = theme_from_dict(saved)

    assert theme.animation.travel_color == "#ffaa00"
    assert theme.animation.impact_color == "#ff5500"
    assert theme.animation.badge_flash_color == "#ffee66"
    assert theme.app_style.border_radius == 32
    assert theme.app_style.small_radius == 7
    assert theme.app_style.border_width == 3
    assert theme.app_style.padding_y == 9
    assert theme.app_style.slider_handle_size == 18
    assert rebuilt == theme
