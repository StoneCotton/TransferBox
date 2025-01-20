# src/core/path_utils.py

import os
import platform
import logging
import stat
from pathlib import Path
from typing import Union

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

def _check_unix_write_permission(path: Path) -> bool:
    """
    Check write permissions on Unix-like systems (macOS and Linux).
    Handles both existing paths and their parent directories.
    
    Args:
        path: Path to check for write permissions
        
    Returns:
        bool: True if write permission exists, False otherwise
    """
    try:
        # If path exists, check direct write permission
        if path.exists():
            return os.access(path, os.W_OK)
            
        # If path doesn't exist, check parent directory
        parent = path.parent
        while not parent.exists():
            parent = parent.parent
            if parent == parent.parent:  # Reached root
                break
                
        return os.access(parent, os.W_OK)
        
    except Exception as e:
        logger.error(f"Error checking Unix permissions: {e}")
        return False

def _validate_macos_path(path: Path, storage) -> Path:
    """
    Validate macOS-specific path requirements.
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If path is invalid
    """
    try:
        # For external drives on macOS, path should start with /Volumes/
        if not str(path).startswith('/Volumes/') and not str(path).startswith('/Users/'):
            raise ValueError("External drive paths must start with /Volumes/")
            
        # Get volume root (e.g., /Volumes/DriveName)
        volume_path = Path('/Volumes')
        if str(path).startswith('/Volumes/'):
            volume_name = path.parts[2]  # Get volume name
            volume_path = volume_path / volume_name
            
            # Check if volume exists
            if not volume_path.exists():
                raise ValueError(f"Volume not found: {volume_path}")
                
            # Check volume permissions
            if not _check_unix_write_permission(volume_path):
                raise ValueError(f"No write permission for volume: {volume_path}")
                
        # For user directory paths
        elif str(path).startswith('/Users/'):
            if not _check_unix_write_permission(path):
                raise ValueError(f"No write permission for path: {path}")
                
        # Check if we can write to the target directory or its parent
        if not _check_unix_write_permission(path):
            raise ValueError(f"No write permission for path: {path}")
            
        return path
        
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Invalid macOS path: {str(e)}")

def _validate_linux_path(path: Path, storage) -> Path:
    """
    Validate Linux-specific path requirements.
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If path is invalid
    """
    try:
        # Check if the path is absolute
        if not path.is_absolute():
            raise ValueError("Path must be absolute")
            
        # Check base mount point permissions
        mount_point = path
        while mount_point != mount_point.parent:
            if mount_point.is_mount():
                break
            mount_point = mount_point.parent
            
        if not _check_unix_write_permission(mount_point):
            raise ValueError(f"No write permission for mount point: {mount_point}")
            
        # Check target path permissions
        if path.exists() and not _check_unix_write_permission(path):
            raise ValueError(f"No write permission for path: {path}")
            
        # If path doesn't exist, check parent directory
        if not path.exists():
            parent = path.parent
            while not parent.exists():
                parent = parent.parent
            if not _check_unix_write_permission(parent):
                raise ValueError(f"No write permission for parent directory: {parent}")
                
        return path
        
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Invalid Linux path: {str(e)}")

def _validate_windows_path(path: Path, storage) -> Path:
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
        if not _check_windows_write_permission(path.drive + '\\'):
            raise ValueError(f"No write permission for drive: {path.drive}")
            
        return path
        
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Invalid Windows path: {str(e)}")

def sanitize_path(path_str: str) -> Path:
    """
    Sanitize a path string by handling escaped characters and normalizing it.
    
    Args:
        path_str: Raw path string that might contain escaped characters
        
    Returns:
        Path object representing a sanitized path
        
    Raises:
        ValueError: If the path is invalid or cannot be sanitized
    """
    try:
        # Remove any surrounding quotes (single or double)
        cleaned_path = path_str.strip("'\"")
        
        # Handle escaped spaces and special characters
        cleaned_path = cleaned_path.replace("\\ ", " ")
        cleaned_path = cleaned_path.replace("\\#", "#")
        cleaned_path = cleaned_path.replace("\\(", "(")
        cleaned_path = cleaned_path.replace("\\)", ")")
        cleaned_path = cleaned_path.replace("\\&", "&")
        
        # Convert to Path object
        path = Path(cleaned_path)
        
        # Platform-specific sanitization
        system = platform.system().lower()
        if system == 'windows':
            # Handle Windows drive letter consistency
            if len(cleaned_path) >= 2 and cleaned_path[1] == ':':
                drive_letter = cleaned_path[0].upper()
                rest_of_path = cleaned_path[2:]
                cleaned_path = f"{drive_letter}:{rest_of_path}"
            
            path = Path(cleaned_path.replace('/', '\\'))
            
            # Make absolute if not already
            if not path.is_absolute():
                current_dir = Path.cwd()
                path = current_dir / path
                
        elif system == 'darwin':
            # Handle macOS paths
            if not path.is_absolute():
                path = path.resolve()
                
            # Ensure /Volumes paths are preserved
            if str(cleaned_path).startswith('/Volumes/'):
                path = Path('/Volumes') / path.relative_to('/Volumes')
                
        else:  # Linux
            # Handle Linux paths
            if not path.is_absolute():
                path = path.resolve()
        
        return path
        
    except Exception as e:
        logger.error(f"Error sanitizing path '{path_str}': {e}")
        raise ValueError(f"Invalid path format: {path_str}")

def validate_destination_path(path: Path, storage) -> Path:
    """
    Validate a destination path for the current platform.
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        ValueError: If the path is invalid
    """
    try:
        system = platform.system().lower()
        
        # Dispatch to platform-specific validation
        if system == 'darwin':
            return _validate_macos_path(path, storage)
        elif system == 'windows':
            return _validate_windows_path(path, storage)
        elif system == 'linux':
            return _validate_linux_path(path, storage)
        else:
            raise ValueError(f"Unsupported platform: {system}")
            
    except Exception as e:
        logger.error(f"Error validating destination path '{path}': {e}")
        raise ValueError(str(e))