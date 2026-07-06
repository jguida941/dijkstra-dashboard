from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..core.algorithms import create_algorithm
from ..core.algorithms.base import AlgorithmResult, AlgorithmStep
from ..core.algorithms.runner import AlgorithmState, apply_step, apply_steps, init_state, result_from_steps
from ..core.errors import AlgorithmError


@dataclass(frozen=True)
class RenderFrame:
    index: int
    total: int
    step: dict | None
    distances: dict[str, float]
    visited: tuple[str, ...]
    current: str | None
    prev: dict[str, str]
    tree_edges: frozenset[tuple[str, str]]
    considered_edges: frozenset[tuple[str, str]]
    is_final: bool
    path: tuple[str, ...]
    forward_step: bool


class PlaybackController(QObject):
    run_loaded = pyqtSignal(object)
    frame_changed = pyqtSignal(object)
    playing_changed = pyqtSignal(bool)
    run_error = pyqtSignal(str)
    run_finished = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.setInterval(500)

        self._steps: list[AlgorithmStep] = []
        self._nodes: list[str] = []
        self._state: AlgorithmState | None = None
        self._result: AlgorithmResult | None = None
        self._fold_error: str | None = None
        self._algorithm_name: str | None = None
        self._start: str | None = None
        self._target: str | None = None
        self._directed = False
        self._index = 0
        self._finished_emitted = False

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    @property
    def is_loaded(self) -> bool:
        return self._state is not None

    @property
    def total(self) -> int:
        return len(self._steps)

    def load_run(self, graph, algorithm_name: str, params: dict) -> bool:
        self.pause()
        algorithm = create_algorithm(algorithm_name)

        try:
            steps = list(algorithm.iter_steps(graph, params))
        except AlgorithmError as exc:
            self.run_error.emit(str(exc))
            self.unload()
            return False

        start = params.get("start")
        target = params.get("target")
        nodes = graph.get_nodes()
        result = None
        fold_error = None
        try:
            result = result_from_steps(steps, nodes, start, target, algorithm.spec.output_kind)
        except AlgorithmError as exc:
            fold_error = str(exc)

        self._steps = steps
        self._nodes = list(nodes)
        self._state = init_state(self._nodes)
        self._result = result
        self._fold_error = fold_error
        self._algorithm_name = algorithm_name
        self._start = start
        self._target = target
        self._directed = graph.directed
        self._index = 0
        self._finished_emitted = False

        meta = {
            "algorithm": algorithm_name,
            "start": start,
            "target": target,
            "total": self.total,
            "directed": self._directed,
            "constraints": dict(algorithm.spec.constraints),
        }
        # Additive: surface the A* heuristic scale carried on the final step.
        if steps:
            last = steps[-1]
            if last.get("kind") == "final":
                payload = last.get("payload") or {}
                if "heuristic_scale" in payload:
                    meta["heuristic_scale"] = payload["heuristic_scale"]
        self.run_loaded.emit(meta)
        self.frame_changed.emit(self._make_frame(forward_step=False))
        return True

    def unload(self) -> None:
        was_playing = self._timer.isActive()
        self.pause()
        self._steps = []
        self._nodes = []
        self._state = None
        self._result = None
        self._fold_error = None
        self._algorithm_name = None
        self._start = None
        self._target = None
        self._directed = False
        self._index = 0
        self._finished_emitted = False
        if not was_playing:
            self.playing_changed.emit(False)

    def play(self) -> None:
        if not self.is_loaded or self._index >= self.total or self._timer.isActive():
            return
        self._timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.playing_changed.emit(False)

    def toggle(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def step_forward(self) -> None:
        if not self.is_loaded or self._index >= self.total or self._state is None:
            return

        apply_step(self._state, self._steps[self._index])
        self._index += 1
        self.frame_changed.emit(self._make_frame(forward_step=True))
        if self._index == self.total:
            self.pause()
            self._emit_finish()

    def step_back(self) -> None:
        self.seek(self._index - 1)

    def seek(self, k: int) -> None:
        if not self.is_loaded:
            return

        index = max(0, min(self.total, int(k)))
        if index == self._index:
            return

        self._state = apply_steps(self._steps[:index], self._nodes)
        self._index = index
        if self._index < self.total:
            self._finished_emitted = False

        self.frame_changed.emit(self._make_frame(forward_step=False))
        if self._index == self.total:
            self._emit_finish()

    def set_interval(self, ms: int) -> None:
        self._timer.setInterval(max(50, int(ms)))

    def _make_frame(self, forward_step: bool) -> RenderFrame:
        if self._state is None:
            raise RuntimeError("Cannot build a frame before a run is loaded.")

        tree_edges = frozenset((parent, node) for node, parent in self._state.prev.items())
        considered_edges = frozenset(self._state.touched_edges.difference(tree_edges))
        is_final = self._index == self.total
        path = tuple(self._result.path) if is_final and self._result is not None else ()
        step = self._steps[self._index - 1] if self._index > 0 else None

        return RenderFrame(
            index=self._index,
            total=self.total,
            step=step,
            distances=dict(self._state.distances),
            visited=tuple(self._state.visited),
            current=self._state.current,
            prev=dict(self._state.prev),
            tree_edges=tree_edges,
            considered_edges=considered_edges,
            is_final=is_final,
            path=path,
            forward_step=forward_step,
        )

    def _emit_finish(self) -> None:
        if self._finished_emitted or self._state is None:
            return

        self._finished_emitted = True
        relaxations = sum(1 for step in self._steps if step.get("kind") == "relax")
        skips = sum(1 for step in self._steps if step.get("kind") == "skip")
        summary = {
            "algorithm": self._algorithm_name,
            "start": self._start,
            "target": self._target,
            "path": tuple(self._result.path) if self._result is not None else (),
            "distance": self._result.distance if self._result is not None else None,
            "visited_order": tuple(self._state.visited),
            "visits": len(self._state.visited),
            "relaxations": relaxations,
            "skips": skips,
            "comparisons": relaxations + skips,
            "error": self._fold_error,
        }
        last = self._steps[-1] if self._steps else None
        if last is not None and last.get("kind") == "final":
            payload = last.get("payload") or {}
            if "converged_at_pass" in payload:
                summary["converged_at_pass"] = payload["converged_at_pass"]
        self.run_finished.emit(summary)
        if self._fold_error:
            self.run_error.emit(self._fold_error)

    def _on_timeout(self) -> None:
        self.step_forward()
