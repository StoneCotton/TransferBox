# src/core/file_operations.py

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union, BinaryIO

from .exceptions import FileTransferError, ChecksumError
from .file_context import error_handler, file_operation, FileOperationContext

logger = logging.getLogger(__name__)

# Constants for improved I/O performance
CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks for efficient large file handling
BUFFER_SIZE = 8 * 1024 * 1024  # 8MB buffer for improved I/O performance
TEMP_FILE_EXTENSION = ".TBPART"  # Temporary file extension during transfer


class FileOperations:
    """Class for handling low-level file operations with standardized error handling."""
    
    def __init__(self, display=None, storage=None, sound_manager=None):
        """
        Initialize the file operations handler.
        
        Args:
            display: Display interface for showing status messages
            storage: Storage interface for handling storage-specific operations
            sound_manager: Sound manager for playing status sounds
        """
        self.display = display
        self.storage = storage
        self.sound_manager = sound_manager

    @error_handler
    def copy_file_with_hash(self, src_path: Path, dst_path: Path, 
                           hash_obj=None, progress_callback=None) -> Tuple[bool, Optional[str]]:
        """
        Copy a file while calculating hash and providing progress updates.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            hash_obj: Optional hash object to update during copy
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (success_flag, checksum_string): 
                success_flag: True if copy succeeded
                checksum_string: File checksum if hash_obj provided, None otherwise
                
        Raises:
            FileTransferError: If copy fails
        """
        try:
            # Use a context manager to handle temporary files and cleanup
            with FileOperationContext(self.display, self.sound_manager) as context:
                # Create a temporary destination path with .TBPART extension
                temp_dst_path = dst_path.with_suffix(dst_path.suffix + TEMP_FILE_EXTENSION)
                context.register_temp_file(temp_dst_path)
                
                # Ensure parent directory exists
                temp_dst_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Get file size for progress updates
                file_size = src_path.stat().st_size
                
                # Copy the file with progress updates
                with open(src_path, 'rb', buffering=BUFFER_SIZE) as src:
                    with open(temp_dst_path, 'wb', buffering=BUFFER_SIZE) as dst:
                        bytes_transferred = 0
                        
                        while True:
                            chunk = src.read(CHUNK_SIZE)
                            if not chunk:
                                break
                                
                            dst.write(chunk)
                            if hash_obj:
                                hash_obj.update(chunk)
                            
                            bytes_transferred += len(chunk)
                            
                            # Update progress if callback provided
                            if progress_callback:
                                progress_callback(bytes_transferred, file_size)
                
                # If we got here, the file was successfully copied to the temporary location
                # Now rename it to the final destination
                if dst_path.exists():
                    dst_path.unlink()
                temp_dst_path.rename(dst_path)
                
                # Return checksum if hash_obj provided
                if hash_obj:
                    return True, hash_obj.hexdigest()
                return True, None
        except Exception as e:
            # Log the error
            logger.error(f"Error copying file {src_path} to {dst_path}: {e}")
            # Return failure result
            return False, None

    @error_handler
    def verify_checksum(self, file_path: Path, expected_checksum: str, progress_callback=None) -> bool:
        """
        Verify a file's checksum.
        
        Args:
            file_path: Path to the file to verify
            expected_checksum: Expected checksum
            progress_callback: Optional callback for progress updates
            
        Returns:
            bool: True if checksum matches, False otherwise
            
        Raises:
            FileTransferError: If verification fails due to I/O errors
        """
        try:
            # Import here to avoid circular imports
            from .checksum import ChecksumCalculator
            calculator = ChecksumCalculator(self.display)
            
            # Use the checksum calculator to verify
            result = calculator.verify_checksum(
                file_path, 
                expected_checksum,
                progress_callback=progress_callback
            )
            return result
        except ChecksumError as e:
            logger.error(f"Checksum verification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verifying checksum for {file_path}: {e}")
            return False

    @error_handler
    def apply_metadata(self, dst_path: Path, metadata: Dict[str, Any]) -> bool:
        """
        Apply metadata to a file.
        
        Args:
            dst_path: Destination file path
            metadata: Metadata to apply
            
        Returns:
            bool: True if metadata applied successfully, False otherwise
        """
        if not metadata or not self.storage:
            return False
            
        return self.storage.set_file_metadata(dst_path, metadata)

    @error_handler
    def get_metadata(self, src_path: Path) -> Optional[Dict[str, Any]]:
        """
        Get metadata from a file.
        
        Args:
            src_path: Source file path
            
        Returns:
            Optional[Dict[str, Any]]: File metadata if available, None otherwise
        """
        if not self.storage:
            return None
            
        return self.storage.get_file_metadata(src_path)

    @error_handler
    def ensure_directory_exists(self, dir_path: Path) -> bool:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            dir_path: Directory path
            
        Returns:
            bool: True if directory exists or was created successfully
            
        Raises:
            FileTransferError: If directory creation fails
        """
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            raise FileTransferError(f"Failed to create directory {dir_path}: {e}", error_type="io")

    @error_handler
    def cleanup_temp_files(self, directory: Path, pattern: str = f"*{TEMP_FILE_EXTENSION}") -> int:
        """
        Clean up temporary files in a directory.
        
        Args:
            directory: Directory to clean up
            pattern: Glob pattern for temporary files
            
        Returns:
            int: Number of files cleaned up
            
        Raises:
            FileTransferError: If cleanup fails
        """
        count = 0
        try:
            # Find all temporary files in the directory and its subdirectories
            for temp_file in directory.glob(f"**/{pattern}"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                        count += 1
                        logger.info(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
            return count
        except Exception as e:
            raise FileTransferError(f"Failed to clean up temporary files: {e}", error_type="io")


def safe_copy_file(src_path: Path, dst_path: Path, 
                 chunk_size: int = CHUNK_SIZE,
                 buffer_size: int = BUFFER_SIZE,
                 hash_obj=None,
                 progress_callback=None) -> Tuple[bool, Optional[str]]:
    """
    Safely copy a file with optional hashing and progress updates.
    This is a standalone function that doesn't require class instantiation.
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        chunk_size: Size of chunks to read
        buffer_size: Buffer size for file I/O
        hash_obj: Optional hash object to update during copy
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (success_flag, checksum_string):
            success_flag: True if copy succeeded
            checksum_string: File checksum if hash_obj provided, None otherwise
            
    Raises:
        FileTransferError: If copy fails
    """
    # Create a temporary destination path
    temp_dst_path = dst_path.with_suffix(dst_path.suffix + TEMP_FILE_EXTENSION)
    
    try:
        # Ensure parent directory exists
        temp_dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file size for progress updates
        file_size = src_path.stat().st_size
        
        # Copy the file
        with open(src_path, 'rb', buffering=buffer_size) as src:
            with open(temp_dst_path, 'wb', buffering=buffer_size) as dst:
                bytes_transferred = 0
                
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                        
                    dst.write(chunk)
                    if hash_obj:
                        hash_obj.update(chunk)
                    
                    bytes_transferred += len(chunk)
                    
                    # Update progress if callback provided
                    if progress_callback:
                        progress_callback(bytes_transferred, file_size)
        
        # If we got here, rename the temporary file to the final destination
        if dst_path.exists():
            dst_path.unlink()
        temp_dst_path.rename(dst_path)
        
        # Return checksum if hash_obj provided
        if hash_obj:
            return True, hash_obj.hexdigest()
        return True, None
        
    except Exception as e:
        # Clean up the temporary file if it exists
        if temp_dst_path.exists():
            try:
                temp_dst_path.unlink()
            except Exception as cleanup_err:
                logger.warning(f"Failed to clean up temporary file {temp_dst_path}: {cleanup_err}")
        
        # Re-raise as FileTransferError
        raise FileTransferError(f"Failed to copy file: {e}", source=src_path, destination=dst_path, error_type="io") from e 