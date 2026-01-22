from .types import GraphIssue


class GraphError(Exception):
    """Base error for graph-related failures."""


class ValidationError(GraphError):
    def __init__(self, issues: list[GraphIssue]):
        super().__init__("Graph validation failed.")
        self.issues = issues


class AlgorithmError(GraphError):
    """Raised when an algorithm cannot run or fails."""
