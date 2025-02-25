# src/core/file_transfer.py

import logging
import os
import shutil 
import time
import platform
from pathlib import Path
from typing import Optional, Tuple, List
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
        """
        try:
            # Convert to Path object if it isn't already
            path = Path(path)
            
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
            next(path.iterdir())
            return True
            
        except StopIteration:
            # Empty directory is valid
            return True
        except PermissionError:
            logger.error(f"Permission denied accessing source: {path}")
            return False
        except Exception as e:
            logger.error(f"Error verifying source access: {path}, {e}")
            return False

    def _get_transferable_files(self, source_path: Path) -> List[Path]:
        """
        Get list of files to transfer with improved path handling.
        """
        files_to_transfer = []
        try:
            # Convert source path to Path object for consistent handling
            source_path = Path(source_path)
            
            # First verify the source path is accessible
            if not self._verify_source_access(source_path):
                logger.error(f"Source path not accessible: {source_path}")
                return []

            # Walk the directory structure safely
            for path in source_path.rglob('*'):
                try:
                    # Skip directories and hidden files
                    if path.is_dir() or path.name.startswith('.'):
                        continue
                        
                    # Skip system directories
                    if 'System Volume Information' in str(path):
                        continue
                        
                    # Apply media filter if configured
                    if self.config.media_only_transfer:
                        if any(path.name.lower().endswith(ext) 
                            for ext in self.config.media_extensions):
                            files_to_transfer.append(path)
                    else:
                        files_to_transfer.append(path)
                        
                except PermissionError:
                    logger.warning(f"Permission denied accessing: {path}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing file {path}: {e}")
                    continue

            return files_to_transfer
            
        except Exception as e:
            logger.error(f"Error scanning for files: {e}")
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
        """
        try:
            # Handle platform-specific path validation
            if platform.system().lower() == 'darwin':
                # For macOS, ensure paths to external drives start with /Volumes/
                if not str(path).startswith('/Volumes/'):
                    raise ValueError("External drive paths must start with /Volumes/")
            elif platform.system().lower() == 'windows':
                # For Windows, ensure path has a drive letter
                if not path.drive:
                    raise ValueError("Windows paths must include a drive letter")
            
            # Check if the path's drive/volume exists and is accessible
            drive_path = Path(path.drive + '\\') if os.name == 'nt' else Path('/Volumes')
            if not drive_path.exists():
                raise ValueError(f"Drive/volume not found: {drive_path}")
                
            # Check if we have permission to write to the drive
            try:
                if not os.access(drive_path, os.W_OK):
                    raise ValueError(f"No write permission for drive: {drive_path}")
            except OSError:
                # Handle access check failures
                raise ValueError(f"Cannot verify permissions for drive: {drive_path}")
                
            return path
            
        except Exception as e:
            logger.error(f"Error validating destination path '{path}': {e}")
            raise ValueError(str(e))


    def _copy_with_progress(self, src_path: Path, dst_path: Path, 
                        file_number: int, total_files: int,
                        total_transferred: int, total_size: int) -> Tuple[bool, Optional[str]]:
        """Copy a file with progress updates and metadata preservation"""
        try:
            # Get source metadata before copy
            source_metadata = self.storage.get_file_metadata(src_path)
            
            file_size = src_path.stat().st_size
            xxh64_hash = self.checksum_calculator.create_hash()
            
            # First phase: Copy with progress
            with open(src_path, 'rb') as src, open(dst_path, 'wb') as dst:
                bytes_transferred = 0
                while True:
                    chunk = src.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    dst.write(chunk)
                    xxh64_hash.update(chunk)
                    bytes_transferred += len(chunk)
                    
                    # Update progress with both file and total progress
                    if self._current_progress:
                        self._current_progress.bytes_transferred = bytes_transferred
                        self._current_progress.current_file_progress = bytes_transferred / file_size
                        self._current_progress.total_transferred = total_transferred + bytes_transferred
                        self._current_progress.status = TransferStatus.COPYING
                        self.display.show_progress(self._current_progress)

            # Second phase: Apply metadata (unchanged)
            if source_metadata:
                if not self.storage.set_file_metadata(dst_path, source_metadata):
                    logger.warning(f"Failed to preserve metadata for {dst_path}")

            # Third phase: Verify checksum
            if self._current_progress:
                self._current_progress.status = TransferStatus.CHECKSUMMING
            verify_success = self.checksum_calculator.verify_checksum(
                dst_path,
                xxh64_hash.hexdigest(),
                current_progress=self._current_progress
            )

            if not verify_success:
                return False, None

            return True, xxh64_hash.hexdigest()
            
        except Exception as e:
            self._play_sound(success=False)
            logger.error(f"Error copying file {src_path}: {e}")
            return False, None

    def _validate_transfer_preconditions(self, destination_path: Path) -> bool:
        """
        Validate preconditions before starting transfer with improved path handling.
        """
        try:
            if destination_path is None:
                self.display.show_error("No destination")
                return False
                
            if self.state_manager.is_utility():
                logger.info("Transfer blocked - utility mode")
                return False

            # Convert to Path object to ensure consistent handling
            dest_path = Path(destination_path)
            
            # Verify the destination exists and is accessible
            if dest_path.exists():
                if not dest_path.is_dir():
                    self.display.show_error("Not a directory")
                    return False
                    
                # Check write permissions
                if not os.access(dest_path, os.W_OK):
                    self.display.show_error("Write permission denied")
                    return False
                    
                logger.info(f"Using existing directory: {dest_path}")
                return True

            # Path doesn't exist, check parent directory
            parent = dest_path.parent
            if not parent.exists():
                self.display.show_error("Parent dir missing")
                return False
                
            if not os.access(parent, os.W_OK):
                self.display.show_error("Parent write denied")
                return False
                
            # Try to create the directory
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {dest_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to create directory: {e}")
                self.display.show_error("Create dir failed")
                return False
                
        except Exception as e:
            logger.error(f"Error validating path: {e}")
            self.display.show_error("Invalid path")
            return False

    def copy_sd_to_dump(self, source_path: Path, destination_path: Path, 
                        log_file: Path) -> bool:
        """
        Copy files from source to destination with comprehensive validation and error handling.
        
        This function manages the complete transfer process including:
        - Source and destination validation
        - File detection and filtering
        - Directory structure creation
        - File copying with progress tracking
        - Checksum generation and verification
        - MHL (Media Hash List) creation
        - Safe unmounting of source drive
        
        Args:
            source_path: Path to source drive (e.g., SD card)
            destination_path: Path where files should be copied
            log_file: Path for transfer log file
            
        Returns:
            bool: True if transfer successful, False if any critical operation fails
        """
        # First validate that we can proceed with the transfer
        if not self._validate_transfer_preconditions(destination_path):
            self._play_sound(success=False)
            return False

        # Verify source drive accessibility
        try:
            if not source_path.exists() or not os.access(str(source_path), os.R_OK):
                logger.error(f"Source path not accessible: {source_path}")
                self.display.show_error("Source Error")
                return False
            
            # Test directory listing
            test_list = list(source_path.iterdir())
            logger.info(f"Source directory contains {len(test_list)} items")
            
        except Exception as e:
            logger.error(f"Error accessing source path: {e}")
            self.display.show_error("Access Error")
            return False

        # Generate timestamp for this transfer session
        timestamp = datetime.now().strftime(self.config.timestamp_format)
        
        # Log the current configuration state
        logger.info(f"Starting transfer with configuration:")
        logger.info(f"  create_date_folders: {self.config.create_date_folders}")
        logger.info(f"  destination_path: {destination_path}")
        
        # Create target directory using directory handler
        target_dir = self.directory_handler.create_organized_directory(
            destination_path,
            source_path,
            timestamp if self.config.create_date_folders else None
        )

        unmount_success = False
        transfer_success = False

        try:
            # Initialize MHL handling for transfer verification
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
            
            # Get card name for organization
            card_name = source_path.name or "unnamed_card"
            
            # Get complete file list using improved file detection
            files_to_transfer = []
            try:
                # Walk through the directory structure with error handling
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
                                    
                            except Exception as file_err:
                                logger.error(f"Error processing file {filename}: {file_err}")
                                continue
                                
                    except Exception as dir_err:
                        logger.error(f"Error processing directory {root}: {dir_err}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error scanning for files: {e}")
                self.display.show_error("Scan Failed")
                return False

            # Verify we found files to transfer
            if not files_to_transfer:
                logger.warning("No files found to transfer")
                self.display.show_error("No Files Found")
                return False

            # Calculate transfer totals with error handling
            try:
                total_size = sum(f.stat().st_size for f in files_to_transfer)
                total_files = len(files_to_transfer)
                
                logger.info(f"Transfer mode: {'Media only' if self.config.media_only_transfer else 'All files'}")
                logger.info(f"Total files to transfer: {total_files}")
                logger.info(f"Total transfer size: {total_size / (1024*1024*1024):.2f} GB")
                
            except Exception as e:
                logger.error(f"Error calculating transfer totals: {e}")
                self.display.show_error("Size Calc Error")
                return False
                
            # Verify sufficient space (with 10% buffer)
            required_space = int(total_size * 1.1)
            if not self.storage.has_enough_space(destination_path, required_space):
                self.display.show_error("Not enough space")
                self._play_sound(success=False)
                return False
                
            # Initialize transfer state
            self.state_manager.enter_transfer()
            
            try:
                file_number = 0
                total_transferred = 0
                failures = []

                with open(log_file, 'a', encoding='utf-8') as log:
                    # Create required directory structure
                    if self.config.preserve_folder_structure:
                        required_directories = set()
                        for file_path in files_to_transfer:
                            rel_path = file_path.parent.relative_to(source_path)
                            target_path = target_dir / rel_path
                            required_directories.add(target_path)
                            
                        for dir_path in sorted(required_directories):
                            dir_path.mkdir(parents=True, exist_ok=True)
                            logger.debug(f"Created directory: {dir_path}")

                    # Transfer each file
                    for src_file in files_to_transfer:
                        file_number += 1
                        file_size = src_file.stat().st_size
                        
                        # Create destination path preserving structure
                        dst_path = self._create_destination_path(
                            src_file, 
                            target_dir, 
                            source_path
                        )
                        
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
                            total_transferred += file_size
                            self._log_success(log, src_file, dst_path)
                            
                            # Add file to MHL for verification
                            add_file_to_mhl(
                                mhl_filename, tree, hashes,
                                dst_path, checksum,
                                file_size
                            )
                        else:
                            failures.append(str(src_file))
                            self._log_failure(log, src_file, dst_path)

                    # Determine transfer success
                    transfer_success = len(failures) == 0
                    
                    if transfer_success:
                        logger.info("Transfer completed successfully")
                        self._play_sound(success=True)
                        
                        # Update final progress
                        if self._current_progress:
                            self._current_progress.status = TransferStatus.SUCCESS
                            self._current_progress.total_transferred = total_size
                            self.display.show_progress(self._current_progress)
                        
                        # Handle unmounting
                        if self.storage.is_drive_mounted(source_path):
                            if self.storage.unmount_drive(source_path):
                                unmount_success = True
                                self.display.show_status("Safe to remove card")
                            else:
                                self.display.show_error("Unmount failed")
                        else:
                            unmount_success = True
                            self.display.show_status("Safe to remove card")
                    else:
                        self._play_sound(success=False)
                        self.display.show_error("Transfer Failed")
                        logger.error("Transfer failed for files: %s", ", ".join(failures))
                    
                    return transfer_success
                    
            except Exception as e:
                logger.error(f"Transfer failed: {e}")
                self._play_sound(success=False)
                if self._current_progress:
                    self._current_progress.status = TransferStatus.ERROR
                    self.display.show_progress(self._current_progress)
                else:
                    self.display.show_error("Transfer Error")
                return False
                
        finally:
            # Cleanup and state management
            if self.state_manager.is_transfer():
                self.state_manager.exit_transfer(source_path if not unmount_success else None)
            if transfer_success and not unmount_success:
                self.display.show_status("Transfer complete")


    def _generate_destination_filename(self, source_path: Path) -> str:
        """
        Generate destination filename based on configuration settings.
        
        This method implements the file renaming logic according to the configuration:
        - Can preserve original filename
        - Can add timestamps in configured format
        - Uses configured filename template
        
        Args:
            source_path: Original file path
            
        Returns:
            New filename according to configuration settings
        """
        try:
            # Get original filename and extension
            original_name = source_path.stem
            extension = source_path.suffix
            
            # If we're not renaming with timestamp, just return original name
            if not self.config.rename_with_timestamp:
                return source_path.name
                
            # Get file creation time
            stat_info = source_path.stat()
            possible_times = [
                stat_info.st_ctime,  # Creation time (Windows) / Status change time (Unix)
                stat_info.st_mtime,  # Modification time
                stat_info.st_atime   # Access time
            ]
            creation_time = min(possible_times)
            
            # Format timestamp according to configuration
            timestamp = datetime.fromtimestamp(creation_time).strftime(
                self.config.timestamp_format
            )
            
            # Build the new filename based on the template
            if self.config.preserve_original_filename:
                # Replace placeholders in the template
                new_name = self.config.filename_template.format(
                    original=original_name,
                    timestamp=timestamp
                )
                return f"{new_name}{extension}"
            else:
                # Just use timestamp if we're not preserving original name
                return f"{timestamp}{extension}"
                
        except Exception as e:
            logger.error(f"Error generating destination filename for {source_path}: {e}")
            # Fallback to original filename if anything goes wrong
            return source_path.name

    def _create_destination_path(self, source_path: Path, target_dir: Path, source_root: Path) -> Path:
        """
        Create the complete destination path for a file, maintaining proper directory structure.ning proper directory structure.
        
        Args:
            source_path: Original file path
            target_dir: Base destination directory
            source_root: Root directory of the source (SD card mount point)SD card mount point)
            
        Returns:
            Complete destination Path object
        """
        try:
            # Generate the new filename according to configuration
            new_filename = self._generate_destination_filename(source_path)
            
            # Get the relative path from the source root, not the entire mount path
            # This ensures we only preserve the directory structure from the SD card root
            try:
                rel_path = source_path.relative_to(source_root)
                # Get just the directory part, excluding the filename
                rel_dir = rel_path.parent
            except ValueError:
                # Fallback if relative_to fails
                logger.warning(f"Could not determine relative path for {source_path}")
                rel_dir = Path()
            
            # Combine target directory with relative directory and new filename
            dest_path = target_dir / rel_dir / new_filename
            # Ensure parent directories exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            return dest_path
            
        except Exception as e:
            logger.error(f"Error creating destination path for {source_path}: {e}")
            # Fallback to simple path in target directory if anything goes wrong
            # Fallback to simple path in target directory if anything goes wrong

    def _process_files(self, source_path: Path, target_dir: Path, 
                    file_list: list, log_file: Path,
                    mhl_filename: Path, tree, hashes) -> bool:
        """Process all files in the transfer."""
        try:
            total_files = sum(1 for f in file_list if f.is_file())
            file_number = 0
            failures = []

            with open(log_file, 'a', encoding='utf-8') as log:
                for src_file in file_list:
                    if not src_file.is_file():
                        continue

                    file_number += 1
                    rel_path = src_file.relative_to(source_path)
                    
                    # Create timestamped filename for the destination
                    timestamped_name = self._get_timestamp_filename(src_file)
                    # Use the parent directory from rel_path but with new filename
                    dst_path = target_dir / rel_path.parent / timestamped_name
                    
                    # Ensure destination directory exists
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Initialize progress tracking
                    self._current_progress = TransferProgress(
                        current_file=src_file.name,
                        file_number=file_number,
                        total_files=total_files,
                        bytes_transferred=0,
                        total_bytes=src_file.stat().st_size,
                        current_file_progress=0.0,
                        overall_progress=(file_number - 1) / total_files,
                        status=TransferStatus.COPYING
                    )

                    # Copy and verify file
                    success, checksum = self._copy_with_progress(
                        src_file, dst_path,
                        file_number, total_files
                    )

                    if success and checksum:
                        self._log_success(log, src_file, dst_path)
                        add_file_to_mhl(
                            mhl_filename, tree, hashes,
                            dst_path, checksum,
                            dst_path.stat().st_size
                        )
                    else:
                        failures.append(str(src_file))
                        self._log_failure(log, src_file, dst_path)

                return len(failures) == 0

        except Exception as e:
            logger.error(f"Error processing files: {e}")
            return False

    def _log_success(self, log_file, src_path: Path, dst_path: Path) -> None:
        """Log successful file transfer."""
        log_file.write(f"Success: {src_path} -> {dst_path}\n")
        log_file.flush()
        logger.info(f"Transferred: {src_path}")

    def _log_failure(self, log_file, src_path: Path, dst_path: Path) -> None:
        """Log failed file transfer."""
        log_file.write(f"Failed: {src_path} -> {dst_path}\n")
        log_file.flush()
        logger.error(f"Failed to transfer: {src_path}")

    def _play_sound(self, success: bool = True) -> None:
        """
        Safely play a sound effect.
        
        Args:
            success: True to play success sound, False to play error sound
        """
        if not hasattr(self, 'sound_manager') or self.sound_manager is None:
            return
            
        try:
            if success:
                self.sound_manager.play_success()
            else:
                self.sound_manager.play_error()
        except Exception as e:
            logger.error(f"Error playing sound effect: {e}")