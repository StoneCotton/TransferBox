# src/core/utils.py

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

def ensure_directory(path: Path) -> Path:
    """
    Ensure directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Returns:
        Path: Same path that was passed in
        
    Raises:
        OSError: If directory cannot be created
    """
    path.mkdir(parents=True, exist_ok=True)
    return path

def safe_copy(source: Path, destination: Path, temp_extension: str = ".tmp") -> bool:
    """
    Safely copy a file using a temporary file during copy.
    
    Args:
        source: Source file path
        destination: Destination file path
        temp_extension: Extension to use for temporary file
        
    Returns:
        bool: True if copy was successful, False otherwise
    """
    temp_path = destination.with_suffix(temp_extension)
    try:
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy to temporary file first
        shutil.copy2(source, temp_path)
        
        # Move temporary file to final destination
        if destination.exists():
            os.remove(destination)
        os.rename(temp_path, destination)
        return True
    except Exception as e:
        logger.error(f"Failed to copy {source} to {destination}: {e}")
        # Clean up temporary file if it exists
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False

def format_size(size_bytes: int) -> str:
    """
    Format byte size into human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.23 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def is_media_file(file_path: Path, media_extensions: List[str]) -> bool:
    """
    Check if file is a media file based on extension.
    
    Args:
        file_path: Path to file
        media_extensions: List of media file extensions (with dot, e.g., ['.mp4', '.jpg'])
        
    Returns:
        bool: True if file has a media extension, False otherwise
    """
    return file_path.suffix.lower() in media_extensions

def get_platform() -> str:
    """
    Get current platform identifier.
    
    Returns:
        str: Platform identifier ("darwin", "windows", "raspberry_pi", "linux")
    """
    import platform as plt
    system = plt.system().lower()
    
    if system == "darwin":
        return "darwin"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        # Check if running on Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'raspberry pi' in model.lower():
                    return "raspberry_pi"
        except Exception:
            pass
        return "linux"
    else:
        return system

def validate_path(path: Path, must_exist: bool = True, must_be_dir: bool = False, 
                must_be_writable: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a path with various conditions.
    
    Args:
        path: Path to validate
        must_exist: Whether path must exist
        must_be_dir: Whether path must be a directory
        must_be_writable: Whether path must be writable
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if path is None:
        return False, "Path is None"
        
    try:
        # Convert to Path if it's a string
        if isinstance(path, str):
            path = Path(path)
            
        # Check existence
        if must_exist and not path.exists():
            return False, f"Path does not exist: {path}"
            
        # Check if directory
        if must_be_dir and path.exists() and not path.is_dir():
            return False, f"Path is not a directory: {path}"
            
        # Check write access
        if must_be_writable:
            if path.exists():
                if not os.access(path, os.W_OK):
                    return False, f"No write permission for: {path}"
            else:
                # Check parent directory
                parent = path.parent
                if not parent.exists():
                    return False, f"Parent directory does not exist: {parent}"
                if not os.access(parent, os.W_OK):
                    return False, f"No write permission for parent directory: {parent}"
                    
        return True, None
        
    except Exception as e:
        return False, f"Error validating path: {e}"

def generate_unique_path(base_path: Path, separator: str = "_") -> Path:
    """
    Generate a unique path by appending numbers if the path already exists.
    
    Args:
        base_path: Base path to start with
        separator: Separator to use between basename and counter
        
    Returns:
        Path: Unique path that doesn't exist
    """
    if not base_path.exists():
        return base_path
        
    counter = 1
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    
    while True:
        unique_path = parent / f"{stem}{separator}{counter}{suffix}"
        if not unique_path.exists():
            return unique_path
        counter += 1

def get_file_size(path: Path) -> int:
    """
    Get file size with error handling.
    
    Args:
        path: Path to file
        
    Returns:
        int: File size in bytes, or 0 if error
    """
    try:
        return path.stat().st_size
    except Exception as e:
        logger.error(f"Error getting file size for {path}: {e}")
        return 0

def get_directory_size(path: Path) -> int:
    """
    Get directory size by summing all files.
    
    Args:
        path: Path to directory
        
    Returns:
        int: Total size in bytes
    """
    total_size = 0
    try:
        for entry in path.glob('**/*'):
            if entry.is_file():
                total_size += get_file_size(entry)
        return total_size
    except Exception as e:
        logger.error(f"Error calculating directory size for {path}: {e}")
        return 0 