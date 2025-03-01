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
        current_progress: Optional[TransferProgress] = None
    ) -> bool:
        """Verify a file's checksum against an expected value."""
        try:
            # Validate input parameters
            if not file_path.exists():
                logger.error(f"File not found during verification: {file_path}")
                self.display.show_error("File Missing")
                return False
                
            if not expected_checksum:
                logger.error(f"Empty expected checksum for {file_path}")
                self.display.show_error("Invalid Checksum")
                return False
                
            # Reset progress for verification phase
            if current_progress:
                try:
                    current_progress.bytes_transferred = 0
                    current_progress.current_file_progress = 0.0
                    current_progress.status = TransferStatus.CHECKSUMMING
                except Exception as progress_err:
                    logger.warning(f"Error resetting progress object: {progress_err}")
                    # Continue with verification despite progress object issues
            
            # Calculate actual checksum with progress monitoring
            try:
                actual_checksum = self.calculate_file_checksum(
                    file_path,
                    current_progress=current_progress
                )
            except Exception as checksum_err:
                logger.error(f"Error during checksum calculation for {file_path}: {checksum_err}")
                self.display.show_error("Checksum Failed")
                return False
            
            if actual_checksum is None:
                logger.error(f"Failed to calculate checksum for {file_path}")
                self.display.show_error("Checksum Failed")
                return False
                
            # Compare checksums in a case-insensitive manner
            try:
                matches = actual_checksum.lower() == expected_checksum.lower()
            except AttributeError as e:
                logger.error(f"Invalid checksum format: {e}")
                self.display.show_error("Invalid Checksum")
                return False
                
            if not matches:
                logger.warning(
                    f"Checksum mismatch for {file_path}:\n"
                    f"Expected: {expected_checksum}\n"
                    f"Actual  : {actual_checksum}"
                )
                self.display.show_error("Verify Failed")
                
            return matches
                
        except Exception as e:
            logger.error(f"Error verifying checksum for {file_path}: {e}", exc_info=True)
            self.display.show_error("Verify Error")
            return False