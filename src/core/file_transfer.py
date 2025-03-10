# src/core/file_transfer.py

import logging
import os
import shutil 
import time
import platform
from pathlib import Path
from typing import Optional, Tuple, List, Any
from datetime import datetime
from .config_manager import TransferConfig
from .interfaces.display import DisplayInterface
from .interfaces.storage_inter import StorageInterface
from .interfaces.types import TransferStatus, TransferProgress
from .checksum import ChecksumCalculator
from .mhl_handler import initialize_mhl_file, add_file_to_mhl
from .sound_manager import SoundManager
from .proxy_generator import ProxyGenerator
from .directory_handler import DirectoryHandler

logger = logging.getLogger(__name__)

CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks for efficient large file handling
BUFFER_SIZE = 8 * 1024 * 1024  # 8MB buffer for improved I/O performance
TEMP_FILE_EXTENSION = ".TBPART"  # Temporary file extension during transfer

class FileTransferError(Exception):
    """Custom exception for file transfer errors"""
    pass

class FileTransfer:
    def __init__(
        self,
        state_manager,
        display: DisplayInterface,
        storage: StorageInterface,
        config: Optional[TransferConfig] = None,
        sound_manager = None
    ):
        self.state_manager = state_manager
        self.display = display
        self.storage = storage
        self.config = config or TransferConfig()
        self.sound_manager = sound_manager
        self._current_progress: Optional[TransferProgress] = None
        self.checksum_calculator = ChecksumCalculator(display)
        self.directory_handler = DirectoryHandler(self.config)
        
        # Initialize proxy generator first
        self.proxy_generator = ProxyGenerator(self.config, self.display)
        self._proxy_generation_active = False
        self._current_proxy_file = None
        
    def _update_progress(self, bytes_transferred: int, total_bytes: int, 
                        file_number: int, total_files: int,
                        status: TransferStatus) -> None:
        """Update progress information and display."""
        if self._current_progress:
            self._current_progress.bytes_transferred = bytes_transferred
            self._current_progress.current_file_progress = bytes_transferred / total_bytes
            self._current_progress.overall_progress = (file_number - 1 + (bytes_transferred / total_bytes)) / total_files
            self._current_progress.status = status
            self.display.show_progress(self._current_progress)

    def sanitize_path(path_str: str) -> Path:
        """
        Sanitize a path string by removing quotes and normalizing it to an absolute path.
        
        Args:
            path_str: Raw path string that might contain quotes
            
        Returns:
            Path object representing an absolute path
            
        Raises:
            ValueError: If the path is invalid or cannot be converted to absolute
            TypeError: If the input is not a string
        """
        if not isinstance(path_str, str):
            logger.error(f"Invalid type for path: expected string, got {type(path_str).__name__}")
            raise TypeError(f"Path must be a string, got {type(path_str).__name__}")
        
        try:
            # Remove any surrounding quotes (single or double)
            cleaned_path = path_str.strip("'\"")
            
            # Convert to Path object
            path = Path(cleaned_path)
            
            # Resolve any relative path components and convert to absolute
            if not path.is_absolute():
                logger.warning(f"Relative path provided: '{path_str}'. Absolute path required.")
                raise ValueError(f"Path must be absolute: {path_str}")
                
            # Normalize the path (resolve any .. or . components)
            try:
                normalized_path = path.resolve()
            except RuntimeError as e:
                # Handle potential recursive symlinks
                logger.error(f"Failed to resolve path '{path_str}': {e}")
                raise ValueError(f"Cannot resolve path due to recursive symlinks: {path_str}") from e
                
            # On Windows, ensure consistent path separator
            if os.name == 'nt':
                normalized_path = Path(str(normalized_path).replace('/', '\\'))
                
            return normalized_path
            
        except ValueError as e:
            # Re-raise ValueError with original as cause
            logger.error(f"Invalid path format '{path_str}': {e}")
            raise
        except OSError as e:
            # Operating system errors (permissions, non-existent directories in path)
            logger.error(f"OS error processing path '{path_str}': {e}")
            raise ValueError(f"Cannot process path due to system error: {e}") from e
        except Exception as e:
            # Catch other unexpected exceptions but log with more detail
            logger.error(f"Unexpected error sanitizing path '{path_str}': {e}", exc_info=True)
            raise ValueError(f"Invalid path format: {path_str}") from e
        

    def _verify_source_access(self, path: Path) -> bool:
        """
        Verify source path accessibility with proper error handling.
        
        Args:
            path: Path to check for accessibility
            
        Returns:
            bool: True if the path is accessible, False otherwise
        """
        try:
            # Convert to Path object if it isn't already
            try:
                path = Path(path)
            except TypeError as e:
                logger.error(f"Invalid path type: {type(path).__name__}, {e}")
                return False
                
            # Basic existence check
            if not path.exists():
                logger.error(f"Source path does not exist: {path}")
                return False
                
            # Check if it's a directory
            if not path.is_dir():
                logger.error(f"Source path is not a directory: {path}")
                return False
                
            # Check read permission
            if not os.access(path, os.R_OK):
                logger.error(f"No read permission for source: {path}")
                return False
                
            # Try to list directory contents
            try:
                next(path.iterdir())
                return True
            except StopIteration:
                # Empty directory is valid
                logger.debug(f"Source directory is empty: {path}")
                return True
                
        except PermissionError as e:
            logger.error(f"Permission denied accessing source: {path}, {e}")
            return False
        except FileNotFoundError as e:
            # This could happen if the directory is removed between checks
            logger.error(f"Source path disappeared during verification: {path}, {e}")
            return False
        except NotADirectoryError as e:
            # This could happen if path changes from directory to file during checks
            logger.error(f"Source path is not a directory during iteration: {path}, {e}")
            return False
        except OSError as e:
            # Handle specific OS errors (disk errors, etc.)
            logger.error(f"OS error accessing source: {path}, {e}")
            return False
        except Exception as e:
            # Last resort catch-all with detailed logging
            logger.error(f"Unexpected error verifying source access: {path}, {e}", exc_info=True)
            return False

    def _get_transferable_files(self, source_path: Path) -> List[Path]:
        """
        Get list of files to transfer with improved path handling.
        
        Args:
            source_path: Root directory to scan for files
            
        Returns:
            List[Path]: List of files to transfer, empty list if error occurs
        """
        files_to_transfer = []
        ignored_files = 0
        permission_errors = 0
        
        try:
            # Convert source path to Path object for consistent handling
            try:
                source_path = Path(source_path)
            except TypeError as e:
                logger.error(f"Invalid source path type: {type(source_path).__name__}, {e}")
                return []
                
            # First verify the source path is accessible
            if not self._verify_source_access(source_path):
                logger.error(f"Source path not accessible: {source_path}")
                return []
                
            # Walk the directory structure safely
            try:
                for path in source_path.rglob('*'):
                    try:
                        # Skip directories and hidden files
                        if path.is_dir():
                            continue
                            
                        if path.name.startswith('.'):
                            ignored_files += 1
                            continue
                            
                        # Skip system directories
                        if 'System Volume Information' in str(path):
                            ignored_files += 1
                            continue
                            
                        # Apply media filter if configured
                        if self.config.media_only_transfer:
                            if any(path.name.lower().endswith(ext) 
                                for ext in self.config.media_extensions):
                                files_to_transfer.append(path)
                            else:
                                ignored_files += 1
                        else:
                            files_to_transfer.append(path)
                            
                    except PermissionError as e:
                        permission_errors += 1
                        logger.warning(f"Permission denied accessing: {path}, {e}")
                        continue
                    except FileNotFoundError as e:
                        # File might have been deleted during scan
                        logger.warning(f"File disappeared during scan: {path}, {e}")
                        continue
                    except OSError as e:
                        # Handle OS-specific errors (like disk errors)
                        logger.warning(f"OS error processing file {path}: {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"Unexpected error processing file {path}: {e}", exc_info=True)
                        continue
                        
                # Log summary statistics
                if files_to_transfer:
                    logger.info(f"Found {len(files_to_transfer)} files to transfer, ignored {ignored_files} files")
                    if permission_errors > 0:
                        logger.warning(f"Encountered {permission_errors} permission errors during scan")
                else:
                    logger.warning(f"No files found to transfer in {source_path}")
                    
                return files_to_transfer
                
            except PermissionError as e:
                logger.error(f"Permission denied during directory traversal: {source_path}, {e}")
                return []
            except RuntimeError as e:
                # Handle recursive symlinks
                logger.error(f"Recursive directory structure detected in {source_path}: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error scanning for files in {source_path}: {e}", exc_info=True)
            return []

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
            TypeError: If path is not a Path object or cannot be converted to one
        """
        if not isinstance(path, Path):
            try:
                path = Path(path)
                logger.debug(f"Converted input to Path object: {path}")
            except TypeError as e:
                logger.error(f"Cannot convert {type(path).__name__} to Path object: {e}")
                raise TypeError(f"Path must be a Path object or convertible to one: {e}") from e
                
        try:
            system = platform.system().lower()
            logger.debug(f"Validating path {path} for platform {system}")
            
            # Handle platform-specific path validation
            if system == 'darwin':
                # For macOS, ensure paths to external drives start with /Volumes/
                if not str(path).startswith('/Volumes/'):
                    logger.error(f"macOS external drive path must start with /Volumes/: {path}")
                    raise ValueError(f"External drive paths on macOS must start with /Volumes/, got: {path}")
                    
            elif system == 'windows':
                # For Windows, ensure path has a drive letter
                if not path.drive:
                    logger.error(f"Windows path missing drive letter: {path}")
                    raise ValueError(f"Windows paths must include a drive letter, got: {path}")
                    
            # Check if the path's drive/volume exists and is accessible
            if system == 'windows':
                drive_path = Path(path.drive + '\\')
            elif system == 'darwin':
                drive_path = Path('/Volumes')
            else:  # Linux/Raspberry Pi
                drive_path = Path('/')
                
            if not drive_path.exists():
                logger.error(f"Drive/volume not found: {drive_path}")
                raise ValueError(f"Drive/volume not found: {drive_path}")
                
            # Check write permissions with better error handling
            try:
                if not os.access(drive_path, os.W_OK):
                    logger.error(f"No write permission for drive: {drive_path}")
                    raise ValueError(f"No write permission for drive: {drive_path}")
            except OSError as e:
                logger.error(f"Error checking permissions for drive {drive_path}: {e}")
                raise ValueError(f"Cannot verify permissions for drive: {drive_path}. Error: {e}") from e
                
            # Additional checks for path validity
            try:
                # Try to normalize the path to catch any format issues
                normalized_path = path.resolve()
            except RuntimeError as e:
                # This catches recursive symlinks
                logger.error(f"Cannot resolve path due to recursive symlinks: {path}")
                raise ValueError(f"Invalid path structure (recursive symlinks): {path}") from e
                
            logger.info(f"Successfully validated destination path: {path}")
            return path
            
        except ValueError:
            # Re-raise ValueError exceptions directly to preserve their specific message
            raise
        except PermissionError as e:
            logger.error(f"Permission error validating path {path}: {e}")
            raise ValueError(f"Permission denied when validating path: {e}") from e
        except FileNotFoundError as e:
            logger.error(f"Path component not found for {path}: {e}")
            raise ValueError(f"Path component not found: {e}") from e
        except OSError as e:
            logger.error(f"OS error validating path {path}: {e}")
            raise ValueError(f"Operating system error when validating path: {e}") from e
        except Exception as e:
            # Last resort catch-all
            logger.error(f"Unexpected error validating destination path '{path}': {e}", exc_info=True)
            raise ValueError(f"Invalid path format: {e}") from e

    def _copy_with_progress(self, src_path: Path, dst_path: Path, 
                        file_number: int, total_files: int,
                        total_transferred: int, total_size: int) -> Tuple[bool, Optional[str]]:
        """
        Copy a file with progress updates and metadata preservation
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            file_number: Current file number in batch
            total_files: Total number of files to transfer
            total_transferred: Total bytes transferred so far
            total_size: Total bytes to transfer
            
        Returns:
            Tuple of (success_flag, checksum_string): 
            - success_flag: True if copy and verification succeeded
            - checksum_string: File checksum if successful, None otherwise
        """
        # Track if destination file was created - needed for cleanup on error
        dst_file_created = False
        
        try:
            # Validate source and prepare for copy
            if not self._validate_source_file(src_path):
                return False, None
                
            # Get source metadata before copy
            source_metadata = self._get_source_metadata(src_path)
            
            # Get file size
            file_size = self._get_file_size(src_path)
            if file_size is None:
                return False, None
                
            # Initialize hash calculator
            xxh64_hash = self.checksum_calculator.create_hash()
            
            # Perform the actual file copy with progress updates
            copy_result = self._perform_file_copy(
                src_path, dst_path, file_size, xxh64_hash,
                file_number, total_files, total_transferred
            )
            
            if not copy_result:
                return False, None
                
            dst_file_created = True
                
            # Apply metadata if available
            self._apply_metadata(dst_path, source_metadata)
            
            # Verify checksum
            checksum = xxh64_hash.hexdigest()
            if not self._verify_file_checksum(dst_path, checksum):
                return False, None
                    
            return True, checksum
                
        except Exception as e:
            self._play_sound(success=False)
            logger.error(f"Unexpected error copying file {src_path} to {dst_path}: {e}", exc_info=True)
            
            # Cleanup: attempt to remove partial/corrupt destination file if we created it
            if dst_file_created:
                self._cleanup_destination_file(dst_path)
                    
            return False, None
            
    def _validate_source_file(self, src_path: Path) -> bool:
        """
        Validate that source file exists.
        
        Args:
            src_path: Source file path
            
        Returns:
            bool: True if source file exists, False otherwise
        """
        if not src_path.exists():
            logger.error(f"Source file does not exist: {src_path}")
            return False
        return True
        
    def _get_source_metadata(self, src_path: Path) -> Optional[Any]:
        """
        Get metadata from source file.
        
        Args:
            src_path: Source file path
            
        Returns:
            Optional[Any]: File metadata if available, None otherwise
        """
        try:
            return self.storage.get_file_metadata(src_path)
        except Exception as e:
            logger.warning(f"Failed to get source metadata for {src_path}: {e}")
            return None
            
    def _get_file_size(self, src_path: Path) -> Optional[int]:
        """
        Get size of source file.
        
        Args:
            src_path: Source file path
            
        Returns:
            Optional[int]: File size in bytes if available, None on error
        """
        try:
            return src_path.stat().st_size
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Failed to get file size for {src_path}: {e}")
            return None
            
    def _perform_file_copy(self, src_path: Path, dst_path: Path, 
                          file_size: int, hash_obj,
                          file_number: int, total_files: int, 
                          total_transferred: int) -> bool:
        """
        Copy file with progress updates and hash calculation.
        Uses buffered I/O and temporary files for safer transfers.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            file_size: Size of source file in bytes
            hash_obj: Hash object to update during copy
            file_number: Current file number in batch
            total_files: Total number of files to transfer
            total_transferred: Total bytes transferred so far
            
        Returns:
            bool: True if copy succeeded, False otherwise
        """
        try:
            # Create a temporary destination path with .TBPART extension
            temp_dst_path = dst_path.with_suffix(dst_path.suffix + TEMP_FILE_EXTENSION)
            
            # Ensure parent directory exists
            temp_dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(src_path, 'rb', buffering=BUFFER_SIZE) as src:
                try:
                    with open(temp_dst_path, 'wb', buffering=BUFFER_SIZE) as dst:
                        bytes_transferred = 0
                        
                        while True:
                            try:
                                chunk = src.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                    
                                dst.write(chunk)
                                hash_obj.update(chunk)
                                bytes_transferred += len(chunk)
                                
                                # Update progress with both file and total progress
                                self._update_copy_progress(
                                    bytes_transferred, file_size,
                                    total_transferred, file_number,
                                    total_files
                                )
                                    
                            except (MemoryError, IOError) as e:
                                logger.error(f"Error processing chunk of {src_path}: {e}")
                                self._play_sound(success=False)
                                # Clean up the temporary file
                                self._cleanup_destination_file(temp_dst_path)
                                return False
                                
                except (PermissionError, IOError) as e:
                    logger.error(f"Error with destination file {temp_dst_path}: {e}")
                    self._play_sound(success=False)
                    # Clean up the temporary file
                    self._cleanup_destination_file(temp_dst_path)
                    return False
                    
            # If we got here, the file was successfully copied to the temporary location
            # Now rename it to the final destination
            try:
                # If the destination file already exists (unlikely but possible), remove it first
                if dst_path.exists():
                    dst_path.unlink()
                # Rename the temporary file to the final destination
                temp_dst_path.rename(dst_path)
            except (PermissionError, IOError) as e:
                logger.error(f"Error renaming temporary file {temp_dst_path} to {dst_path}: {e}")
                self._play_sound(success=False)
                # Clean up the temporary file
                self._cleanup_destination_file(temp_dst_path)
                return False
                    
        except (PermissionError, FileNotFoundError, IOError) as e:
            logger.error(f"Error with source file {src_path}: {e}")
            self._play_sound(success=False)
            return False
            
        return True
        
    def _update_copy_progress(self, bytes_transferred: int, file_size: int,
                             total_transferred: int, file_number: int,
                             total_files: int) -> None:
        """
        Update progress information during file copy.
        
        Args:
            bytes_transferred: Bytes transferred for current file
            file_size: Total size of current file
            total_transferred: Total bytes transferred in batch so far
            file_number: Current file number in batch
            total_files: Total number of files in batch
        """
        if self._current_progress:
            self._current_progress.bytes_transferred = bytes_transferred
            self._current_progress.current_file_progress = bytes_transferred / file_size
            self._current_progress.total_transferred = total_transferred + bytes_transferred
            self._current_progress.status = TransferStatus.COPYING
            self.display.show_progress(self._current_progress)
            
    def _apply_metadata(self, dst_path: Path, metadata) -> None:
        """
        Apply metadata to destination file.
        
        Args:
            dst_path: Destination file path
            metadata: Metadata to apply
        """
        if metadata:
            try:
                if not self.storage.set_file_metadata(dst_path, metadata):
                    logger.warning(f"Failed to preserve metadata for {dst_path}")
            except Exception as e:
                # Log but continue - metadata failure isn't critical
                logger.warning(f"Error setting metadata for {dst_path}: {e}")
                
    def _verify_file_checksum(self, dst_path: Path, checksum: str) -> bool:
        """
        Verify file checksum.
        
        Args:
            dst_path: Destination file path
            checksum: Expected checksum
            
        Returns:
            bool: True if checksum verification succeeded, False otherwise
        """
        try:
            if self._current_progress:
                self._current_progress.status = TransferStatus.CHECKSUMMING
                
            verify_success = self.checksum_calculator.verify_checksum(
                dst_path,
                checksum,
                current_progress=self._current_progress
            )
            
            if not verify_success:
                logger.error(f"Checksum verification failed for {dst_path}")
                self._cleanup_destination_file(dst_path)
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error during checksum verification of {dst_path}: {e}")
            self._play_sound(success=False)
            return False
            
    def _cleanup_destination_file(self, dst_path: Path) -> None:
        """
        Safely remove a destination file if it exists.
        
        Args:
            dst_path: Path to the file to remove
        """
        try:
            if dst_path.exists():
                logger.info(f"Cleaning up incomplete file: {dst_path}")
                dst_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to clean up file {dst_path}: {e}")

    def _check_utility_mode(self) -> bool:
        """
        Check if system is in utility mode.
        
        Returns:
            bool: True if validation passes (not in utility mode), False otherwise
        """
        if self.state_manager.is_utility():
            logger.info("Transfer blocked - system is in utility mode")
            self.display.show_error("In utility mode")
            return False
        return True

    def _validate_destination_path_type(self, destination_path: Path) -> Optional[Path]:
        """
        Validate and convert destination path to Path object.
        
        Args:
            destination_path: Path to validate
            
        Returns:
            Optional[Path]: Valid Path object or None if validation fails
        """
        if destination_path is None:
            logger.error("No destination path provided")
            self.display.show_error("No destination")
            return None
            
        try:
            return Path(destination_path)
        except TypeError as e:
            logger.error(f"Invalid destination path type: {type(destination_path).__name__}, {e}")
            self.display.show_error("Invalid path type")
            return None

    def _validate_existing_destination(self, dest_path: Path) -> bool:
        """
        Validate an existing destination directory.
        
        Args:
            dest_path: Path to validate
            
        Returns:
            bool: True if validation passes, False otherwise
        """
        # Check if it's a directory
        if not dest_path.is_dir():
            logger.error(f"Destination exists but is not a directory: {dest_path}")
            self.display.show_error("Not a directory")
            return False
            
        # Check write permissions
        if not os.access(dest_path, os.W_OK):
            logger.error(f"No write permission for destination: {dest_path}")
            self.display.show_error("Write permission denied")
            return False
            
        # Check for available space
        try:
            min_space = 1 * 1024 * 1024 * 1024  # 1GB in bytes
            if not self.storage.has_enough_space(dest_path, min_space):
                logger.error(f"Not enough space in destination: {dest_path}")
                self.display.show_error("Not enough space")
                return False
        except Exception as space_err:
            # Log but continue - we'll check space again before actual transfer
            logger.warning(f"Could not verify free space: {space_err}")
            
        logger.info(f"Using existing directory: {dest_path}")
        return True

    def _validate_parent_directory(self, dest_path: Path) -> bool:
        """
        Validate parent directory for a non-existent destination.
        
        Args:
            dest_path: Path whose parent should be validated
            
        Returns:
            bool: True if parent directory is valid, False otherwise
        """
        parent = dest_path.parent
        
        if not parent.exists():
            logger.error(f"Parent directory doesn't exist: {parent}")
            self.display.show_error("Parent dir missing")
            return False
            
        if not os.access(parent, os.W_OK):
            logger.error(f"No write permission for parent directory: {parent}")
            self.display.show_error("Parent write denied")
            return False
            
        return True

    def _create_destination_directory(self, dest_path: Path) -> bool:
        """
        Create the destination directory.
        
        Args:
            dest_path: Directory to create
            
        Returns:
            bool: True if directory was created successfully, False otherwise
        """
        try:
            dest_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {dest_path}")
            return True
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {dest_path}: {e}")
            self.display.show_error("Permission denied")
            return False
        except OSError as e:
            logger.error(f"OS error creating directory {dest_path}: {e}")
            self.display.show_error("Create dir failed")
            return False
        except Exception as e:
            logger.error(f"Failed to create directory {dest_path}: {e}")
            self.display.show_error("Create dir failed")
            return False

    def _validate_transfer_preconditions(self, destination_path: Path) -> bool:
        """
        Validate preconditions before starting transfer.
        
        Args:
            destination_path: Target path for file transfer
            
        Returns:
            bool: True if destination is valid and ready for transfer, False otherwise
        """
        try:
            # Check utility mode first
            if not self._check_utility_mode():
                return False
                
            # Validate and convert path
            dest_path = self._validate_destination_path_type(destination_path)
            if dest_path is None:
                return False
                
            # Handle existing vs non-existing destination
            if dest_path.exists():
                return self._validate_existing_destination(dest_path)
                
            # For non-existing destination, validate parent and create
            if not self._validate_parent_directory(dest_path):
                return False
                
            return self._create_destination_directory(dest_path)
                
        except FileNotFoundError as e:
            logger.error(f"Path component not found: {e}")
            self.display.show_error("Path not found")
            return False
        except PermissionError as e:
            logger.error(f"Permission error validating path: {e}")
            self.display.show_error("Access denied")
            return False
        except OSError as e:
            logger.error(f"OS error validating path: {e}")
            self.display.show_error("System error")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating path: {e}", exc_info=True)
            self.display.show_error("Invalid path")
            return False

    def _validate_source_path(self, source_path: Path) -> bool:
        """Validate source path accessibility with proper error handling."""
        try:
            if not source_path.exists():
                logger.error(f"Source path does not exist: {source_path}")
                self.display.show_error("Source Missing")
                return False
                
            if not os.access(str(source_path), os.R_OK):
                logger.error(f"No read permission for source path: {source_path}")
                self.display.show_error("Source Not Readable")
                return False
            
            # Test directory listing with specific error handling
            try:
                test_list = list(source_path.iterdir())
                logger.info(f"Source directory contains {len(test_list)} items")
            except PermissionError as e:
                logger.error(f"Permission denied listing source directory: {source_path}, {e}")
                self.display.show_error("Permission Denied")
                return False
            except NotADirectoryError as e:
                logger.error(f"Source path is not a directory: {source_path}, {e}")
                self.display.show_error("Not A Directory")
                return False
            
            return True
            
        except PermissionError as e:
            logger.error(f"Permission denied accessing source path: {source_path}, {e}")
            self.display.show_error("Permission Denied")
            return False
        except FileNotFoundError as e:
            logger.error(f"Source path not found: {source_path}, {e}")
            self.display.show_error("Source Not Found")
            return False
        except OSError as e:
            logger.error(f"OS error accessing source path: {source_path}, {e}")
            self.display.show_error("Access Error")
            return False
        except Exception as e:
            logger.error(f"Unexpected error accessing source path: {source_path}, {e}", exc_info=True)
            self.display.show_error("Source Error")
            return False

    def _initialize_mhl_file(self, timestamp: str, target_dir: Path) -> Optional[Tuple[Path, Any, Any]]:
        """Initialize MHL file for transfer verification."""
        try:
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
            return mhl_filename, tree, hashes
        except OSError as e:
            logger.error(f"Failed to create MHL file: {e}")
            self.display.show_error("MHL Create Failed")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating MHL file: {e}")
            self.display.show_error("MHL Create Failed")
            return None

    def _get_files_with_os_walk(self, source_path: Path) -> List[Path]:
        """Get files using the os.walk method as a fallback."""
        files_to_transfer = []
        source_str = str(source_path)
        logger.debug(f"Starting file scan from: {source_str}")
        
        for root, dirs, files in os.walk(source_str, onerror=lambda err: logger.error(f"Walk error: {err}")):
            try:
                current_dir = Path(root)
                logger.debug(f"Processing directory: {current_dir}")
                
                # Skip system directories
                if any(part.startswith('.') or part == 'System Volume Information' 
                    for part in current_dir.parts):
                    logger.debug(f"Skipping system directory: {current_dir}")
                    continue
                
                # Process each file in current directory
                for filename in files:
                    try:
                        file_path = current_dir / filename
                        logger.debug(f"Examining file: {file_path}")
                        
                        # Skip hidden files
                        if filename.startswith('.'):
                            logger.debug(f"Skipping hidden file: {filename}")
                            continue
                            
                        # Verify file exists and is readable
                        if not file_path.exists():
                            logger.warning(f"File not accessible: {file_path}")
                            continue
                            
                        # Apply media filtering if enabled
                        if self.config.media_only_transfer:
                            if any(file_path.name.lower().endswith(ext) 
                                for ext in self.config.media_extensions):
                                files_to_transfer.append(file_path)
                                logger.debug(f"Added media file: {file_path}")
                        else:
                            files_to_transfer.append(file_path)
                            logger.debug(f"Added file: {file_path}")
                            
                    except FileNotFoundError as file_err:
                        # File disappeared between listing and examination
                        logger.warning(f"File disappeared during scan: {filename}, {file_err}")
                        continue
                    except PermissionError as file_err:
                        logger.warning(f"Permission denied accessing file: {filename}, {file_err}")
                        continue
                    except Exception as file_err:
                        logger.error(f"Error processing file {filename}: {file_err}")
                        continue
                        
            except PermissionError as dir_err:
                logger.warning(f"Permission denied for directory {root}: {dir_err}")
                continue
            except Exception as dir_err:
                logger.error(f"Error processing directory {root}: {dir_err}")
                continue
        
        return files_to_transfer

    def _get_files_to_transfer(self, source_path: Path) -> Optional[List[Path]]:
        """Get list of files to transfer with fallback mechanisms."""
        try:
            # First try using the faster _get_transferable_files method
            files_to_transfer = self._get_transferable_files(source_path)
            
            # If that fails, fall back to the slower os.walk method
            if not files_to_transfer:
                logger.warning(f"Fast file scan failed, falling back to os.walk")
                files_to_transfer = self._get_files_with_os_walk(source_path)
                
            # Verify we found files to transfer
            if not files_to_transfer:
                logger.warning(f"No {'media' if self.config.media_only_transfer else ''} files found to transfer in {source_path}")
                
                # More informative error message based on transfer mode
                if self.config.media_only_transfer:
                    self.display.show_error("No Media Found")
                else:
                    self.display.show_error("No Files Found")
                    
                self._play_sound(success=False)
                return None
                
            return files_to_transfer
            
        except PermissionError as e:
            logger.error(f"Permission denied scanning for files: {e}")
            self.display.show_error("Scan Permission")
            return None
        except Exception as e:
            logger.error(f"Error scanning for files: {e}", exc_info=True)
            self.display.show_error("Scan Failed")
            return None

    def _calculate_transfer_totals(self, files_to_transfer: List[Path]) -> Optional[Tuple[List[Path], int, int]]:
        """Calculate transfer totals and validate files."""
        try:
            total_size = 0
            valid_files = []
            
            for f in files_to_transfer:
                try:
                    size = f.stat().st_size
                    total_size += size
                    valid_files.append(f)
                except (FileNotFoundError, PermissionError) as e:
                    # File disappeared or became inaccessible
                    logger.warning(f"File {f} skipped: {e}")
                    continue
            
            total_files = len(valid_files)
            
            if total_files == 0:
                logger.warning("All files became inaccessible during size calculation")
                self.display.show_error("Files Disappeared")
                return None
            
            logger.info(f"Transfer mode: {'Media only' if self.config.media_only_transfer else 'All files'}")
            logger.info(f"Total files to transfer: {total_files}")
            logger.info(f"Total transfer size: {total_size / (1024*1024*1024):.2f} GB")
            
            return valid_files, total_size, total_files
            
        except Exception as e:
            logger.error(f"Error calculating transfer totals: {e}", exc_info=True)
            self.display.show_error("Size Calc Error")
            return None

    def _verify_space_requirements(self, destination_path: Path, required_space: int) -> bool:
        """Verify destination has enough space."""
        try:
            if not self.storage.has_enough_space(destination_path, required_space):
                available_space = self.storage.get_drive_info(destination_path)['free']
                logger.error(
                    f"Not enough space. Need {required_space / (1024*1024*1024):.2f} GB, "
                    f"have {available_space / (1024*1024*1024):.2f} GB"
                )
                self.display.show_error("Not enough space")
                self._play_sound(success=False)
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking available space: {e}")
            self.display.show_error("Space Check Error")
            return False

    def _create_directory_structure(self, files_to_transfer: List[Path], source_path: Path, target_dir: Path) -> bool:
        """Create required directory structure for transfer."""
        if not self.config.preserve_folder_structure:
            return True
            
        try:
            required_directories = set()
            for file_path in files_to_transfer:
                try:
                    rel_path = file_path.parent.relative_to(source_path)
                    target_path = target_dir / rel_path
                    required_directories.add(target_path)
                except ValueError as e:
                    # Handle case where relative_to fails
                    logger.warning(f"Could not determine relative path for {file_path}: {e}")
                    continue
                
            for dir_path in sorted(required_directories):
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"Created directory: {dir_path}")
                except PermissionError as e:
                    logger.error(f"Permission denied creating directory {dir_path}: {e}")
                    raise
                except OSError as e:
                    logger.error(f"OS error creating directory {dir_path}: {e}")
                    raise
            return True
        except Exception as e:
            logger.error(f"Failed to create directory structure: {e}")
            self.display.show_error("Dir Structure Error")
            return False

    def _transfer_single_file(self, src_file: Path, target_dir: Path, source_path: Path, 
                            file_number: int, total_files: int, total_transferred: int, 
                            total_size: int, mhl_data: Optional[Tuple], log_file) -> Tuple[bool, Optional[int], Optional[str]]:
        """Transfer a single file and update progress."""
        try:
            # Check if file still exists before attempting transfer
            if not src_file.exists():
                logger.warning(f"File disappeared before transfer: {src_file}")
                self._log_failure(log_file, src_file, None, "File disappeared")
                return False, None, f"{src_file} (disappeared)"
                
            file_size = src_file.stat().st_size
            
            # Create destination path preserving structure
            try:
                dst_path = self._create_destination_path(src_file, target_dir, source_path)
            except Exception as e:
                logger.error(f"Failed to create destination path for {src_file}: {e}")
                self._log_failure(log_file, src_file, None, f"Path error: {e}")
                return False, None, f"{src_file} (path error)"
            
            # Check if a .TBPART file exists from a previous interrupted transfer
            temp_dst_path = dst_path.with_suffix(dst_path.suffix + TEMP_FILE_EXTENSION)
            if temp_dst_path.exists():
                logger.warning(f"Found incomplete transfer file: {temp_dst_path}")
                try:
                    temp_dst_path.unlink()
                    logger.info(f"Removed incomplete file: {temp_dst_path}")
                except Exception as e:
                    logger.error(f"Failed to remove incomplete file {temp_dst_path}: {e}")
                    self._log_failure(log_file, src_file, temp_dst_path, f"Failed to remove incomplete file: {e}")
                    return False, None, f"{src_file} (cleanup error)"
            
            logger.info(f"Processing file {file_number}/{total_files}: {src_file.name}")
            
            # Initialize progress tracking
            self._current_progress = TransferProgress(
                current_file=src_file.name,
                file_number=file_number,
                total_files=total_files,
                bytes_transferred=0,
                total_bytes=file_size,
                total_transferred=total_transferred,
                total_size=total_size,
                current_file_progress=0.0,
                overall_progress=(file_number - 1) / total_files,
                status=TransferStatus.COPYING
            )

            # Copy and verify file
            success, checksum = self._copy_with_progress(
                src_file, dst_path,
                file_number, total_files,
                total_transferred, total_size
            )

            if success and checksum:
                self._log_success(log_file, src_file, dst_path)
                
                # Add file to MHL for verification
                if mhl_data:
                    try:
                        mhl_filename, tree, hashes = mhl_data
                        add_file_to_mhl(mhl_filename, tree, hashes, dst_path, checksum, file_size)
                    except Exception as mhl_err:
                        logger.warning(f"Failed to add file to MHL: {dst_path}, {mhl_err}")
                        # Continue without stopping the transfer
                        
                return True, file_size, None
            else:
                # Check if a .TBPART file was left behind after a failed transfer
                temp_dst_path = dst_path.with_suffix(dst_path.suffix + TEMP_FILE_EXTENSION)
                if temp_dst_path.exists():
                    try:
                        temp_dst_path.unlink()
                        logger.info(f"Cleaned up incomplete file after failed transfer: {temp_dst_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up incomplete file {temp_dst_path}: {e}")
                
                self._log_failure(log_file, src_file, dst_path, "Checksum verification failed")
                return False, None, str(src_file)
                
        except FileNotFoundError as e:
            logger.warning(f"File not found during transfer: {src_file}, {e}")
            self._log_failure(log_file, src_file, None, f"Not found: {e}")
            return False, None, f"{src_file} (not found)"
        except PermissionError as e:
            logger.error(f"Permission error with file: {src_file}, {e}")
            self._log_failure(log_file, src_file, None, f"Permission denied: {e}")
            return False, None, f"{src_file} (permission)"
        except Exception as e:
            logger.error(f"Unexpected error processing file {src_file}: {e}", exc_info=True)
            self._log_failure(log_file, src_file, None, f"Unknown error: {e}")
            return False, None, f"{src_file} (error)"

    def _log_transfer_completion(self, transfer_start_time: datetime, log_file, total_files: int, failures: List[str]) -> None:
        """
        Log transfer completion details to the log file.
        
        Args:
            transfer_start_time: When the transfer started
            log_file: Log file to write to
            total_files: Total number of files processed
            failures: List of failed transfers
        """
        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                # Log completion time
                transfer_end_time = datetime.now()
                duration = (transfer_end_time - transfer_start_time).total_seconds()
                log.write(f"\nTransfer completed at {transfer_end_time.isoformat()}\n")
                log.write(f"Duration: {duration:.1f} seconds\n")
                log.write(f"Files transferred: {total_files - len(failures)}/{total_files}\n")
                
                if failures:
                    log.write(f"Failed files: {len(failures)}\n")
                    # Only log the first 10 failures to avoid excessive log file size
                    for i, failure in enumerate(failures[:10]):
                        log.write(f"  {i+1}. {failure}\n")
                    if len(failures) > 10:
                        log.write(f"  ... and {len(failures) - 10} more\n")
        except Exception as e:
            logger.error(f"Error updating log file with completion info: {e}")

    def _update_final_progress(self, total_size: int, success: bool) -> None:
        """
        Update the final progress display.
        
        Args:
            total_size: Total size of transferred files
            success: Whether the transfer was successful
        """
        if self._current_progress:
            self._current_progress.status = TransferStatus.SUCCESS if success else TransferStatus.ERROR
            self._current_progress.total_transferred = total_size
            self.display.show_progress(self._current_progress)

    def _handle_drive_unmount(self, source_path: Path) -> bool:
        """
        Attempt to unmount the source drive.
        
        Args:
            source_path: Path to the source drive
            
        Returns:
            bool: True if unmount successful or not needed, False if unmount failed
        """
        if not self.storage.is_drive_mounted(source_path):
            return True
            
        try:
            if self.storage.unmount_drive(source_path):
                self.display.show_status("Safe to remove card")
                return True
            else:
                logger.warning(f"Failed to unmount drive: {source_path}")
                self.display.show_error("Unmount failed")
                return False
        except Exception as e:
            logger.error(f"Error unmounting drive {source_path}: {e}")
            self.display.show_error("Unmount error")
            return False

    def _process_transfer_results(self, transfer_start_time: datetime, log_file, 
                                total_files: int, failures: List[str], source_path: Path, 
                                total_size: int) -> Tuple[bool, bool]:
        """
        Process transfer results and handle unmounting.
        
        Args:
            transfer_start_time: When the transfer started
            log_file: Log file to write to
            total_files: Total number of files processed
            failures: List of failed transfers
            source_path: Path to the source drive
            total_size: Total size of transferred files
            
        Returns:
            Tuple of (success_flag, unmount_success): 
            - success_flag: True if transfer succeeded
            - unmount_success: True if unmount succeeded or wasn't needed
        """
        transfer_success = len(failures) == 0
        
        # Log completion details
        self._log_transfer_completion(transfer_start_time, log_file, total_files, failures)
        
        if transfer_success:
            logger.info("Transfer completed successfully")
            self._play_sound(success=True)
            
            # Update final progress
            self._update_final_progress(total_size, True)
            
            # Handle unmounting
            unmount_success = self._handle_drive_unmount(source_path)
        else:
            self._play_sound(success=False)
            self._update_final_progress(total_size, False)
            
            # Create more informative error message
            if len(failures) == total_files:
                self.display.show_error("All transfers failed")
            else:
                self.display.show_error(f"{len(failures)}/{total_files} failed")
                
            logger.error(f"Transfer failed for {len(failures)}/{total_files} files")
            # Log first few failures for debugging
            for i, failure in enumerate(failures[:5]):
                logger.error(f"  Failed file {i+1}: {failure}")
            
            unmount_success = False
        
        return transfer_success, unmount_success

    def _cleanup_transfer_state(self, transfer_started: bool, transfer_success: bool, 
                            unmount_success: bool, source_path: Path) -> None:
        """Cleanup after transfer completes or fails."""
        try:
            # Always properly exit transfer state if we entered it
            if transfer_started and self.state_manager.is_transfer():
                try:
                    self.state_manager.exit_transfer(source_path if not unmount_success else None)
                except Exception as state_err:
                    logger.error(f"Error exiting transfer state: {state_err}")
                    # Don't propagate this error, as we're in cleanup
            
            # Show appropriate status message
            if transfer_success and not unmount_success:
                self.display.show_status("Transfer complete")
                
            # Log final status
            logger.info(
                f"Transfer completed. Status: {'Success' if transfer_success else 'Failed'}, "
                f"Unmount: {'Success' if unmount_success else 'Failed'}"
            )
            
        except Exception as cleanup_err:
            # Last resort error handling for cleanup failures
            logger.error(f"Error during cleanup: {cleanup_err}", exc_info=True)
            # Don't propagate cleanup errors

    def copy_sd_to_dump(self, source_path: Path, destination_path: Path, log_file: Path) -> bool:
        """
        Copy files from SD card to dump drive.
        
        Args:
            source_path: Path to source drive (SD card)
            destination_path: Path to destination drive (dump drive)
            log_file: Path to log file
            
        Returns:
            bool: True if transfer was successful, False otherwise
        """
        # Initialize variables used in finally block to prevent UnboundLocalError
        transfer_started = False
        transfer_success = False
        unmount_success = False
        
        try:
            # Check for and clean up any interrupted transfers from previous sessions
            self._recover_interrupted_transfers(destination_path)
            
            # Phase 1: Enter transfer state (only once)
            transfer_started = self._enter_transfer_state()
            if not transfer_started:
                return False
                
            # Phase 2: Validation and preparation
            if not self._prepare_for_transfer(source_path, destination_path):
                return False
                
            # Phase 3: Setup transfer environment
            setup_result = self._setup_transfer_environment(source_path, destination_path)
            if not setup_result:
                return False
                
            timestamp, target_dir, mhl_data = setup_result
                
            # Phase 4: Identify and prepare files
            file_prep_result = self._prepare_files_for_transfer(source_path, destination_path, target_dir)
            if not file_prep_result:
                return False
                
            files_to_transfer, total_size, total_files = file_prep_result
                
            # Phase 5: Initialize logging
            transfer_start_time = self._initialize_transfer_log(log_file, source_path, target_dir, total_files, total_size)
                
            # Phase 6: Execute file transfers
            transfer_result = self._execute_file_transfers(
                files_to_transfer, target_dir, source_path, 
                total_files, total_size, mhl_data, log_file
            )
            
            if not transfer_result:
                return False
                
            failures, total_transferred = transfer_result
            
            # Phase 7: Process results and handle unmounting
            transfer_success, unmount_success = self._process_transfer_results(
                transfer_start_time, log_file, total_files, 
                failures, source_path, total_size
            )
            
            return transfer_success
                
        except Exception as e:
            logger.error(f"Unhandled error in transfer process: {e}", exc_info=True)
            self._play_sound(success=False)
            self.display.show_error("System Error")
            return False
            
        finally:
            # Always perform cleanup
            self._cleanup_transfer_state(transfer_started, transfer_success, unmount_success, source_path)
            
    def _prepare_for_transfer(self, source_path: Path, destination_path: Path) -> bool:
        """
        Validate source and destination paths before transfer.
        
        Args:
            source_path: Path to source drive
            destination_path: Path where files should be copied
            
        Returns:
            bool: True if validation passes, False otherwise
        """
        # Validate destination path
        if not self._validate_transfer_preconditions(destination_path):
            self._play_sound(success=False)
            return False

        # Validate source path
        if not self._validate_source_path(source_path):
            return False
            
        return True
        
    def _setup_transfer_environment(self, source_path: Path, destination_path: Path) -> Optional[Tuple[str, Path, Optional[Tuple]]]:
        """
        Set up the transfer environment including directories and MHL file.
        
        Args:
            source_path: Path to source drive
            destination_path: Path where files should be copied
            
        Returns:
            Optional[Tuple]: (timestamp, target_dir, mhl_data) if successful, None otherwise
        """
        # Generate timestamp for this transfer session
        timestamp = datetime.now().strftime(self.config.timestamp_format)
        
        # Log the current configuration state
        logger.info(f"Starting transfer with configuration:")
        logger.info(f"  create_date_folders: {self.config.create_date_folders}")
        logger.info(f"  destination_path: {destination_path}")
        
        # Create target directory
        try:
            target_dir = self.directory_handler.create_organized_directory(
                destination_path,
                source_path,
                timestamp if self.config.create_date_folders else None
            )
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}", exc_info=True)
            self.display.show_error("Dir Create Error")
            return None

        # Initialize MHL file
        mhl_data = self._initialize_mhl_file(timestamp, target_dir)
        if not mhl_data:
            return None
            
        return timestamp, target_dir, mhl_data
        
    def _prepare_files_for_transfer(self, source_path: Path, destination_path: Path, target_dir: Path) -> Optional[Tuple[List[Path], int, int]]:
        """
        Identify files to transfer and calculate totals.
        
        Args:
            source_path: Path to source drive
            destination_path: Path where files should be copied
            target_dir: Target directory for the transfer
            
        Returns:
            Optional[Tuple]: (files_to_transfer, total_size, total_files) if successful, None otherwise
        """
        # Get files to transfer
        files_to_transfer = self._get_files_to_transfer(source_path)
        if not files_to_transfer:
            return None
            
        # Calculate transfer totals
        result = self._calculate_transfer_totals(files_to_transfer)
        if not result:
            return None
            
        files_to_transfer, total_size, total_files = result
            
        # Verify space requirements
        required_space = int(total_size * 1.1)  # Add 10% buffer
        if not self._verify_space_requirements(destination_path, required_space):
            return None
            
        # Create directory structure for preserving folders
        if not self._create_directory_structure(files_to_transfer, source_path, target_dir):
            return None
            
        return files_to_transfer, total_size, total_files
        
    def _enter_transfer_state(self) -> bool:
        """
        Enter transfer state in the state manager.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.state_manager.enter_transfer()
            return True
        except Exception as e:
            logger.error(f"Failed to enter transfer state: {e}")
            self.display.show_error("State Error")
            return False
            
    def _initialize_transfer_log(self, log_file: Path, source_path: Path, 
                               target_dir: Path, total_files: int, 
                               total_size: int) -> datetime:
        """
        Initialize the transfer log file.
        
        Args:
            log_file: Path to log file
            source_path: Path to source drive
            target_dir: Target directory for the transfer
            total_files: Total number of files to transfer
            total_size: Total size of files to transfer in bytes
            
        Returns:
            datetime: Transfer start time
        """
        # Prepare log file directory
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log file directory: {e}")
            # Continue without log file

        # Initialize log
        transfer_start_time = datetime.now()
        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"Transfer started at {transfer_start_time.isoformat()}\n")
                log.write(f"Source: {source_path}\n")
                log.write(f"Destination: {target_dir}\n")
                log.write(f"Files to transfer: {total_files}\n")
                log.write(f"Total size: {total_size / (1024*1024*1024):.2f} GB\n\n")
        except Exception as e:
            logger.error(f"Failed to initialize log file: {e}")
            # Continue without log file
            
        return transfer_start_time
        
    def _execute_file_transfers(self, files_to_transfer: List[Path], target_dir: Path, 
                              source_path: Path, total_files: int, total_size: int, 
                              mhl_data: Optional[Tuple], log_file: Path) -> Optional[Tuple[List[str], int]]:
        """
        Execute the transfer of all files.
        
        Args:
            files_to_transfer: List of files to transfer
            target_dir: Target directory for the transfer
            source_path: Path to source drive
            total_files: Total number of files to transfer
            total_size: Total size of files to transfer in bytes
            mhl_data: MHL file data tuple (filename, tree, hashes)
            log_file: Path to log file
            
        Returns:
            Optional[Tuple]: (failures, total_transferred) if successful, None otherwise
        """
        failures = []
        total_transferred = 0
        file_number = 0
        
        for src_file in files_to_transfer:
            file_number += 1
            success, size_transferred, failure = self._transfer_single_file(
                src_file, target_dir, source_path, 
                file_number, total_files, total_transferred, 
                total_size, mhl_data, log_file
            )
            
            if success:
                total_transferred += size_transferred
            else:
                failures.append(failure)
                
        return failures, total_transferred

    def _generate_destination_filename(self, source_path: Path) -> str:
        """
        Generate destination filename based on configuration settings.
        Uses file creation time for timestamp to prevent duplicates.
        
        Args:
            source_path: Original file path
            
        Returns:
            New filename according to configuration
        """
        # Validate source_path is a Path object
        if not isinstance(source_path, Path):
            logger.error(f"Invalid source_path type: {type(source_path).__name__}")
            try:
                source_path = Path(source_path)
            except Exception as e:
                logger.error(f"Could not convert {source_path} to Path: {e}")
                return str(source_path)  # Return string representation as fallback
        
        try:
            # Get original filename and extension
            try:
                original_name = source_path.stem
                extension = source_path.suffix
            except AttributeError as e:
                logger.error(f"Error accessing filename attributes: {e}")
                return str(source_path)
                
            # If we're not renaming with timestamp, just return original name
            if not self.config.rename_with_timestamp:
                return source_path.name
                
            # Get file creation time with specific exception handling
            try:
                stat_info = source_path.stat()
            except FileNotFoundError as e:
                logger.error(f"File not found when getting stats: {source_path}, {e}")
                return source_path.name
            except PermissionError as e:
                logger.error(f"Permission denied accessing file stats: {source_path}, {e}")
                return source_path.name
            except OSError as e:
                logger.error(f"OS error accessing file stats: {source_path}, {e}")
                return source_path.name
                
            possible_times = [
                stat_info.st_ctime,  # Creation time (Windows) / Status change time (Unix)
                stat_info.st_mtime,  # Modification time
                stat_info.st_atime   # Access time
            ]
            creation_time = min(possible_times)
            
            # Format timestamp according to configuration
            try:
                timestamp = datetime.fromtimestamp(creation_time).strftime(
                    self.config.timestamp_format
                )
            except ValueError as e:
                logger.error(f"Invalid timestamp format '{self.config.timestamp_format}': {e}")
                # Fallback to ISO format if timestamp format is invalid
                timestamp = datetime.fromtimestamp(creation_time).strftime("%Y%m%d_%H%M%S")
                
            # Build the new filename based on the template
            if self.config.preserve_original_filename:
                # Replace placeholders in the template
                try:
                    new_name = self.config.filename_template.format(
                        original=original_name,
                        timestamp=timestamp
                    )
                    return f"{new_name}{extension}"
                except KeyError as e:
                    logger.error(f"Invalid placeholder in filename template '{self.config.filename_template}': {e}")
                    # Fallback to simple concatenation
                    return f"{original_name}_{timestamp}{extension}"
                except ValueError as e:
                    logger.error(f"Invalid filename template '{self.config.filename_template}': {e}")
                    return f"{original_name}_{timestamp}{extension}"
            else:
                # Just use timestamp if we're not preserving original name
                return f"{timestamp}{extension}"
                
        except Exception as e:
            logger.error(f"Unexpected error generating destination filename for {source_path}: {e}", exc_info=True)
            # Fallback to original filename if anything goes wrong
            return source_path.name

    def _create_destination_path(self, source_path: Path, target_dir: Path, source_root: Path) -> Path:
        """
        Create the complete destination path for a file, maintaining proper directory structure.
        
        Args:
            source_path: Original file path
            target_dir: Base destination directory
            source_root: Root directory of the source (SD card mount point)
            
        Returns:
            Complete destination Path object
        """
        # Validate input parameters
        if not isinstance(source_path, Path) or not isinstance(target_dir, Path) or not isinstance(source_root, Path):
            logger.error(f"Invalid parameter types: source_path={type(source_path).__name__}, "
                        f"target_dir={type(target_dir).__name__}, "
                        f"source_root={type(source_root).__name__}")
            # Fallback: return a path in the target directory with original filename
            try:
                return target_dir / source_path.name
            except Exception:
                return target_dir / "unknown_file"
        
        try:
            # Generate the new filename according to configuration
            try:
                new_filename = self._generate_destination_filename(source_path)
            except Exception as e:
                logger.error(f"Failed to generate destination filename for {source_path}: {e}")
                new_filename = source_path.name  # Fall back to original filename
            
            # Get the relative path from the source root, not the entire mount path
            # This ensures we only preserve the directory structure from the SD card root
            try:
                rel_path = source_path.relative_to(source_root)
                # Get just the directory part, excluding the filename
                rel_dir = rel_path.parent
            except ValueError as e:
                # Fallback if relative_to fails
                logger.warning(f"Could not determine relative path for {source_path}: {e}")
                rel_dir = Path()
            except Exception as e:
                # Catch other unexpected errors with relative path calculation
                logger.error(f"Unexpected error calculating relative path for {source_path}: {e}")
                rel_dir = Path()
            
            # Combine target directory with relative directory and new filename
            dest_path = target_dir / rel_dir / new_filename
            
            # Ensure parent directories exist
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.error(f"Permission denied creating directory {dest_path.parent}: {e}")
                # Fallback to just using the target directory without subdirectories
                dest_path = target_dir / new_filename
            except OSError as e:
                logger.error(f"OS error creating directory {dest_path.parent}: {e}")
                # Fallback to just using the target directory without subdirectories
                dest_path = target_dir / new_filename
                
            return dest_path
            
        except Exception as e:
            logger.error(f"Error creating destination path for {source_path}: {e}", exc_info=True)
            # Fallback to simple path in target directory if anything goes wrong
            try:
                filename = source_path.name
            except Exception:
                filename = "unknown_file"
            return target_dir / filename

    def _log_success(self, log_file, src_path: Path, dst_path: Path) -> None:
        """
        Log successful file transfer.
        
        Args:
            log_file: Open file object for logging
            src_path: Source file path
            dst_path: Destination file path
        """
        if log_file is None:
            logger.warning("Cannot log success: log_file is None")
            return
            
        try:
            # Convert paths to strings safely
            src_str = str(src_path) if src_path is not None else "unknown_source"
            dst_str = str(dst_path) if dst_path is not None else "unknown_destination"
            
            # Format with timestamp for better logging
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] Success: {src_str} -> {dst_str}\n"
            
            # Write and flush with error handling
            try:
                log_file.write(log_entry)
                log_file.flush()
            except IOError as e:
                logger.warning(f"Failed to write to log file: {e}")
            
            logger.info(f"Transferred: {src_str}")
        except Exception as e:
            # Last resort error handler
            logger.warning(f"Error logging successful transfer: {e}")

    def _log_failure(self, log_file, src_path: Path, dst_path: Path, reason: str = None) -> None:
        """
        Log failed file transfer.
        
        Args:
            log_file: Open file object for logging
            src_path: Source file path
            dst_path: Destination file path
            reason: Optional reason for failure
        """
        if log_file is None:
            logger.warning("Cannot log failure: log_file is None")
            return
            
        try:
            # Convert paths to strings safely
            src_str = str(src_path) if src_path is not None else "unknown_source"
            dst_str = str(dst_path) if dst_path is not None else "unknown_destination"
            
            # Format with timestamp and reason for better diagnostics
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reason_text = f" - Reason: {reason}" if reason else ""
            log_entry = f"[{timestamp}] Failed: {src_str} -> {dst_str}{reason_text}\n"
            
            # Write and flush with error handling
            try:
                log_file.write(log_entry)
                log_file.flush()
            except IOError as e:
                logger.warning(f"Failed to write to log file: {e}")
            
            # Include reason in log message if available
            if reason:
                logger.error(f"Failed to transfer: {src_str} - {reason}")
            else:
                logger.error(f"Failed to transfer: {src_str}")
        except Exception as e:
            # Last resort error handler
            logger.warning(f"Error logging failed transfer: {e}")

    def _play_sound(self, success: bool = True) -> None:
        """
        Safely play a sound effect.
        
        Args:
            success: True to play success sound, False to play error sound
        """
        # Early return if sound manager is not available
        if not hasattr(self, 'sound_manager') or self.sound_manager is None:
            logger.debug("Sound manager not available, skipping sound effect")
            return
            
        # Check if sounds are enabled in configuration
        try:
            if hasattr(self, 'config') and hasattr(self.config, 'enable_sounds') and not self.config.enable_sounds:
                logger.debug("Sounds disabled in configuration, skipping sound effect")
                return
        except Exception as e:
            # Don't let configuration check errors prevent trying to play sound
            logger.debug(f"Error checking sound configuration: {e}")
        
        try:
            if success:
                self.sound_manager.play_success()
                logger.debug("Played success sound")
            else:
                self.sound_manager.play_error()
                logger.debug("Played error sound")
        except AttributeError as e:
            # Sound manager exists but methods are missing
            logger.warning(f"Sound manager missing required methods: {e}")
        except RuntimeError as e:
            # Sound system might not be initialized
            logger.warning(f"Sound system runtime error: {e}")
        except Exception as e:
            logger.error(f"Error playing sound effect: {e}")

    def _recover_interrupted_transfers(self, target_dir: Path) -> None:
        """
        Check for and clean up any .TBPART files from previously interrupted transfers.
        
        Args:
            target_dir: Target directory to check for interrupted transfers
        """
        try:
            # Find all .TBPART files in the target directory and its subdirectories
            part_files = list(target_dir.glob(f"**/*{TEMP_FILE_EXTENSION}"))
            
            if part_files:
                logger.info(f"Found {len(part_files)} incomplete transfers from previous session")
                self.display.show_status(f"Cleaning up {len(part_files)} incomplete transfers...")
                
                # Remove all partial files
                for part_file in part_files:
                    try:
                        part_file.unlink()
                        logger.info(f"Removed incomplete file: {part_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove incomplete file {part_file}: {e}")
                        
                self.display.show_status("Cleanup complete")
                
        except Exception as e:
            logger.error(f"Error recovering interrupted transfers: {e}")