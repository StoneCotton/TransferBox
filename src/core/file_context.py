# src/core/file_context.py

import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Callable, Any

from .exceptions import FileTransferError, ChecksumError, StorageError

logger = logging.getLogger(__name__)

class FileOperationContext:
    """Context manager for file operations with standardized error handling."""
    
    def __init__(self, display=None, sound_manager=None):
        """
        Initialize the context manager.
        
        Args:
            display: Optional display interface for showing status messages
            sound_manager: Optional sound manager for playing status sounds
        """
        self.display = display
        self.sound_manager = sound_manager
        self.temp_files = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up any temporary files if an exception occurred."""
        if exc_type:
            self._handle_exception(exc_type, exc_val)
            self._clean_up_temp_files()
            if self.sound_manager:
                try:
                    self.sound_manager.play_error()
                except Exception as e:
                    logger.warning(f"Failed to play error sound: {e}")
            return True  # Suppress the exception
        return False
    
    def _handle_exception(self, exc_type, exc_val):
        """Handle exceptions in a standardized way."""
        if isinstance(exc_val, FileTransferError):
            # Already a FileTransferError, just log and display
            logger.error(f"Transfer error: {exc_val}")
            if self.display:
                self.display.show_error(str(exc_val))
        elif isinstance(exc_val, (OSError, IOError)):
            # Convert to FileTransferError for better error messages
            error_msg = f"I/O error: {exc_val}"
            logger.error(error_msg)
            if self.display:
                self.display.show_error("I/O Error")
        else:
            # Other exceptions
            error_msg = f"Unexpected error: {exc_val}"
            logger.error(error_msg, exc_info=True)
            if self.display:
                self.display.show_error("Unexpected Error")
    
    def _clean_up_temp_files(self):
        """Clean up any temporary files registered with this context."""
        for temp_file in self.temp_files:
            try:
                if isinstance(temp_file, Path) and temp_file.exists():
                    temp_file.unlink()
                    logger.info(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
    
    def register_temp_file(self, temp_file: Path):
        """
        Register a temporary file for cleanup in case of errors.
        
        Args:
            temp_file: Path to the temporary file
        """
        self.temp_files.append(temp_file)
        
    def validate_source(self, path: Path) -> bool:
        """
        Validate that source file exists and is readable.
        
        Args:
            path: Source file path
            
        Returns:
            bool: True if source file exists and is readable
            
        Raises:
            FileTransferError: If source file doesn't exist or isn't readable
        """
        if not path.exists():
            raise FileTransferError(f"Source file does not exist: {path}", source=path)
        if not path.is_file():
            raise FileTransferError(f"Source is not a file: {path}", source=path)
        return True
        
    def prepare_copy(self, src_path: Path):
        """
        Prepare for file copy operation.
        
        Args:
            src_path: Source file path
            
        Returns:
            tuple: (file_size, hash_object)
            
        Raises:
            FileTransferError: If preparation fails
        """
        try:
            # Get file size
            file_size = src_path.stat().st_size
            
            # Initialize hash calculator (needs to be implemented or imported)
            from .checksum import ChecksumCalculator
            calculator = ChecksumCalculator(self.display)
            xxh64_hash = calculator.create_hash()
            
            return file_size, xxh64_hash
        except OSError as e:
            raise FileTransferError(f"Failed to prepare for copy: {e}", source=src_path, error_type="io")


@contextmanager
def file_operation(display=None, sound_manager=None, operation_name="File Operation"):
    """
    Context manager for general file operations.
    
    Args:
        display: Optional display interface
        sound_manager: Optional sound manager
        operation_name: Name of the operation for logging
        
    Yields:
        None
        
    Raises:
        FileTransferError: Converted from other exceptions
    """
    logger.debug(f"Starting {operation_name}")
    try:
        yield
        logger.debug(f"Completed {operation_name}")
    except FileTransferError:
        # Re-raise FileTransferError as is
        if sound_manager:
            try:
                sound_manager.play_error()
            except Exception as sound_err:
                logger.warning(f"Failed to play error sound: {sound_err}")
        raise
    except Exception as e:
        # Convert other exceptions to FileTransferError
        logger.error(f"Error in {operation_name}: {e}", exc_info=True)
        if sound_manager:
            try:
                sound_manager.play_error()
            except Exception as sound_err:
                logger.warning(f"Failed to play error sound: {sound_err}")
        raise FileTransferError(f"Error in {operation_name}: {str(e)}", error_type="io") from e


def error_handler(func):
    """
    Decorator for standardized error handling in file operations.
    
    Args:
        func: Function to decorate
        
    Returns:
        Wrapped function with error handling
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileTransferError:
            # Re-raise FileTransferError as is
            raise
        except OSError as e:
            # Convert OSError to FileTransferError
            logger.error(f"OS error in {func.__name__}: {e}")
            raise FileTransferError(f"I/O error: {str(e)}", error_type="io") from e
        except Exception as e:
            # Convert other exceptions to FileTransferError
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise FileTransferError(f"Unexpected error: {str(e)}") from e
    return wrapper 