# src/core/file_transfer.py

import logging
import platform
import re
import subprocess
import sys
import os
import shutil
from typing import Tuple
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from threading import Event, Thread
from .interfaces.display import DisplayInterface
from .interfaces.storage import StorageInterface
from .interfaces.types import TransferStatus, TransferProgress
from .checksum import ChecksumCalculator
from .mhl_handler import initialize_mhl_file, add_file_to_mhl

logger = logging.getLogger(__name__)

class TransferStrategy:
    """Abstract base class for platform-specific transfer strategies"""
    def dry_run(self, source: Path, destination: Path) -> Tuple[int, int]:
        raise NotImplementedError
        
    def copy_file(self, source: Path, destination: Path) -> bool:
        raise NotImplementedError
    
class RsyncStrategy(TransferStrategy):
    """Unix-like systems transfer strategy using rsync"""
    def dry_run(self, source: Path, destination: Path) -> Tuple[int, int]:
        try:
            process = subprocess.run(
                ['rsync', '-a', '--dry-run', '--stats', str(source), str(destination)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            output = process.stdout
            file_count = int(re.search(r'Number of regular files transferred: (\d+)', output).group(1))
            total_size = int(re.search(r'Total transferred file size: ([\d,]+)', output).group(1).replace(',', ''))
            
            return file_count, total_size
            
        except Exception as e:
            logger.error(f"Rsync dry run failed: {e}")
            raise

    def copy_file(self, source: Path, destination: Path) -> bool:
        try:
            result = subprocess.run(
                ['rsync', '-av', '--progress', str(source), str(destination)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True
        except Exception as e:
            logger.error(f"Rsync copy failed: {e}")
            raise

class WSLRsyncStrategy(TransferStrategy):
    """Windows transfer strategy using WSL rsync"""
    def _convert_to_wsl_path(self, path: Path) -> str:
        """Convert Windows path to WSL path format"""
        wsl_path = str(path).replace('\\', '/').replace(':', '')
        return f"/mnt/{wsl_path.lower()}"

    def dry_run(self, source: Path, destination: Path) -> Tuple[int, int]:
        try:
            wsl_source = self._convert_to_wsl_path(source)
            wsl_dest = self._convert_to_wsl_path(destination)
            
            # Test WSL path accessibility
            subprocess.run(['wsl', 'test', '-e', wsl_source], check=True)
            
            process = subprocess.run(
                ['wsl', 'rsync', '-av', '--dry-run', '--stats', wsl_source, wsl_dest],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            output = process.stdout
            if not output:
                return 0, 0
                
            logger.debug(f"WSL rsync output: {output}")
            file_count = int(re.search(r'Number of files: (\d+)', output).group(1))
            total_size = int(re.search(r'Total file size: (\d+)', output).group(1))
            
            return file_count, total_size
            
        except subprocess.CalledProcessError as e:
            logger.error(f"WSL rsync dry run failed: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"WSL dry run error: {e}")
            raise

    def copy_file(self, source: Path, destination: Path) -> bool:
        try:
            wsl_source = self._convert_to_wsl_path(source)
            wsl_dest = self._convert_to_wsl_path(destination)
            
            # Ensure destination directory exists
            os.makedirs(destination.parent, exist_ok=True)
            
            result = subprocess.run(
                ['wsl', 'rsync', '-av', '--progress', wsl_source, wsl_dest],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.debug(f"WSL rsync output: {result.stdout}")
            if result.stderr:
                logger.debug(f"WSL rsync stderr: {result.stderr}")
                
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"WSL rsync copy failed: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"WSL copy error: {e}")
            raise

class WindowsFallbackStrategy(TransferStrategy):
    """Windows native transfer strategy using robocopy/shutil"""
    def dry_run(self, source: Path, destination: Path) -> Tuple[int, int]:
        try:
            file_count = 0
            total_size = 0
            for item in source.rglob('*'):
                if item.is_file():
                    file_count += 1
                    total_size += item.stat().st_size
            logger.debug(f"Windows dry run found {file_count} files, total size {total_size} bytes")
            return file_count, total_size
        except Exception as e:
            logger.error(f"Windows dry run failed: {e}")
            raise

    def copy_file(self, source: Path, destination: Path) -> bool:
        try:
            # Ensure destination directory exists
            os.makedirs(destination.parent, exist_ok=True)
            
            # Use robocopy for files larger than 1GB, shutil for smaller files
            file_size = source.stat().st_size
            if file_size > 1_000_000_000:  # 1GB
                # Use robocopy for large files
                source_dir = str(source.parent)
                dest_dir = str(destination.parent)
                filename = source.name
                
                result = subprocess.run(
                    ['robocopy', source_dir, dest_dir, filename, 
                     '/Z',  # Restartable mode
                     '/W:1',  # Wait time between retries
                     '/R:2',  # Number of retries
                     '/J',  # Unbuffered I/O (faster for large files)
                     '/NDL',  # No directory list
                     '/NP'  # No progress
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Robocopy returns specific codes, 0-7 are successful
                if result.returncode > 7:
                    raise subprocess.CalledProcessError(
                        result.returncode, result.args, result.stdout, result.stderr
                    )
            else:
                # Use shutil for smaller files
                shutil.copy2(str(source), str(destination))
            
            # Verify the copy
            if not destination.exists():
                raise IOError(f"Destination file {destination} was not created")
            if destination.stat().st_size != file_size:
                raise IOError(f"Destination file size mismatch for {destination}")
                
            return True
            
        except Exception as e:
            logger.error(f"Windows copy failed: {e}")
            raise

def get_transfer_strategy() -> TransferStrategy:
    """Factory function to get appropriate transfer strategy"""
    system = platform.system().lower()
    
    if system == "linux":
        return RsyncStrategy()
    elif system == "windows":
        # For Windows, always use native strategy for removable drives
        return WindowsFallbackStrategy()
    else:  # Darwin/macOS
        return RsyncStrategy()


class FileTransfer:
    def __init__(self, state_manager, display: DisplayInterface, storage: StorageInterface):
        self.state_manager = state_manager
        self.display = display
        self.storage = storage
        self._current_progress: Optional[TransferProgress] = None

    @contextmanager
    def _status_context(self, status: TransferStatus, message: Optional[str] = None):
        """Context manager for maintaining transfer status."""
        if self._current_progress is None:
            self._current_progress = TransferProgress(
                current_file="",
                file_number=0,
                total_files=0,
                bytes_transferred=0,
                total_bytes=0,
                current_file_progress=0.0,
                overall_progress=0.0,
                status=status
            )
        
        previous_status = self._current_progress.status
        self._current_progress.status = status
        
        # Only show status message if explicitly provided and not during transfer
        if message and status not in (TransferStatus.COPYING, TransferStatus.CHECKSUMMING):
            self.display.show_status(message)
        
        try:
            yield
        finally:
            self._current_progress.status = previous_status
            # Only update progress display during transfer states
            if status in (TransferStatus.COPYING, TransferStatus.CHECKSUMMING):
                self.display.show_progress(self._current_progress)

    def create_timestamped_dir(self, base_path: Path, timestamp: Optional[str] = None) -> Path:
        """
        Create a timestamped directory for file transfers.
        
        Args:
            base_path: The base directory where the timestamped directory should be created
            timestamp: Optional timestamp string. If None, current timestamp will be used
            
        Returns:
            Path to the created directory
            
        Raises:
            OSError: If directory creation fails
        """
        try:
            # Use provided timestamp or generate new one
            if timestamp is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Convert string path to Path object if needed
            if isinstance(base_path, str):
                base_path = Path(base_path)
            
            # Create the target directory
            target_dir = base_path / timestamp
            target_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created timestamped directory: {target_dir}")
            return target_dir
            
        except Exception as e:
            error_msg = f"Failed to create timestamped directory: {e}"
            logger.error(error_msg)
            self.display.show_error(error_msg)
            raise OSError(error_msg) from e
        
    def rsync_dry_run(self, source: Path, destination: Path) -> tuple[int, int]:
        """Platform-agnostic dry run implementation"""
        try:
            strategy = get_transfer_strategy()
            return strategy.dry_run(source, destination)
        except Exception as e:
            logger.error(f"Dry run failed: {e}")
            return 0, 0
    
    def rsync_copy(self, source: Path, destination: Path, file_size: int, file_number: int, file_count: int) -> tuple[bool, str]:
        """Platform-agnostic copy implementation"""
        with self._status_context(TransferStatus.COPYING):
            try:
                strategy = get_transfer_strategy()
                success = strategy.copy_file(source, destination)
                
                if success and self._current_progress is not None:
                    self._current_progress.bytes_transferred = file_size
                    self._current_progress.current_file_progress = 1.0
                    self._current_progress.overall_progress = file_number / file_count
                    self.display.show_progress(self._current_progress)
                    
                return success, ""
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Copy failed: {error_msg}")
                self.display.show_error(error_msg)
                return False, error_msg

            
    def copy_file_with_verification(
        self,
        src_path: Path,
        dst_path: Path,
        file_number: int,
        file_count: int
    ) -> tuple[bool, Optional[str]]:
        """Copy a file and verify the copy using checksums."""
        try:
            # Get file size
            file_size = src_path.stat().st_size
            
            # Update progress for copying state
            self._current_progress = TransferProgress(
                current_file=src_path.name,
                file_number=file_number,
                total_files=file_count,
                bytes_transferred=0,
                total_bytes=file_size,
                current_file_progress=0.0,
                overall_progress=file_number / file_count,
                status=TransferStatus.COPYING
            )
            self.display.show_progress(self._current_progress)
            
            # Copy file
            success, error = self.rsync_copy(src_path, dst_path, file_size, file_number, file_count)
            if not success:
                self.display.show_error(f"Copy failed: {error}")
                return False, None

            # Calculate and verify checksums
            calculator = ChecksumCalculator(self.display)
            
            # Update progress for checksumming state
            self._current_progress.status = TransferStatus.CHECKSUMMING
            self._current_progress.current_file_progress = 0.0  # Reset for checksum progress
            self.display.show_progress(self._current_progress)
            
            # Calculate source checksum (will represent 0-50% of checksum progress)
            logger.info(f"Calculating checksum for source file: {src_path}")
            def source_progress_callback(bytes_processed: int, total_bytes: int):
                self._current_progress.current_file_progress = (bytes_processed / total_bytes) * 0.5
                self.display.show_progress(self._current_progress)
                
            src_checksum = calculator.calculate_file_checksum(
                src_path,
                progress_callback=source_progress_callback
            )
            
            if src_checksum is None:
                self.display.show_error("Source checksum failed")
                return False, None
                
            # Calculate destination checksum (will represent 50-100% of checksum progress)
            logger.info(f"Calculating checksum for destination file: {dst_path}")
            def dest_progress_callback(bytes_processed: int, total_bytes: int):
                self._current_progress.current_file_progress = 0.5 + (bytes_processed / total_bytes) * 0.5
                self.display.show_progress(self._current_progress)
                
            dst_checksum = calculator.calculate_file_checksum(
                dst_path,
                progress_callback=dest_progress_callback
            )
            
            if dst_checksum is None:
                self.display.show_error("Dest checksum failed")
                return False, None
            
            if src_checksum != dst_checksum:
                logger.warning(f"Checksum mismatch for {src_path.name}")
                self.display.show_error("Checksum failed")
                return False, None
            
            return True, src_checksum
            
        except Exception as e:
            logger.error(f"Error during copy and verification: {e}")
            self.display.show_error(str(e))
            return False, None
        
    def copy_sd_to_dump(
        self,
        source_path: Path,
        destination_path: Path,
        log_file: Path
    ) -> bool:
        """Copy files from source (SD card) to destination with verification."""
        if not self._validate_transfer_preconditions(destination_path):
            if self.state_manager.is_utility():
                # If in utility mode, just unmount the drive
                logger.info("System in utility mode - unmounting drive without transfer")
                try:
                    if self.storage.unmount_drive(source_path):
                        self.display.show_status("Safe to remove SD")
                    else:
                        self.display.show_error("Unmount failed")
                except Exception as e:
                    logger.error(f"Error unmounting drive: {e}")
                    self.display.show_error("Unmount error")
                return False
            else:
                self.display.show_error("Transfer preconditions failed")
                return False

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            with self._transfer_session():
                success = self._execute_transfer(source_path, destination_path, timestamp, log_file)
                if success:
                    self._current_progress.status = TransferStatus.SUCCESS
                    self.display.show_progress(self._current_progress)
                return success
        except Exception as e:
            error_msg = f"Transfer failed: {e}"
            logger.error(error_msg)
            if self._current_progress:
                self._current_progress.status = TransferStatus.ERROR
                self.display.show_progress(self._current_progress)
            else:
                self.display.show_error("Transfer error")
            return False

    def _validate_transfer_preconditions(self, destination_path: Path) -> bool:
        """Validate all preconditions before starting transfer."""
        if destination_path is None:
            self.display.show_error("Destination not found")
            return False
            
        # Block transfers during utility mode
        if self.state_manager.is_utility():
            logger.info("Transfer blocked - system in utility mode")
            return False
            
        return True
    
    def _transfer_session(self):
        """Context manager for handling transfer state."""
        class TransferSessionManager:
            def __init__(self, file_transfer):
                self.file_transfer = file_transfer
                
            def __enter__(self):
                self.file_transfer.state_manager.enter_transfer()
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.file_transfer.state_manager.exit_transfer()
                
        return TransferSessionManager(self)

    def _execute_transfer(
        self,
        source_path: Path,
        destination_path: Path,
        timestamp: str,
        log_file: Path
    ) -> bool:
        """Execute the actual transfer operation."""
        target_dir = self.create_timestamped_dir(destination_path, timestamp)
        
        # Initialize MHL file
        mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
        
        # Check space requirements
        if not self._check_space_requirements(source_path, target_dir):
            return False
        
        # Perform the transfer
        return self._process_files(
            source_path,
            target_dir,
            log_file,
            mhl_filename,
            tree,
            hashes
        )

    def _check_space_requirements(self, source_path: Path, target_dir: Path) -> bool:
        """Check if there's enough space for the transfer."""
        file_count, total_size = self.rsync_dry_run(source_path, target_dir)
        logger.info(f"Transfer requirements - Files: {file_count}, Size: {total_size} bytes")
        
        if not self.storage.has_enough_space(target_dir, total_size):
            self.display.show_error("Not enough space")
            return False
            
        return True

    def _process_files(
        self,
        source_path: Path,
        target_dir: Path,
        log_file: Path,
        mhl_filename: Path,
        tree,
        hashes
    ) -> bool:
        """Process all files in the source directory."""
        failures = []
        total_files = sum(1 for _ in source_path.rglob('*') if _.is_file())
        file_number = 0
        
        with open(log_file, 'a') as log:
            for src_file in source_path.rglob('*'):
                if not src_file.is_file():
                    continue
                    
                file_number += 1
                rel_path = src_file.relative_to(source_path)
                dst_path = target_dir / rel_path
                
                if not self._process_single_file(
                    src_file,
                    dst_path,
                    file_number,
                    total_files,
                    log,
                    mhl_filename,
                    tree,
                    hashes,
                    failures
                ):
                    continue

        return self._handle_transfer_completion(failures)

    def _process_single_file(
        self,
        src_file: Path,
        dst_path: Path,
        file_number: int,
        total_files: int,
        log_file,
        mhl_filename: Path,
        tree,
        hashes,
        failures: list
    ) -> bool:
        """Process a single file during transfer."""
        try:
            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy and verify file
            success, checksum = self.copy_file_with_verification(
                src_file,
                dst_path,
                file_number,
                total_files
            )
            
            if success:
                self._log_successful_transfer(log_file, src_file, dst_path)
                if checksum:
                    add_file_to_mhl(mhl_filename, tree, hashes, dst_path, checksum, dst_path.stat().st_size)
            else:
                failures.append(str(src_file))
                self._log_failed_transfer(log_file, src_file, dst_path)
                
            return success
                
        except Exception as e:
            logger.error(f"Error processing {src_file}: {e}")
            failures.append(str(src_file))
            return False

    def _log_successful_transfer(self, log_file, src_path: Path, dst_path: Path):
        """Log a successful file transfer."""
        log_file.write(f"Success: {src_path} -> {dst_path}\n")
        log_file.flush()
        logger.info(f"Transferred: {src_path}")

    def _log_failed_transfer(self, log_file, src_path: Path, dst_path: Path):
        """Log a failed file transfer."""
        log_file.write(f"Failed: {src_path} -> {dst_path}\n")
        log_file.flush()
        logger.error(f"Failed to transfer: {src_path}")

    def _handle_transfer_completion(self, failures: list) -> bool:
        """Handle the completion of the transfer process."""
        if failures:
            error_msg = "Transfer Failed"  # Keep error message short for LCD
            logger.error("Some files failed to transfer")
            for failure in failures:
                logger.error(f"Failed: {failure}")
            self.display.show_error(error_msg)
            return False
        
        logger.info("Transfer completed successfully")
        # Don't show status message here as it will be handled by state management
        return True
        
        logger.info("Transfer completed successfully")
        self.display.show_status("Transfer complete")
        return True