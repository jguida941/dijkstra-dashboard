#!/usr/bin/env python3
"""One-command launcher for the Dijkstra Path Visualizer (macOS, Windows, Linux).

Run it with any Python 3.10+ interpreter:

    python launch.py            # macOS / Linux
    py launch.py                # Windows

On the first run it creates a project-local virtual environment in ``.venv`` and
installs the app into it. After that it starts instantly. The app is always run
from that dedicated environment, never from whatever ``python`` happens to be on
your PATH, so a broken or partial system PyQt6 install can't break startup.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def venv_python(venv: Path) -> Path:
    """Return the interpreter inside ``venv`` for the current OS."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def has_pyqt6(python: Path) -> bool:
    """True if PyQt6 can actually be imported by ``python``."""
    result = subprocess.run(
        [str(python), "-c", "import PyQt6.QtWidgets"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def main() -> int:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        sys.exit("Python 3.10 or newer is required (found %d.%d)." % (major, minor))

    py = venv_python(VENV)

    if not py.exists():
        print("First-time setup: creating a virtual environment in .venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)

    if not has_pyqt6(py):
        print("Installing dependencies (this happens only once) ...")
        subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-e", "."], cwd=ROOT, check=True)
        print("Setup complete.")

    print("Starting Dijkstra Path Visualizer ...")
    return subprocess.run([str(py), str(ROOT / "main.py")], cwd=ROOT).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit("Setup failed: %s" % exc)
    except KeyboardInterrupt:
        sys.exit(130)
