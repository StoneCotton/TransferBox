# src/core/checksum.py

import logging
import xxhash
from pathlib import Path
from typing import Optional, Callable, Iterator
from .interfaces.types import TransferProgress, TransferStatus
from .interfaces.display import DisplayInterface

logger = logging.getLogger(__name__)

class ChecksumCalculator:
    """Handles file checksum calculations with progress monitoring"""

    def __init__(self, display: DisplayInterface):
        self.display = display

    def create_hash(self) -> xxhash.xxh64:
        """Create a new xxhash object for checksum calculation."""
        return xxhash.xxh64()

    def calculate_file_checksum(
        self, 
        file_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        current_progress: Optional[TransferProgress] = None
    ) -> Optional[str]:
        """Calculate XXH64 checksum for a file with progress monitoring."""
        try:
            # Verify file exists and is accessible
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                self.display.show_error("File not found")
                return None
                
            try:
                file_size = file_path.stat().st_size
            except (OSError, FileNotFoundError) as e:
                logger.error(f"Failed to get file size for {file_path}: {e}")
                self.display.show_error("File access error")
                return None
            
            bytes_processed = 0
            
            try:
                hash_obj = xxhash.xxh64()
            except Exception as e:
                logger.error(f"Failed to initialize xxhash for {file_path}: {e}")
                self.display.show_error("Checksum init failed")
                return None
            
            # Use existing progress object if provided, otherwise create new one
            progress = current_progress or TransferProgress(
                current_file=file_path.name,
                file_number=1,
                total_files=1,
                bytes_transferred=0,
                total_bytes=file_size,
                total_transferred=0,
                total_size=file_size,
                current_file_progress=0.0,
                overall_progress=0.0,
                status=TransferStatus.CHECKSUMMING
            )

            try:
                with open(file_path, 'rb') as f:
                    while True:
                        try:
                            chunk = f.read(32 * 1024 * 1024)  # 32MB chunks
                            if not chunk:
                                break
                                
                            hash_obj.update(chunk)
                            bytes_processed += len(chunk)
                            
                            if current_progress:
                                progress.bytes_transferred = bytes_processed
                                # Scale progress to 0-50% for first checksum, 50-100% for verification
                                if progress.status == TransferStatus.CHECKSUMMING:
                                    progress.current_file_progress = (bytes_processed / file_size)
                                
                                try:
                                    self.display.show_progress(progress)
                                except Exception as display_err:
                                    logger.warning(f"Failed to update progress display: {display_err}")
                                    # Continue checksumming despite display error
                            
                            if progress_callback:
                                try:
                                    progress_callback(bytes_processed, file_size)
                                except Exception as callback_err:
                                    logger.warning(f"Progress callback error: {callback_err}")
                                    # Continue checksumming despite callback error
                                    
                        except MemoryError as e:
                            logger.error(f"Memory error processing chunk of {file_path}: {e}")
                            self.display.show_error("Memory error")
                            return None
                        except IOError as e:
                            logger.error(f"I/O error reading {file_path}: {e}")
                            self.display.show_error("Read error")
                            return None
            
            except FileNotFoundError as e:
                logger.error(f"File disappeared during checksum: {file_path}, {e}")
                self.display.show_error("File not found")
                return None
            except PermissionError as e:
                logger.error(f"Permission denied reading {file_path}: {e}")
                self.display.show_error("Access denied")
                return None
                
            try:
                checksum = hash_obj.hexdigest()
                logger.info(f"Checksum calculated for {file_path}: {checksum}")
                return checksum
            except Exception as e:
                logger.error(f"Failed to generate final checksum for {file_path}: {e}")
                self.display.show_error("Checksum generation failed")
                return None
                
        except Exception as e:
            error_msg = "Error calculating checksum"
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            self.display.show_error(error_msg)
            return None

    def verify_checksum(
        self, 
        file_path: Path, 
        expected_checksum: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        current_progress: Optional[TransferProgress] = None
    ) -> bool:
        """
        Verify a file's checksum against an expected value.
        
        Args:
            file_path: Path to the file to verify
            expected_checksum: Expected checksum value to check against
            progress_callback: Optional callback for progress updates
            current_progress: Optional progress object to update
            
        Returns:
            bool: True if checksum matches, False otherwise
        """
        if not expected_checksum:
            logger.error("No expected checksum provided")
            return False
            
        if not file_path.exists():
            logger.error(f"File not found for verification: {file_path}")
            return False
            
        # Get file size for progress tracking
        try:
            file_size = file_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to get file size for verification: {e}")
            return False
            
        # Update progress status if provided
        if current_progress:
            current_progress.status = TransferStatus.CHECKSUMMING
            current_progress.bytes_transferred = 0
            try:
                self.display.show_progress(current_progress)
            except Exception as e:
                logger.warning(f"Failed to update display for verification: {e}")
                
        # Calculate actual checksum with progress updates
        try:
            bytes_processed = 0
            hash_obj = xxhash.xxh64()
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(32 * 1024 * 1024)  # 32MB chunks
                    if not chunk:
                        break
                        
                    hash_obj.update(chunk)
                    bytes_processed += len(chunk)
                    
                    # Update progress
                    if progress_callback:
                        try:
                            progress_callback(bytes_processed, file_size)
                        except Exception as callback_err:
                            logger.warning(f"Progress callback error during verification: {callback_err}")
                    
            actual_checksum = hash_obj.hexdigest()
            
            # Check if checksums match
            checksums_match = actual_checksum.lower() == expected_checksum.lower()
            
            if checksums_match:
                logger.info(f"Checksum verification successful: {file_path}")
            else:
                logger.error(f"Checksum verification failed for {file_path}. Expected: {expected_checksum}, Got: {actual_checksum}")
                
            # Update final progress status
            if current_progress:
                current_progress.bytes_transferred = file_size
                current_progress.current_file_progress = 1.0
                current_progress.status = TransferStatus.SUCCESS if checksums_match else TransferStatus.ERROR
                try:
                    self.display.show_progress(current_progress)
                except Exception as e:
                    logger.warning(f"Failed to update final verification progress: {e}")
                    
            return checksums_match
            
        except Exception as e:
            logger.error(f"Error during checksum verification: {e}")
            
            # Update progress on error
            if current_progress:
                current_progress.status = TransferStatus.ERROR
                try:
                    self.display.show_progress(current_progress)
                except Exception as display_err:
                    logger.warning(f"Failed to update error progress: {display_err}")
                    
            return False