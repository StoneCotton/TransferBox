# src/core/progress_tracker.py

import logging
from typing import Optional, Callable, Dict, Any
import time
from .interfaces.types import TransferStatus, TransferProgress
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Class for tracking transfer progress."""
    
    def __init__(self, display=None):
        """
        Initialize the progress tracker.
        
        Args:
            display: Optional display interface for showing progress
        """
        self.display = display
        self.current_file = None
        self.file_number = 0
        self.total_files = 0
        self.bytes_transferred = 0
        self.total_bytes = 0
        self.total_transferred = 0
        self.total_size = 0
        self.current_file_progress = 0.0
        self.overall_progress = 0.0
        self.status = TransferStatus.READY
        self.source_drive_name = ""
        self.source_drive_path = ""
        
        # Time tracking for speed and ETA calculation
        self.start_time = time.time()
        self.file_start_time = time.time()
        self.checksum_start_time = None  # Track checksum start time
        self.last_update_time = time.time()
        self.last_bytes = 0
        self.speed_bytes_per_sec = 0
        self.eta_seconds = 0

    def start_transfer(self, total_files: int, total_size: int) -> None:
        """
        Start tracking progress for the entire transfer operation.
        
        Args:
            total_files: Total number of files to transfer
            total_size: Total size of all files in bytes
        """
        self.total_files = total_files
        self.total_size = total_size
        self.total_transferred = 0
        self.file_number = 0
        self.overall_progress = 0.0
        self.status = TransferStatus.READY
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_bytes = 0
        self.checksum_start_time = None
        self._update_display()
    
    def start_file(self, file_path, file_number: int, total_files: int, 
                 file_size: int, total_size: int, total_transferred: int) -> None:
        """
        Start tracking progress for a new file.
        
        Args:
            file_path: Path to the file being transferred
            file_number: Current file number
            total_files: Total number of files
            file_size: Size of the current file in bytes
            total_size: Total size of all files in bytes
            total_transferred: Total bytes transferred so far
        """
        self.current_file = str(file_path.name)
        self.file_number = file_number
        self.total_files = total_files
        self.bytes_transferred = 0
        self.total_bytes = file_size
        self.total_transferred = total_transferred
        self.total_size = total_size
        self.current_file_progress = 0.0
        self.overall_progress = (file_number - 1) / total_files
        self.status = TransferStatus.COPYING
        self.file_start_time = time.time()
        self.checksum_start_time = None
        self.last_update_time = time.time()
        self.last_bytes = 0
        self._update_display()
    
    def update_progress(self, bytes_transferred: int = None, files_processed: int = None, 
                      total_files: int = None, status: TransferStatus = None) -> None:
        """
        Update progress for the current file or overall transfer.
        
        Args:
            bytes_transferred: Bytes transferred for the current file
            files_processed: Number of files processed (for overall progress)
            total_files: Total number of files
            status: Current transfer status
        """
        current_time = time.time()
        
        # Handle overall transfer progress updates
        if files_processed is not None:
            self.file_number = files_processed
            
        if total_files is not None:
            self.total_files = total_files
            
        if status is not None:
            self.status = status
            
        # Handle file-specific progress updates
        if bytes_transferred is not None:
            # Calculate the additional bytes since last update 
            additional_bytes = bytes_transferred - self.bytes_transferred
            if additional_bytes > 0 and self.status == TransferStatus.COPYING:
                # Only update total_transferred during copy operations, not checksumming
                self.total_transferred += additional_bytes
                
            # Update current file progress
            self.bytes_transferred = bytes_transferred
            self.current_file_progress = bytes_transferred / self.total_bytes if self.total_bytes > 0 else 1.0
            
            # Calculate speed (bytes per second)
            time_delta = current_time - self.last_update_time
            if time_delta > 0.1:  # Only update speed every 100ms to prevent division by zero/small numbers
                bytes_delta = bytes_transferred - self.last_bytes
                # Calculate instant speed (with smoothing)
                instant_speed = bytes_delta / time_delta
                # Apply exponential moving average (EMA) for smoother speed display
                alpha = 0.3  # Smoothing factor
                self.speed_bytes_per_sec = alpha * instant_speed + (1 - alpha) * self.speed_bytes_per_sec
                
                # Calculate ETA
                if self.speed_bytes_per_sec > 0:
                    if self.status == TransferStatus.COPYING:
                        # ETA for current file
                        bytes_remaining = self.total_bytes - bytes_transferred
                        self.eta_seconds = bytes_remaining / self.speed_bytes_per_sec
                    else:
                        # ETA for overall transfer
                        bytes_remaining = self.total_size - self.total_transferred
                        self.eta_seconds = bytes_remaining / self.speed_bytes_per_sec
                
                # Update time and bytes for next calculation
                self.last_update_time = current_time
                self.last_bytes = bytes_transferred
            
        # Calculate overall progress
        if self.total_files > 0:
            if bytes_transferred is not None:
                # If updating a specific file's progress
                self.overall_progress = (self.file_number - 1 + self.current_file_progress) / self.total_files
            else:
                # If just updating overall file count
                self.overall_progress = self.file_number / self.total_files
        else:
            self.overall_progress = 0.0
        
        # Update the display
        self._update_display()
    
    def set_status(self, status: TransferStatus) -> None:
        """
        Set the current transfer status.
        
        Args:
            status: New transfer status
        """
        self.status = status
        if status == TransferStatus.CHECKSUMMING:
            self.checksum_start_time = time.time()
        self._update_display()
    
    def complete_file(self, success: bool = True) -> None:
        """
        Mark the current file as complete.
        
        Args:
            success: Whether the transfer was successful
        """
        self.status = TransferStatus.SUCCESS if success else TransferStatus.ERROR
        self.current_file_progress = 1.0
        self.overall_progress = self.file_number / self.total_files if self.total_files > 0 else 1.0
        
        # Make sure bytes_transferred matches total_bytes for display consistency
        if success and self.bytes_transferred < self.total_bytes:
            self.bytes_transferred = self.total_bytes
        
        self._update_display()
    
    def complete_transfer(self, successful: bool = True, stopped: bool = False) -> None:
        """
        Mark the entire transfer as complete.
        
        Args:
            successful: Whether the transfer was successful
            stopped: Whether the transfer was stopped gracefully by user
        """
        if stopped:
            self.status = TransferStatus.STOPPED
        else:
            self.status = TransferStatus.SUCCESS if successful else TransferStatus.ERROR
            
        self.overall_progress = 1.0
        
        # For display consistency, make sure total_transferred matches total_size for successful transfers
        if (successful or stopped) and self.total_transferred < self.total_size:
            self.total_transferred = self.total_size
            
        self._update_display()
    
    def _update_display(self) -> None:
        """Update the display with current progress."""
        if self.display:
            try:
                now = time.time()
                total_elapsed = now - self.start_time if self.start_time else 0.0
                file_elapsed = now - self.file_start_time if self.file_start_time else 0.0
                checksum_elapsed = (now - self.checksum_start_time) if (self.checksum_start_time and self.status == TransferStatus.CHECKSUMMING) else 0.0
                progress = TransferProgress(
                    current_file=self.current_file,
                    file_number=self.file_number,
                    total_files=self.total_files,
                    bytes_transferred=self.bytes_transferred,
                    total_bytes=self.total_bytes,
                    total_transferred=self.total_transferred,
                    total_size=self.total_size,
                    current_file_progress=self.current_file_progress,
                    overall_progress=self.overall_progress,
                    status=self.status,
                    speed_bytes_per_sec=getattr(self, 'speed_bytes_per_sec', 0),
                    eta_seconds=getattr(self, 'eta_seconds', 0),
                    total_elapsed=total_elapsed,
                    file_elapsed=file_elapsed,
                    checksum_elapsed=checksum_elapsed,
                    source_drive_name=self.source_drive_name,
                    source_drive_path=self.source_drive_path
                )
                self.display.show_progress(progress)
            except Exception as e:
                logger.warning(f"Failed to update display: {e}")
    
    def create_progress_callback(self) -> Callable[[int, int], None]:
        """
        Create a callback function for updating progress.
        
        Returns:
            Callable that takes (bytes_transferred, total_bytes) as parameters
        """
        def callback(bytes_transferred: int, total_bytes: int) -> None:
            # Update the internal total_bytes if it's different
            if total_bytes != self.total_bytes and total_bytes > 0:
                self.total_bytes = total_bytes
            
            # Update the progress with only bytes_transferred parameter
            self.update_progress(bytes_transferred=bytes_transferred)
        return callback

    def set_source_drive(self, source_path: Path) -> None:
        """
        Set the source drive information from the source path.
        
        Args:
            source_path: Path to the source drive (e.g., /Volumes/CanonA_002)
        """
        try:
            source_str = str(source_path)
            
            if source_str.startswith("/Volumes/"):
                # macOS path - extract drive name after /Volumes/
                path_parts = source_str.split("/")
                if len(path_parts) >= 3:
                    self.source_drive_name = path_parts[2]
                    self.source_drive_path = f"/Volumes/{self.source_drive_name}"
                else:
                    self.source_drive_name = source_path.name or "Unknown Drive"
                    self.source_drive_path = source_str
            elif re.match(r'^[A-Za-z]:[\\\/]?$', source_str):
                # Windows drive path (C:\, D:\, etc.)
                self.source_drive_name = source_str[:2] if len(source_str) >= 2 else source_str
                self.source_drive_path = self.source_drive_name + "\\"
            else:
                # Fallback - use the name or full path
                self.source_drive_name = source_path.name or "Unknown Drive"
                self.source_drive_path = source_str
                
        except Exception as e:
            logger.warning(f"Error setting source drive info: {e}")
            self.source_drive_name = "Unknown Drive"
            self.source_drive_path = str(source_path) 