# main.py

import os
import logging
import signal
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Event
from src import __version__, __project_name__, __author__
from src.core.config_manager import ConfigManager
from src.core.platform_manager import PlatformManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage_inter import StorageInterface
from src.core.state_manager import StateManager
from src.core.file_transfer import FileTransfer
from src.core.logger_setup import setup_logging
from src.core.sound_manager import SoundManager
from src.core.utils import validate_path, get_platform
from src.core.path_utils import sanitize_path, is_plausible_user_path
from src.core.exceptions import HardwareError, StorageError, StateError, FileTransferError
from src.core.context_managers import operation_context
import argparse
import tempfile
import platform
import shutil

# Initialize configuration first
config_manager = ConfigManager()
config = config_manager.load_config()

# Now initialize logging with config settings
logger = setup_logging(
    log_level=getattr(logging, config.log_level),  # Convert string level to logging constant
    log_format='%(message)s',
    log_file_rotation=config.log_file_rotation,
    log_file_max_size=config.log_file_max_size
)

class TransferOperation:
    """Handles the core transfer logic for both desktop and embedded modes"""
    
    def __init__(self, display, storage, file_transfer, sound_manager):
        self.display = display
        self.storage = storage
        self.file_transfer = file_transfer
        self.sound_manager = sound_manager
        self.source_removed_error_shown = False
        
    def execute_transfer(self, source_drive, destination_path):
        """Execute the transfer operation with proper error handling"""
        error_occurred = False
        
        # Prepare for transfer
        self.display.show_status(f"Preparing transfer...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = destination_path / f"transfer_log_{timestamp}.log"
        
        try:
            success = self.file_transfer.copy_sd_to_dump(
                source_drive,
                destination_path,
                log_file
            )
            
            if success:
                error_occurred = self._handle_successful_transfer(source_drive)
            else:
                error_occurred = self._handle_failed_transfer(source_drive)
                
        except Exception as e:
            error_occurred = self._handle_transfer_error(e, source_drive)
            
        return error_occurred
    
    def _handle_successful_transfer(self, source_drive):
        """Handle successful transfer completion"""
        self.display.show_status("Transfer complete")
        logger.info(f"Unmounting source drive: {source_drive}")
        if self.storage.unmount_drive(source_drive):
            self.display.show_status("Safe to remove card")
            return False
        else:
            self.display.show_error("Unmount failed")
            return True
    
    def _handle_failed_transfer(self, source_drive):
        """Handle failed transfer"""
        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
            if not self.source_removed_error_shown:
                self.display.show_error("Source removed")
                self.source_removed_error_shown = True
            if self.sound_manager:
                self.sound_manager.play_error()
            return True
            
        if self.file_transfer.no_files_found:
            return False
            
        self.display.show_error("Transfer failed")
        logger.info(f"Attempting to unmount source drive after failed transfer: {source_drive}")
        try:
            if self.storage.unmount_drive(source_drive):
                self.display.show_status("Safe to remove card")
        except Exception as unmount_err:
            logger.warning(f"Failed to unmount drive after failed transfer: {unmount_err}")
        return True
    
    def _handle_transfer_error(self, error, source_drive):
        """Handle transfer error"""
        logger.error(f"Error during transfer: {error}", exc_info=True)
        
        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
            if not self.source_removed_error_shown:
                self.display.show_error("Source removed")
                self.source_removed_error_shown = True
            if self.sound_manager:
                self.sound_manager.play_error()
        else:
            self.display.show_error("Transfer error")
        return True

class BaseTransferBox:
    """Base class for TransferBox functionality"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Log application metadata
        logger.info(f"Starting {__project_name__} v{__version__} by {__author__}")
        
        # Initialize components
        self.sound_manager = SoundManager(self.config)
        self.stop_event = Event()
        self.platform = get_platform()
        logger.info(f"Initializing TransferBox on {self.platform} platform")
        
        # Create components with unified initialization
        self.display = PlatformManager.create_display()
        self.storage = PlatformManager.create_storage()
        self.state_manager = StateManager(self.display)
        
        # Initialize file transfer
        self.file_transfer = FileTransfer(
            config_manager=self.config_manager,
            display=self.display,
            storage=self.storage,
            state_manager=self.state_manager,
            sound_manager=self.sound_manager,
            stop_event=self.stop_event
        )
        
        # Initialize transfer operation handler
        self.transfer_op = TransferOperation(
            self.display,
            self.storage,
            self.file_transfer,
            self.sound_manager
        )
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        with operation_context(self.display, self.sound_manager, "Shutdown", 
                             on_error=lambda e: logger.critical(f"Critical error during shutdown: {e}")):
            signal_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM"
            }
            signal_name = signal_names.get(signum, f"Signal {signum}")
            logger.info(f"Shutdown signal received: {signal_name}")
            
            self.stop_event.set()
            self.cleanup()
            
            logger.info("Exiting program")
            sys.exit(0)

    def setup(self):
        """Perform initial setup"""
        with operation_context(self.display, self.sound_manager, "Setup"):
            self.display.clear()
            self.display.show_status("TransferBox Ready")

    def cleanup(self):
        """Cleanup resources"""
        with operation_context(self.display, None, "Cleanup", keep_error_display=True):
            logger.info("Cleaning up resources")
            try:
                self.sound_manager.cleanup()
            except Exception as e:
                logger.error(f"Sound manager cleanup error: {e}")

    def run(self):
        """Main application loop"""
        try:
            setup_success = self.setup()
            if not setup_success:
                logger.error("Setup failed. Exiting.")
                return
            self._run_impl()
        except Exception as e:
            logger.error(f"Critical runtime error: {e}", exc_info=True)
            self.display.show_error(f"Critical Error")
        finally:
            self.cleanup()
    
    def _run_impl(self):
        """Implementation specific run method to be overridden"""
        raise NotImplementedError

class DesktopTransferBox(BaseTransferBox):
    """Desktop-specific TransferBox implementation"""
    
    def _run_impl(self):
        """Desktop-specific run implementation"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Desktop Mode", keep_error_display=True):
                # Get and validate destination path
                destination_path = self._get_destination_path()
                if not destination_path:
                    continue
                
                # Show the destination path to the user
                self.display.show_status(f"[bold yellow]Destination set to: {destination_path}[/bold yellow]")
                
                # Wait for source drive
                source_drive = self._wait_for_source_drive()
                if not source_drive:
                    continue
                
                # Execute transfer
                error_occurred = self.transfer_op.execute_transfer(source_drive, destination_path)
                
                # Wait for drive removal and handle errors
                self._handle_completion(source_drive, error_occurred)
    
    def _get_destination_path(self):
        """Get and validate destination path from user, with robust input validation."""
        from src.core.path_utils import is_plausible_user_path
        import platform as plt
        system = plt.system().lower()
        if system == 'darwin':
            example_path = '/Volumes/BM-PRODUCTION/01_Burden Media/#2025 Content/05_FPV Shoot'
        elif system == 'windows':
            example_path = r'K:\BM-PRODUCTION\01_Burden Media\2025 Content\05_FPV Shoot'
        elif system == 'linux':
            example_path = '/home/yourname/Media'
        else:
            example_path = '/absolute/path/to/destination'
        def get_valid_input(prompt, valid, max_attempts=3):
            attempts = 0
            while attempts < max_attempts:
                self.display.show_status(prompt)
                resp = input().strip().lower()
                if resp in valid:
                    return resp
                self.display.show_error("Invalid input. Please choose a correct option.")
                attempts += 1
            self.display.show_error("Too many invalid attempts.")
            return 'exit'
        if getattr(self.config, 'tutorial_mode', False):
            if not hasattr(self, '_tutorial_shown'):
                self._tutorial_shown = False
            if not self._tutorial_shown:
                self._run_tutorial_flow()
                self._tutorial_shown = True
        max_attempts = 3
        attempts = 0
        while True:
            if attempts >= max_attempts:
                # Hybrid: ask user if they want to retry tutorial or exit
                prompt = "Too many invalid attempts. Would you like to retry the tutorial or exit? (retry/exit)"
                resp = get_valid_input(prompt, {'retry', 'exit'}, max_attempts=1)
                if resp == 'retry':
                    self._run_tutorial_flow()
                    attempts = 0
                    continue
                else:
                    self.display.show_error("Exiting destination entry.")
                    return None
            self.display.show_status(f"Enter destination path (e.g., {example_path}):")
            raw_destination = input().strip()
            plausible, plausible_error = is_plausible_user_path(raw_destination)
            if not plausible:
                self.display.show_error(f"{plausible_error} Example: {example_path}")
                attempts += 1
                continue
            try:
                sanitized_destination = sanitize_path(raw_destination)
            except Exception as e:
                logger.error(f"Error sanitizing path: {e}")
                self.display.show_error(f"Invalid path format. Example: {example_path}")
                attempts += 1
                continue
            is_valid, error_msg = validate_path(
                sanitized_destination, 
                must_exist=False, 
                must_be_writable=True
            )
            if not is_valid:
                self.display.show_error(f"{error_msg} Example: {example_path}")
                attempts += 1
                continue
            return sanitized_destination
    
    def _run_tutorial_flow(self):
        """Interactive tutorial for first-time users in desktop mode."""
        platform = get_platform()
        console = None
        try:
            from rich.console import Console
            console = Console()
        except ImportError:
            pass
        def print_msg(msg):
            if console:
                console.print(msg)
            else:
                print(msg)
        def get_valid_input(prompt, valid, max_attempts=3):
            attempts = 0
            while attempts < max_attempts:
                print_msg(prompt)
                resp = input().strip().lower()
                if resp in valid:
                    return resp
                print_msg("[red]Invalid input. Please choose a correct option.[/red]")
                attempts += 1
            print_msg("[yellow]Too many invalid attempts. Skipping this step.[/yellow]")
            return 'skip'
        # Step 1
        step1_prompt = "[bold cyan]Make sure that your SD card is not plugged into the system. If it is, safely eject the card.[/bold cyan]\nPress Enter to continue or type 'skip' to skip tutorial..."
        resp = get_valid_input(step1_prompt, {'', 'skip'})
        if resp == 'skip':
            return
        # Step 2/2a loop
        while True:
            step2_prompt = "[bold cyan]Have you located the directory that the media will be transferred to?[/bold cyan]\n([green]YES[/green] / [red]NO[/red] / SKIP)"
            resp = get_valid_input(step2_prompt, {'y', 'yes', 'n', 'no', 'skip'})
            if resp == 'skip':
                return
            if resp in {'y', 'yes'}:
                break
            # Step 2a
            if platform == 'darwin':
                print_msg("[yellow]Go to Finder, and find the destination that you want to transfer your media. Once found, right click on the destination and press 'Option' to then 'Copy as Pathname'.[/yellow]")
            elif platform == 'windows':
                print_msg("[yellow]Go to Explorer, and find the destination that you want to transfer your media. Once found, highlight and copy the destination path from the navigation pane.[/yellow]")
            else:
                print_msg("[yellow]Locate your destination directory using your file manager and copy its path.[/yellow]")
        print_msg("[bold green]Great! Proceeding to destination path entry...[/bold green]")
    
    def _wait_for_source_drive(self):
        """Wait for source drive insertion"""
        self.display.show_status("Waiting for source drive...")
        initial_drives = self.storage.get_available_drives()
        source_drive = self.storage.wait_for_new_drive(initial_drives)
        
        if not source_drive or self.stop_event.is_set():
            return None
        
        return source_drive
    
    def _handle_completion(self, source_drive, error_occurred):
        """Handle transfer completion and cleanup"""
        if source_drive.exists() and os.path.ismount(str(source_drive)):
            self.storage.wait_for_drive_removal(source_drive)
        else:
            time.sleep(2)
        
        if error_occurred:
            print("\nTransfer failed. Press Enter to continue...")
            input()
            if self.display:
                self.display.clear(preserve_errors=False)

class EmbeddedTransferBox(BaseTransferBox):
    """Embedded (Raspberry Pi) specific TransferBox implementation"""
    
    def setup(self):
        """Embedded-specific setup"""
        super().setup()
        self._setup_raspberry_pi()
    
    def _setup_raspberry_pi(self):
        """Setup specific to Raspberry Pi platform"""
        with operation_context(self.display, self.sound_manager, "Raspberry Pi Setup"):
            try:
                from src.platform.raspberry_pi.initializer_pi import RaspberryPiInitializer
                self.pi_initializer = RaspberryPiInitializer()
            except ImportError as import_err:
                logger.error(f"Failed to import RaspberryPiInitializer: {import_err}")
                self.display.show_error("Import Error")
                raise

            self.pi_initializer.initialize_hardware()
            self.pi_initializer.initialize_display()
            self.pi_initializer.initialize_storage()

            def menu_callback():
                self.display.show_status("Menu Mode")
                self.pi_initializer.handle_utility_mode(True)

            self.pi_initializer.initialize_buttons(
                self.state_manager, 
                menu_callback
            )
    
    def _run_impl(self):
        """Embedded-specific run implementation"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Embedded Mode", keep_error_display=True):
                try:
                    destination_path = sanitize_path(self.config.transfer_destination)
                except Exception as e:
                    logger.error(f"Error sanitizing destination path from config: {e}")
                    self.display.show_error("Invalid destination")
                    time.sleep(5)
                    continue
                
                source_drive = self._wait_for_source_drive()
                if not source_drive:
                    continue
                
                error_occurred = self.transfer_op.execute_transfer(source_drive, destination_path)
                
                self._handle_completion(source_drive, error_occurred)
    
    def _wait_for_source_drive(self):
        """Wait for source drive insertion"""
        self.display.show_status("Waiting for source...")
        initial_drives = self.storage.get_available_drives()
        source_drive = self.storage.wait_for_new_drive(initial_drives)
        
        if not source_drive or self.stop_event.is_set():
            return None
        
        return source_drive
    
    def _handle_completion(self, source_drive, error_occurred):
        """Handle transfer completion and cleanup"""
        if source_drive.exists() and os.path.ismount(str(source_drive)):
            self.storage.wait_for_drive_removal(source_drive)
        else:
            time.sleep(2)
        
        if error_occurred:
            print("\nTransfer failed. Waiting 5 seconds before continuing...")
            time.sleep(5)
            if self.display:
                self.display.clear(preserve_errors=False)
    
    def cleanup(self):
        """Embedded-specific cleanup"""
        super().cleanup()
        try:
            if hasattr(self, 'pi_initializer'):
                self.pi_initializer.cleanup()
        except Exception as e:
            logger.error(f"Platform-specific cleanup error: {e}")

class WebUITransferBox(DesktopTransferBox):
    """Web UI specific TransferBox implementation"""
    
    def __init__(self, config_manager=None):
        # Initialize with web-specific components
        from src.core.websocket_display import WebSocketDisplay
        from src.core.web_server import WebServer
        
        # Call BaseTransferBox.__init__ instead of DesktopTransferBox to skip Rich display
        BaseTransferBox.__init__(self, config_manager)
        
        # Replace the display with WebSocket display
        self.display = WebSocketDisplay()
        
        # Update components that use display
        self.state_manager = StateManager(self.display)
        self.file_transfer = FileTransfer(
            config_manager=self.config_manager,
            display=self.display,
            storage=self.storage,
            state_manager=self.state_manager,
            sound_manager=self.sound_manager,
            stop_event=self.stop_event
        )
        
        # Update transfer operation handler
        self.transfer_op = TransferOperation(
            self.display,
            self.storage,
            self.file_transfer,
            self.sound_manager
        )
        
        # Initialize web server
        self.web_server = WebServer(self.display, self)
        self.destination_path = None
        
    def setup(self):
        """Web UI specific setup"""
        super().setup()
        
        # Start the web server
        server_started = self.web_server.start_server()
        
        if not server_started:
            logger.error("Failed to start web server. Exiting.")
            self.display.show_error("Web server failed to start. Please check if port 8000 is available.")
            return False
        
        # Start NextJS frontend in a separate process
        self._start_nextjs_frontend()
        
        # Open the web browser
        self._open_web_browser()
        
        return True
    
    def _start_nextjs_frontend(self):
        """Start the NextJS frontend - either dev server or static serving"""
        import subprocess
        import os
        
        # Check if we're running from a PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle - serve static files through FastAPI
            logger.info("Running from executable - serving NextJS static files through FastAPI")
            self._setup_static_file_serving()
        else:
            # Running from source - start development server
            logger.info("Running from source - starting NextJS development server")
            self._start_nextjs_dev_server()
    
    def _setup_static_file_serving(self):
        """Setup static file serving for built NextJS files in the executable"""
        try:
            # First, try to run npm start if we have the NextJS production build
            webui_path = Path(sys._MEIPASS) / "webui"
            package_json_path = webui_path / "package.json"
            
            # Initialize nextjs_process as None
            self.nextjs_process = None
            
            if package_json_path.exists() and (webui_path / ".next").exists():
                logger.info("Found NextJS build files, attempting to start production server...")
                
                # Try to run npm start for production mode
                try:
                    import subprocess
                    import os
                    
                    env = os.environ.copy()
                    env["NEXT_PUBLIC_API_URL"] = "http://127.0.0.1:8000"
                    env["PORT"] = "3000"
                    
                    # Check if npm is available
                    if shutil.which("npm"):
                        self.nextjs_process = subprocess.Popen(
                            ["npm", "start"],
                            cwd=webui_path,
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        
                        # Give the server time to start and verify it's still running
                        time.sleep(8)
                        
                        # Check if the process is still alive
                        if self.nextjs_process.poll() is None:
                            logger.info("NextJS production server started successfully")
                            self.nextjs_started = True
                            return
                        else:
                            # Process died, read error output
                            stdout, stderr = self.nextjs_process.communicate()
                            logger.warning(f"NextJS process exited. stdout: {stdout.decode()}, stderr: {stderr.decode()}")
                            self.nextjs_process = None
                    else:
                        logger.warning("npm not found, falling back to basic static serving")
                        
                except Exception as e:
                    logger.warning(f"Failed to start NextJS production server: {e}, falling back to static serving")
                    self.nextjs_process = None
            
            # Mark that NextJS was not started
            self.nextjs_started = False
            
            # Fallback: Basic static file serving through FastAPI
            logger.info("Setting up basic static file serving through FastAPI...")
            self._setup_basic_static_serving(webui_path)
            
        except Exception as e:
            logger.error(f"Failed to setup any frontend serving: {e}")
            self.nextjs_started = False
    
    def _setup_basic_static_serving(self, webui_path):
        """Setup basic static file serving as fallback"""
        try:
            from fastapi.staticfiles import StaticFiles
            from fastapi.responses import HTMLResponse
            
            # Mount NextJS static assets with correct paths
            static_dir = webui_path / ".next" / "static"
            if static_dir.exists():
                self.web_server.app.mount("/_next/static", StaticFiles(directory=str(static_dir)), name="nextjs_static")
                logger.info(f"Mounted NextJS static files: /_next/static -> {static_dir}")
            
            # Mount public files (favicon, icons, etc.)
            public_dir = webui_path / "public"
            if public_dir.exists():
                self.web_server.app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")
                logger.info(f"Mounted public files: /public -> {public_dir}")
            
            # Serve the main NextJS application HTML
            main_html_path = webui_path / ".next" / "server" / "app" / "index.html"
            if main_html_path.exists():
                @self.web_server.app.get("/")
                async def serve_nextjs_app():
                    """Serve the main NextJS application"""
                    with open(main_html_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return HTMLResponse(content=content)
                
                # Serve specific public files at root level (for favicon.ico, etc.)
                @self.web_server.app.get("/favicon.ico")
                async def serve_favicon():
                    """Serve favicon from public directory"""
                    from fastapi.responses import FileResponse
                    from fastapi import HTTPException
                    
                    favicon_path = public_dir / "favicon.ico"
                    if favicon_path.exists():
                        return FileResponse(str(favicon_path))
                    raise HTTPException(status_code=404, detail="Favicon not found")
                
                @self.web_server.app.get("/{filename}.{ext}")
                async def serve_public_assets(filename: str, ext: str):
                    """Serve specific public assets like icon files"""
                    from fastapi import HTTPException
                    from fastapi.responses import FileResponse
                    
                    # Only serve certain file types for security
                    allowed_extensions = {'ico', 'png', 'jpg', 'jpeg', 'svg', 'webp'}
                    if ext.lower() not in allowed_extensions:
                        raise HTTPException(status_code=404, detail="File type not allowed")
                    
                    asset_file = public_dir / f"{filename}.{ext}"
                    if asset_file.exists() and asset_file.is_file():
                        return FileResponse(str(asset_file))
                    raise HTTPException(status_code=404, detail="File not found")
                
                logger.info("NextJS application serving configured")
            else:
                # Fallback to basic UI if no NextJS HTML found
                @self.web_server.app.get("/")
                async def serve_basic_ui():
                    """Serve a basic UI when NextJS isn't available"""
                    return HTMLResponse(content="""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>TransferBox</title>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body { 
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                                max-width: 800px; 
                                margin: 0 auto; 
                                padding: 20px;
                                background: #f8fafc;
                            }
                            .container { 
                                background: white; 
                                padding: 30px; 
                                border-radius: 8px; 
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            }
                            h1 { color: #1f2937; margin-bottom: 20px; }
                            .status { 
                                padding: 15px; 
                                margin: 15px 0; 
                                border-radius: 4px; 
                                background: #dbeafe; 
                                border-left: 4px solid #3b82f6;
                            }
                            .api-link { 
                                color: #3b82f6; 
                                text-decoration: none; 
                                padding: 8px 16px;
                                border: 1px solid #3b82f6;
                                border-radius: 4px;
                                display: inline-block;
                                margin-top: 10px;
                            }
                            .api-link:hover { background: #eff6ff; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>TransferBox</h1>
                            <div class="status">
                                <strong>Web UI Mode Active</strong><br>
                                The full NextJS interface is not available in this build.
                            </div>
                            <p>You can still access the API endpoints:</p>
                            <a href="/api/app-metadata" class="api-link">App Metadata</a>
                            <a href="/api/drives" class="api-link">Available Drives</a>
                            <a href="/api/status" class="api-link">Status</a>
                            <p style="margin-top: 30px; color: #6b7280; font-size: 14px;">
                                For the full web interface, please run TransferBox from source with Node.js installed.
                            </p>
                        </div>
                    </body>
                    </html>
                    """)
                
                logger.warning("NextJS HTML not found, using basic fallback UI")
            
            logger.info("Static file serving configured")
            
        except Exception as e:
            logger.error(f"Failed to setup static serving: {e}")
    
    def _start_nextjs_dev_server(self):
        """Start the NextJS development server (for source runs)"""
        import subprocess
        import os
        
        webui_path = Path(__file__).parent / "webui"
        
        if not webui_path.exists():
            logger.error("WebUI directory not found")
            return
            
        try:
            # Check if node_modules exists, if not run npm install
            if not (webui_path / "node_modules").exists():
                logger.info("Installing frontend dependencies...")
                subprocess.run(["npm", "install"], cwd=webui_path, check=True)
            
            # Start the development server in the background
            logger.info("Starting NextJS frontend server...")
            env = os.environ.copy()
            env["NEXT_PUBLIC_API_URL"] = "http://127.0.0.1:8000"
            
            self.nextjs_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=webui_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give the server time to start
            time.sleep(5)
            logger.info("NextJS frontend server started")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start NextJS server: {e}")
        except FileNotFoundError:
            logger.error("npm not found. Please install Node.js and npm")
    
    def _open_web_browser(self):
        """Open the web browser to the frontend URL"""
        import webbrowser
        
        try:
            # Wait a moment for servers to be ready
            time.sleep(3)
            
            # Choose the correct URL based on execution mode
            if getattr(sys, 'frozen', False):
                # Running from PyInstaller bundle
                # Check if NextJS production server was started successfully
                if getattr(self, 'nextjs_started', False):
                    frontend_url = "http://localhost:3000"
                    logger.info(f"Opening web browser to {frontend_url} (NextJS production server)")
                else:
                    # Fall back to FastAPI basic serving
                    frontend_url = "http://127.0.0.1:8000"
                    logger.info(f"Opening web browser to {frontend_url} (FastAPI basic serving)")
            else:
                # Running from source - use NextJS dev server
                frontend_url = "http://localhost:3000"
                logger.info(f"Opening web browser to {frontend_url} (NextJS dev server)")
            
            webbrowser.open(frontend_url)
            
        except Exception as e:
            logger.error(f"Failed to open web browser: {e}")
            if getattr(sys, 'frozen', False):
                if getattr(self, 'nextjs_started', False):
                    logger.info("Please manually navigate to http://localhost:3000")
                else:
                    logger.info("Please manually navigate to http://127.0.0.1:8000")
            else:
                logger.info("Please manually navigate to http://localhost:3000")
    
    def set_destination_path(self, path: Path):
        """Set the destination path for transfers"""
        self.destination_path = path
        logger.info(f"Destination path set to: {path}")
    
    def _get_destination_path(self):
        """Get destination path for web UI transfers"""
        # In web UI mode, the path should be set via the web interface
        if self.destination_path:
            return self.destination_path
        
        # If no path is set, wait for it to be set via web interface
        self.display.show_status("Waiting for destination path via web interface...")
        
        # Poll for destination path to be set
        while not self.destination_path and not self.stop_event.is_set():
            time.sleep(1)
        
        return self.destination_path
    
    def _run_tutorial_flow(self):
        """Tutorial flow for web UI - handled by frontend"""
        # In web UI mode, tutorial is handled by the frontend
        # Just show a message that tutorial is available
        self.display.show_status("Tutorial available in web interface")
        time.sleep(2)
    
    def cleanup(self):
        """Web UI specific cleanup"""
        super().cleanup()
        
        # Stop the web server
        if hasattr(self, 'web_server'):
            self.web_server.stop_server()
        
        # Stop the NextJS process
        if hasattr(self, 'nextjs_process'):
            try:
                self.nextjs_process.terminate()
                self.nextjs_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error stopping NextJS process: {e}")

def create_transfer_box_app(use_webui=False):
    """Factory function to create the appropriate TransferBox instance"""
    platform = get_platform()
    
    if use_webui:
        # Only allow web UI on desktop platforms
        if platform in ["darwin", "windows"]:
            return WebUITransferBox()
        else:
            logger.warning("Web UI not supported on embedded platforms, falling back to terminal UI")
            return EmbeddedTransferBox()
    
    if platform in ["darwin", "windows"]:
        return DesktopTransferBox()
    return EmbeddedTransferBox()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description=f"{__project_name__} v{__version__}")
    parser.add_argument("--benchmark", action="store_true", help="Run transfer benchmark")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB for benchmark")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB for benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark test")
    parser.add_argument("--webui", action="store_true", help="Start web UI instead of terminal interface")
    return parser.parse_args()

def run_benchmark(args):
    """Run benchmark with specified arguments"""
    from src.core.benchmark import run_benchmark_cli
    
    sys.argv = [sys.argv[0]]
    if args.buffer_sizes:
        sys.argv.extend(["--buffer-sizes", args.buffer_sizes])
    if args.file_sizes:
        sys.argv.extend(["--file-sizes", args.file_sizes])
    if args.iterations:
        sys.argv.extend(["--iterations", str(args.iterations)])
        
    return run_benchmark_cli()

def main():
    """Main entry point"""
    args = parse_arguments()
    
    if args.benchmark:
        return run_benchmark(args)
    
    try:
        app = create_transfer_box_app(use_webui=args.webui)
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Unhandled exception")
        return 1

if __name__ == "__main__":
    sys.exit(main())