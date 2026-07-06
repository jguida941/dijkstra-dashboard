"""Pure narration formatters — no Qt imports so the goldens stay headless.

Every string produced here is pinned by tests/core/test_narration.py. The role
key returned alongside each sentence is resolved to a colour by the panel at
write time (and re-resolved on theme switch), never baked in here.
"""

from __future__ import annotations

INF = float("inf")

# F16: canonical display names — used by main_window when populating the
# algorithm combo and everywhere a display name is shown; the goldens use them.
DISPLAY_NAMES = {
    "dijkstra": "Dijkstra",
    "bfs": "BFS",
    "bellman-ford": "Bellman-Ford",
    "astar": "A*",
}

# F13: skip/"visited" wording is algorithm-aware.
_SETTLED_WORD = {
    "dijkstra": "already settled.",
    "astar": "already settled.",
    "bellman-ford": "already settled.",
    "bfs": "already discovered.",
}


def _fmt(value) -> str:
    """Trim floats identically to graph_view.format_distance (duplicated to keep
    this module free of the graph_view parcel)."""
    if value is None:
        return "∞"
    if value == INF:
        return "∞"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _display(algorithm) -> str:
    return DISPLAY_NAMES.get(algorithm, str(algorithm))


def describe_step(step, label_of, algorithm):
    """Return (sentence, role_key) for a single algorithm step."""
    kind = step.get("kind")
    payload = step.get("payload") or {}

    if kind == "visit":
        node = step.get("node")
        if node is None:
            # Bellman-Ford pass marker — no current node.
            return (f"— pass {payload.get('pass')} —", "muted")
        suffix = ""
        if "f" in payload and "h" in payload:
            # A* teaching payload: show the priority the selection used.
            suffix = f", f={_fmt(payload['f'])}, h={_fmt(payload['h'])}"
        return (f"Visit {label_of(node)} (d={_fmt(step.get('new_distance'))}{suffix}).", "accent")

    if kind == "relax":
        edge = step.get("edge")
        node = step.get("node")
        if edge is None:
            # F2: edge-free source seed (Bellman-Ford dist[start] = 0).
            return (f"Initialize {label_of(node)}: distance ← {_fmt(step.get('new_distance'))}.", "accent")
        u, v = label_of(edge[0]), label_of(edge[1])
        new = _fmt(step.get("new_distance"))
        old = _fmt(step.get("old_distance"))
        return (f"Relax {u}→{v}: {new} < {old} → update, prev[{v}]={u}.", "success")

    if kind == "skip":
        edge = step.get("edge")
        u, v = label_of(edge[0]), label_of(edge[1])
        reason = payload.get("reason")
        if reason == "visited":
            word = _SETTLED_WORD.get(algorithm, "already settled.")
            return (f"Skip {u}→{v}: {word}", "muted")
        new = _fmt(step.get("new_distance"))
        old = _fmt(step.get("old_distance"))
        return (f"Skip {u}→{v}: {new} ≥ {old} → no improvement.", "muted")

    if kind == "final":
        if payload.get("negative_cycle"):
            return ("Negative cycle detected — no shortest paths exist.", "error")
        reason = payload.get("reason")
        node = step.get("node")
        if reason == "target_found":
            return (f"Target {label_of(node)} settled — shortest distance {_fmt(step.get('new_distance'))}.", "success")
        if reason == "unreachable":
            return (f"Target {label_of(node)} is unreachable from the source.", "error")
        return ("Search complete.", "muted")

    return ("", "muted")


def run_header(meta, label_of) -> str:
    """One-line run banner, e.g. 'Dijkstra: A → F · heuristic scale c=0.5'."""
    display = _display(meta.get("algorithm"))
    start = meta.get("start")
    target = meta.get("target")
    if target is None:
        header = f"{display}: {label_of(start)}"
    else:
        header = f"{display}: {label_of(start)} → {label_of(target)}"

    if "heuristic_scale" in meta:
        header += f" · heuristic scale c={meta['heuristic_scale']:g}"

    constraints = meta.get("constraints") or {}
    if constraints.get("ignores_weights"):
        header += " · ignores weights"

    return header


def describe_summary(summary, label_of):
    """Return the post-run narration lines as [(sentence, role_key), ...]."""
    lines = []
    path = summary.get("path") or ()
    if path:
        joined = " → ".join(label_of(node_id) for node_id in path)
        lines.append((f"Path: {joined} ({_cost_phrase(summary)})", "success"))
    else:
        lines.append(("No path found.", "error"))

    lines.append((
        f"Visits {summary.get('visits', 0)} · "
        f"Relaxations {summary.get('relaxations', 0)} · "
        f"Skips {summary.get('skips', 0)} · "
        f"Comparisons {summary.get('comparisons', 0)}",
        "text",
    ))

    error = summary.get("error")
    if error:
        lines.append((error, "error"))

    return lines


def _cost_phrase(summary) -> str:
    """'cost 6' for weighted algorithms, '2 hops' for BFS (its distances are hops)."""
    distance = summary.get("distance")
    value = "∞" if distance is None else _fmt(distance)
    if summary.get("algorithm") == "bfs":
        return f"{value} hop" if value == "1" else f"{value} hops"
    return f"cost {value}"


def comparison_line(a, b, label_of) -> str:
    """'Dijkstra: 5 visits, cost 6 | BFS: 5 visits, 2 hops'."""
    return (
        f"{_display(a.get('algorithm'))}: {a.get('visits')} visits, {_cost_phrase(a)} | "
        f"{_display(b.get('algorithm'))}: {b.get('visits')} visits, {_cost_phrase(b)}"
    )
