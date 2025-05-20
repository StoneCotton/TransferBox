# src/core/path_utils.py

import os
import platform
import logging
import stat
import urllib.parse
from pathlib import Path
from typing import Union, Tuple, Optional
from .exceptions import StorageError, FileTransferError
import re

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
        StorageError: If path is invalid or inaccessible
    """
    try:
        # Handle paths starting with /Users/
        if str(path).startswith('/Users/'):
            if not _check_unix_write_permission(path):
                # If path doesn't exist, check parent directory
                if not path.exists():
                    parent = path.parent
                    while not parent.exists():
                        parent = parent.parent
                    if not _check_unix_write_permission(parent):
                        raise StorageError(
                            f"No write permission for parent directory: {parent}",
                            path=parent,
                            error_type="permission"
                        )
                else:
                    raise StorageError(
                        f"No write permission for path: {path}",
                        path=path,
                        error_type="permission"
                    )
            return path

        # For external drives on macOS, path should start with /Volumes/
        if not str(path).startswith('/Volumes/'):
            raise StorageError(
                "External drive paths must start with /Volumes/",
                path=path,
                error_type="mount"
            )
            
        # Get volume root (e.g., /Volumes/DriveName)
        volume_path = Path('/Volumes')
        volume_name = path.parts[2]  # Get volume name
        volume_path = volume_path / volume_name
            
        # Check if volume exists
        if not volume_path.exists():
            raise StorageError(
                f"Volume not found: {volume_path}",
                path=volume_path,
                error_type="mount"
            )
            
        # Check volume permissions
        if not _check_unix_write_permission(volume_path):
            raise StorageError(
                f"No write permission for volume: {volume_path}",
                path=volume_path,
                error_type="permission"
            )
            
        # Check if we can write to the target directory or its parent
        if not _check_unix_write_permission(path):
            if not path.exists():
                parent = path.parent
                while not parent.exists():
                    parent = parent.parent
                if not _check_unix_write_permission(parent):
                    raise StorageError(
                        f"No write permission for parent directory: {parent}",
                        path=parent,
                        error_type="permission"
                    )
            else:
                raise StorageError(
                    f"No write permission for path: {path}",
                    path=path,
                    error_type="permission"
                )
            
        return path
        
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Invalid macOS path: {str(e)}", path=path)

def _validate_linux_path(path: Path, storage) -> Path:
    """
    Validate Linux/Raspberry Pi specific path requirements with improved handling.
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        StorageError: If path is invalid or inaccessible
    """
    try:
        # Ensure path is absolute
        if not path.is_absolute():
            raise StorageError("Path must be absolute", path=path)

        # Handle /media paths specifically
        if str(path).startswith('/media/'):
            parts = str(path).split('/')
            if len(parts) >= 4:
                # Verify the media path structure
                user_name = parts[2]
                volume_name = parts[3]
                
                # Check if the user directory exists
                user_path = Path('/media') / user_name
                if not user_path.exists():
                    raise StorageError(
                        f"Media user path not found: {user_path}",
                        path=user_path,
                        error_type="mount"
                    )
                
                # For volume paths, be more lenient as they might not exist yet
                volume_path = user_path / volume_name
                if volume_path.exists() and not os.access(volume_path, os.W_OK):
                    raise StorageError(
                        f"No write permission for volume: {volume_path}",
                        path=volume_path,
                        error_type="permission"
                    )

        # Check mount point permissions
        mount_point = path
        while mount_point != mount_point.parent:
            if mount_point.is_mount():
                break
            mount_point = mount_point.parent

        if not os.access(mount_point, os.W_OK):
            raise StorageError(
                f"No write permission for mount point: {mount_point}",
                path=mount_point,
                error_type="permission"
            )

        # If path exists, check direct permissions
        if path.exists() and not os.access(path, os.W_OK):
            raise StorageError(
                f"No write permission for path: {path}",
                path=path,
                error_type="permission"
            )

        # If path doesn't exist, check parent directory
        if not path.exists():
            parent = path.parent
            while not parent.exists():
                parent = parent.parent
            if not os.access(parent, os.W_OK):
                raise StorageError(
                    f"No write permission for parent directory: {parent}",
                    path=parent,
                    error_type="permission"
                )

        return path

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Invalid Linux path: {str(e)}", path=path)

def _validate_windows_path(path: Path, storage) -> Path:
    """
    Validate Windows-specific path requirements
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        StorageError: If path is invalid or inaccessible
    """
    try:
        # Check for drive letter
        if not path.drive:
            raise StorageError(
                "Windows paths must include a drive letter",
                path=path,
                error_type="mount"
            )
        
        # Split path into drive and remainder for separate validation
        drive_part = path.drive  # e.g., "C:"
        path_part = str(path)[len(drive_part):]  # Rest of the path
        
        # Check for invalid characters in path part only (not drive letter)
        invalid_chars = '<>"|?*'
        found_invalid = next((char for char in invalid_chars if char in path_part), None)
        if found_invalid:
            raise StorageError(
                f"Invalid character '{found_invalid}' in path",
                path=path
            )
        
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
                raise StorageError(
                    f"Drive {drive_path} is not a valid storage drive (Type: {type_name})",
                    path=drive_path,
                    error_type="mount"
                )
        except ImportError:
            logger.warning("win32file not available - skipping drive type check")
            
        # Check write permissions
        if not _check_windows_write_permission(path.drive + '\\'):
            raise StorageError(
                f"No write permission for drive: {path.drive}",
                path=Path(path.drive),
                error_type="permission"
            )
            
        return path
        
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"Invalid Windows path: {str(e)}", path=path)

def sanitize_path(path_str: str) -> Path:
    """
    Sanitize a path string with improved handling of special characters.
    
    Args:
        path_str: Raw path string that might contain special characters
        
    Returns:
        Path object representing a sanitized path
        
    Raises:
        FileTransferError: If the path is invalid or cannot be sanitized
    """
    try:
        # First, handle any URL-encoded characters
        try:
            # Try to decode any percent-encoded or hex-encoded characters
            decoded_path = urllib.parse.unquote(path_str)
            # Also handle \x encoded characters
            decoded_path = bytes(decoded_path, 'utf-8').decode('unicode_escape')
        except Exception as e:
            logger.debug(f"Path decoding failed, using original: {e}")
            decoded_path = path_str

        # Remove any surrounding quotes
        cleaned_path = decoded_path.strip("'\"")

        # Platform-specific handling
        system = platform.system().lower()
        if system == 'darwin':  # macOS specific handling
            # Handle special characters that could cause issues on macOS
            cleaned_path = cleaned_path.replace("\\ ", " ")  # Convert escaped spaces
            cleaned_path = cleaned_path.replace("\\#", "#")
            cleaned_path = cleaned_path.replace("\\(", "(")
            cleaned_path = cleaned_path.replace("\\)", ")")
            cleaned_path = cleaned_path.replace("\\&", "&")
            
            # Handle /Volumes paths properly
            if cleaned_path.startswith('/Volumes/'):
                # Keep path as is for /Volumes paths
                pass
        elif system == 'linux':  # Includes Raspberry Pi
            # For Linux/Raspberry Pi, handle spaces and special characters
            cleaned_path = cleaned_path.replace("\\ ", " ")  # Convert escaped spaces
            cleaned_path = cleaned_path.replace("\\#", "#")
            cleaned_path = cleaned_path.replace("\\(", "(")
            cleaned_path = cleaned_path.replace("\\)", ")")
            cleaned_path = cleaned_path.replace("\\&", "&")
            
            # Ensure media paths are properly formatted
            if cleaned_path.startswith('/media/'):
                parts = cleaned_path.split('/')
                if len(parts) >= 4:  # /media/user/volume/...
                    # Ensure the volume name is properly handled
                    volume_name = parts[3]
                    parts[3] = volume_name.replace('\\x20', ' ')
                    cleaned_path = '/'.join(parts)

        elif system == 'windows':
            # Handle Windows-specific path issues
            if len(cleaned_path) >= 2 and cleaned_path[1] == ':':
                drive_letter = cleaned_path[0].upper()
                rest_of_path = cleaned_path[2:]
                cleaned_path = f"{drive_letter}:{rest_of_path}"
            
            # Convert forward slashes to backslashes for Windows
            cleaned_path = cleaned_path.replace('/', '\\')

        # Convert to Path object
        path = Path(cleaned_path)

        # Make absolute if not already
        if not path.is_absolute():
            path = path.resolve()

        logger.debug(f"Sanitized path: {str(path)}")
        return path

    except Exception as e:
        logger.error(f"Error sanitizing path '{path_str}': {e}")
        raise FileTransferError(
            f"Invalid path format: {path_str}",
            error_type="io"
        )

def validate_destination_path(path: Path, storage) -> Path:
    """
    Validate a destination path for the current platform.
    
    Args:
        path: Path to validate
        storage: StorageInterface instance
        
    Returns:
        Validated Path object
        
    Raises:
        StorageError: If the path is invalid or inaccessible
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
            raise StorageError(
                f"Unsupported platform: {system}",
                error_type="mount"
            )
            
    except StorageError:
        raise
    except Exception as e:
        logger.error(f"Error validating destination path '{path}': {e}")
        raise StorageError(str(e), path=path)

def get_safe_path(unsafe_path: Union[str, Path]) -> Path:
    """
    Convert any path string to a safe Path object.
    This is a convenience function that combines sanitization and validation.
    
    Args:
        unsafe_path: Raw path string or Path object that might contain special characters
        
    Returns:
        Safe Path object
        
    Raises:
        FileTransferError: If the path cannot be safely converted
    """
    try:
        # First sanitize the path
        if isinstance(unsafe_path, str):
            path = sanitize_path(unsafe_path)
        else:
            path = unsafe_path

        # Ensure it's absolute
        if not path.is_absolute():
            path = path.resolve()

        # Log the conversion for debugging
        logger.debug(f"Converted path: {unsafe_path} -> {path}")
        return path

    except Exception as e:
        logger.error(f"Error converting path: {e}")
        raise FileTransferError(
            f"Cannot safely convert path: {unsafe_path}",
            error_type="io"
        )

def is_plausible_user_path(path_str: str) -> tuple[bool, str | None]:
    """
    Check if a user input string is a plausible absolute path for the current platform.
    Returns (True, None) if plausible, (False, reason) if not.
    Only allows:
      - Absolute paths (macOS/Linux: /..., Windows: C:\..., C:/...)
      - UNC/network paths (Windows: \\...)
    Disallows relative, single-word, or nonsense input.
    Accepts paths wrapped in single or double quotes (e.g., from macOS Copy as Pathname).
    """
    if not isinstance(path_str, str):
        return False, "Input is not a string."
    s = path_str.strip()
    # Strip leading/trailing single or double quotes
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1].strip()
    if not s:
        return False, "Path cannot be empty."
    # Only slashes/backslashes
    if all(c in '/\\' for c in s):
        return False, "Path must contain directory or file name."
    # Only special characters (not alphanumeric, not . or _ or -)
    if not re.search(r'[\w\.-]', s):
        return False, "Path must contain at least one alphanumeric or valid character."
    system = platform.system().lower()
    # macOS/Linux: must be absolute (start with /)
    if system in ('darwin', 'linux'):
        if not s.startswith('/'):
            return False, "Path must be an absolute path starting with '/'."
        return True, None
    # Windows: allow drive letter, UNC, or absolute
    if system == 'windows':
        # UNC/network path
        if s.startswith('\\\\'):
            return True, None
        # Drive letter path (C:\ or C:/)
        if re.match(r'^[a-zA-Z]:[\\/]', s):
            return True, None
        # Absolute path with forward slash (e.g., /Users/...)
        if s.startswith('/'):
            return True, None
        return False, "Path must be an absolute path (C:\\..., C:/..., \\server\\..., or /...)."
    # Fallback: require absolute
    if not os.path.isabs(s):
        return False, "Path must be absolute."
    return True, None