# src/core/context_managers.py

import logging
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Callable, List, Any

logger = logging.getLogger(__name__)

@contextmanager
def operation_context(
    display=None,
    sound_manager=None,
    operation_name="Operation",
    on_error: Optional[Callable] = None,
    keep_error_display: bool = True
):
    """
    Unified context manager for operations with proper error handling.
    
    Args:
        display: Optional display interface for showing status messages
        sound_manager: Optional sound manager for playing status sounds
        operation_name: Name of the operation for logging and display
        on_error: Optional callback function to handle errors
        keep_error_display: When True, skip clearing the display on exit if an error occurred
        
    Yields:
        None
    """
    error_occurred = False
    try:
        if display:
            display.show_status(f"Starting: {operation_name}")
        logger.debug(f"Starting {operation_name}")
        yield
        
        if display:
            # Only show completion status if no error occurred
            display.show_status(f"Completed: {operation_name}")
        logger.debug(f"Completed {operation_name}")
        
    except Exception as e:
        error_occurred = True
        logger.error(f"Error in {operation_name}: {e}", exc_info=True)
        
        if display:
            display.show_error(f"{operation_name} failed")
            
        if sound_manager:
            try:
                sound_manager.play_error()
            except Exception as sound_err:
                logger.warning(f"Failed to play error sound: {sound_err}")
        
        if on_error:
            on_error(e)
            
        raise
    finally:
        # Clean up the display when exiting, but skip if we should preserve error messages
        if display and not (error_occurred and keep_error_display):
            # Only clear the display if no error occurred or we don't need to keep error display
            logger.debug(f"Clearing display after {operation_name}")
        # Otherwise leave the error message visible


class TransferContext:
    """Context manager for file transfers with error handling and cleanup."""
    
    def __init__(self, display=None, sound_manager=None, operation_name="Transfer"):
        """
        Initialize the transfer context.
        
        Args:
            display: Optional display interface for showing status messages
            sound_manager: Optional sound manager for playing status sounds
            operation_name: Name of the operation for logging and display
        """
        self.display = display
        self.sound_manager = sound_manager
        self.operation_name = operation_name
        self.temp_files: List[Path] = []
        
    def __enter__(self):
        if self.display:
            self.display.show_status(f"Starting: {self.operation_name}")
        logger.debug(f"Starting {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up and handle exceptions."""
        if exc_type:
            logger.error(f"Error in {self.operation_name}: {exc_val}", exc_info=True)
            
            if self.display:
                self.display.show_error(f"{self.operation_name} failed")
                
            if self.sound_manager:
                try:
                    self.sound_manager.play_error()
                except Exception as e:
                    logger.warning(f"Failed to play error sound: {e}")
            
            # Clean up any temporary files
            self._clean_up_temp_files()
            
            # Don't suppress the exception
            return False
            
        if self.display:
            self.display.show_status(f"Completed: {self.operation_name}")
            
        logger.debug(f"Completed {self.operation_name}")
        return False
    
    def _clean_up_temp_files(self):
        """Clean up any temporary files registered with this context."""
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    os.remove(temp_file)
                    logger.debug(f"Removed temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
    
    def register_temp_file(self, temp_file: Path):
        """
        Register a temporary file for cleanup if an exception occurs.
        
        Args:
            temp_file: Path to temporary file
        """
        self.temp_files.append(temp_file)


@contextmanager
def file_transfer(display=None, sound_manager=None, operation_name="File Transfer"):
    """
    Context manager specifically for file transfer operations.
    
    Args:
        display: Display interface for showing status
        sound_manager: Sound manager for playing status sounds
        operation_name: Name of the operation for logging
        
    Yields:
        TransferContext: Transfer context object with temp file tracking
    """
    context = TransferContext(display, sound_manager, operation_name)
    try:
        with context:
            yield context
    except Exception:
        # Exception already handled by TransferContext exit method
        raise


@contextmanager
def safe_file_operation(file_path: Path, mode='w', **kwargs):
    """
    Context manager for safely writing to files with atomic updates.
    
    Args:
        file_path: Path to the file
        mode: File open mode
        **kwargs: Additional keyword arguments for open()
        
    Yields:
        file object: Open file object
    """
    temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
    
    try:
        with open(temp_path, mode, **kwargs) as f:
            yield f
            
        # If we get here without exception, rename temp file to target
        if temp_path.exists():
            if file_path.exists():
                os.remove(file_path)
            os.rename(temp_path, file_path)
            
    except Exception:
        # Clean up temp file and re-raise
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_path}: {e}")
        raise 