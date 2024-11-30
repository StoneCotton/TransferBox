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
            file_size = file_path.stat().st_size
            bytes_processed = 0
            hash_obj = xxhash.xxh64()

            # Use existing progress object if provided, otherwise create new one
            progress = current_progress or TransferProgress(
                current_file=file_path.name,
                file_number=1,
                total_files=1,
                bytes_transferred=0,
                total_bytes=file_size,
                current_file_progress=0.0,
                overall_progress=0.0,
                status=TransferStatus.CHECKSUMMING
            )

            with open(file_path, 'rb') as f:
                while chunk := f.read(32 * 1024 * 1024):  # 32MB chunks
                    hash_obj.update(chunk)
                    bytes_processed += len(chunk)
                    
                    if current_progress:
                        progress.bytes_transferred = bytes_processed
                        # Scale progress to 0-50% for first checksum, 50-100% for verification
                        if progress.status == TransferStatus.CHECKSUMMING:
                            progress.current_file_progress = (bytes_processed / file_size)
                        self.display.show_progress(progress)

                    if progress_callback:
                        progress_callback(bytes_processed, file_size)

            checksum = hash_obj.hexdigest()
            logger.info(f"Checksum calculated for {file_path}: {checksum}")
            return checksum

        except Exception as e:
            error_msg = f"Error calculating checksum"
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
            # Reset progress for verification phase
            if current_progress:
                current_progress.bytes_transferred = 0
                current_progress.current_file_progress = 0.0
            
            actual_checksum = self.calculate_file_checksum(
                file_path,
                current_progress=current_progress
            )
            
            if actual_checksum is None:
                return False
                
            matches = actual_checksum.lower() == expected_checksum.lower()
            
            if not matches:
                logger.warning(
                    f"Checksum mismatch for {file_path}:\n"
                    f"Expected: {expected_checksum}\n"
                    f"Actual  : {actual_checksum}"
                )
                self.display.show_error("Verify Failed")
                
            return matches
            
        except Exception as e:
            logger.error(f"Error verifying checksum: {e}")
            return False
