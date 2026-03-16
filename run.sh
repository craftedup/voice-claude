#!/bin/bash
# Run the Voice Claude interface

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the main script
python main.py "$@"
