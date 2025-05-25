#!/usr/bin/env python3
# Terminal launcher for TransferBox.
# This script opens a Terminal window and launches the main application inside it.
import os
import sys
import subprocess

def main():
    # Get the path to the actual executable
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        main_exec = os.path.join(app_dir, 'TransferBox-main')
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        main_exec = os.path.join(app_dir, 'main.py')

    if not os.path.exists(main_exec):
        print("Error: Main executable not found at {}".format(main_exec))
        return 1

    # AppleScript to open Terminal and run the main executable
    applescript_cmd = 'tell application "Terminal" to do script "' + main_exec + '"'
    try:
        subprocess.run(['osascript', '-e', applescript_cmd], check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print("Error launching Terminal: {}".format(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
