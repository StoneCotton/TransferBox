import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from pydantic import BaseModel

from src.core.websocket_display import WebSocketDisplay
from src.core.utils import validate_path
from src.core.path_utils import sanitize_path, is_plausible_user_path
from src.core.config_manager import ConfigManager
from src import __version__, __author__, __project_name__, __description__, __license__

logger = logging.getLogger(__name__)

class PathValidationRequest(BaseModel):
    path: str

class PathValidationResponse(BaseModel):
    is_valid: bool
    error_message: Optional[str] = None
    sanitized_path: Optional[str] = None

class TutorialStepRequest(BaseModel):
    step: int
    action: str  # 'next', 'previous', 'complete', 'skip'

class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]

class ConfigResponse(BaseModel):
    success: bool
    config: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class AppMetadata(BaseModel):
    appName: str
    version: str
    author: str
    description: str
    license: str
    platform: str

class DriveInfo(BaseModel):
    path: str
    name: str
    total_space: int
    free_space: int
    used_space: int
    total_space_gb: float
    free_space_gb: float
    used_space_gb: float
    drive_type: Optional[str] = None
    is_mounted: bool
    is_removable: Optional[bool] = None

class AvailableDrivesResponse(BaseModel):
    success: bool
    drives: List[DriveInfo]
    message: Optional[str] = None

class WebServer:
    """FastAPI web server for TransferBox web UI"""
    
    def __init__(self, websocket_display: WebSocketDisplay, transfer_box_app):
        self.websocket_display = websocket_display
        self.transfer_box_app = transfer_box_app
        self.app = FastAPI(title="TransferBox Web UI")
        self.server_thread: Optional[threading.Thread] = None
        self.server = None
        self.loop = None
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify your frontend URL
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes and endpoints"""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            client_address = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
            
            try:
                await websocket.accept()
                self.websocket_display.add_websocket_client(websocket)
                logger.info(f"WebSocket client connected from {client_address}")
                
                # Send current state to newly connected client
                current_state = self.websocket_display.get_current_state()
                await websocket.send_text(json.dumps({
                    "type": "initial_state",
                    "data": current_state,
                    "timestamp": str(time.time())
                }))
                
                # Keep connection alive and handle incoming messages
                while True:
                    try:
                        message = await websocket.receive_text()
                        await self._handle_websocket_message(websocket, message)
                    except WebSocketDisconnect as e:
                        # Re-raise to be caught by outer handler
                        raise e
                    
            except WebSocketDisconnect as e:
                # Handle different disconnect codes
                disconnect_code = e.code if hasattr(e, 'code') else None
                disconnect_reason = e.reason if hasattr(e, 'reason') else None
                
                if disconnect_code == 1001:
                    # Normal "going away" disconnect (browser tab closed, page refreshed, etc.)
                    logger.debug(f"WebSocket client {client_address} disconnected normally (going away)")
                elif disconnect_code == 1000:
                    # Normal closure
                    logger.debug(f"WebSocket client {client_address} disconnected normally (closed)")
                elif disconnect_code is None:
                    # Connection lost without proper close frame
                    logger.info(f"WebSocket client {client_address} disconnected (connection lost)")
                else:
                    # Other disconnect codes
                    logger.warning(f"WebSocket client {client_address} disconnected with code {disconnect_code}: {disconnect_reason}")
                    
            except ConnectionResetError:
                logger.info(f"WebSocket client {client_address} connection was reset")
            except Exception as e:
                logger.error(f"WebSocket error for client {client_address}: {e}")
            finally:
                # Always clean up the client connection
                try:
                    self.websocket_display.remove_websocket_client(websocket)
                    logger.debug(f"WebSocket client {client_address} cleaned up")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up WebSocket client {client_address}: {cleanup_error}")
        
        @self.app.post("/api/validate-path", response_model=PathValidationResponse)
        async def validate_destination_path(request: PathValidationRequest):
            """Validate destination path for file transfers"""
            try:
                path = request.path.strip()
                
                if not path:
                    return PathValidationResponse(
                        is_valid=False,
                        error_message="Path cannot be empty"
                    )
                
                # Use existing validation logic
                is_valid_path = validate_path(path)
                is_plausible, plausible_error = is_plausible_user_path(path)
                is_valid = is_valid_path and is_plausible
                
                if is_valid:
                    try:
                        sanitized = sanitize_path(path)
                        return PathValidationResponse(
                            is_valid=True,
                            sanitized_path=str(sanitized)
                        )
                    except Exception as e:
                        return PathValidationResponse(
                            is_valid=False,
                            error_message=f"Path sanitization failed: {str(e)}"
                        )
                else:
                    error_msg = plausible_error if plausible_error else "Invalid or inaccessible path"
                    return PathValidationResponse(
                        is_valid=False,
                        error_message=error_msg
                    )
                    
            except Exception as e:
                logger.error(f"Path validation error: {e}")
                return PathValidationResponse(
                    is_valid=False,
                    error_message=f"Validation error: {str(e)}"
                )
        
        @self.app.post("/api/set-destination")
        async def set_destination_path(request: PathValidationRequest):
            """Set the destination path for transfers"""
            try:
                path = request.path.strip()
                
                # Validate path first
                validation = await validate_destination_path(request)
                if not validation.is_valid:
                    raise HTTPException(status_code=400, detail=validation.error_message)
                
                # Set the destination in the transfer box app
                if hasattr(self.transfer_box_app, 'set_destination_path'):
                    self.transfer_box_app.set_destination_path(Path(validation.sanitized_path))
                else:
                    # Store it for later use
                    self.transfer_box_app.destination_path = Path(validation.sanitized_path)
                
                logger.info(f"Destination path set to: {validation.sanitized_path}")
                
                return JSONResponse({
                    "success": True,
                    "message": "Destination path set successfully",
                    "path": validation.sanitized_path
                })
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Set destination error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to set destination: {str(e)}")
        
        @self.app.post("/api/tutorial")
        async def handle_tutorial_action(request: TutorialStepRequest):
            """Handle tutorial navigation and completion"""
            try:
                # For now, just log the tutorial action
                # In a full implementation, you might want to track tutorial state
                logger.info(f"Tutorial action: step {request.step}, action {request.action}")
                
                return JSONResponse({
                    "success": True,
                    "message": f"Tutorial {request.action} processed",
                    "step": request.step
                })
                
            except Exception as e:
                logger.error(f"Tutorial action error: {e}")
                raise HTTPException(status_code=500, detail=f"Tutorial action failed: {str(e)}")
        
        @self.app.get("/api/status")
        async def get_status():
            """Get current application status"""
            try:
                current_state = self.websocket_display.get_current_state()
                return JSONResponse({
                    "success": True,
                    "data": current_state
                })
            except Exception as e:
                logger.error(f"Status retrieval error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

        @self.app.get("/api/config", response_model=ConfigResponse)
        async def get_config():
            """Get current configuration"""
            try:
                # Access config through the transfer box app
                if hasattr(self.transfer_box_app, 'config_manager') and self.transfer_box_app.config_manager:
                    config = self.transfer_box_app.config_manager.config
                    config_dict = config.to_dict() if config else {}
                else:
                    # Fallback: create a new config manager
                    config_manager = ConfigManager()
                    config = config_manager.load_config()
                    config_dict = config.to_dict()
                
                return ConfigResponse(
                    success=True,
                    config=config_dict,
                    message="Configuration retrieved successfully"
                )
            except Exception as e:
                logger.error(f"Config retrieval error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

        @self.app.post("/api/config", response_model=ConfigResponse)
        async def update_config(request: ConfigUpdateRequest):
            """Update configuration"""
            try:
                # Access config manager through the transfer box app
                if hasattr(self.transfer_box_app, 'config_manager') and self.transfer_box_app.config_manager:
                    config_manager = self.transfer_box_app.config_manager
                else:
                    # Fallback: create a new config manager
                    config_manager = ConfigManager()
                    config_manager.load_config()
                
                # Update the configuration
                updated_config = config_manager.update_config(request.config)
                config_dict = updated_config.to_dict()
                
                logger.info("Configuration updated successfully")
                
                return ConfigResponse(
                    success=True,
                    config=config_dict,
                    message="Configuration updated successfully"
                )
                
            except Exception as e:
                logger.error(f"Config update error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

        @self.app.get("/api/app-metadata", response_model=AppMetadata)
        async def get_app_metadata():
            """Get application metadata"""
            try:
                from src.core.utils import get_platform
                platform = get_platform()
                
                return AppMetadata(
                    appName=__project_name__,
                    version=__version__,
                    author=__author__,
                    description=__description__,
                    license=__license__,
                    platform=platform
                )
            except Exception as e:
                logger.error(f"App metadata retrieval error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get app metadata: {str(e)}")

        @self.app.get("/api/drives", response_model=AvailableDrivesResponse)
        async def get_available_drives():
            """Get available drives with detailed information"""
            try:
                # Access storage through the transfer box app
                if hasattr(self.transfer_box_app, 'storage') and self.transfer_box_app.storage:
                    storage = self.transfer_box_app.storage
                else:
                    # Fallback: create a new storage instance
                    from src.core.platform_manager import PlatformManager
                    storage = PlatformManager.create_storage()
                
                # Get available drives from storage interface
                available_drives = storage.get_available_drives()
                drives_info = []
                
                for drive_path in available_drives:
                    try:
                        # Get drive information
                        drive_info = storage.get_drive_info(drive_path)
                        is_mounted = storage.is_drive_mounted(drive_path)
                        
                        # Calculate GB values for frontend display
                        total_gb = drive_info['total'] / (1024 ** 3)
                        free_gb = drive_info['free'] / (1024 ** 3) 
                        used_gb = drive_info['used'] / (1024 ** 3)
                        
                        # Get drive type if available (Windows specific)
                        drive_type = None
                        is_removable = None
                        if hasattr(storage, 'get_drive_type'):
                            drive_type = storage.get_drive_type(drive_path)
                            is_removable = drive_type == "REMOVABLE"
                        
                        # Extract drive name (last part of path)
                        drive_name = drive_path.name if drive_path.name else str(drive_path)
                        
                        drives_info.append(DriveInfo(
                            path=str(drive_path),
                            name=drive_name,
                            total_space=drive_info['total'],
                            free_space=drive_info['free'],
                            used_space=drive_info['used'],
                            total_space_gb=round(total_gb, 2),
                            free_space_gb=round(free_gb, 2),
                            used_space_gb=round(used_gb, 2),
                            drive_type=drive_type,
                            is_mounted=is_mounted,
                            is_removable=is_removable
                        ))
                        
                    except Exception as drive_error:
                        logger.warning(f"Error getting info for drive {drive_path}: {drive_error}")
                        # Add basic info even if detailed info fails
                        drives_info.append(DriveInfo(
                            path=str(drive_path),
                            name=drive_path.name if drive_path.name else str(drive_path),
                            total_space=0,
                            free_space=0,
                            used_space=0,
                            total_space_gb=0.0,
                            free_space_gb=0.0,
                            used_space_gb=0.0,
                            drive_type="UNKNOWN",
                            is_mounted=False,
                            is_removable=None
                        ))
                
                logger.debug(f"Retrieved {len(drives_info)} available drives")
                
                return AvailableDrivesResponse(
                    success=True,
                    drives=drives_info,
                    message=f"Found {len(drives_info)} available drives"
                )
                
            except Exception as e:
                logger.error(f"Drive retrieval error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get drives: {str(e)}")

        @self.app.post("/api/stop-transfer")
        async def stop_transfer():
            """Stop the current transfer operation"""
            try:
                # Access the transfer box app to stop the transfer
                if hasattr(self.transfer_box_app, 'transfer_stop_event') and self.transfer_box_app.transfer_stop_event:
                    # Set the transfer stop event to signal transfer should stop
                    self.transfer_box_app.transfer_stop_event.set()
                    
                    logger.info("Transfer stop requested via API")
                    
                    # Send WebSocket message to notify frontend
                    await self.websocket_display.broadcast_message("transfer_stopped", {
                        "message": "Transfer stopped by user request",
                        "cleanup_initiated": True,
                        "user_requested": True
                    })
                    
                    return {
                        "success": True,
                        "message": "Transfer stop initiated"
                    }
                else:
                    logger.warning("No active transfer to stop")
                    return {
                        "success": False,
                        "message": "No active transfer found"
                    }
                    
            except Exception as e:
                logger.error(f"Stop transfer error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to stop transfer: {str(e)}")

        @self.app.post("/api/shutdown")
        async def shutdown_application():
            """Shutdown the TransferBox application"""
            try:
                # Send WebSocket message to notify frontend before shutdown
                await self.websocket_display.broadcast_message("shutdown_initiated", {
                    "message": "Application shutdown initiated"
                })
                
                logger.info("Application shutdown requested via API")
                
                # Set the stop event to signal the application should exit
                if hasattr(self.transfer_box_app, 'stop_event') and self.transfer_box_app.stop_event:
                    self.transfer_box_app.stop_event.set()
                
                # Schedule the actual shutdown after a brief delay to allow response to be sent
                import asyncio
                async def delayed_shutdown():
                    await asyncio.sleep(1)  # Give time for response to be sent
                    logger.info("Initiating application shutdown")
                    
                    # Use os._exit() to avoid threading issues during cleanup
                    # The main application loop will handle cleanup when stop_event is set
                    import os
                    os._exit(0)
                
                # Start the delayed shutdown
                asyncio.create_task(delayed_shutdown())
                
                return {
                    "success": True,
                    "message": "Shutdown initiated"
                }
                
            except Exception as e:
                logger.error(f"Shutdown error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to shutdown: {str(e)}")
    
    async def _handle_websocket_message(self, websocket: WebSocket, message: str):
        """Handle incoming WebSocket messages from the frontend"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "ping":
                # Respond to ping with pong
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "data": {},
                    "timestamp": str(time.time())
                }))
            elif message_type == "request_state":
                # Send current state
                current_state = self.websocket_display.get_current_state()
                await websocket.send_text(json.dumps({
                    "type": "state_update",
                    "data": current_state,
                    "timestamp": str(time.time())
                }))
            else:
                logger.warning(f"Unknown WebSocket message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in WebSocket message: {message}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    def start_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Start the FastAPI server in a separate thread"""
        self.server_started = False
        self.server_error = None
        
        def run_server():
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Set the event loop in the websocket display
            self.websocket_display.set_event_loop(self.loop)
            
            # Create and run the server
            config = uvicorn.Config(
                app=self.app,
                host=host,
                port=port,
                log_level="info",
                loop="asyncio"
            )
            
            self.server = uvicorn.Server(config)
            logger.info(f"Starting FastAPI server on http://{host}:{port}")
            
            try:
                self.loop.run_until_complete(self.server.serve())
                self.server_started = True
            except Exception as e:
                self.server_error = e
                logger.error(f"Server error: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait a moment for the server to start and check if it succeeded
        time.sleep(2)
        
        if self.server_error:
            logger.error(f"FastAPI server failed to start: {self.server_error}")
            if "address already in use" in str(self.server_error):
                logger.error("Port 8000 is already in use. Please close any other TransferBox instances.")
            return False
        else:
            logger.info("FastAPI server started successfully")
            return True
    
    def stop_server(self):
        """Stop the FastAPI server"""
        if self.server:
            logger.info("Stopping FastAPI server")
            if self.loop:
                asyncio.run_coroutine_threadsafe(self.server.shutdown(), self.loop)
            
        if self.server_thread and self.server_thread.is_alive():
            # Check if we're trying to join from within the server thread itself
            import threading
            current_thread = threading.current_thread()
            if current_thread == self.server_thread:
                logger.debug("Skipping thread join - called from within server thread")
            else:
                self.server_thread.join(timeout=5)
                logger.info("FastAPI server stopped") 