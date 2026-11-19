#!/usr/bin/env bash
#
# macOS: double-click this file in Finder.
# Delegate environment setup and app startup to the Python launcher.

set -euo pipefail

on_error() {
    local status=$?
    printf '\nThe app did not start cleanly. See the message above.\n' >&2
    if [ -t 0 ]; then
        read -r -p "Press Return to close this window. " _ || true
    fi
    exit "$status"
}
trap on_error ERR

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 launch.py
