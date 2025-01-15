import os
import platform
import logging
from pathlib import Path
from typing import Union
from .interfaces.storage import StorageInterface

logger = logging.getLogger(__name__)

def sanitize_path(path_str: str) -> Path:
    """
    Sanitize a path string by removing quotes and normalizing it to an absolute path.
    
    Args:
        path_str: Raw path string that might contain quotes
        
    Returns:
        Path object representing an absolute path
        
    Raises:
        ValueError: If the path is invalid or cannot be converted to absolute
    """
    try:
        # Remove any surrounding quotes (single or double)
        cleaned_path = path_str.strip("'\"")
        
        # Convert to Path object
        path = Path(cleaned_path)
        
        # Resolve any relative path components and convert to absolute
        if not path.is_absolute():
            raise ValueError(f"Path must be absolute: {path_str}")
            
        # Normalize the path (resolve any .. or . components)
        normalized_path = path.resolve()
        
        # On Windows, ensure consistent path separator
        if os.name == 'nt':
            normalized_path = Path(str(normalized_path).replace('/', '\\'))
            
        return normalized_path
        
    except Exception as e:
        logger.error(f"Error sanitizing path '{path_str}': {e}")
        raise ValueError(f"Invalid path format: {path_str}")

def validate_destination_path(path: Path, storage: StorageInterface) -> Path:
    """
    Validate a destination path and ensure it's properly formatted for the current platform.
    
    Args:
        path: Path to validate
        storage: StorageInterface implementation for the current platform
        
    Returns:
        Validated and normalized Path object
        
    Raises:
        ValueError: If the path is invalid for the current platform
    """
    try:
        # Handle platform-specific path validation
        if platform.system().lower() == 'darwin':
            # For macOS, ensure paths to external drives start with /Volumes/
            if not str(path).startswith('/Volumes/'):
                raise ValueError("External drive paths must start with /Volumes/")
                
            # For macOS, get the volume root (e.g., /Volumes/BM-INACTIVE)
            volume_path = Path('/Volumes') / path.relative_to('/Volumes').parts[0]
            drive_path = volume_path
            
        elif platform.system().lower() == 'windows':
            # For Windows, ensure path has a drive letter
            if not path.drive:
                raise ValueError("Windows paths must include a drive letter")
            # For Windows, use the drive root
            drive_path = Path(path.drive + '\\')
        else:
            # For other platforms (like Raspberry Pi), use the root of the path
            drive_path = path.anchor
            
        # Check if the drive/volume exists and is accessible
        if not drive_path.exists():
            raise ValueError(f"Drive/volume not found: {drive_path}")
            
        # Check if we have permission to write to the drive
        try:
            if not os.access(drive_path, os.W_OK):
                raise ValueError(f"No write permission for drive: {drive_path}")
                
            # Also check the target directory if it exists
            if path.exists() and not os.access(path, os.W_OK):
                raise ValueError(f"No write permission for destination: {path}")
                
            # If target directory doesn't exist, check parent directories until we find one that exists
            parent_path = path.parent
            while not parent_path.exists():
                parent_path = parent_path.parent
            if not os.access(parent_path, os.W_OK):
                raise ValueError(f"No write permission for parent directory: {parent_path}")
                
        except OSError as e:
            # Handle access check failures
            logger.error(f"Error checking permissions: {e}")
            raise ValueError(f"Cannot verify permissions for path: {path}")
            
        return path
        
    except Exception as e:
        logger.error(f"Error validating destination path '{path}': {e}")
        raise ValueError(str(e))