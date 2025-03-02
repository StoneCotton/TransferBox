#!/usr/bin/env python3
"""
Build script for creating a standalone macOS executable for TransferBox
using PyInstaller.
"""

import os
import re
import subprocess
import sys
import shutil
from pathlib import Path

# Ensure we're on macOS
if sys.platform != 'darwin':
    print("This build script is for macOS only!")
    sys.exit(1)

# Read version from src/__init__.py
with open(os.path.join('src', '__init__.py'), 'r') as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string in src/__init__.py")

print(f"Building TransferBox v{version} for macOS...")

# Make sure PyInstaller is installed
try:
    import PyInstaller
except ImportError:
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller==6.5.0'])

# Define paths
ROOT_DIR = Path(__file__).parent.absolute()
DIST_DIR = ROOT_DIR / 'dist'
BUILD_DIR = ROOT_DIR / 'build'
ASSETS_DIR = ROOT_DIR / 'assets'
SOUNDS_DIR = ROOT_DIR / 'sounds'

# Create the PyInstaller command
pyinstaller_args = [
    'pyinstaller',
    '--clean',
    '--onefile',
    '--name', f'TransferBox-{version}',
    '--add-data', f'{ASSETS_DIR}:assets',
    '--add-data', f'{SOUNDS_DIR}:sounds',
    '--hidden-import', 'matplotlib',
    '--hidden-import', 'pkg_resources.py2_warn',
    '--hidden-import', 'yaml',
    '--icon', f'{ASSETS_DIR}/adobe_proxy_logo.png',
    'main.py'
]

# Run PyInstaller
print(f"Running PyInstaller with args: {' '.join(pyinstaller_args)}")
subprocess.check_call(pyinstaller_args)

# Check if build was successful
executable_path = DIST_DIR / f'TransferBox-{version}'
if executable_path.exists():
    print(f"\nBuild successful! Executable created at: {executable_path}")
    # Make executable
    os.chmod(executable_path, 0o755)
    print(f"File permissions set to executable")
else:
    print("\nBuild failed! Executable not found.")
    sys.exit(1)

print("\nYou can now run the application with:")
print(f"./dist/TransferBox-{version}") 