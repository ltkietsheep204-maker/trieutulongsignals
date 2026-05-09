#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -x "$SCRIPT_DIR/.venv/bin/python3" ]]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [[ -x "$SCRIPT_DIR/.venv-1/bin/python3" ]]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv-1/bin/python3"
elif [[ -x "$SCRIPT_DIR/.venv-1/bin/python" ]]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv-1/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/web_ui.py"
