"""Phase 6 (UI) — RandomGraphDialog contract + pure helpers.

F1: ``values()`` returns EXACTLY the ``random_graph`` kwargs with the seed
already resolved to a concrete int; ``resolved_seed`` mirrors that int and is
cached at accept()-time so every generation is reproducible and echoable.
"""
from __future__ import annotations

import pytest

from dijkstra_dashboard.core.generate import random_graph
from dijkstra_dashboard.ui.random_graph_dialog import (
    RandomGraphDialog,
    normalize_weight_range,
    parse_seed,
    resolve_seed,
)


# ---- pure helpers (no QApplication needed) --------------------------------
def test_parse_seed_digits_empty_and_invalid():
    assert parse_seed("123") == 123
    assert parse_seed("") is None
    assert parse_seed("   ") is None
    assert parse_seed("12a") is None
    assert parse_seed(None) is None


def test_resolve_seed_passthrough_and_random():
    assert resolve_seed(7) == 7
    drawn = resolve_seed(None)
    assert isinstance(drawn, int)
    assert drawn >= 0


def test_normalize_weight_range_clamps_max_below_min():
    assert normalize_weight_range(5, 3) == (5, 5)
    assert normalize_weight_range(2, 9) == (2, 9)
    assert normalize_weight_range(4, 4) == (4, 4)


# ---- dialog behaviour ------------------------------------------------------
@pytest.mark.ui
def test_dialog_values_match_random_graph_kwargs(qapp):
    dialog = RandomGraphDialog()
    dialog.node_spin.setValue(6)
    dialog.density_spin.setValue(0.3)
    dialog.weight_min_spin.setValue(2)
    dialog.weight_max_spin.setValue(7)
    dialog.seed_edit.setText("99")
    dialog.directed_check.setChecked(True)
    dialog.connected_check.setChecked(True)
    dialog.accept()

    values = dialog.values()
    assert set(values.keys()) == {
        "node_count", "edge_density", "weight_range", "seed", "directed", "connected",
    }
    assert values["node_count"] == 6
    assert values["weight_range"] == (2, 7)
    assert values["seed"] == 99
    assert dialog.resolved_seed == 99
    assert values["directed"] is True
    assert values["connected"] is True

    # The kwargs must feed random_graph directly (F1 contract).
    graph = random_graph(**values)
    assert len(graph.get_nodes()) == 6


@pytest.mark.ui
def test_dialog_resolves_empty_seed_to_stable_int(qapp):
    dialog = RandomGraphDialog()
    dialog.seed_edit.setText("")
    dialog.accept()

    assert isinstance(dialog.resolved_seed, int)
    values = dialog.values()
    assert values["seed"] == dialog.resolved_seed
    # Resolved exactly once: repeated reads stay identical.
    assert dialog.values()["seed"] == dialog.resolved_seed


@pytest.mark.ui
def test_dialog_weight_max_follows_min(qapp):
    dialog = RandomGraphDialog()
    dialog.weight_min_spin.setValue(20)
    assert dialog.weight_max_spin.value() >= 20
