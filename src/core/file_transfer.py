# src/core/file_transfer.py

import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple, List, Any
from datetime import datetime

from .config_manager import TransferConfig
from .interfaces.display import DisplayInterface
from .interfaces.storage_inter import StorageInterface
from .interfaces.types import TransferStatus as InterfaceTransferStatus
from .interfaces.types import TransferProgress

# Import our new utility modules
from .checksum import ChecksumCalculator
from .mhl_handler import initialize_mhl_file, add_file_to_mhl
from .sound_manager import SoundManager
from .proxy_generator import ProxyGenerator
from .directory_handler import DirectoryHandler
from .file_operations import FileOperations, TEMP_FILE_EXTENSION
from .file_context import error_handler, file_operation
from .transfer_utils import (
    get_transferable_files, calculate_transfer_totals, 
    create_destination_path, create_directory_structure,
    validate_source_path, verify_space_requirements
)
from .transfer_logger import TransferLogger, create_transfer_log
from .progress_tracker import ProgressTracker, TransferStatus
from .exceptions import FileTransferError as CoreFileTransferError
from .transfer_components import TransferValidator, TransferEnvironment, FileProcessor
from .validation import PathValidator, ErrorMessages

logger = logging.getLogger(__name__)

class FileTransfer:
    """
    Main file transfer orchestrator using composition for cleaner architecture.
    
    This class coordinates the file transfer process by delegating to specialized
    components, following a composition-based approach for better maintainability.
    """
    
    def __init__(
        self,
        config_manager,
        display: DisplayInterface,
        storage: StorageInterface,
        state_manager,
        sound_manager = None,
        stop_event = None
    ):
        """
        Initialize file transfer system.
        
        Args:
            config_manager: Configuration manager instance
            display: Display interface for status messages
            storage: Storage interface for device operations
            state_manager: State manager for system state tracking
            sound_manager: Optional sound manager for playing audio cues
            stop_event: Optional threading.Event to check for stop conditions
        """
        self.config = config_manager.config
        self.display = display
        self.storage = storage
        self.state_manager = state_manager
        self.sound_manager = sound_manager
        self.stop_event = stop_event
        self.no_files_found = False
        
        # Initialize components
        self.validator = TransferValidator(display, storage, state_manager)
        self.environment = TransferEnvironment(self.config, display, sound_manager)
        self.processor = FileProcessor(display, storage, self.config, sound_manager, stop_event)
        
        # Initialize utility classes
        self.checksum_calculator = ChecksumCalculator(display)
        self.directory_handler = DirectoryHandler(self.config)
        self.progress_tracker = ProgressTracker(display)
        self.file_ops = FileOperations(display, storage, sound_manager)
        
        # Initialize proxy generator
        self.proxy_generator = ProxyGenerator(self.config, self.display)
        self._proxy_generation_active = False
        self._current_proxy_file = None
    
    def _play_sound(self, success: bool = True) -> None:
        """
        Play a sound effect.
        
        Args:
            success: True to play success sound, False to play error sound
        """
        if not self.sound_manager or not hasattr(self.config, 'enable_sounds') or not self.config.enable_sounds:
            return
            
        try:
            if success:
                self.sound_manager.play_success()
            else:
                self.sound_manager.play_error()
        except Exception as e:
            logger.warning(f"Failed to play sound: {e}")
    
    def _check_utility_mode(self) -> bool:
        """
        Check if system is in utility mode.
        
        Returns:
            bool: True if validation passes (not in utility mode), False otherwise
        """
        if self.state_manager.is_utility():
            logger.info("Transfer blocked - system is in utility mode")
            self.display.show_error("In utility mode")
            return False
        return True
    
    def _validate_transfer_preconditions(self, destination_path: Path) -> bool:
        """
        Validate preconditions before starting transfer using centralized validation.
        
        Args:
            destination_path: Target path for file transfer
            
        Returns:
            bool: True if destination is valid and ready for transfer, False otherwise
        """
        with file_operation(self.display, self.sound_manager, "Validate Transfer Preconditions"):
            # Check utility mode first
            if not self._check_utility_mode():
                return False
                
            # Use centralized validation
            result = PathValidator.validate_destination(destination_path, auto_create=True)
            
            if not result.is_valid:
                logger.error(f"Destination validation failed: {result.error_message}")
                self.display.show_error(result.error_message)
                return False
                
            logger.info(f"Using validated directory: {result.sanitized_path}")
            return True
    
    def _prepare_for_transfer(self, source_path: Path, destination_path: Path) -> bool:
        """
        Prepare for file transfer by validating source and destination.
        
        Args:
            source_path: Source path
            destination_path: Destination path
            
        Returns:
            bool: True if preparation was successful, False otherwise
        """
        # Validate destination path
        if not self._validate_transfer_preconditions(destination_path):
            self._play_sound(success=False)
            return False
            
        # Validate source path
        if not validate_source_path(source_path):
            self.display.show_error("Source Error")
            self._play_sound(success=False)
            return False
            
        return True
    
    def _setup_transfer_environment(self, source_path: Path, destination_path: Path) -> Optional[Tuple[str, Path, Optional[Tuple]]]:
        """
        Set up transfer environment including directories and MHL file.
        
        Args:
            source_path: Source path
            destination_path: Destination path
            
        Returns:
            Optional[Tuple]: (timestamp, target_dir, mhl_data) if successful, None otherwise
        """
        with file_operation(self.display, self.sound_manager, "Setup Transfer Environment"):
            # Generate timestamp for this transfer session
            timestamp_format = "%Y%m%d_%H%M%S"  # Default format
            if hasattr(self.config, 'timestamp_format'):
                timestamp_format = self.config.timestamp_format
                
            timestamp = datetime.now().strftime(timestamp_format)
            
            # Create target directory
            try:
                create_date_folders = hasattr(self.config, 'create_date_folders') and self.config.create_date_folders
                target_dir = self.directory_handler.create_organized_directory(
                    destination_path,
                    source_path,
                    timestamp if create_date_folders else None
                )
            except Exception as e:
                logger.error(f"Error creating directory structure: {e}")
                self.display.show_error("Dir Create Error")
                return None
                
            # Initialize MHL file if needed (only if the config supports it)
            mhl_data = None
            if hasattr(self.config, 'create_mhl_files') and self.config.create_mhl_files:
                try:
                    mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
                    mhl_data = (mhl_filename, tree, hashes)
                except Exception as e:
                    logger.error(f"Failed to create MHL file: {e}")
                    self.display.show_error("MHL Create Failed")
                    return None
                
            return timestamp, target_dir, mhl_data
    
    def _prepare_files_for_transfer(self, source_path: Path, destination_path: Path, target_dir: Path) -> Optional[Tuple[List[Path], int, int]]:
        """
        Prepare files for transfer by scanning, calculating totals, and creating directory structure.
        
        Args:
            source_path: Source path
            destination_path: Destination path
            target_dir: Target directory
            
        Returns:
            Optional[Tuple]: (files_to_transfer, total_size, total_files) if successful, None otherwise
        """
        with file_operation(self.display, self.sound_manager, "Prepare Files for Transfer"):
            # Get files to transfer
            try:
                media_only = False
                media_extensions = []
                
                if hasattr(self.config, 'media_only_transfer'):
                    media_only = self.config.media_only_transfer
                    
                if hasattr(self.config, 'media_extensions'):
                    media_extensions = self.config.media_extensions
                    
                files_to_transfer = get_transferable_files(
                    source_path, 
                    media_only,
                    media_extensions
                )
            except Exception as e:
                logger.error(f"Error getting files to transfer: {e}")
                self.display.show_error("File Scan Error")
                return None
                
            if not files_to_transfer:
                if hasattr(self.config, 'media_only_transfer') and self.config.media_only_transfer:
                    self.display.show_error("No Media Found")
                else:
                    self.display.show_error("No Files Found")
                self._play_sound(success=False)
                return None
                
            # Calculate transfer totals
            try:
                files_to_transfer, total_size, total_files = calculate_transfer_totals(files_to_transfer)
            except Exception as e:
                logger.error(f"Error calculating transfer totals: {e}")
                self.display.show_error("Size Calc Error")
                return None
                
            if total_files == 0:
                self.display.show_error("No Valid Files")
                self._play_sound(success=False)
                return None
                
            # Verify space requirements
            required_space = int(total_size * 1.1)  # Add 10% buffer
            if not verify_space_requirements(self.storage, destination_path, required_space):
                self.display.show_error("Not enough space")
                self._play_sound(success=False)
                return None
                
            # Create directory structure for preserving folders
            if hasattr(self.config, 'preserve_folder_structure') and self.config.preserve_folder_structure:
                if not create_directory_structure(files_to_transfer, source_path, target_dir):
                    self.display.show_error("Dir Structure Error")
                    self._play_sound(success=False)
                    return None
                    
            return files_to_transfer, total_size, total_files
    
    #TODO: Test if this is needed or if it is legacy code that can be removed.
    
    # def _transfer_single_file(self, src_file: Path, target_dir: Path, source_path: Path,
    #                        file_number: int, total_files: int, total_transferred: int,
    #                        total_size: int, mhl_data: Optional[Tuple], transfer_logger: TransferLogger) -> Tuple[bool, Optional[int], Optional[str]]:
    #     """
    #     Transfer a single file.
        
    #     Args:
    #         src_file: Source file path
    #         target_dir: Target directory
    #         source_path: Source root path
    #         file_number: Current file number
    #         total_files: Total number of files
    #         total_transferred: Total bytes transferred so far
    #         total_size: Total size of all files in bytes
    #         mhl_data: Optional MHL data tuple
    #         transfer_logger: Transfer logger object
            
    #     Returns:
    #         Tuple of (success_flag, size_transferred, failure_reason):
    #             success_flag: True if transfer succeeded
    #             size_transferred: Size of transferred file if successful, None otherwise
    #             failure_reason: Reason for failure if failed, None otherwise
    #     """
    #     with file_operation(self.display, self.sound_manager, f"Transfer File {file_number}/{total_files}"):
    #         # Check if file still exists
    #         if not src_file.exists():
    #             logger.warning(f"File disappeared before transfer: {src_file}")
    #             transfer_logger.log_failure(src_file, None, "File disappeared")
    #             return False, None, f"{src_file} (disappeared)"
                
    #         # Get file size
    #         try:
    #             file_size = src_file.stat().st_size
    #         except Exception as e:
    #             logger.error(f"Failed to get file size: {e}")
    #             transfer_logger.log_failure(src_file, None, f"Size error: {e}")
    #             return False, None, f"{src_file} (size error)"
                
    #         # Create destination path
    #         try:
    #             rename_with_timestamp = False
    #             preserve_original_filename = True
    #             timestamp_format = "%Y%m%d_%H%M%S"
    #             filename_template = "{original}_{timestamp}"
                
    #             if hasattr(self.config, 'rename_with_timestamp'):
    #                 rename_with_timestamp = self.config.rename_with_timestamp
                    
    #             if hasattr(self.config, 'preserve_original_filename'):
    #                 preserve_original_filename = self.config.preserve_original_filename
                    
    #             if hasattr(self.config, 'timestamp_format'):
    #                 timestamp_format = self.config.timestamp_format
                    
    #             if hasattr(self.config, 'filename_template'):
    #                 filename_template = self.config.filename_template
                
    #             dst_path = create_destination_path(
    #                 src_file, target_dir, source_path,
    #                 rename_with_timestamp,
    #                 preserve_original_filename,
    #                 timestamp_format,
    #                 filename_template
    #             )
    #         except Exception as e:
    #             logger.error(f"Failed to create destination path: {e}")
    #             transfer_logger.log_failure(src_file, None, f"Path error: {e}")
    #             return False, None, f"{src_file} (path error)"
                
    #         # Initialize progress tracking
    #         self.progress_tracker.start_file(
    #             src_file, file_number, total_files,
    #             file_size, total_size, total_transferred
    #         )
                
    #         # Get source metadata
    #         try:
    #             metadata = self.file_ops.get_metadata(src_file)
    #         except Exception as e:
    #             logger.warning(f"Failed to get metadata: {e}")
    #             metadata = None
                
    #         # Copy file with progress tracking
    #         try:
    #             # Initialize hash calculator
    #             xxh64_hash = self.checksum_calculator.create_hash()
                
    #             # Create progress callback
    #             progress_callback = self.progress_tracker.create_progress_callback()
                
    #             # Perform file copy
    #             success, checksum = self.file_ops.copy_file_with_hash(
    #                 src_file, dst_path, xxh64_hash, progress_callback
    #             )
                
    #             if not success:
    #                 transfer_logger.log_failure(src_file, dst_path, "Copy failed")
    #                 return False, None, str(src_file)
                    
    #             # Apply metadata if available
    #             if metadata:
    #                 self.file_ops.apply_metadata(dst_path, metadata)
                    
    #             # Set progress status to checksum verification
    #             self.progress_tracker.set_status(TransferStatus.CHECKSUMMING)
                
    #             # Verify checksum
    #             verify_result = self.file_ops.verify_checksum(
    #                 dst_path, checksum, progress_callback
    #             )
                
    #             if not verify_result:
    #                 logger.error(f"Checksum verification failed for {dst_path}")
    #                 transfer_logger.log_failure(src_file, dst_path, "Checksum verification failed")
                    
    #                 # Cleanup the file
    #                 try:
    #                     if dst_path.exists():
    #                         dst_path.unlink()
    #                 except Exception as cleanup_err:
    #                     logger.warning(f"Failed to clean up file after checksum failure: {cleanup_err}")
                        
    #                 return False, None, str(src_file)
                    
    #             # Add to MHL file if needed
    #             if mhl_data:
    #                 try:
    #                     mhl_filename, tree, hashes = mhl_data
    #                     logger.info(f"Adding file to MHL: {dst_path}")
    #                     add_file_to_mhl(mhl_filename, tree, hashes, dst_path, checksum, file_size)
    #                     logger.info(f"Successfully added file to MHL: {dst_path}")
    #                 except Exception as mhl_err:
    #                     logger.error(f"Failed to add file to MHL: {mhl_err}", exc_info=True)
    #                     # Continue without stopping the transfer
                        
    #             # Mark progress as complete
    #             self.progress_tracker.complete_file(True)
                
    #             # Log success
    #             transfer_logger.log_success(src_file, dst_path)
                
    #             return True, file_size, None
                
    #         except Exception as e:
    #             logger.error(f"Error transferring file {src_file}: {e}")
    #             transfer_logger.log_failure(src_file, dst_path, f"Transfer error: {e}")
    #             return False, None, f"{src_file} (error: {e})"
    
    # def _execute_file_transfers(self, files_to_transfer: List[Path], target_dir: Path,
    #                          source_path: Path, total_files: int, total_size: int,
    #                          mhl_data: Optional[Tuple], log_file: Path) -> Optional[Tuple[List[str], int]]:
    #     """
    #     Execute file transfers for all files.
        
    #     Args:
    #         files_to_transfer: List of files to transfer
    #         target_dir: Target directory
    #         source_path: Source root path
    #         total_files: Total number of files
    #         total_size: Total size of all files in bytes
    #         mhl_data: Optional MHL data tuple
    #         log_file: Path to log file
            
    #     Returns:
    #         Optional[Tuple]: (failures, total_transferred) if successful, None otherwise
    #     """
    #     with file_operation(self.display, self.sound_manager, "Execute File Transfers"):
    #         # Initialize transfer logger
    #         transfer_logger = TransferLogger(log_file)
    #         transfer_start_time = transfer_logger.start_transfer(
    #             source_path, target_dir, total_files, total_size
    #         )
            
    #         failures = []
    #         total_transferred = 0
    #         file_number = 0
            
    #         for src_file in files_to_transfer:
    #             file_number += 1
    #             success, size_transferred, failure = self._transfer_single_file(
    #                 src_file, target_dir, source_path, 
    #                 file_number, total_files, total_transferred, 
    #                 total_size, mhl_data, transfer_logger
    #             )
                
    #             if success:
    #                 total_transferred += size_transferred
    #             else:
    #                 failures.append(failure)
                    
    #         # Complete transfer logging
    #         successful_files = total_files - len(failures)
    #         transfer_logger.complete_transfer(total_files, successful_files, failures)
            
    #         return failures, total_transferred
    
    def copy_sd_to_dump(self, source_path: Path, destination_path: Path, log_file: Path = None) -> bool:
        """
        Copy files from source path to destination dump location.
        
        Args:
            source_path: Source path (SD card or other media)
            destination_path: Destination path (dump location)
            log_file: Optional path to log file
            
        Returns:
            bool: True if transfer was successful, False otherwise
        """
        try:
            # Reset no_files_found flag at start of transfer
            self.no_files_found = False
            
            # Check if the source path exists before starting
            if not source_path.exists() or not os.path.ismount(str(source_path)):
                logger.error(f"Source drive not found or not mounted: {source_path}")
                self.display.show_error("Source not found")
                if self.sound_manager:
                    self.sound_manager.play_error()
                return False
                
            # Validate transfer preconditions
            if not self.validator.validate_transfer(source_path, destination_path):
                return False
            
            # Set up transfer environment
            env_result = self.environment.setup(source_path, destination_path)
            if not env_result:
                return False
                
            timestamp, target_dir, mhl_data = env_result
            
            # Check if the source path still exists before starting file processing
            if not source_path.exists() or not os.path.ismount(str(source_path)):
                logger.error(f"Source drive removed before transfer could start: {source_path}")
                self.display.show_error(ErrorMessages.SOURCE_REMOVED)
                if self.sound_manager:
                    self.sound_manager.play_error()
                return False
            
            # Process files
            success = self.processor.process_files(source_path, target_dir, log_file)
            
            # Set no_files_found flag based on processor result
            self.no_files_found = self.processor.no_files_found if hasattr(self.processor, 'no_files_found') else False
            
            return success
            
        except Exception as e:
            logger.error(f"Error during file transfer: {e}", exc_info=True)
            
            # Check if it could be a drive removal error
            if not source_path.exists() or not os.path.ismount(str(source_path)):
                logger.error(f"Source drive seems to have been removed during transfer: {source_path}")
                self.display.show_error(ErrorMessages.SOURCE_REMOVED)
            else:
                self.display.show_error(ErrorMessages.TRANSFER_ERROR)
                
            if self.sound_manager:
                self.sound_manager.play_error()
                
            return False
            
    def generate_proxies(self, source_path: Path, destination_path: Optional[Path] = None) -> bool:
        """
        Generate proxy files for media in source path.
        
        Args:
            source_path: Source path containing media files
            destination_path: Optional custom destination path for proxies
            
        Returns:
            bool: True if proxy generation was successful, False otherwise
        """
        try:
            # Check if proxy generation is enabled
            if not self.config.generate_proxies:
                logger.info("Proxy generation is disabled in configuration")
                return False
                
            # Create proxy generator
            proxy_generator = ProxyGenerator(self.config, self.display)
            
            # Generate proxies
            if destination_path:
                return proxy_generator.generate_proxies(source_path, destination_path)
            else:
                # Use default proxy path from source
                proxy_dir = source_path / self.config.proxy_subfolder
                return proxy_generator.generate_proxies(source_path, proxy_dir)
                
        except Exception as e:
            logger.error(f"Error during proxy generation: {e}", exc_info=True)
            self.display.show_error("Proxy Error")
            return False
            return False