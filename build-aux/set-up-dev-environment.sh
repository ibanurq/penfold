#!/bin/sh
# Create the project's virtual environment (.venv) with the development tools, and install the pre-commit hook.
# The system's PyGObject, Poppler and pikepdf stay visible inside it (--system-site-packages).
set -eu

cd "$(dirname "$0")/.."
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --requirement requirements-dev.txt
# Type descriptions of GTK 4 for mypy. --no-deps: PyGObject comes from the system, it must not be rebuilt.
PYGOBJECT_STUB_CONFIG=Gtk4,Gdk4 .venv/bin/pip install --quiet --no-deps --no-cache-dir pygobject-stubs==2.20.0
# Not on GitHub Actions (CI is set there), where the checks run as separate steps.
if [ -d .git ] && [ -z "${CI:-}" ]; then
    .venv/bin/pre-commit install
fi
