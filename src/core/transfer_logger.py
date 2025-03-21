# src/core/transfer_logger.py

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

class TransferLogger:
    """Class for standardized logging of file transfers."""
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the transfer logger.
        
        Args:
            log_file: Optional path to log file
        """
        self.log_file = log_file
        self.start_time = None
        self.is_open = False
        self._file_handle = None
    
    def start_transfer(self, source_path: Path, destination_path: Path, 
                     total_files: int, total_size: int) -> datetime:
        """
        Start logging a transfer operation.
        
        Args:
            source_path: Source path
            destination_path: Destination path
            total_files: Total number of files to transfer
            total_size: Total size in bytes
            
        Returns:
            Transfer start time
        """
        self.start_time = datetime.now()
        self._ensure_log_directory()
        
        try:
            self._open_log_file()
            self._write_line(f"Transfer started at {self.start_time.isoformat()}")
            self._write_line(f"Source: {source_path}")
            self._write_line(f"Destination: {destination_path}")
            self._write_line(f"Files to transfer: {total_files}")
            self._write_line(f"Total size: {total_size / (1024*1024*1024):.2f} GB")
            self._write_line("")  # Empty line
            return self.start_time
        except Exception as e:
            logger.error(f"Failed to start transfer log: {e}")
            return self.start_time
    
    def log_success(self, src_path: Path, dst_path: Path) -> None:
        """
        Log successful file transfer.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
        """
        if not self._ensure_log_open():
            return
            
        try:
            # Format with timestamp for better logging
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] Success: {src_path} -> {dst_path}"
            self._write_line(log_entry)
            logger.info(f"Transferred: {src_path}")
        except Exception as e:
            logger.warning(f"Error logging successful transfer: {e}")
    
    def log_failure(self, src_path: Path, dst_path: Optional[Path] = None, reason: str = None) -> None:
        """
        Log failed file transfer.
        
        Args:
            src_path: Source file path
            dst_path: Optional destination file path
            reason: Optional reason for failure
        """
        if not self._ensure_log_open():
            return
            
        try:
            # Format with timestamp and reason for better diagnostics
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            dst_str = f" -> {dst_path}" if dst_path else ""
            reason_text = f" - Reason: {reason}" if reason else ""
            log_entry = f"[{timestamp}] Failed: {src_path}{dst_str}{reason_text}"
            self._write_line(log_entry)
            
            # Include reason in log message if available
            if reason:
                logger.error(f"Failed to transfer: {src_path} - {reason}")
            else:
                logger.error(f"Failed to transfer: {src_path}")
        except Exception as e:
            logger.warning(f"Error logging failed transfer: {e}")
    
    def complete_transfer(self, total_files: int, successful_files: int, failures: List[str] = None) -> None:
        """
        Complete transfer logging with summary.
        
        Args:
            total_files: Total number of files
            successful_files: Number of successfully transferred files
            failures: Optional list of failed transfers
        """
        if not self.start_time or not self._ensure_log_open():
            return
            
        try:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            self._write_line("")  # Empty line
            self._write_line(f"Transfer completed at {end_time.isoformat()}")
            self._write_line(f"Duration: {duration:.1f} seconds")
            self._write_line(f"Files transferred: {successful_files}/{total_files}")
            
            if failures:
                self._write_line(f"Failed files: {len(failures)}")
                # Only log the first 10 failures to avoid excessive log file size
                for i, failure in enumerate(failures[:10]):
                    self._write_line(f"  {i+1}. {failure}")
                if len(failures) > 10:
                    self._write_line(f"  ... and {len(failures) - 10} more")
        except Exception as e:
            logger.error(f"Error completing transfer log: {e}")
        finally:
            self._close_log_file()
    
    def _ensure_log_directory(self) -> bool:
        """Ensure log directory exists."""
        if not self.log_file:
            return False
            
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create log directory: {e}")
            return False
    
    def _open_log_file(self) -> bool:
        """Open log file for writing."""
        if not self.log_file or self.is_open:
            return False
            
        try:
            self._file_handle = open(self.log_file, 'a', encoding='utf-8')
            self.is_open = True
            return True
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")
            return False
    
    def _close_log_file(self) -> None:
        """Close log file."""
        if self._file_handle and self.is_open:
            try:
                self._file_handle.close()
            except Exception as e:
                logger.warning(f"Error closing log file: {e}")
            finally:
                self._file_handle = None
                self.is_open = False
    
    def _ensure_log_open(self) -> bool:
        """Ensure log file is open for writing."""
        if not self.log_file:
            return False
            
        if not self.is_open:
            return self._open_log_file()
            
        return True
    
    def _write_line(self, line: str) -> None:
        """Write a line to the log file."""
        if not self._file_handle or not self.is_open:
            return
            
        try:
            self._file_handle.write(f"{line}\n")
            self._file_handle.flush()
        except Exception as e:
            logger.warning(f"Failed to write to log file: {e}")
    
    def log_message(self, message: str) -> None:
        """
        Log a general message to the log file.
        
        Args:
            message: Message to log
        """
        try:
            self._open_log_file()
            self._write_line(f"[INFO] {message}")
            logger.info(message)
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            
    def error(self, message: str) -> None:
        """
        Log an error message to the log file.
        
        Args:
            message: Error message to log
        """
        try:
            self._open_log_file()
            self._write_line(f"[ERROR] {message}")
            logger.error(message)
        except Exception as e:
            logger.error(f"Error logging error message: {e}")
    
    def log_file_transfer(self, source_file: Path, dest_file: Path, success: bool) -> None:
        """
        Log a file transfer result.
        
        Args:
            source_file: Source file path
            dest_file: Destination file path
            success: Whether the transfer was successful
        """
        if success:
            self.log_success(source_file, dest_file)
        else:
            self.log_failure(source_file, dest_file, "Transfer failed")
    
    def log_transfer_summary(self, source_path: Path, destination_path: Path, 
                          start_time: datetime, end_time: datetime,
                          total_files: int, successful_files: int, 
                          failures: List[str] = None) -> None:
        """
        Log a summary of the transfer operation.
        
        Args:
            source_path: Source path
            destination_path: Destination path
            start_time: Start time of the transfer
            end_time: End time of the transfer
            total_files: Total number of files
            successful_files: Number of successfully transferred files
            failures: Optional list of failed transfers
        """
        if not self._ensure_log_open():
            return
            
        try:
            duration = (end_time - start_time).total_seconds()
            
            self._write_line("")  # Empty line
            self._write_line(f"Transfer Summary")
            self._write_line(f"---------------")
            self._write_line(f"Source: {source_path}")
            self._write_line(f"Destination: {destination_path}")
            self._write_line(f"Start time: {start_time.isoformat()}")
            self._write_line(f"End time: {end_time.isoformat()}")
            self._write_line(f"Duration: {duration:.1f} seconds")
            self._write_line(f"Files transferred: {successful_files}/{total_files}")
            
            if failures:
                self._write_line(f"Failed files: {len(failures)}")
                # Only log the first 10 failures to avoid excessive log file size
                for i, failure in enumerate(failures[:10]):
                    self._write_line(f"  {i+1}. {failure}")
                if len(failures) > 10:
                    self._write_line(f"  ... and {len(failures) - 10} more")
            
            transfer_rate = successful_files / duration if duration > 0 else 0
            self._write_line(f"Transfer rate: {transfer_rate:.2f} files/second")
            
            logger.info(f"Transfer summary: {successful_files}/{total_files} files transferred in {duration:.1f} seconds")
        except Exception as e:
            logger.error(f"Error logging transfer summary: {e}")


def create_transfer_log(log_dir: Path, prefix: str = "transfer_log") -> Path:
    """
    Create a log file path with timestamp.
    
    Args:
        log_dir: Directory for log file
        prefix: Prefix for log file name
        
    Returns:
        Path to log file
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return log_dir / f"{prefix}_{timestamp}.log" 