#!/usr/bin/env bash
#
# Dijkstra Path Visualizer — one-click launcher
# ---------------------------------------------
# macOS: double-click this file in Finder to start the app.
# Linux/other: run `bash launch.command`.
#
# On the first run (or on a fresh clone) it will create a local virtual
# environment and install dependencies automatically. After that it starts
# instantly.

set -euo pipefail

# Always operate from the folder this script lives in (the repo root),
# so it works no matter where it's double-clicked from.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Keep the Terminal window open if anything fails, so the error is readable.
on_error() {
  echo ""
  echo "❌ The app didn't start cleanly. See the message above."
  echo "   Press Return to close this window."
  read -r _
  exit 1
}
trap on_error ERR

echo "▶  Starting Dijkstra Path Visualizer…"

launch() {
  # "$1" is the python interpreter to use.
  "$1" main.py
}

# 1) Prefer a project-local virtual environment if one exists.
if [ -x ".venv/bin/python" ]; then
  launch ".venv/bin/python"
  exit 0
fi

# 2) Fast path: if the system python already has PyQt6, just use it.
if python3 -c "import PyQt6" >/dev/null 2>&1; then
  launch "python3"
  exit 0
fi

# 3) First-time setup: build a local venv and install dependencies.
echo "⏳ First-time setup — creating a virtual environment and installing"
echo "   dependencies. This happens only once and may take a minute…"
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip >/dev/null
./.venv/bin/python -m pip install -e .
echo "✅ Setup complete."
launch ".venv/bin/python"
