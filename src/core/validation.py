"""
Centralized validation utilities for TransferBox.
Eliminates duplication of validation logic across modules.
"""
import os
import logging
from pathlib import Path
from typing import Tuple, Optional, Union
from .exceptions import FileTransferError, ValidationError

logger = logging.getLogger(__name__)

class ErrorMessages:
    """Centralized error message definitions."""
    
    # Path validation errors
    PATH_NONE = "No path provided"
    PATH_INVALID_TYPE = "Invalid path type"
    PATH_NOT_EXIST = "Path does not exist"
    PATH_NOT_DIRECTORY = "Path is not a directory"
    PATH_NOT_WRITABLE = "No write permission"
    PARENT_NOT_EXIST = "Parent directory missing"
    PARENT_NOT_WRITABLE = "Parent directory not writable"
    CREATE_FAILED = "Failed to create directory"
    
    # Source validation errors
    SOURCE_NOT_MOUNTED = "Source drive not mounted"
    SOURCE_REMOVED = "Source removed"
    SOURCE_NOT_FOUND = "Source not found"
    SOURCE_ERROR = "Source Error"
    
    # Transfer errors
    TRANSFER_FAILED = "Transfer failed"
    TRANSFER_ERROR = "Transfer error"
    UNMOUNT_FAILED = "Unmount failed"
    NO_FILES_FOUND = "No Files Found"
    NO_MEDIA_FOUND = "No Media Found"
    NOT_ENOUGH_SPACE = "Not enough space"
    
    # System errors
    IN_UTILITY_MODE = "In utility mode"
    IMPORT_ERROR = "Import Error"
    CRITICAL_ERROR = "Critical Error"

class ValidationResult:
    """Encapsulates validation results for better error handling."""
    
    def __init__(self, is_valid: bool, error_message: Optional[str] = None, 
                 sanitized_path: Optional[Path] = None):
        self.is_valid = is_valid
        self.error_message = error_message
        self.sanitized_path = sanitized_path

class PathValidator:
    """Centralized path validation with consistent error messages."""
    
    @classmethod
    def validate_destination(cls, path: Union[str, Path, None], 
                           auto_create: bool = True) -> ValidationResult:
        """
        Comprehensive destination path validation.
        
        Args:
            path: Path to validate
            auto_create: Whether to auto-create directory if it doesn't exist
            
        Returns:
            ValidationResult with validation outcome
        """
        # Type validation
        if path is None:
            return ValidationResult(False, ErrorMessages.PATH_NONE)
            
        # Check for valid types before conversion
        if not isinstance(path, (str, Path)):
            return ValidationResult(False, ErrorMessages.PATH_INVALID_TYPE)
            
        try:
            dest_path = Path(path) if isinstance(path, str) else path
        except Exception:
            return ValidationResult(False, ErrorMessages.PATH_INVALID_TYPE)
            
        if not str(dest_path).strip():
            return ValidationResult(False, ErrorMessages.PATH_INVALID_TYPE)
            
        # Existing path validation
        if dest_path.exists():
            if not dest_path.is_dir():
                return ValidationResult(False, ErrorMessages.PATH_NOT_DIRECTORY)
            if not os.access(dest_path, os.W_OK):
                return ValidationResult(False, ErrorMessages.PATH_NOT_WRITABLE)
            return ValidationResult(True, sanitized_path=dest_path)
            
        # Non-existing path validation
        parent = dest_path.parent
        if not parent.exists():
            return ValidationResult(False, ErrorMessages.PARENT_NOT_EXIST)
        if not os.access(parent, os.W_OK):
            return ValidationResult(False, ErrorMessages.PARENT_NOT_WRITABLE)
            
        # Auto-create if requested
        if auto_create:
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                return ValidationResult(True, sanitized_path=dest_path)
            except Exception:
                return ValidationResult(False, ErrorMessages.CREATE_FAILED)
                
        return ValidationResult(True, sanitized_path=dest_path)
    
    @classmethod
    def validate_source(cls, path: Union[str, Path, None], 
                       check_mounted: bool = True) -> ValidationResult:
        """
        Comprehensive source path validation.
        
        Args:
            path: Path to validate
            check_mounted: Whether to check if path is mounted (for removable drives)
            
        Returns:
            ValidationResult with validation outcome
        """
        if path is None:
            return ValidationResult(False, ErrorMessages.PATH_NONE)
            
        # Check for valid types before conversion
        if not isinstance(path, (str, Path)):
            return ValidationResult(False, ErrorMessages.PATH_INVALID_TYPE)
            
        try:
            source_path = Path(path) if isinstance(path, str) else path
        except Exception:
            return ValidationResult(False, ErrorMessages.PATH_INVALID_TYPE)
            
        if not source_path.exists():
            return ValidationResult(False, ErrorMessages.PATH_NOT_EXIST)
            
        if check_mounted and hasattr(os, 'path') and hasattr(os.path, 'ismount'):
            if not os.path.ismount(str(source_path)):
                return ValidationResult(False, ErrorMessages.SOURCE_NOT_MOUNTED)
                
        return ValidationResult(True, sanitized_path=source_path)

class DriveValidator:
    """Specialized validation for removable drives."""
    
    @staticmethod
    def is_drive_accessible(drive_path: Path) -> bool:
        """Check if drive is still accessible (not removed)."""
        return (drive_path.exists() and 
                os.path.ismount(str(drive_path)) if hasattr(os.path, 'ismount') else True)
    
    @staticmethod
    def check_drive_removed(drive_path: Path) -> bool:
        """Check if drive has been removed."""
        return not DriveValidator.is_drive_accessible(drive_path) 