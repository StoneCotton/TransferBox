# src/core/transfer_box_webui.py

import os
import sys
import time
import logging
import shutil
import webbrowser
import subprocess
from pathlib import Path

from .transfer_box_base import BaseTransferBox
from .state_manager import StateManager
from .file_transfer import FileTransfer
from .transfer_operation import TransferOperation
from .tutorial import TutorialManager
from .context_managers import operation_context

logger = logging.getLogger(__name__)


class WebUITransferBox(BaseTransferBox):
    """Web UI specific TransferBox implementation"""
    
    def __init__(self, config_manager=None):
        # Initialize with web-specific components
        from src.core.websocket_display import WebSocketDisplay
        from src.core.web_server import WebServer
        
        # Call BaseTransferBox.__init__ directly to avoid Rich display setup
        super().__init__(config_manager)
        
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
        self.tutorial_manager = TutorialManager(self.display)
        
        # Separate event for stopping transfers without shutting down the app
        self.transfer_stop_event = None
        
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
                
                # Handle Next.js Image optimization requests by serving images directly
                @self.web_server.app.get("/_next/image")
                async def serve_nextjs_image(url: str, w: int = 32, q: int = 75):
                    """Handle Next.js Image optimization requests"""
                    from fastapi import HTTPException, Query
                    from fastapi.responses import FileResponse
                    from urllib.parse import unquote
                    
                    # Decode the URL parameter (e.g., %2Ftransferbox-logo.png -> /transferbox-logo.png)
                    decoded_url = unquote(url)
                    
                    # Remove leading slash if present
                    if decoded_url.startswith('/'):
                        decoded_url = decoded_url[1:]
                    
                    # Construct the file path
                    image_path = public_dir / decoded_url
                    
                    # Security check: ensure the path is within public directory
                    try:
                        resolved_path = image_path.resolve()
                        public_resolved = public_dir.resolve()
                        if not str(resolved_path).startswith(str(public_resolved)):
                            raise HTTPException(status_code=404, detail="File not found")
                    except Exception:
                        raise HTTPException(status_code=404, detail="File not found")
                    
                    # Check if file exists and is a valid image
                    if image_path.exists() and image_path.is_file():
                        # Check file extension
                        allowed_extensions = {'.ico', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'}
                        if image_path.suffix.lower() in allowed_extensions:
                            return FileResponse(str(image_path))
                    
                    raise HTTPException(status_code=404, detail="Image not found")
            
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
                    return HTMLResponse(content=self._get_basic_html_content())
                
                logger.warning("NextJS HTML not found, using basic fallback UI")
            
            logger.info("Static file serving configured")
            
        except Exception as e:
            logger.error(f"Failed to setup static serving: {e}")
    
    def _get_basic_html_content(self):
        """Get basic HTML content for fallback UI"""
        return """
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
        """
    
    def _start_nextjs_dev_server(self):
        """Start the NextJS development server (for source runs)"""
        webui_path = Path(__file__).parent.parent.parent / "webui"
        
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
            
            # Start with stdout/stderr capture to parse the actual port
            self.nextjs_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=webui_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Initialize default port
            self.nextjs_port = 3000
            
            # Read the output to detect the actual port
            logger.info("Detecting NextJS server port...")
            for i in range(20):  # Try for up to 10 seconds
                if self.nextjs_process.poll() is not None:
                    # Process ended unexpectedly
                    stdout, _ = self.nextjs_process.communicate()
                    logger.error(f"NextJS process ended unexpectedly: {stdout}")
                    return
                
                # Try to read a line from stdout
                try:
                    line = self.nextjs_process.stdout.readline()
                    if line:
                        logger.debug(f"NextJS output: {line.strip()}")
                        # Look for port information in the output
                        if "Local:" in line and "http://localhost:" in line:
                            # Extract port from line like "- Local:        http://localhost:3001"
                            import re
                            match = re.search(r'http://localhost:(\d+)', line)
                            if match:
                                self.nextjs_port = int(match.group(1))
                                logger.info(f"NextJS detected on port {self.nextjs_port}")
                                break
                        elif "Ready" in line:
                            # NextJS is ready, stop reading
                            break
                except Exception as e:
                    logger.debug(f"Error reading NextJS output: {e}")
                
                time.sleep(0.5)
            
            logger.info(f"NextJS frontend server started on port {self.nextjs_port}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start NextJS server: {e}")
        except FileNotFoundError:
            logger.error("npm not found. Please install Node.js and npm")
    
    def _open_web_browser(self):
        """Open the web browser to the frontend URL"""
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
                # Running from source - use NextJS dev server with detected port
                nextjs_port = getattr(self, 'nextjs_port', 3000)
                frontend_url = f"http://localhost:{nextjs_port}"
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
                nextjs_port = getattr(self, 'nextjs_port', 3000)
                logger.info(f"Please manually navigate to http://localhost:{nextjs_port}")
    
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
        self.tutorial_manager.run_webui_tutorial_flow()
    
    def cleanup(self):
        """Web UI specific cleanup"""
        logger.info("Starting Web UI cleanup")
        
        # Stop the NextJS process first (more gracefully)
        if hasattr(self, 'nextjs_process') and self.nextjs_process:
            try:
                logger.info("Stopping NextJS process gracefully")
                
                # First try SIGTERM (graceful shutdown)
                self.nextjs_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.nextjs_process.wait(timeout=3)
                    logger.info("NextJS process stopped gracefully")
                except subprocess.TimeoutExpired:
                    # If graceful shutdown didn't work, force kill
                    logger.warning("NextJS process didn't stop gracefully, forcing shutdown")
                    self.nextjs_process.kill()
                    try:
                        self.nextjs_process.wait(timeout=2)
                        logger.info("NextJS process forcefully stopped")
                    except subprocess.TimeoutExpired:
                        logger.error("NextJS process failed to stop even with force")
                        
            except Exception as e:
                logger.error(f"Error stopping NextJS process: {e}")
        
        # Stop the web server
        if hasattr(self, 'web_server') and self.web_server:
            try:
                logger.info("Stopping Web Server")
                self.web_server.stop_server()
                logger.info("Web Server stopped")
            except Exception as e:
                logger.error(f"Error stopping web server: {e}")
        
        # Call parent cleanup
        try:
            super().cleanup()
        except Exception as e:
            logger.error(f"Error in parent cleanup: {e}")

    def _run_impl(self):
        """Web UI specific run implementation"""
        try:
            # Server and frontend are already started in setup() method
            logger.info("FastAPI server and frontend already started in setup")
            logger.info("Web UI is ready. Press Ctrl+C to stop.")
            
            # Run the main transfer loop in addition to keeping servers alive
            self._run_transfer_loop()
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Web UI runtime error: {e}")
            raise
    
    def _run_transfer_loop(self):
        """Run the main transfer detection and execution loop"""
        import threading
        
        def transfer_thread():
            """Background thread for handling transfers"""
            while not self.stop_event.is_set():
                error_occurred = False
                
                try:
                    with operation_context(self.display, self.sound_manager, "Web UI Mode", keep_error_display=True):
                        # Get destination path (will wait if not set)
                        destination_path = self._get_destination_path()
                        if not destination_path or self.stop_event.is_set():
                            continue
                        
                        # Wait for source drive
                        source_drive = self._wait_for_source_drive()
                        if not source_drive or self.stop_event.is_set():
                            continue
                        
                        # Create a new transfer stop event for this transfer session
                        from threading import Event
                        self.transfer_stop_event = Event()
                        
                        # Create a new file transfer instance with the transfer stop event
                        transfer_file_transfer = FileTransfer(
                            config_manager=self.config_manager,
                            display=self.display,
                            storage=self.storage,
                            state_manager=self.state_manager,
                            sound_manager=self.sound_manager,
                            stop_event=self.transfer_stop_event  # Use transfer-specific stop event
                        )
                        
                        # Create a new transfer operation with the transfer-specific file transfer
                        transfer_op = TransferOperation(
                            self.display,
                            self.storage,
                            transfer_file_transfer,
                            self.sound_manager
                        )
                        
                        # Execute transfer
                        error_occurred = transfer_op.execute_transfer(source_drive, destination_path)
                        
                        # Check if transfer was stopped
                        if self.transfer_stop_event and self.transfer_stop_event.is_set():
                            logger.info("Transfer was stopped by user request")
                            self.display.show_status("Transfer stopped - returning to standby mode")
                            # Clear any error state and return to standby
                            error_occurred = False
                        
                        # Reset the transfer stop event after completion
                        self.transfer_stop_event = None
                        
                        # Handle completion
                        self._handle_completion(source_drive, error_occurred)
                        
                except Exception as e:
                    logger.error(f"Transfer loop error: {e}")
                    if self.display:
                        self.display.show_error(f"Transfer error: {str(e)}")
                    # Reset transfer stop event on error
                    self.transfer_stop_event = None
                    time.sleep(5)  # Wait before retrying
        
        def server_monitoring_thread():
            """Background thread for monitoring server health"""
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # Check if web server is still running
                if hasattr(self.web_server, 'server') and not self.web_server.server:
                    logger.warning("FastAPI server stopped unexpectedly")
                    break
                    
                # Check if NextJS process is still running (in dev mode)
                if hasattr(self, 'nextjs_process') and self.nextjs_process:
                    if self.nextjs_process.poll() is not None:
                        logger.warning("NextJS process stopped unexpectedly")
                        # Don't break, as we can still serve via FastAPI
        
        # Start both threads
        transfer_worker = threading.Thread(target=transfer_thread, daemon=True)
        server_monitor = threading.Thread(target=server_monitoring_thread, daemon=True)
        
        transfer_worker.start()
        server_monitor.start()
        
        # Wait for either thread to complete or stop event
        while not self.stop_event.is_set() and transfer_worker.is_alive() and server_monitor.is_alive():
            time.sleep(0.5)
        
        logger.info("Web UI shutting down...")
    
    def _wait_for_source_drive(self):
        """Wait for source drive insertion - web UI version"""
        self.display.show_status("Waiting for source drive...")
        initial_drives = self.storage.get_available_drives()
        source_drive = self.storage.wait_for_new_drive(initial_drives)
        
        if not source_drive or self.stop_event.is_set():
            return None
        
        return source_drive
    
    def _handle_completion(self, source_drive, error_occurred):
        """Handle transfer completion and cleanup - web UI version"""
        if source_drive.exists() and os.path.ismount(str(source_drive)):
            self.storage.wait_for_drive_removal(source_drive)
        else:
            time.sleep(2)
        
        # Clear destination path after transfer completion to prevent automatic transfers
        self.destination_path = None
        logger.info("Destination path cleared after transfer completion")
        
        # Notify frontend that destination has been reset
        if hasattr(self.display, 'send_destination_reset'):
            self.display.send_destination_reset()
        
        if error_occurred:
            logger.warning("Transfer failed. Waiting 5 seconds before continuing...")
            time.sleep(5)
            if self.display:
                self.display.clear(preserve_errors=False) 