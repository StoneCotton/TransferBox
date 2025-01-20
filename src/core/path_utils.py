# src/core/path_utils.py

import os
import platform
import logging
from pathlib import Path
from typing import Union
from .interfaces.storage_inter import StorageInterface

logger = logging.getLogger(__name__)

def _check_windows_write_permission(path: Path) -> bool:
    """
    Check if the current user has write permission on Windows.
    Uses a more reliable approach by attempting to get write access token.
    
    Args:
        path: Path to check for write permissions
        
    Returns:
        bool: True if write permission exists, False otherwise
    """
    try:
        import win32security
        import ntsecuritycon as con
        import win32api
        
        # First try the simple access check
        if os.access(path, os.W_OK):
            return True
            
        try:
            # Get the security descriptor
            security = win32security.GetNamedSecurityInfo(
                str(path),
                win32security.SE_FILE_OBJECT,
                win32security.DACL_SECURITY_INFORMATION
            )
            
            # Get current user's token
            process_token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32security.TOKEN_QUERY
            )
            
            # Get user SID from token
            sid = win32security.GetTokenInformation(
                process_token,
                win32security.TokenUser
            )[0]
            
            # Get DACL from security descriptor
            dacl = security.GetSecurityDescriptorDacl()
            if dacl is None:
                return False
                
            # Check for write permission in ACEs
            for i in range(dacl.GetAceCount()):
                ace_type, ace_flag, ace_mask, ace_sid = dacl.GetAce(i)
                if ace_sid == sid and ace_mask & con.FILE_GENERIC_WRITE:
                    return True
                    
            return False
            
        except Exception as e:
            logger.debug(f"Detailed permission check failed, falling back to basic check: {e}")
            return os.access(path, os.W_OK)
            
    except ImportError as e:
        logger.debug(f"Windows security modules not available, using basic check: {e}")
        return os.access(path, os.W_OK)
    except Exception as e:
        logger.error(f"Error checking Windows permissions: {e}")
        return False

def _validate_windows_path(path: Path, storage: StorageInterface) -> Path:
    """Validate Windows-specific path requirements"""
    try:
        # Check for drive letter
        if not path.drive:
            raise ValueError("Windows paths must include a drive letter")
        
        # Split path into drive and remainder for separate validation
        drive_part = path.drive  # e.g., "C:"
        path_part = str(path)[len(drive_part):]  # Rest of the path
        
        # Check for invalid characters in path part only (not drive letter)
        invalid_chars = '<>"|?*'
        found_invalid = next((char for char in invalid_chars if char in path_part), None)
        if found_invalid:
            raise ValueError(f"Invalid character '{found_invalid}' in path")
        
        # Check drive accessibility and type
        try:
            import win32file
            drive_path = Path(path.drive + '\\')
            drive_type = win32file.GetDriveType(str(drive_path))
            if drive_type not in [win32file.DRIVE_FIXED, win32file.DRIVE_REMOVABLE]:
                drive_types = {
                    win32file.DRIVE_UNKNOWN: "Unknown",
                    win32file.DRIVE_NO_ROOT_DIR: "No Root Directory",
                    win32file.DRIVE_REMOVABLE: "Removable",
                    win32file.DRIVE_FIXED: "Fixed",
                    win32file.DRIVE_REMOTE: "Network",
                    win32file.DRIVE_CDROM: "CD-ROM",
                    win32file.DRIVE_RAMDISK: "RAM Disk"
                }
                type_name = drive_types.get(drive_type, f"Unknown Type ({drive_type})")
                raise ValueError(f"Drive {drive_path} is not a valid storage drive (Type: {type_name})")
        except ImportError:
            logger.warning("win32file not available - skipping drive type check")
            
        # Check write permissions
        drive_path = Path(path.drive + '\\')
        if not _check_windows_write_permission(drive_path):
            raise ValueError(f"No write permission for drive: {drive_path}")
            
        # If the path exists, check its write permission too
        if path.exists() and not _check_windows_write_permission(path):
            raise ValueError(f"No write permission for path: {path}")
            
        # If path doesn't exist, check parent directory
        if not path.exists():
            parent = path.parent
            while not parent.exists():
                parent = parent.parent
            if not _check_windows_write_permission(parent):
                raise ValueError(f"No write permission for parent directory: {parent}")
                
        return path
        
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Invalid Windows path: {str(e)}")

def sanitize_path(path_str: str) -> Path:
    """
    Sanitize a path string by handling escaped characters and normalizing it to an absolute path.
    
    Args:
        path_str: Raw path string that might contain escaped characters
        
    Returns:
        Path object representing an absolute path
        
    Raises:
        ValueError: If the path is invalid or cannot be converted to absolute
    """
    try:
        # Remove any surrounding quotes (single or double)
        cleaned_path = path_str.strip("'\"")
        
        # Handle escaped spaces and special characters from shell
        cleaned_path = cleaned_path.replace("\\ ", " ")
        cleaned_path = cleaned_path.replace("\\#", "#")
        cleaned_path = cleaned_path.replace("\\(", "(")
        cleaned_path = cleaned_path.replace("\\)", ")")
        cleaned_path = cleaned_path.replace("\\&", "&")
        
        # Convert to Path object
        path = Path(cleaned_path)
        
        # On Windows, ensure consistent path separator
        if os.name == 'nt':
            # Handle the case where the path starts with a drive letter
            if len(cleaned_path) >= 2 and cleaned_path[1] == ':':
                drive_letter = cleaned_path[0].upper()
                rest_of_path = cleaned_path[2:]
                cleaned_path = f"{drive_letter}:{rest_of_path}"
            
            path = Path(cleaned_path.replace('/', '\\'))
            
            # Make absolute if not already
            if not path.is_absolute():
                current_dir = Path.cwd()
                path = current_dir / path
            
        else:
            # For non-Windows, use standard Path resolution
            if not path.is_absolute():
                path = path.resolve()
        
        return path
        
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
        Path object representing validated absolute path
        
    Raises:
        ValueError: If the path is invalid for the current platform
    """
    try:
        if platform.system().lower() == 'windows':
            return _validate_windows_path(path, storage)
        else:
            # Non-Windows validation logic remains unchanged
            logger.error("Non-Windows platforms not handled in this code snippet")
            raise ValueError("Platform not supported in this example")
            
    except Exception as e:
        logger.error(f"Error validating destination path '{path}': {e}")
        raise ValueError(str(e))