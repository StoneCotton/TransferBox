# src/core/checksum.py

import logging
from pathlib import Path
from typing import Optional, Callable, Iterator
import xxhash
from .interfaces.types import TransferProgress, TransferStatus
from .interfaces.display import DisplayInterface

logger = logging.getLogger(__name__)

CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks

class ChecksumCalculator:
    """Handles file checksum calculations with progress monitoring"""

    def __init__(self, display: DisplayInterface):
        self.display = display

    def calculate_file_checksum(
        self, 
        file_path: Path, 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Calculate XXH64 checksum for a file with progress monitoring.
        
        Args:
            file_path: Path to the file
            progress_callback: Optional callback function(bytes_processed, total_bytes)
        
        Returns:
            Hexadecimal checksum string or None if calculation fails
        """
        try:
            file_size = file_path.stat().st_size
            bytes_processed = 0
            hash_obj = xxhash.xxh64()

            progress = TransferProgress(
                current_file=file_path.name,
                file_number=1,
                total_files=1,
                bytes_transferred=0,
                total_bytes=file_size,
                current_file_progress=0.0,
                overall_progress=0.0,
                status=TransferStatus.CHECKSUMMING
            )

            self.display.show_status(f"Checksumming: {file_path.name}")

            with open(file_path, 'rb') as f:
                for chunk in self._read_chunks(f):
                    hash_obj.update(chunk)
                    bytes_processed += len(chunk)
                    
                    # Update progress
                    progress.bytes_transferred = bytes_processed
                    progress.current_file_progress = bytes_processed / file_size
                    progress.overall_progress = bytes_processed / file_size
                    self.display.show_progress(progress)

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(bytes_processed, file_size)

            checksum = hash_obj.hexdigest()
            logger.info(f"Checksum calculated for {file_path}: {checksum}")
            return checksum

        except Exception as e:
            error_msg = f"Error calculating checksum for {file_path}: {e}"
            logger.error(error_msg)
            self.display.show_error(error_msg)
            return None

    def verify_checksum(
        self, 
        file_path: Path, 
        expected_checksum: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Verify a file's checksum against an expected value.
        
        Args:
            file_path: Path to the file
            expected_checksum: Expected checksum value
            progress_callback: Optional callback function(bytes_processed, total_bytes)
            
        Returns:
            True if checksums match, False otherwise
        """
        self.display.show_status(f"Verifying: {file_path.name}")
        actual_checksum = self.calculate_file_checksum(file_path, progress_callback)
        
        if actual_checksum is None:
            return False
            
        matches = actual_checksum.lower() == expected_checksum.lower()
        
        if not matches:
            logger.warning(
                f"Checksum mismatch for {file_path}:\n"
                f"Expected: {expected_checksum}\n"
                f"Actual  : {actual_checksum}"
            )
            self.display.show_error("Checksum verification failed")
            
        return matches

    @staticmethod
    def _read_chunks(file_obj) -> Iterator[bytes]:
        """Generator to read file in chunks"""
        return iter(lambda: file_obj.read(CHUNK_SIZE), b'')

    def batch_verify_checksums(
        self, 
        files_with_checksums: list[tuple[Path, str]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[tuple[Path, bool]]:
        """
        Verify checksums for multiple files.
        
        Args:
            files_with_checksums: List of (file_path, expected_checksum) tuples
            progress_callback: Optional callback function(files_processed, total_files)
            
        Returns:
            List of (file_path, verification_success) tuples
        """
        results = []
        total_files = len(files_with_checksums)

        for idx, (file_path, expected_checksum) in enumerate(files_with_checksums, 1):
            if progress_callback:
                progress_callback(idx, total_files)
                
            verification_result = self.verify_checksum(file_path, expected_checksum)
            results.append((file_path, verification_result))

        return results