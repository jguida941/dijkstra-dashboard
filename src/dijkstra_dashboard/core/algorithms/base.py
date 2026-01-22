from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Literal, TypedDict

AlgorithmOutput = Literal["single_path", "all_pairs", "multi_path"]
StepMode = Literal["delta", "snapshot"]


class AlgorithmStep(TypedDict):
    kind: Literal["visit", "relax", "final", "skip"]
    node: str | None
    edge: tuple[str, str] | None
    old_distance: float | None
    new_distance: float | None
    payload: dict | None


@dataclass(frozen=True)
class AlgorithmParam:
    name: str
    type: str
    required: bool = False
    default: object | None = None
    choices: list[object] | None = None


@dataclass(frozen=True)
class AlgorithmSpec:
    name: str
    description: str
    inputs: list[AlgorithmParam]
    output_kind: AlgorithmOutput
    constraints: dict


@dataclass
class AlgorithmResult:
    kind: AlgorithmOutput
    path: list[str]
    distance: float | None
    distances: dict
    paths: dict
    visited_order: list[str]
    steps: list[AlgorithmStep] | None


class PathfindingAlgorithm(ABC):
    spec: AlgorithmSpec

    @abstractmethod
    def solve(self, graph, params: dict) -> AlgorithmResult:
        raise NotImplementedError

    def iter_steps(self, graph, params: dict, mode: StepMode = "delta") -> Iterable[AlgorithmStep]:
        raise NotImplementedError
