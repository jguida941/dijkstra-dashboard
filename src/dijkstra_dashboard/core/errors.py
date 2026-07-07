from .types import GraphIssue


class GraphError(Exception):
    """Base error for graph-related failures."""


class ValidationError(GraphError):
    #: Cap the per-issue lines folded into the message so a hundred bad edges
    #: can't produce a wall-of-text dialog.
    _MAX_LISTED = 6

    def __init__(self, issues: list[GraphIssue]):
        super().__init__(self._format(issues))
        self.issues = issues

    @staticmethod
    def _format(issues: list[GraphIssue]) -> str:
        header = "Graph validation failed."
        if not issues:
            return header
        lines = []
        for issue in issues[: ValidationError._MAX_LISTED]:
            where = f" ({issue.path})" if issue.path else ""
            lines.append(f"  • {issue.message}{where}")
        remaining = len(issues) - ValidationError._MAX_LISTED
        if remaining > 0:
            lines.append(f"  • …and {remaining} more issue(s).")
        return header + "\n" + "\n".join(lines)


class AlgorithmError(GraphError):
    """Raised when an algorithm cannot run or fails."""
