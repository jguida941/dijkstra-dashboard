"""Pure-Python goldens for the narration formatter (no Qt, no ui marker)."""

from dijkstra_dashboard.ui.narration import (
    DISPLAY_NAMES,
    comparison_line,
    describe_step,
    describe_summary,
    run_header,
)

INF = float("inf")


def _identity(node_id):
    return node_id


# --------------------------------------------------------------------------
# describe_step goldens
# --------------------------------------------------------------------------
def test_visit_normal_golden():
    step = {"kind": "visit", "node": "C", "edge": None,
            "old_distance": None, "new_distance": 3, "payload": None}
    assert describe_step(step, _identity, "dijkstra") == ("Visit C (d=3).", "accent")


def test_visit_pass_marker_golden():
    step = {"kind": "visit", "node": None, "edge": None,
            "old_distance": None, "new_distance": None, "payload": {"pass": 2}}
    assert describe_step(step, _identity, "bellman-ford") == ("— pass 2 —", "muted")


def test_relax_normal_golden():
    step = {"kind": "relax", "node": "D", "edge": ("C", "D"),
            "old_distance": INF, "new_distance": 4, "payload": None}
    assert describe_step(step, _identity, "dijkstra") == (
        "Relax C→D: 4 < ∞ → update, prev[D]=C.",
        "success",
    )


def test_relax_edge_free_seed_golden():
    # F2 (CRITICAL): Bellman-Ford seeds the source with an edge=None relax.
    step = {"kind": "relax", "node": "A", "edge": None,
            "old_distance": INF, "new_distance": 0.0, "payload": None}
    assert describe_step(step, _identity, "bellman-ford") == (
        "Initialize A: distance ← 0.",
        "accent",
    )


def test_skip_visited_settled_golden():
    step = {"kind": "skip", "node": "A", "edge": ("B", "A"),
            "old_distance": 0, "new_distance": 7, "payload": {"reason": "visited"}}
    assert describe_step(step, _identity, "dijkstra") == (
        "Skip B→A: already settled.",
        "muted",
    )


def test_skip_visited_bfs_discovered_golden():
    # F13: BFS wording differs from the settle-based algorithms.
    step = {"kind": "skip", "node": "A", "edge": ("B", "A"),
            "old_distance": 0, "new_distance": 2, "payload": {"reason": "visited"}}
    assert describe_step(step, _identity, "bfs") == (
        "Skip B→A: already discovered.",
        "muted",
    )


def test_skip_worse_golden():
    step = {"kind": "skip", "node": "E", "edge": ("D", "E"),
            "old_distance": 13, "new_distance": 13, "payload": {"reason": "worse"}}
    assert describe_step(step, _identity, "dijkstra") == (
        "Skip D→E: 13 ≥ 13 → no improvement.",
        "muted",
    )


def test_final_target_found_golden():
    step = {"kind": "final", "node": "F", "edge": None,
            "old_distance": None, "new_distance": 6, "payload": {"reason": "target_found"}}
    assert describe_step(step, _identity, "dijkstra") == (
        "Target F settled — shortest distance 6.",
        "success",
    )


def test_final_unreachable_golden():
    step = {"kind": "final", "node": "X", "edge": None,
            "old_distance": None, "new_distance": INF, "payload": {"reason": "unreachable"}}
    assert describe_step(step, _identity, "dijkstra") == (
        "Target X is unreachable from the source.",
        "error",
    )


def test_final_negative_cycle_golden():
    step = {"kind": "final", "node": None, "edge": None,
            "old_distance": None, "new_distance": None, "payload": {"negative_cycle": True}}
    assert describe_step(step, _identity, "bellman-ford") == (
        "Negative cycle detected — no shortest paths exist.",
        "error",
    )


# --------------------------------------------------------------------------
# run_header goldens
# --------------------------------------------------------------------------
def test_run_header_plain():
    meta = {"algorithm": "dijkstra", "start": "A", "target": "F",
            "constraints": {"non_negative": True}}
    assert run_header(meta, _identity) == "Dijkstra: A → F"


def test_run_header_with_heuristic_scale():
    meta = {"algorithm": "astar", "start": "A", "target": "F",
            "constraints": {"non_negative": True, "requires_target": True},
            "heuristic_scale": 0.5}
    assert run_header(meta, _identity) == "A*: A → F · heuristic scale c=0.5"


def test_run_header_ignores_weights():
    meta = {"algorithm": "bfs", "start": "A", "target": "F",
            "constraints": {"ignores_weights": True}}
    assert run_header(meta, _identity) == "BFS: A → F · ignores weights"


# --------------------------------------------------------------------------
# describe_summary goldens
# --------------------------------------------------------------------------
def test_describe_summary_with_path():
    summary = {"algorithm": "dijkstra", "path": ("A", "C", "B", "F"), "distance": 6,
               "visits": 5, "relaxations": 7, "skips": 6, "comparisons": 13, "error": None}
    assert describe_summary(summary, _identity) == [
        ("Path: A → C → B → F (cost 6)", "success"),
        ("Visits 5 · Relaxations 7 · Skips 6 · Comparisons 13", "text"),
    ]


def test_describe_summary_no_path():
    summary = {"algorithm": "dijkstra", "path": (), "distance": None,
               "visits": 3, "relaxations": 0, "skips": 2, "comparisons": 2, "error": None}
    assert describe_summary(summary, _identity) == [
        ("No path found.", "error"),
        ("Visits 3 · Relaxations 0 · Skips 2 · Comparisons 2", "text"),
    ]


def test_comparison_line_bellman_ford_uses_passes():
    a = {"algorithm": "dijkstra", "visits": 3, "distance": 4}
    b = {"algorithm": "bellman-ford", "visits": 0, "passes": 2, "distance": 4}
    assert comparison_line(a, b, _identity) == (
        "Dijkstra: 3 visits, cost 4 | Bellman-Ford: 2 passes, cost 4"
    )


def test_describe_summary_bf_counts_use_passes():
    summary = {"algorithm": "bellman-ford", "path": ("A", "B"), "distance": 4,
               "visits": 0, "passes": 2, "relaxations": 6, "skips": 1,
               "comparisons": 7, "error": None}
    lines = describe_summary(summary, _identity)
    assert ("Passes 2 · Relaxations 6 · Skips 1 · Comparisons 7", "text") in lines


def test_describe_summary_notes_bf_early_convergence():
    summary = {"algorithm": "bellman-ford", "path": ("A", "B"), "distance": 4,
               "visits": 0, "relaxations": 2, "skips": 5, "comparisons": 7,
               "converged_at_pass": 2, "error": None}
    lines = describe_summary(summary, _identity)
    assert ("Converged after pass 2 — later passes skipped.", "muted") in lines


def test_describe_summary_appends_error_line():
    summary = {"algorithm": "bellman-ford", "path": (), "distance": None,
               "visits": 2, "relaxations": 1, "skips": 0, "comparisons": 1,
               "error": "Negative cycle detected."}
    lines = describe_summary(summary, _identity)
    assert lines[-1] == ("Negative cycle detected.", "error")


# --------------------------------------------------------------------------
# comparison_line golden
# --------------------------------------------------------------------------
def test_comparison_line_golden():
    a = {"algorithm": "dijkstra", "visits": 5, "distance": 6}
    b = {"algorithm": "bfs", "visits": 5, "distance": 2}
    assert comparison_line(a, b, _identity) == (
        "Dijkstra: 5 visits, cost 6 | BFS: 5 visits, 2 hops"
    )


def test_describe_summary_bfs_uses_hops():
    summary = {"algorithm": "bfs", "path": ("A", "B", "F"), "distance": 2,
               "visits": 5, "relaxations": 5, "skips": 8, "comparisons": 13, "error": None}
    assert describe_summary(summary, _identity)[0] == ("Path: A → B → F (2 hops)", "success")


def test_describe_step_astar_visit_shows_f_and_h():
    step = {"kind": "visit", "node": "C", "edge": None, "old_distance": None,
            "new_distance": 3.0, "payload": {"h": 1.25, "f": 4.25}}
    assert describe_step(step, _identity, "astar") == (
        "Visit C (d=3, f=4.25, h=1.25).", "accent"
    )


def test_display_names_map():
    assert DISPLAY_NAMES == {
        "dijkstra": "Dijkstra",
        "bfs": "BFS",
        "bellman-ford": "Bellman-Ford",
        "astar": "A*",
    }
