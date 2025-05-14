# src/core/transfer_logger.py

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import getpass
import os
import stat
from src.core.utils import format_size, format_duration

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
    
    def log_success(self, src_path: Path, dst_path: Path, file_size: int, duration: float, src_xxhash: str, dst_xxhash: str, retries: int, ext: str, src_mtime: str, dst_mtime: str, user: str, src_perm: str, dst_perm: str) -> None:
        """
        Log successful file transfer with detailed info (multi-line, indented, no user).
        """
        if not self._ensure_log_open():
            return
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = (
                f"[{timestamp}] Success: {src_path} -> {dst_path}\n"
                f"    size: {format_size(file_size)}\n"
                f"    duration: {duration:.2f}s\n"
                f"    src_xxhash: {src_xxhash}\n"
                f"    dst_xxhash: {dst_xxhash}\n"
                f"    retries: {retries}\n"
                f"    ext: {ext}\n"
                f"    src_mtime: {src_mtime}\n"
                f"    dst_mtime: {dst_mtime}\n"
                f"    src_perm: {src_perm}\n"
                f"    dst_perm: {dst_perm}"
            )
            self._write_line(log_entry)
            logger.info(f"Transferred: {src_path}")
        except Exception as e:
            logger.warning(f"Error logging successful transfer: {e}")
    
    def log_failure(self, src_path: Path, dst_path: Path = None, reason: str = None, file_size: int = 0, duration: float = 0.0, src_xxhash: str = None, dst_xxhash: str = None, retries: int = 0, ext: str = None, src_mtime: str = None, dst_mtime: str = None, user: str = None, src_perm: str = None, dst_perm: str = None, error_message: str = None) -> None:
        """
        Log failed file transfer with detailed info (multi-line, indented, no user).
        """
        if not self._ensure_log_open():
            return
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            dst_str = f" -> {dst_path}" if dst_path else ""
            log_entry = (
                f"[{timestamp}] Failed: {src_path}{dst_str}\n"
                f"    size: {format_size(file_size)}\n"
                f"    duration: {duration:.2f}s\n"
                f"    src_xxhash: {src_xxhash}\n"
                f"    retries: {retries}\n"
                f"    ext: {ext}\n"
                f"    src_mtime: {src_mtime}\n"
                f"    src_perm: {src_perm}"
            )
            if dst_xxhash:
                log_entry += f"\n    dst_xxhash: {dst_xxhash}"
            if dst_mtime:
                log_entry += f"\n    dst_mtime: {dst_mtime}"
            if dst_perm:
                log_entry += f"\n    dst_perm: {dst_perm}"
            if error_message:
                log_entry += f"\n    error: {error_message}"
            self._write_line(log_entry)
            if reason:
                logger.error(f"Failed to transfer: {src_path} - {reason}")
            else:
                logger.error(f"Failed to transfer: {src_path}")
        except Exception as e:
            logger.warning(f"Error logging failed transfer: {e}")
    
    def complete_transfer(self, total_files: int, successful_files: int, failures: list = None, total_data_transferred: int = 0, average_file_size: int = 0, average_speed: float = 0.0, total_retries: int = 0, skipped_files: int = 0, error_breakdown: dict = None, user: str = None, duration_str: str = None) -> None:
        """
        Complete transfer logging with summary and new fields (user only in summary).
        """
        if not self.start_time or not self._ensure_log_open():
            return
        try:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            if not duration_str:
                duration_str = format_duration(duration)
            self._write_line("")
            self._write_line(f"Transfer completed at {end_time.isoformat()}")
            self._write_line(f"Duration: {duration_str}")
            self._write_line(f"Files transferred: {successful_files}/{total_files}")
            if failures:
                self._write_line(f"Failed files: {len(failures)}")
                for i, failure in enumerate(failures[:10]):
                    self._write_line(f"  {i+1}. {failure}")
                if len(failures) > 10:
                    self._write_line(f"  ... and {len(failures) - 10} more")
            self._write_line(f"Total data transferred: {format_size(total_data_transferred)}")
            self._write_line(f"Average file size: {format_size(average_file_size)}")
            self._write_line(f"Average speed: {average_speed:.2f} MB/s")
            self._write_line(f"Total retries: {total_retries}")
            self._write_line(f"Skipped files: {skipped_files}")
            if error_breakdown:
                self._write_line("Failures:")
                for err, count in error_breakdown.items():
                    self._write_line(f"  {err}: {count}")
            if user:
                self._write_line(f"User: {user}")
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
    
    def log_file_transfer(self, source_file: Path, dest_file: Path, success: bool, file_size: int, duration: float, src_xxhash: str, dst_xxhash: str, retries: int, ext: str, src_mtime: str, dst_mtime: str, user: str, src_perm: str, dst_perm: str, error_message: str = None) -> None:
        """
        Log a file transfer result with all new fields.
        """
        if success:
            self.log_success(
                src_path=source_file,
                dst_path=dest_file,
                file_size=file_size,
                duration=duration,
                src_xxhash=src_xxhash,
                dst_xxhash=dst_xxhash,
                retries=retries,
                ext=ext,
                src_mtime=src_mtime,
                dst_mtime=dst_mtime,
                user=user,
                src_perm=src_perm,
                dst_perm=dst_perm
            )
        else:
            self.log_failure(
                src_path=source_file,
                dst_path=dest_file,
                reason=error_message,
                file_size=file_size,
                duration=duration,
                src_xxhash=src_xxhash,
                dst_xxhash=dst_xxhash,
                retries=retries,
                ext=ext,
                src_mtime=src_mtime,
                dst_mtime=dst_mtime,
                user=user,
                src_perm=src_perm,
                dst_perm=dst_perm,
                error_message=error_message
            )
    
    def log_transfer_summary(self, source_path: Path, destination_path: Path, start_time: datetime, end_time: datetime, total_files: int, successful_files: int, failures: list = None, total_data_transferred: int = 0, average_file_size: int = 0, average_speed: float = 0.0, total_retries: int = 0, skipped_files: int = 0, error_breakdown: dict = None, user: str = None, duration_str: str = None) -> None:
        """
        Log a summary of the transfer operation with new fields.
        """
        if not self._ensure_log_open():
            return
        try:
            if not duration_str:
                duration = (end_time - start_time).total_seconds()
                duration_str = format_duration(duration)
            self._write_line("")
            self._write_line(f"Transfer Summary")
            self._write_line(f"---------------")
            self._write_line(f"Source: {source_path}")
            self._write_line(f"Destination: {destination_path}")
            self._write_line(f"Start time: {start_time.isoformat()}")
            self._write_line(f"End time: {end_time.isoformat()}")
            self._write_line(f"Duration: {duration_str}")
            self._write_line(f"Files transferred: {successful_files}/{total_files}")
            if failures:
                self._write_line(f"Failed files: {len(failures)}")
                for i, failure in enumerate(failures[:10]):
                    self._write_line(f"  {i+1}. {failure}")
                if len(failures) > 10:
                    self._write_line(f"  ... and {len(failures) - 10} more")
            self._write_line(f"Total data transferred: {format_size(total_data_transferred)}")
            self._write_line(f"Average file size: {format_size(average_file_size)}")
            self._write_line(f"Average speed: {average_speed:.2f} MB/s")
            self._write_line(f"Total retries: {total_retries}")
            self._write_line(f"Skipped files: {skipped_files}")
            if error_breakdown:
                self._write_line("Failures:")
                for err, count in error_breakdown.items():
                    self._write_line(f"  {err}: {count}")
            if user:
                self._write_line(f"User: {user}")
            logger.info(f"Transfer summary: {successful_files}/{total_files} files transferred in {duration_str}")
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