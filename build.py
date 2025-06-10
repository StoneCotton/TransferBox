#!/usr/bin/env python3
"""
Cross-platform build script for creating standalone executables for TransferBox
using PyInstaller. Supports macOS, Windows, and Linux.
Includes NextJS web UI frontend and defaults to web UI mode.

Usage:
  python3 build.py              # Build for current platform
  python3 build.py --clean      # Clean previous builds and then build
  python3 build.py --clean-build # Clean previous builds only (no build)
"""
import os
import re
import subprocess
import sys
import shutil
import platform
import json
from pathlib import Path

# Define paths
ROOT_DIR = Path(__file__).parent.absolute()
DIST_DIR = ROOT_DIR / 'dist'
BUILD_DIR = ROOT_DIR / 'build'
ASSETS_DIR = ROOT_DIR / 'assets'
SOUNDS_DIR = ROOT_DIR / 'sounds'
WEBUI_DIR = ROOT_DIR / 'webui'
WEBUI_BUILD_DIR = WEBUI_DIR / '.next'

def extract_metadata():
    """
    Extract all metadata from src/__init__.py.
    
    Returns a dictionary containing project metadata like version,
    author, license, etc. This ensures consistent branding across
    all platform builds.
    """
    init_path = os.path.join('src', '__init__.py')
    
    metadata = {
        'version': None,
        'author': None,
        'license': None,
        'description': None,
        'project_name': None,
        'copyright': None
    }
    
    # Read the file content
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Extract each piece of metadata using regex
    patterns = {
        'version': r"^__version__ = ['\"]([^'\"]*)['\"]",
        'author': r"^__author__ = ['\"]([^'\"]*)['\"]",
        'license': r"^__license__ = ['\"]([^'\"]*)['\"]",
        'description': r"^__description__ = ['\"]([^'\"]*)['\"]",
        'project_name': r"^__project_name__ = ['\"]([^'\"]*)['\"]",
        'copyright': r"^__copyright__ = ['\"]([^'\"]*)['\"]"
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.M)
        if match:
            metadata[key] = match.group(1)
    
    # Validate that we found the version at minimum
    if not metadata['version']:
        raise RuntimeError("Unable to find version string in src/__init__.py")
    
    # Use TransferBox as default project name if not found
    if not metadata['project_name']:
        metadata['project_name'] = "TransferBox"
    
    return metadata

def ensure_pyinstaller_installed():
    """
    Make sure PyInstaller is installed.
    Checks if PyInstaller is available, and installs it if not.
    """
    if shutil.which("pyinstaller") is None:
        print("Installing PyInstaller with uv...")
        subprocess.check_call(['uv', 'pip', 'install', 'pyinstaller==6.5.0'])
    else:
        subprocess.run(["pyinstaller", "--version"])

def check_nodejs_available():
    """
    Check if Node.js and npm are available.
    Returns True if both are available, False otherwise.
    """
    node_available = shutil.which("node") is not None
    npm_available = shutil.which("npm") is not None
    
    if not node_available:
        print("Error: Node.js is not installed or not in PATH")
        print("Please install Node.js from https://nodejs.org/")
        return False
    
    if not npm_available:
        print("Error: npm is not installed or not in PATH")
        return False
    
    # Check versions
    try:
        node_version = subprocess.check_output(["node", "--version"], text=True).strip()
        npm_version = subprocess.check_output(["npm", "--version"], text=True).strip()
        print(f"Node.js version: {node_version}")
        print(f"npm version: {npm_version}")
        return True
    except subprocess.CalledProcessError:
        print("Error: Failed to get Node.js/npm versions")
        return False

def build_nextjs_frontend():
    """
    Build the NextJS frontend for production.
    Returns True if successful, False otherwise.
    """
    print("Building NextJS frontend...")
    
    if not WEBUI_DIR.exists():
        print(f"Error: WebUI directory not found at {WEBUI_DIR}")
        return False
    
    if not (WEBUI_DIR / "package.json").exists():
        print(f"Error: package.json not found in {WEBUI_DIR}")
        return False
    
    try:
        # Install dependencies if node_modules doesn't exist
        if not (WEBUI_DIR / "node_modules").exists():
            print("Installing frontend dependencies...")
            subprocess.check_call(["npm", "install"], cwd=WEBUI_DIR)
        
        # Build the frontend
        print("Building production frontend...")
        subprocess.check_call(["npm", "run", "build"], cwd=WEBUI_DIR)
        
        # Verify build was successful
        if not WEBUI_BUILD_DIR.exists():
            print("Error: Frontend build failed - .next directory not found")
            return False
        
        print("Frontend build successful!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error building frontend: {e}")
        return False

def create_webui_launcher():
    """
    Create a launcher script that defaults to --webui mode.
    This replaces the main.py as the entry point to default to web UI.
    """
    launcher_content = '''#!/usr/bin/env python3
"""
TransferBox Launcher - Defaults to Web UI mode
"""
import sys
import os
from pathlib import Path

# Add the main application directory to the path
if getattr(sys, 'frozen', False):
    # Running from PyInstaller bundle
    app_dir = Path(sys.executable).parent
else:
    # Running from source
    app_dir = Path(__file__).parent

sys.path.insert(0, str(app_dir))

# Import and run the main application
try:
    from main import main, parse_arguments
    
    # Check if --webui is already in arguments
    if '--webui' not in sys.argv and '--benchmark' not in sys.argv:
        # Add --webui flag by default
        sys.argv.append('--webui')
        print("Starting TransferBox in Web UI mode...")
        print("To use terminal mode, run with: --webui=false or remove --webui")
    
    # Run the main application
    sys.exit(main())
    
except ImportError as e:
    print(f"Error importing main application: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error running application: {e}")
    sys.exit(1)
'''
    
    launcher_path = ROOT_DIR / "webui_launcher.py"
    with open(launcher_path, "w") as f:
        f.write(launcher_content)
    
    # Make executable on Unix systems
    if platform.system() != "Windows":
        os.chmod(launcher_path, 0o755)
    
    return launcher_path

def get_platform_icon():
    """
    Get the appropriate icon path for the current platform.
    
    First, this function checks for platform-specific optimized icons.
    If those aren't available, it falls back to the TransferBox_Icon.png.
    """
    system = platform.system()
    
    # Check for platform-specific icons first
    if system == "Darwin" and (ASSETS_DIR / "icon.icns").exists():
        return str(ASSETS_DIR / "icon.icns")
    elif system == "Windows" and (ASSETS_DIR / "icon.ico").exists():
        return str(ASSETS_DIR / "icon.ico")
    elif system == "Linux" and (ASSETS_DIR / "icon.png").exists():
        return str(ASSETS_DIR / "icon.png")
    
    # Fall back to the existing TransferBox icon
    return str(ASSETS_DIR / "TransferBox_Icon.png")

def create_macos_redirect_app():
    """
    Create a small Python script to wrap the actual application for better macOS compatibility.
    
    This creates a wrapper that helps handle the "open and immediately close" issue by
    redirecting stdout/stderr and properly handling the working directory.
    """
    wrapper_path = ROOT_DIR / "mac_app_wrapper.py"
    
    wrapper_content = """#!/usr/bin/env python3
import os
import sys
import subprocess
import traceback

# Set up logging to application directory for debugging
def setup_logging():
    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        # Running from bundle
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running from script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    log_dir = os.path.join(app_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "transferbox_app.log")
    return log_file

def main():
    # Capture exceptions and log them
    log_file = setup_logging()
    
    try:
        with open(log_file, "a") as log:
            log.write("\\n--- Application Starting ---\\n")
            
            # Get the directory where the main executable should be
            if getattr(sys, 'frozen', False):
                # Running from bundle
                app_dir = os.path.dirname(sys.executable)
                # The main executable has the same name but with -main suffix
                exec_name = os.path.basename(sys.executable).replace(".app", "")
                if not exec_name.endswith("-main"):
                    # If executable doesn't already end with -main, add it
                    if "-" in exec_name:
                        # For cases like TransferBox-1.2.0, make it TransferBox-main
                        parts = exec_name.split("-")
                        exec_name = parts[0] + "-main"
                    else:
                        exec_name = exec_name + "-main"
                
                main_exec = os.path.join(app_dir, exec_name)
            else:
                # In development mode
                app_dir = os.path.dirname(os.path.abspath(__file__))
                main_exec = os.path.join(app_dir, "main.py")
            
            # Log detailed information for debugging
            log.write(f"App directory: {app_dir}\\n")
            log.write(f"Main executable path: {main_exec}\\n")
            log.write(f"Checking if main executable exists: {os.path.exists(main_exec)}\\n")
            
            # List directory contents for debugging
            log.write("Directory contents:\\n")
            for item in os.listdir(app_dir):
                item_path = os.path.join(app_dir, item)
                if os.path.isfile(item_path):
                    log.write(f"  FILE: {item}\\n")
                elif os.path.isdir(item_path):
                    log.write(f"  DIR: {item}\\n")
            
            # Change working directory to the app directory
            os.chdir(app_dir)
            log.write(f"Changed working directory to: {app_dir}\\n")
            
            # Start the main application with stdout/stderr redirected to our log
            log.write(f"Launching main application: {main_exec}\\n")
            log.flush()
            
            if os.path.exists(main_exec):
                # Pass all command line arguments to the main executable
                cmd = [main_exec] + sys.argv[1:]
                
                # Run the real application
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=log,
                    universal_newlines=True
                )
                
                # Wait for the process to complete
                process.wait()
                log.write(f"Main application exited with code: {process.returncode}\\n")
            else:
                log.write(f"ERROR: Main executable not found at {main_exec}\\n")
                
                # Try finding any executable in the directory as a fallback
                execs = [f for f in os.listdir(app_dir) if os.access(os.path.join(app_dir, f), os.X_OK)]
                log.write(f"Available executables in directory: {execs}\\n")
    
    except Exception as e:
        # Catch any exceptions in the wrapper itself
        with open(log_file, "a") as log:
            log.write(f"WRAPPER ERROR: {str(e)}\\n")
            log.write(traceback.format_exc())
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
    
    with open(wrapper_path, "w") as f:
        f.write(wrapper_content)
    
    # Make executable
    os.chmod(wrapper_path, 0o755)
    
    return wrapper_path

# Top-level launcher script for macOS .app bundle
launcher_script = '''#!/usr/bin/env python3
# Terminal launcher for TransferBox.
# This script opens a Terminal window and launches the main application inside it.
import os
import sys
import subprocess

def main():
    # Get the path to the actual executable
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        main_exec = os.path.join(app_dir, '{main_exec_name}')
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        main_exec = os.path.join(app_dir, 'main.py')

    if not os.path.exists(main_exec):
        print("Error: Main executable not found at {{}}".format(main_exec))
        return 1

    # AppleScript to open Terminal and run the main executable
    applescript_cmd = 'tell application "Terminal" to do script "' + main_exec + '"'
    try:
        subprocess.run(['osascript', '-e', applescript_cmd], check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print("Error launching Terminal: {{}}".format(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''

def build_macos(metadata):
    """
    Build macOS application with Terminal support and Web UI.
    Always creates both the main console executable and a launcher .app bundle
    that opens Terminal to run the main executable. Sets the .app icon.
    """
    print(f"Building {metadata['project_name']} v{metadata['version']} for macOS with Web UI...")

    # Check Node.js availability
    if not check_nodejs_available():
        return False
    
    # Build the frontend
    if not build_nextjs_frontend():
        return False

    # Create the webui launcher
    launcher_path = create_webui_launcher()

    # Get the icon path
    icon_path = get_platform_icon()

    # Build the main executable (console app)
    main_exec_name = f"{metadata['project_name']}-main"
    print("Building main executable...")
    pyinstaller_args = [
        'pyinstaller',
        '--clean',
        '--onefile',
        '--name', main_exec_name,
        '--add-data', f'{ASSETS_DIR}:assets',
        '--add-data', f'{SOUNDS_DIR}:sounds',
        '--add-data', f'{WEBUI_DIR}/.next:webui/.next',
        '--add-data', f'{WEBUI_DIR}/public:webui/public',
        '--add-data', f'{WEBUI_DIR}/package.json:webui',
        '--hidden-import', 'matplotlib',
        '--hidden-import', 'pkg_resources.py2_warn',
        '--hidden-import', 'yaml',
        '--hidden-import', 'fastapi',
        '--hidden-import', 'uvicorn',
        '--hidden-import', 'websockets',
        '--icon', icon_path,
        str(launcher_path)
    ]
    print(f"Running PyInstaller with args: {' '.join(pyinstaller_args)}")
    subprocess.check_call(pyinstaller_args)

    # Create the launcher script (always)
    launcher_name = f"{metadata['project_name']}-{metadata['version']}"
    terminal_launcher_path = ROOT_DIR / "terminal_launcher.py"
    with open(terminal_launcher_path, "w") as f:
        f.write(launcher_script.format(main_exec_name=main_exec_name))
    os.chmod(terminal_launcher_path, 0o755)

    # Build the launcher .app bundle
    launcher_args = [
        'pyinstaller',
        '--clean',
        '--windowed',  # Create .app bundle
        '--name', launcher_name,
        '--add-binary', f'{DIST_DIR}/{main_exec_name}:.',
        '--osx-bundle-identifier', f'com.{metadata["author"].lower().replace(" ", "")}.{metadata["project_name"].lower()}',
        '--icon', icon_path,
        str(terminal_launcher_path)
    ]
    print(f"Running PyInstaller with args: {' '.join(launcher_args)}")
    subprocess.check_call(launcher_args)

    # Check if build was successful
    app_path = DIST_DIR / f"{launcher_name}.app"
    main_exec_in_app = app_path / "Contents" / "MacOS" / main_exec_name
    if app_path.exists() and (DIST_DIR / main_exec_name).exists():
        # Copy the main executable into the app bundle if it's not already there
        if not main_exec_in_app.exists():
            shutil.copy2(DIST_DIR / main_exec_name, app_path / "Contents" / "MacOS")
            os.chmod(app_path / "Contents" / "MacOS" / main_exec_name, 0o755)
            print(f"Copied main executable to app bundle")
        print(f"\nBuild successful! Application bundle created at: {app_path}")
        print("\nYou can now run the application by double-clicking it in Finder.")
        print("It will open a Terminal window and start the Web UI automatically.")
        print("The web interface will be available at: http://localhost:3000")
        return True
    else:
        print("\nBuild failed: Missing components")
        return False

def build_windows(metadata):
    """
    Build Windows executable with Web UI.
    
    Creates a single .exe file that includes all dependencies, assets, and the web UI.
    The --windowed flag prevents a console window from appearing when run.
    """
    print(f"Building {metadata['project_name']} v{metadata['version']} for Windows with Web UI...")
    
    # Check Node.js availability
    if not check_nodejs_available():
        return False
    
    # Build the frontend
    if not build_nextjs_frontend():
        return False

    # Create the webui launcher
    launcher_path = create_webui_launcher()
    
    # Get the icon path
    icon_path = get_platform_icon()
    
    # Create the PyInstaller command
    pyinstaller_args = [
        'pyinstaller',
        '--clean',
        '--onefile',
        '--windowed',  # No console window on Windows
        '--name', f"{metadata['project_name']}-{metadata['version']}",
        '--add-data', f'{ASSETS_DIR};assets',  # Note semicolon for Windows
        '--add-data', f'{SOUNDS_DIR};sounds',  # Note semicolon for Windows
        '--add-data', f'{WEBUI_DIR}/.next;webui/.next',
        '--add-data', f'{WEBUI_DIR}/public;webui/public',
        '--add-data', f'{WEBUI_DIR}/package.json;webui',
        '--hidden-import', 'matplotlib',
        '--hidden-import', 'pkg_resources.py2_warn',
        '--hidden-import', 'yaml',
        '--hidden-import', 'fastapi',
        '--hidden-import', 'uvicorn',
        '--hidden-import', 'websockets',
        '--icon', icon_path,
        str(launcher_path)
    ]
    
    # Run PyInstaller
    print(f"Running PyInstaller with args: {' '.join(pyinstaller_args)}")
    subprocess.check_call(pyinstaller_args)
    
    # Check if build was successful
    executable_path = DIST_DIR / f"{metadata['project_name']}-{metadata['version']}.exe"
    if executable_path.exists():
        print(f"\nBuild successful! Executable created at: {executable_path}")
        print("\nYou can now run the application by double-clicking the .exe file.")
        print("It will start the Web UI automatically.")
        print("The web interface will be available at: http://localhost:3000")
        return True
    
    print("\nBuild failed! Executable not found.")
    return False

def build_linux(metadata):
    """
    Build Linux executable with Web UI.
    
    Creates a single executable file that includes all dependencies, assets, and the web UI.
    On Linux, we don't use the --windowed flag as we want to allow terminal output.
    """
    print(f"Building {metadata['project_name']} v{metadata['version']} for Linux with Web UI...")
    
    # Check Node.js availability
    if not check_nodejs_available():
        return False
    
    # Build the frontend
    if not build_nextjs_frontend():
        return False

    # Create the webui launcher
    launcher_path = create_webui_launcher()
    
    # Get the icon path
    icon_path = get_platform_icon()
    
    # Create the PyInstaller command
    pyinstaller_args = [
        'pyinstaller',
        '--clean',
        '--onefile',
        '--name', f"{metadata['project_name']}-{metadata['version']}",
        '--add-data', f'{ASSETS_DIR}:assets',
        '--add-data', f'{SOUNDS_DIR}:sounds',
        '--add-data', f'{WEBUI_DIR}/.next:webui/.next',
        '--add-data', f'{WEBUI_DIR}/public:webui/public',
        '--add-data', f'{WEBUI_DIR}/package.json:webui',
        '--hidden-import', 'matplotlib',
        '--hidden-import', 'pkg_resources.py2_warn',
        '--hidden-import', 'yaml',
        '--hidden-import', 'fastapi',
        '--hidden-import', 'uvicorn',
        '--hidden-import', 'websockets',
        '--icon', icon_path,
        str(launcher_path)
    ]
    
    # Run PyInstaller
    print(f"Running PyInstaller with args: {' '.join(pyinstaller_args)}")
    subprocess.check_call(pyinstaller_args)
    
    # Check if build was successful
    executable_path = DIST_DIR / f"{metadata['project_name']}-{metadata['version']}"
    if executable_path.exists():
        print(f"\nBuild successful! Executable created at: {executable_path}")
        # Make executable
        os.chmod(executable_path, 0o755)
        print(f"File permissions set to executable")
        print("\nYou can now run the application with:")
        print(f"./dist/{metadata['project_name']}-{metadata['version']}")
        print("It will start the Web UI automatically.")
        print("The web interface will be available at: http://localhost:3000")
        return True
    
    print("\nBuild failed! Executable not found.")
    return False

def clean_build_directories():
    """
    Clean up build and dist directories, including NextJS build artifacts.
    
    Removes previous build artifacts to ensure a clean build.
    This prevents potential conflicts with previous builds.
    """
    directories_to_clean = [DIST_DIR, BUILD_DIR]
    
    # Add NextJS build directories
    if WEBUI_BUILD_DIR.exists():
        directories_to_clean.append(WEBUI_BUILD_DIR)
    
    webui_out_dir = WEBUI_DIR / 'out'
    if webui_out_dir.exists():
        directories_to_clean.append(webui_out_dir)
    
    # Clean temporary launcher files
    temp_files = [
        ROOT_DIR / "webui_launcher.py",
        ROOT_DIR / "terminal_launcher.py",
        ROOT_DIR / "mac_app_wrapper.py"
    ]
    
    for directory in directories_to_clean:
        if directory.exists():
            print(f"Cleaning {directory}...")
            shutil.rmtree(directory)
    
    for temp_file in temp_files:
        if temp_file.exists():
            print(f"Removing {temp_file}...")
            temp_file.unlink()

def main():
    """
    Main entry point for the build script.
    
    Handles command line arguments, detects the platform,
    and calls the appropriate build function.
    """
    print("TransferBox Build Script with Web UI Support")
    print("=" * 50)
    
    # Check for clean-build flag (clean only, no build)
    if "--clean-build" in sys.argv:
        clean_build_directories()
        print("Clean completed.")
        return 0
    
    # Check for clean flag (clean and then build)
    clean_before_build = "--clean" in sys.argv
    if clean_before_build:
        print("Cleaning previous builds before building...")
        clean_build_directories()
        print("Clean completed. Starting build...")
    
    # Extract metadata from __init__.py
    try:
        metadata = extract_metadata()
        print(f"Building {metadata['project_name']} v{metadata['version']} by {metadata['author']}")
        print(f"Description: {metadata['description']}")
        print()
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    
    # Make sure PyInstaller is installed
    print("Checking build dependencies...")
    ensure_pyinstaller_installed()
    
    # Determine the platform and build accordingly
    system = platform.system()
    print(f"Building for platform: {system}")
    print()
    
    success = False
    
    if system == "Darwin":
        success = build_macos(metadata)
    elif system == "Windows":
        success = build_windows(metadata)
    elif system == "Linux":
        success = build_linux(metadata)
    else:
        print(f"Unsupported platform: {system}")
        return 1
    
    if success:
        print("\n" + "=" * 50)
        print("BUILD COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("\nYour TransferBox application with Web UI is ready!")
        print("The application will automatically start in Web UI mode.")
        print("\nFor advanced users:")
        print("- To use terminal mode: run the executable with appropriate flags")
        print("- To run benchmarks: use the --benchmark flag")
        print("- To clean previous builds: use --clean-build")
        print("- To clean and rebuild: use --clean")
        print("\nEnjoy using TransferBox!")
    else:
        print("\n" + "=" * 50)
        print("BUILD FAILED!")
        print("=" * 50)
        print("Please check the error messages above and try again.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())