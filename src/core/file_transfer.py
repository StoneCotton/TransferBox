# src/core/file_transfer.py

import logging
import os
import shutil 
import time
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from .interfaces.display import DisplayInterface
from .interfaces.storage import StorageInterface
from .interfaces.types import TransferStatus, TransferProgress
from .checksum import ChecksumCalculator
from .mhl_handler import initialize_mhl_file, add_file_to_mhl

logger = logging.getLogger(__name__)

CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks for efficient large file handling

class FileTransferError(Exception):
    """Custom exception for file transfer errors"""
    pass

class FileTransfer:
    def __init__(self, state_manager, display: DisplayInterface, storage: StorageInterface):
        self.state_manager = state_manager
        self.display = display
        self.storage = storage
        self._current_progress: Optional[TransferProgress] = None
        self.checksum_calculator = ChecksumCalculator(display)

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
                        file_number: int, total_files: int) -> Tuple[bool, Optional[str]]:
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
                    
                    self._update_progress(
                        bytes_transferred, file_size,
                        file_number, total_files,
                        TransferStatus.COPYING
                    )

            # Second phase: Apply metadata
            if source_metadata:
                if not self.storage.set_file_metadata(dst_path, source_metadata):
                    logger.warning(f"Failed to preserve metadata for {dst_path}")

            # Third phase: Verify checksum
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
        """Copy files from source to destination with verification."""
        if not self._validate_transfer_preconditions(destination_path):
            return False

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_dir = self._create_target_directory(destination_path, timestamp)
        unmount_success = False
        transfer_success = False
        
        try:
            # Initialize MHL handling
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
            
            # Get file list
            file_list = list(source_path.rglob('*'))
            total_size = sum(f.stat().st_size for f in file_list if f.is_file())
            
            # Add 10% buffer for temporary files and overhead
            required_space = int(total_size * 1.1)
            
            logger.info(f"Required space: {required_space / (1024*1024*1024):.2f} GB")
            
            # Check available space with detailed logging
            try:
                drive_info = self.storage.get_drive_info(target_dir)
                available_space = drive_info['free']
                logger.info(f"Available space: {available_space / (1024*1024*1024):.2f} GB")
                
                if available_space < required_space:
                    space_needed = (required_space - available_space) / (1024*1024*1024)
                    error_msg = f"Insufficient space. Need {space_needed:.2f} GB more"
                    logger.error(error_msg)
                    self.display.show_error(error_msg)
                    return False
                    
            except Exception as e:
                logger.error(f"Error checking space: {e}")
                self.display.show_error(f"Space check failed: {str(e)}")
                return False

            # Initialize transfer state before starting work
            self.state_manager.enter_transfer()
            
            # Perform transfer
            transfer_success = self._process_files(
                source_path, target_dir, file_list,
                log_file, mhl_filename, tree, hashes
            )

            # Handle completion
            if transfer_success:
                logger.info("Transfer completed successfully")
                
                # Update progress to success state before unmounting
                if self._current_progress:
                    self._current_progress.status = TransferStatus.SUCCESS
                    self.display.show_progress(self._current_progress)
                
                # Only try to unmount if the drive is still mounted
                if self.storage.is_drive_mounted(source_path):
                    if self.storage.unmount_drive(source_path):
                        unmount_success = True
                        self.display.show_status("Safe to remove card")
                    else:
                        self.display.show_error("Unmount failed")
                else:
                    # Drive is already unmounted
                    unmount_success = True
                    self.display.show_status("Safe to remove card")
            
            return transfer_success

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            if self._current_progress:
                self._current_progress.status = TransferStatus.ERROR
                self.display.show_progress(self._current_progress)
            else:
                self.display.show_error("Transfer Error")
            return False
            
        finally:
            # Only exit transfer state if we entered it
            if self.state_manager.is_transfer():
                self.state_manager.exit_transfer(source_path if not unmount_success else None)
            # Show final status only if we haven't already shown it
            if transfer_success and not unmount_success:
                self.display.show_status("Transfer complete")

    def _create_target_directory(self, base_path: Path, timestamp: str) -> Path:
        """Create timestamped directory for transfer."""
        target_dir = base_path / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir
    
    def _get_timestamp_filename(self, original_path: Path) -> str:
        """
        Create a new filename that includes the file's creation timestamp.
        
        For example, transforms:
            MVI_3045.MP4 (created 2024-11-21 09:23:08)
        into:
            MVI_3045_2024112109-23-08.MP4
        
        Args:
            original_path: Path to the original file
            
        Returns:
            New filename with embedded timestamp
        """
        try:
            # Get file creation time - we'll look for multiple possible timestamps
            # and use the earliest one as the true creation time
            stat_info = original_path.stat()
            possible_times = [
                stat_info.st_ctime,  # Creation time (Windows) / Status change time (Unix)
                stat_info.st_mtime,  # Modification time
                stat_info.st_atime   # Access time
            ]
            
            # Use the earliest timestamp as the creation time
            creation_time = min(possible_times)
            timestamp = datetime.fromtimestamp(creation_time)
            
            # Split the original filename and extension
            stem = original_path.stem
            suffix = original_path.suffix
            
            # Create the new filename with timestamp
            # Format: {original_name}_{YYYYMMDDHH-MM-SS}{extension}
            new_filename = f"{stem}_{timestamp.strftime('%Y%m%d%H-%M-%S')}{suffix}"
            
            logger.debug(f"Renamed {original_path.name} to {new_filename}")
            return new_filename
            
        except Exception as e:
            # If anything goes wrong, log it but return original filename
            logger.error(f"Error creating timestamp filename for {original_path}: {e}")
            return original_path.name

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