from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class Edge:
    id: str
    start: str
    end: str
    weight: float


@dataclass(frozen=True)
class GraphIssue:
    code: str
    message: str
    severity: Severity
    path: str | None = None


@dataclass(frozen=True)
class GraphStats:
    node_count: int
    edge_count: int
    directed: bool
