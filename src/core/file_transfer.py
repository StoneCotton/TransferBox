# src/core/file_transfer.py

import logging
import os
import shutil 
import time
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from .config_manager import TransferConfig
from .interfaces.display import DisplayInterface
from .interfaces.storage import StorageInterface
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
        """Validate preconditions before starting transfer."""
        if destination_path is None:
            self.display.show_error("No destination")
            return False
            
        if self.state_manager.is_utility():
            logger.info("Transfer blocked - utility mode")
            return False
            
        return True

    def copy_sd_to_dump(self, source_path: Path, destination_path: Path, 
                        log_file: Path) -> bool:
        """
        Copy files from source to destination with directory organization and proxy generation.
        
        Args:
            source_path: Path to source drive
            destination_path: Path to destination drive
            log_file: Path to transfer log file
            
        Returns:
            bool: True if transfer was successful, False otherwise
        """
        if not self._validate_transfer_preconditions(destination_path):
            self._play_sound(success=False)
            return False

        # Generate timestamp for this transfer session
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create organized directory structure
        target_dir = self.directory_handler.create_organized_directory(
            destination_path,
            source_path,
            timestamp
        )
        
        unmount_success = False
        transfer_success = False
        
        try:
            # Initialize MHL handling for transfer verification
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
            
            # Initialize proxy generator if enabled
            proxy_generator = None
            if self.config.generate_proxies:
                proxy_generator = ProxyGenerator(self.config, self.display)
            
            # Get complete file list from source
            all_files = list(source_path.rglob('*'))
            
            # Smart file filtering and directory tracking
            files_to_transfer = []
            required_directories = set()
            
            if self.config.media_only_transfer:
                # First pass: identify media files and their parent directories
                for file_path in all_files:
                    if file_path.is_file():
                        if file_path.suffix.lower() in self.config.media_extensions:
                            files_to_transfer.append(file_path)
                            # Add all parent directories of this media file
                            if self.config.preserve_folder_structure:
                                current_dir = file_path.parent
                                while current_dir != source_path:
                                    required_directories.add(current_dir)
                                    current_dir = current_dir.parent
            else:
                # If not media only, include all files and their directories
                files_to_transfer = [f for f in all_files if f.is_file()]
                if self.config.preserve_folder_structure:
                    required_directories = {
                        f.parent for f in all_files if f.is_file()
                    }
            
            # Calculate totals for transfer
            total_size = sum(f.stat().st_size for f in files_to_transfer)
            total_files = len(files_to_transfer)
            
            # Log transfer configuration and statistics
            logger.info(f"Transfer mode: {'Media only' if self.config.media_only_transfer else 'All files'}")
            if self.config.media_only_transfer:
                logger.info(f"Media extensions: {', '.join(self.config.media_extensions)}")
            logger.info(f"Total files to transfer: {total_files}")
            logger.info(f"Required directories: {len(required_directories)}")
            logger.info(f"Total transfer size: {total_size / (1024*1024*1024):.2f} GB")
            
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
                created_dirs = set()

                with open(log_file, 'a', encoding='utf-8') as log:
                    # Create only the necessary directory structure
                    if self.config.preserve_folder_structure:
                        for dir_path in sorted(required_directories):
                            # Convert source directory path to destination directory path
                            rel_path = dir_path.relative_to(source_path)
                            target_path = target_dir / rel_path
                            
                            # Create directory and all necessary parents
                            if target_path not in created_dirs:
                                target_path.mkdir(parents=True, exist_ok=True)
                                created_dirs.add(target_path)
                                logger.debug(f"Created directory: {target_path}")

                    # Transfer files
                    for src_file in files_to_transfer:
                        file_number += 1
                        file_size = src_file.stat().st_size
                        
                        # Create destination path maintaining structure if enabled
                        dst_path = self._create_destination_path(src_file, target_dir, source_path)
                        
                        # Ensure the destination directory exists
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        
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
                            add_file_to_mhl(
                                mhl_filename, tree, hashes,
                                dst_path, checksum,
                                file_size
                            )
                            
                            # Generate proxy if needed and file was copied successfully
                            if (proxy_generator and 
                                proxy_generator.should_generate_proxy(src_file)):
                                
                                proxy_success = proxy_generator.generate_proxy(
                                    dst_path,  # Use the copied file as source
                                    target_dir,
                                    self._current_progress
                                )
                                
                                if not proxy_success:
                                    logger.warning(f"Failed to generate proxy for {src_file}")
                        else:
                            failures.append(str(src_file))
                            self._log_failure(log, src_file, dst_path)

                    # Determine transfer success and handle completion
                    transfer_success = len(failures) == 0
                    
                    if transfer_success:
                        logger.info("Transfer completed successfully")
                        self._play_sound(success=True)
                        
                        # Update final progress
                        if self._current_progress:
                            self._current_progress.status = TransferStatus.SUCCESS
                            self._current_progress.total_transferred = total_size
                            self.display.show_progress(self._current_progress)
                        
                        # Handle unmounting if drive is still mounted
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

    def _create_target_directory(self, base_path: Path, timestamp: str) -> Path:
        """Create timestamped directory for transfer."""
        target_dir = base_path / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir
    
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
        Create the complete destination path for a file, maintaining proper directory structure.
        
        Args:
            source_path: Original file path
            target_dir: Base destination directory
            source_root: Root directory of the source (SD card mount point)
            
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
            return target_dir / new_filename

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