import asyncio
import json
import logging
from typing import Dict, Any, Set, Optional
from threading import Thread, Lock
from dataclasses import asdict

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus

logger = logging.getLogger(__name__)

class WebSocketDisplay(DisplayInterface):
    """WebSocket-based display implementation for web UI"""
    
    def __init__(self):
        self.websocket_lock = Lock()
        self.connected_clients: Set[Any] = set()  # WebSocket connections
        self.current_status: str = ""
        self.current_progress: Optional[TransferProgress] = None
        self.error_messages: list = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def add_websocket_client(self, websocket):
        """Add a WebSocket client connection"""
        with self.websocket_lock:
            self.connected_clients.add(websocket)
            logger.debug(f"WebSocket client connected. Total clients: {len(self.connected_clients)}")
            
    def remove_websocket_client(self, websocket):
        """Remove a WebSocket client connection"""
        with self.websocket_lock:
            self.connected_clients.discard(websocket)
            logger.debug(f"WebSocket client disconnected. Total clients: {len(self.connected_clients)}")
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop for async operations"""
        self._loop = loop
    
    async def broadcast_message(self, message_type: str, data: Dict[str, Any]):
        """Broadcast a message to all connected WebSocket clients"""
        if not self.connected_clients:
            logger.debug(f"No WebSocket clients connected to receive {message_type}")
            return
            
        message = {
            "type": message_type,
            "data": data,
            "timestamp": str(asyncio.get_event_loop().time())
        }
        
        # Create a copy of clients to avoid modification during iteration
        clients_copy = self.connected_clients.copy()
        
        # Send to all connected clients
        for client in clients_copy:
            try:
                await client.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket client: {e}")
                # Remove the failed client
                self.remove_websocket_client(client)
    
    def _send_async_message(self, message_type: str, data: Dict[str, Any]):
        """Send message asynchronously from a sync context"""
        if self._loop and self._loop.is_running():
            if message_type == "progress":
                logger.info(f"Sending WebSocket progress message to {len(self.connected_clients)} clients")
            asyncio.run_coroutine_threadsafe(
                self.broadcast_message(message_type, data),
                self._loop
            )
        else:
            # Log at debug level since this is expected during startup
            logger.debug(f"Event loop not available for {message_type} message")
    
    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message via WebSocket"""
        self.current_status = message
        logger.info(f"Status: {message}")
        
        self._send_async_message("status", {
            "message": message,
            "line": line
        })
    
    def show_progress(self, progress: TransferProgress) -> None:
        """Display transfer progress via WebSocket"""
        self.current_progress = progress
        
        # Convert the dataclass to a dictionary for JSON serialization
        progress_data = asdict(progress)
        
        # Convert enum to string
        progress_data["status"] = progress.status.name
        
        # Convert fractional progress values (0.0-1.0) to percentages (0-100) for frontend
        if "current_file_progress" in progress_data:
            progress_data["current_file_progress"] = progress_data["current_file_progress"] * 100
        if "overall_progress" in progress_data:
            progress_data["overall_progress"] = progress_data["overall_progress"] * 100
        if "proxy_progress" in progress_data:
            progress_data["proxy_progress"] = progress_data["proxy_progress"] * 100
        
        # Log more detailed progress information
        logger.info(f"WebSocket Progress Update - File: {progress.current_file}, "
                   f"File Progress: {progress.current_file_progress * 100:.2f}%, "
                   f"Overall Progress: {progress.overall_progress * 100:.2f}%, "
                   f"Status: {progress.status.name}, "
                   f"File {progress.file_number}/{progress.total_files}")
        
        self._send_async_message("progress", progress_data)
    
    def show_error(self, message: str) -> None:
        """Display an error message via WebSocket"""
        self.error_messages.append(message)
        logger.error(f"Error: {message}")
        
        self._send_async_message("error", {
            "message": message
        })
    
    def clear(self, preserve_errors: bool = False) -> None:
        """Clear the display via WebSocket"""
        if not preserve_errors:
            self.error_messages.clear()
        
        self.current_status = ""
        self.current_progress = None
        
        logger.debug("Display cleared")
        
        self._send_async_message("clear", {
            "preserve_errors": preserve_errors
        })
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current display state for new WebSocket connections"""
        state = {
            "status": self.current_status,
            "errors": self.error_messages.copy()
        }
        
        if self.current_progress:
            progress_data = asdict(self.current_progress)
            progress_data["status"] = self.current_progress.status.name
            
            # Convert fractional progress values (0.0-1.0) to percentages (0-100) for frontend
            if "current_file_progress" in progress_data:
                progress_data["current_file_progress"] = progress_data["current_file_progress"] * 100
            if "overall_progress" in progress_data:
                progress_data["overall_progress"] = progress_data["overall_progress"] * 100
            if "proxy_progress" in progress_data:
                progress_data["proxy_progress"] = progress_data["proxy_progress"] * 100
            
            state["progress"] = progress_data
        
        return state 