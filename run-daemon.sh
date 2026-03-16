#!/bin/bash
# Run the Voice Claude daemon (global hotkey mode)

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the daemon
python daemon.py "$@"
