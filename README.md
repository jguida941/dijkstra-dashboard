# Dijkstra Path Visualizer

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An interactive teaching tool for shortest-path algorithms. Build a weighted graph on the canvas, pick an
algorithm, and watch it run **step by step** — play, pause, step forward or back, and scrub the timeline to
any point. A live inspector shows the distance table, the algorithm's pseudocode with the current line
highlighted, and a plain-English narration of every visit, relaxation, and skip. Four algorithms
(Dijkstra, BFS, Bellman-Ford, A\*) and three themes (including a colorblind-safe light mode) make the same
graph easy to compare and easy to read.

## Screenshots

| Neon Dark | Midnight | Paper Light |
|-----------|----------|-------------|
| ![Dijkstra Path Visualizer running in the Neon Dark theme](img/theme-neon.png) | ![The visualizer in the Midnight theme](img/theme-midnight.png) | ![The visualizer in the colorblind-safe Paper Light theme](img/theme-paper.png) |

![The Algorithm Inspector mid-run: distance table, pseudocode with the current line highlighted, and step-by-step narration](img/inspector-midrun.png)

## Features

### Step / scrub playback
- **Transport controls** — Run, Step, Step Back, Play/Pause, and Reset.
- **Timeline scrubber** — drag to jump to any step; the whole view re-derives that frame exactly.
- **Adjustable speed** — a slider sets the autoplay interval.
- **Keyboard shortcuts** — Space to play/pause, Left/Right to step, Home/End to jump to the first/last step.

### Educational inspector
- **Distance table** that updates live as nodes are settled and edges relaxed.
- **Pseudocode panel** that highlights the exact line(s) responsible for the current step.
- **Narration log** describing each step in words (visit, relax, skip, target found / unreachable), plus a
  post-run summary (path, cost, visits, relaxations, skips, comparisons) and a cross-algorithm comparison
  when you re-run the same start/target with a different algorithm.
- **Color legend** for current / visited / final-path / not-in-path / unreachable states.

### Algorithm suite
- **Dijkstra** — least-total-weight shortest path over non-negative weights.
- **BFS** — fewest-*hops* path that ignores weights, so you can contrast "fewest edges" against Dijkstra's
  "least total weight" on the same graph.
- **Bellman-Ford** — handles negative edge weights and **detects negative cycles**, reporting when no
  shortest path exists.
- **A\*** — Dijkstra guided by a spatial (Euclidean) heuristic scaled to stay admissible (see below).

### Graph editing
- Add nodes, connect them with weighted edges, rename nodes, edit weights, drag to reposition, and delete —
  all directly on the canvas.
- **Undirected** or **directed** mode (directed uses selection order for arrow direction; add reverse edges
  for two-way paths with different weights).
- **Open / Save / Save As** graphs as JSON (node positions, labels, weights, and directed/undirected mode
  are preserved).

### Themes
- **Neon Dark**, **Midnight**, and **Paper Light** — switch live from the View → Theme menu; your choice is
  persisted between sessions.
- **Paper Light** uses the **Okabe-Ito** colorblind-safe palette.

## Installation

**Requirements:** Python >= 3.10. The only runtime dependency is **PyQt6** (`>= 6.4.0`).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # runtime + test tooling
```

For a runtime-only install, use `pip install -e .` or `pip install -r requirements.txt`.

## Running

```bash
python main.py
```

Equivalent entry points once installed:

```bash
dijkstra-ui                # console script (see pyproject.toml [project.scripts])
python -m dijkstra_dashboard
```

### Tests

```bash
pytest
```

## Controls

Editing gestures and keyboard shortcuts (the in-app **Help → Controls** dialog lists the same set):

| Action | Input |
|--------|-------|
| Add node | Shift + click empty canvas |
| Add / update edge | Ctrl / Option / Shift + click two nodes, then enter a weight |
| Rename node | Double-click a node |
| Edit edge weight | Double-click an edge or its weight chip |
| Move node | Drag the node |
| Remove node / edge | Select it and press Delete (or Backspace) |
| Pan the view | Right-click and drag |
| Zoom | Mouse wheel (anchored under the cursor), or the +/- / 100% overlay buttons |
| Zoom / fit menu | View → Zoom In / Zoom Out / Reset Zoom / Fit to Graph |
| Play / Pause | Space |
| Step forward / back | Right / Left arrow |
| Jump to first / last step | Home / End |

Transport shortcuts use a window-level binding with a focus guard: they are ignored while an editable widget
(a combo box, slider, or text field) holds keyboard focus, so typing a weight or picking an algorithm never
triggers playback.

## Algorithms

**Dijkstra** — Repeatedly settles the unvisited node with the smallest tentative distance, then relaxes its
outgoing edges. Requires non-negative weights (negative weights raise an error). With a target set, it stops
as soon as the target is settled.

**BFS (breadth-first search)** — Explores in FIFO order, counting *hops* rather than summing weights, so it
returns the path with the fewest edges. Running BFS and Dijkstra on the same weighted graph makes the
difference between "fewest edges" and "least total weight" concrete.

**Bellman-Ford** — Relaxes every edge over up to `|V| - 1` passes (undirected edges are relaxed in both
directions), stopping early once a pass makes no changes. A final detection pass checks whether any edge can
still be relaxed; if so, a **negative cycle** exists and the run reports that no shortest paths are defined —
the teaching point that Dijkstra cannot handle negative weights but Bellman-Ford can, up to a cycle.

**A\*** — Dijkstra ordered by `f = g + h`, where `h(n)` is the straight-line (Euclidean) distance from `n`
to the target scaled by a constant `c`. That constant is the minimum ratio of edge weight to edge length
across the graph, so every edge costs at least `c` times its Euclidean length. Because the straight-line
distance scaled by `c` is therefore never more than the true remaining cost, the heuristic is admissible
(and consistent), which guarantees A\* still returns an optimal path — it just settles fewer nodes by
steering toward the target. A\* requires a target.

## Architecture

- **Trace-first core.** Each algorithm's `iter_steps` yields a stream of typed step events
  (`visit` / `relax` / `skip` / `final`); a small runner folds that stream into distances, predecessors,
  reconstructed paths, and visit order (`runner.apply_steps` / `result_from_steps`).
- **Qt-free core, thin UI.** `core/` (graph model, the four algorithms, the runner, the narration
  formatters) imports no Qt and is fully unit-tested headlessly; `ui/` holds the PyQt6 widgets that render
  those results.
- **Refold scrubbing.** `PlaybackController` owns the trace and replay state. Seeking or stepping back
  re-folds `steps[:index]` from scratch, so every frame — forward, backward, or a timeline jump — is
  reconstructed deterministically, and the graph view stays a pure renderer of the emitted `RenderFrame`.
- **Theme engine.** A `ThemeManager` holds three immutable `Theme` dataclasses with per-state node/edge
  style maps; it generates the Qt palette and stylesheet from color tokens, emits `theme_changed`, and
  persists the selection via a small JSON config.
- **Pseudocode / step-line maps.** Every algorithm carries its own `pseudocode` lines and a `step_line_map`
  from `(step kind, reason)` to the pseudocode line numbers to highlight, which is what lets the inspector
  point at the code responsible for each step.
- **Teaching twin.** `lessons/shortest_path.py` is a compact, heavily commented Dijkstra that reads like the
  textbook version; the UI's Dijkstra pseudocode is derived from it.

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2025 Justin Guida.
