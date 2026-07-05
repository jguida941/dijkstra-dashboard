"""Repo-hygiene guards — added RED-first by the read-only governance pilot (2026-07-05).

Each guard pins a candidate finding from the scout pilot so the defect cannot silently return:
  - F-BIN-1  no oversized tracked binary (a 68 MB img/demo.mp4 bloated every clone)
  - F-DEP-1  requirements.txt must reconcile with pyproject.toml (no over-declared/unused deps)
  - F-CI-1   a CI workflow must exist AND actually run the tests

These are target-shape contracts: they FAIL on the pre-fix tree and pass once the fix lands.
Guards #2/#3 hardened after a codex adversarial review (revise): the dep guard now reconciles the WHOLE
requirements list against pyproject (catches PyQt6-Charts, not just 3 hardcoded libs); the CI guard now
requires the workflow to invoke pytest (an empty/unrelated workflow no longer passes).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10 — tomllib is stdlib only from 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
MAX_TRACKED_BYTES = 5 * 1024 * 1024  # 5 MB
# PyQt6 runtime-support wheels: legitimately shipped (not directly imported) because PyQt6 itself is imported.
_PYQT_RUNTIME_SUPPORT = {"pyqt6-qt6", "pyqt6-sip"}


def _tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(ROOT), "ls-files"], text=True)
    return [line for line in out.splitlines() if line]


def _pkg_name(spec: str) -> str:
    """Normalize a requirement/dependency spec to a bare lowercase package name."""
    head = spec.split("#", 1)[0].strip()
    for sep in (">=", "==", "<=", "~=", "!=", "<", ">", "[", ";", " "):
        head = head.split(sep)[0]
    return head.strip().lower()


def _pyproject_runtime_deps() -> set[str]:
    p = ROOT / "pyproject.toml"
    if not p.exists():
        return set()
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    return {_pkg_name(d) for d in data.get("project", {}).get("dependencies", [])}


def test_no_oversized_tracked_binaries():
    """F-BIN-1: no tracked file may exceed 5 MB — large media belongs in LFS/releases/links, not git history."""
    big = []
    for rel in _tracked_files():
        try:
            size = (ROOT / rel).stat().st_size
        except OSError:
            continue
        if size > MAX_TRACKED_BYTES:
            big.append(f"{rel} ({size / 1048576:.1f} MB)")
    assert not big, "oversized tracked files (relocate to LFS/release/external link): " + ", ".join(big)


def test_requirements_reconciled_with_pyproject():
    """F-DEP-1: every runtime package in requirements.txt must be declared in pyproject.toml
    [project.dependencies] (the source of truth), plus the PyQt6 runtime-support wheels.
    Catches ANY over-declared/unused dep (numpy, matplotlib, networkx, PyQt6-Charts, …), not a hardcoded few.
    """
    req = ROOT / "requirements.txt"
    text = req.read_text(encoding="utf-8") if req.exists() else ""
    allowed = _pyproject_runtime_deps() | _PYQT_RUNTIME_SUPPORT
    extra = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = _pkg_name(stripped)
        if name and name not in allowed:
            extra.append(name)
    assert not extra, (
        "requirements.txt declares packages absent from pyproject.toml [project.dependencies] "
        f"(reconcile — pyproject is source of truth): {sorted(set(extra))}"
    )


def test_ci_workflow_runs_tests():
    """F-CI-1: a CI workflow must exist AND invoke the test runner (not just any yaml file)."""
    wf = ROOT / ".github" / "workflows"
    ymls = (list(wf.glob("*.yml")) + list(wf.glob("*.yaml"))) if wf.exists() else []
    assert ymls, "no CI workflow under .github/workflows/ — add one that runs pytest on push/PR"
    runs_tests = any("pytest" in y.read_text(encoding="utf-8", errors="ignore") for y in ymls)
    assert runs_tests, "a CI workflow exists but none invoke pytest — CI must actually run the tests"
