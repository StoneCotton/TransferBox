import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
            await websocket.accept()
            self.websocket_display.add_websocket_client(websocket)
            logger.info("WebSocket client connected")
            
            try:
                # Send current state to newly connected client
                current_state = self.websocket_display.get_current_state()
                await websocket.send_text(json.dumps({
                    "type": "initial_state",
                    "data": current_state,
                    "timestamp": str(time.time())
                }))
                
                # Keep connection alive and handle incoming messages
                while True:
                    message = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, message)
                    
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_display.remove_websocket_client(websocket)
        
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
                return AppMetadata(
                    appName=__project_name__,
                    version=__version__,
                    author=__author__,
                    description=__description__,
                    license=__license__
                )
            except Exception as e:
                logger.error(f"App metadata retrieval error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get app metadata: {str(e)}")
    
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
            except Exception as e:
                logger.error(f"Server error: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait a moment for the server to start
        time.sleep(2)
        logger.info("FastAPI server started successfully")
    
    def stop_server(self):
        """Stop the FastAPI server"""
        if self.server:
            logger.info("Stopping FastAPI server")
            if self.loop:
                asyncio.run_coroutine_threadsafe(self.server.shutdown(), self.loop)
            
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            logger.info("FastAPI server stopped") 