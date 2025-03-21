# src/core/transfer_utils.py

import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import sys

from .exceptions import FileTransferError, StorageError

logger = logging.getLogger(__name__)


def get_transferable_files(source_path: Path, media_only: bool = False, 
                        media_extensions: List[str] = None) -> List[Path]:
    """
    Get a list of files to transfer from a source path.
    
    Args:
        source_path: Root directory to scan for files
        media_only: Whether to only include media files
        media_extensions: List of media file extensions to include if media_only is True
        
    Returns:
        List of Path objects for files to transfer
        
    Raises:
        FileTransferError: If source path is invalid or inaccessible
    """
    files_to_transfer = []
    ignored_files = 0
    permission_errors = 0
    
    if not source_path.is_dir():
        raise FileTransferError(f"Source path is not a directory: {source_path}", source=source_path)
        
    if not os.access(str(source_path), os.R_OK):
        raise FileTransferError(f"No read permission for source: {source_path}", source=source_path)
    
    # Default media extensions if not provided
    if media_only and not media_extensions:
        media_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.tif', '.raw', '.arw', '.cr2', '.nef',
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.mp3', '.wav', '.aac', '.flac'
        ]
    
    try:
        for path in source_path.rglob('*'):
            # Skip directories and hidden files
            if path.is_dir() or path.name.startswith('.'):
                continue
                
            # Skip system directories
            if 'System Volume Information' in str(path):
                ignored_files += 1
                continue
                
            # Apply media filter if configured
            if media_only:
                if any(path.name.lower().endswith(ext) for ext in media_extensions):
                    files_to_transfer.append(path)
                else:
                    ignored_files += 1
            else:
                files_to_transfer.append(path)
                
    except PermissionError as e:
        permission_errors += 1
        logger.warning(f"Permission denied: {e}")
    except Exception as e:
        logger.error(f"Error scanning for files: {e}")
        raise FileTransferError(f"Error scanning for files: {e}", source=source_path)
    
    # Log summary statistics
    logger.info(f"Found {len(files_to_transfer)} files to transfer, ignored {ignored_files} files")
    if permission_errors > 0:
        logger.warning(f"Encountered {permission_errors} permission errors during scan")
    
    return files_to_transfer


def calculate_transfer_totals(files: List[Path]) -> Tuple[List[Path], int, int]:
    """
    Calculate total size and count of files to transfer.
    
    Args:
        files: List of files to transfer
        
    Returns:
        Tuple of (valid_files, total_size, total_files):
            valid_files: List of valid files to transfer
            total_size: Total size of files in bytes
            total_files: Total number of files
    """
    total_size = 0
    valid_files = []
    
    for f in files:
        try:
            size = f.stat().st_size
            total_size += size
            valid_files.append(f)
        except (FileNotFoundError, PermissionError) as e:
            # File disappeared or became inaccessible
            logger.warning(f"File {f} skipped: {e}")
            continue
    
    total_files = len(valid_files)
    
    logger.info(f"Total files to transfer: {total_files}")
    logger.info(f"Total transfer size: {total_size / (1024*1024*1024):.2f} GB")
    
    return valid_files, total_size, total_files


def create_destination_path(source_path: Path, target_dir: Path, source_root: Path,
                         rename_with_timestamp: bool = False,
                         preserve_original_filename: bool = True,
                         timestamp_format: str = "%Y%m%d_%H%M%S",
                         filename_template: str = "{original}_{timestamp}") -> Path:
    """
    Create the destination path for a file, maintaining directory structure if needed.
    
    Args:
        source_path: Source file path
        target_dir: Target directory root
        source_root: Source directory root
        rename_with_timestamp: Whether to rename with timestamp
        preserve_original_filename: Whether to preserve original filename
        timestamp_format: Format for timestamp
        filename_template: Template for filename with timestamp
        
    Returns:
        Destination file path
    """
    try:
        # Get original filename and extension
        original_name = source_path.stem
        extension = source_path.suffix
        
        # Get the new filename according to configuration
        if rename_with_timestamp:
            # Get file creation time
            stat_info = source_path.stat()
            possible_times = [
                stat_info.st_ctime,  # Creation time (Windows) / Status change time (Unix)
                stat_info.st_mtime,  # Modification time
                stat_info.st_atime   # Access time
            ]
            creation_time = min(possible_times)
            
            # Format timestamp
            timestamp = datetime.fromtimestamp(creation_time).strftime(timestamp_format)
            
            # Build the new filename based on the template
            if preserve_original_filename:
                new_name = filename_template.format(
                    original=original_name,
                    timestamp=timestamp
                )
                new_filename = f"{new_name}{extension}"
            else:
                # Just use timestamp if we're not preserving original name
                new_filename = f"{timestamp}{extension}"
        else:
            new_filename = source_path.name
        
        # Get the relative path from the source root
        try:
            rel_path = source_path.relative_to(source_root)
            # Get just the directory part, excluding the filename
            rel_dir = rel_path.parent
        except ValueError:
            # Fallback if relative_to fails
            rel_dir = Path()
        
        # Combine target directory with relative directory and new filename
        dest_path = target_dir / rel_dir / new_filename
        
        # Ensure parent directories exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        return dest_path
        
    except Exception as e:
        logger.error(f"Error creating destination path: {e}")
        # Fallback to simple path in target directory
        return target_dir / source_path.name


def create_directory_structure(files: List[Path], source_path: Path, target_dir: Path) -> bool:
    """
    Create directory structure for preserving folders.
    
    Args:
        files: List of files to transfer
        source_path: Source root path
        target_dir: Target root path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        required_directories = set()
        for file_path in files:
            try:
                rel_path = file_path.parent.relative_to(source_path)
                target_path = target_dir / rel_path
                required_directories.add(target_path)
            except ValueError:
                # Skip if relative_to fails
                continue
            
        for dir_path in sorted(required_directories):
            dir_path.mkdir(parents=True, exist_ok=True)
            
        return True
    except Exception as e:
        logger.error(f"Failed to create directory structure: {e}")
        return False


def validate_source_path(source_path: Path) -> bool:
    """
    Validate that a source path is accessible.
    
    Args:
        source_path: Path to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        if not source_path.exists():
            logger.error(f"Source path does not exist: {source_path}")
            return False
        
        # Check if path is mounted for removable drives
        if sys.platform != 'win32':  # Unix-like systems
            try:
                if not os.path.ismount(str(source_path)):
                    logger.error(f"Source path is not mounted: {source_path}")
                    return False
            except Exception as e:
                logger.warning(f"Could not check mount status of {source_path}: {e}")
                # Continue with other validations
            
        if not source_path.is_dir():
            logger.error(f"Source path is not a directory: {source_path}")
            return False
            
        if not os.access(str(source_path), os.R_OK):
            logger.error(f"No read permission for source: {source_path}")
            return False
            
        # Try listing the directory
        try:
            next(source_path.iterdir())
            return True
        except StopIteration:
            # Empty directory is valid
            return True
        except (PermissionError, OSError) as e:
            logger.error(f"Error accessing source directory {source_path}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error validating source path {source_path}: {e}")
        return False


def verify_space_requirements(storage, destination_path: Path, required_space: int) -> bool:
    """
    Verify destination has enough space.
    
    Args:
        storage: Storage interface
        destination_path: Destination path
        required_space: Required space in bytes
        
    Returns:
        bool: True if enough space, False otherwise
    """
    try:
        if not storage.has_enough_space(destination_path, required_space):
            available_space = storage.get_drive_info(destination_path)['free']
            logger.error(
                f"Not enough space. Need {required_space / (1024*1024*1024):.2f} GB, "
                f"have {available_space / (1024*1024*1024):.2f} GB"
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking available space: {e}")
        return False


def log_transfer_results(log_file: Path, source_path: Path, destination_path: Path, 
                       start_time: datetime, end_time: datetime, 
                       total_files: int, successful_files: int, 
                       failures: List[str] = None) -> bool:
    """
    Log transfer results to a log file.
    
    Args:
        log_file: Path to log file
        source_path: Source path
        destination_path: Destination path
        start_time: Transfer start time
        end_time: Transfer end time
        total_files: Total number of files
        successful_files: Number of successful transfers
        failures: List of failed transfers
        
    Returns:
        bool: True if log was written successfully, False otherwise
    """
    try:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as log:
            # Log basic info
            log.write(f"Transfer started at {start_time.isoformat()}\n")
            log.write(f"Source: {source_path}\n")
            log.write(f"Destination: {destination_path}\n")
            
            # Log completion details
            duration = (end_time - start_time).total_seconds()
            log.write(f"Transfer completed at {end_time.isoformat()}\n")
            log.write(f"Duration: {duration:.1f} seconds\n")
            log.write(f"Files transferred: {successful_files}/{total_files}\n")
            
            # Log failures if any
            if failures:
                log.write(f"Failed files: {len(failures)}\n")
                # Only log the first 10 failures to avoid excessive log file size
                for i, failure in enumerate(failures[:10]):
                    log.write(f"  {i+1}. {failure}\n")
                if len(failures) > 10:
                    log.write(f"  ... and {len(failures) - 10} more\n")
        
        return True
    except Exception as e:
        logger.error(f"Error writing to log file: {e}")
        return False 