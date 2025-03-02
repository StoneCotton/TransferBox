#!/bin/bash
# Simple script to build TransferBox for macOS

# Ensure we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
  echo "This build script is for macOS only!"
  exit 1
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
  echo "Python 3 is required but not found!"
  exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
fi

# Run the Python build script
echo "Running build script..."
python3 build_macos.py

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
  deactivate
fi 