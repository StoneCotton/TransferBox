# src/core/transfer_components.py

import logging
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Union
from datetime import datetime

from .config_manager import TransferConfig
from .interfaces.display import DisplayInterface
from .interfaces.storage_inter import StorageInterface
from .interfaces.types import TransferStatus, TransferProgress
from .exceptions import FileTransferError, StorageError
from .transfer_utils import (
    get_transferable_files, calculate_transfer_totals,
    create_destination_path, create_directory_structure,
    validate_source_path, verify_space_requirements
)
from .file_context import file_operation
from .mhl_handler import initialize_mhl_file, add_file_to_mhl
from .transfer_logger import TransferLogger, create_transfer_log
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

def get_valid_media_files(source_path: Path, config) -> List[Path]:
    """
    Get a list of valid media files from the source path based on configuration.
    
    Args:
        source_path: Source directory
        config: Configuration object
        
    Returns:
        List of valid media file paths
        
    Raises:
        FileTransferError: If source path is invalid or inaccessible
    """
    # Initialize parameters from config
    media_only = getattr(config, 'media_only_transfer', False)
    media_extensions = getattr(config, 'media_extensions', [])
    recursive = getattr(config, 'recursive_search', True)
    
    logger.info(f"Scanning for files in {source_path} (media_only={media_only})")
    
    # Check if source path exists and is mounted
    if not source_path.exists():
        logger.error(f"Source path doesn't exist: {source_path}")
        raise FileTransferError(f"Source path doesn't exist: {source_path}")
        
    # For Unix-like systems, check if path is mounted
    if hasattr(os, 'path') and hasattr(os.path, 'ismount'):
        if not os.path.ismount(str(source_path)):
            logger.error(f"Source path is not mounted: {source_path}")
            raise FileTransferError(f"Source path is not mounted: {source_path}")
        
    # Get all files
    files = []
    
    try:
        if recursive:
            # Recursively get all files (excluding hidden files and directories)
            file_glob = source_path.glob('**/*')
            files = []
            
            # Process files in chunks to check for drive removal between chunks
            chunk_size = 100
            file_chunk = []
            
            for i, f in enumerate(file_glob):
                # Check every chunk_size files if the drive is still there
                if i % chunk_size == 0 and i > 0:
                    if not source_path.exists() or not os.path.ismount(str(source_path)):
                        logger.error(f"Source drive removed during file scan: {source_path}")
                        raise FileTransferError(f"Source drive removed during scan")
                        
                if f.is_file() and not any(p.startswith('.') for p in f.parts):
                    files.append(f)
        else:
            # Get only files in the top directory
            files = [f for f in source_path.iterdir() if f.is_file() and not f.name.startswith('.')]
    except (FileNotFoundError, PermissionError, OSError) as e:
        # Check if it's because the drive was removed
        if not source_path.exists() or not os.path.ismount(str(source_path)):
            logger.error(f"Source drive removed during file scan: {e}")
            raise FileTransferError(f"Source drive removed during scan")
        else:
            logger.error(f"Error scanning files: {e}")
            raise FileTransferError(f"Error scanning for files: {e}")
    
    # Filter by media extensions if needed
    if media_only and media_extensions:
        files = [f for f in files if f.suffix.lower() in media_extensions]
    
    # Log result
    logger.info(f"Found {len(files)} valid files to transfer")
    
    # Sort files for consistent ordering
    return sorted(files)

def create_mhl(target_dir: Path) -> Tuple[Path, Any, Dict]:
    """
    Create a new MHL file for the transfer.
    
    Args:
        target_dir: Target directory for the MHL file
        
    Returns:
        Tuple of (mhl_filename, xml_tree, hash_dict)
    """
    try:
        from datetime import datetime
        import xml.etree.ElementTree as ET
        
        # Create an MHL filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        mhl_filename = target_dir / f"transfer_{timestamp}.mhl"
        
        # Create the XML structure
        root = ET.Element("hashlist")
        root.set("version", "1.0")
        
        # Create a creator element
        creator = ET.SubElement(root, "creator")
        ET.SubElement(creator, "name").text = "TransferBox"
        ET.SubElement(creator, "datemodified").text = datetime.now().isoformat()
        
        # Create an initial tree with the header information
        tree = ET.ElementTree(root)
        
        # Create a dictionary to store hashes
        hashes = {}
        
        # Write the initial MHL file
        tree.write(mhl_filename, encoding="UTF-8", xml_declaration=True)
        
        logger.info(f"Created MHL file: {mhl_filename}")
        return mhl_filename, tree, hashes
        
    except Exception as e:
        logger.error(f"Error creating MHL file: {e}")
        return None, None, {}

def add_file_to_mhl(src_path: Path, dst_path: Path, tree, hashes: Dict) -> bool:
    """
    Add a file entry to an MHL file.
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        tree: XML tree object
        hashes: Dictionary of file hashes
        
    Returns:
        True if added successfully, False otherwise
    """
    try:
        import xml.etree.ElementTree as ET
        from datetime import datetime
        
        # Get the hash from our dictionary
        checksum = hashes.get(str(src_path))
        if not checksum:
            logger.warning(f"No hash found for {src_path} in MHL data")
            return False
            
        # Get the root element
        root = tree.getroot()
        
        # Create a hash element
        hash_elem = ET.SubElement(root, "hash")
        
        # Add file info
        ET.SubElement(hash_elem, "file").text = str(dst_path.name)
        ET.SubElement(hash_elem, "size").text = str(dst_path.stat().st_size)
        ET.SubElement(hash_elem, "lastmodificationdate").text = datetime.fromtimestamp(
            dst_path.stat().st_mtime).isoformat()
        
        # Add the hash info
        hash_info = ET.SubElement(hash_elem, "hashinfo")
        ET.SubElement(hash_info, "hashtype").text = "md5"
        ET.SubElement(hash_info, "value").text = checksum
        
        # Write the updated MHL file
        tree.write(str(tree.getroot().findtext("creator/datemodified")), encoding="UTF-8", xml_declaration=True)
        
        logger.info(f"Added {dst_path.name} to MHL file")
        return True
        
    except Exception as e:
        logger.error(f"Error adding file to MHL: {e}")
        return False

class TransferValidator:
    """Validates transfer preconditions and requirements"""
    
    def __init__(self, display: DisplayInterface, storage: StorageInterface, state_manager):
        """
        Initialize transfer validator.
        
        Args:
            display: Display interface for showing status messages
            storage: Storage interface for interacting with storage devices
            state_manager: State manager for checking system state
        """
        self.display = display
        self.storage = storage
        self.state_manager = state_manager
        
    def validate_transfer(self, source_path: Path, destination_path: Path) -> bool:
        """
        Validate all transfer prerequisites.
        
        Args:
            source_path: Source path for file transfer
            destination_path: Destination path for file transfer
            
        Returns:
            True if all validations pass, False otherwise
        """
        # Check utility mode
        if not self._check_utility_mode():
            return False
            
        # Validate source and destination
        return (self._validate_source(source_path) and 
                self._validate_destination(destination_path))
    
    def _check_utility_mode(self) -> bool:
        """
        Check if system is in utility mode.
        
        Returns:
            True if validation passes (not in utility mode), False otherwise
        """
        if self.state_manager.is_utility():
            logger.info("Transfer blocked - system is in utility mode")
            self.display.show_error("In utility mode")
            return False
        return True
        
    def _validate_source(self, source_path: Path) -> bool:
        """
        Validate source path exists and is readable.
        
        Args:
            source_path: Source path to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        if not validate_source_path(source_path):
            self.display.show_error("Invalid source")
            return False
        return True
        
    def _validate_destination(self, destination_path: Path) -> bool:
        """
        Validate destination path is writable.
        
        Args:
            destination_path: Destination path to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        with file_operation(self.display, None, "Validate Destination"):
            # Validate path type
            if destination_path is None:
                logger.error("No destination path provided")
                self.display.show_error("No destination")
                return False
                
            try:
                dest_path = Path(destination_path)
            except TypeError:
                logger.error(f"Invalid destination path type: {type(destination_path).__name__}")
                self.display.show_error("Invalid path type")
                return False
                
            # Handle existing vs non-existing destination
            if dest_path.exists():
                # Check if it's a directory
                if not dest_path.is_dir():
                    logger.error(f"Destination exists but is not a directory: {dest_path}")
                    self.display.show_error("Not a directory")
                    return False
                    
                # Check write permissions
                if not os.access(dest_path, os.W_OK):
                    logger.error(f"No write permission for destination: {dest_path}")
                    self.display.show_error("Write permission denied")
                    return False
                    
                logger.info(f"Using existing directory: {dest_path}")
                return True
                
            # For non-existing destination, validate parent and create
            parent = dest_path.parent
            
            if not parent.exists():
                logger.error(f"Parent directory doesn't exist: {parent}")
                self.display.show_error("Parent dir missing")
                return False
                
            if not os.access(parent, os.W_OK):
                logger.error(f"No write permission for parent directory: {parent}")
                self.display.show_error("Parent write denied")
                return False
                
            # Create the destination directory
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {dest_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to create directory {dest_path}: {e}")
                self.display.show_error("Create dir failed")
                return False


class TransferEnvironment:
    """Sets up environment for file transfers"""
    
    def __init__(self, config: TransferConfig, display: DisplayInterface, sound_manager=None):
        """
        Initialize transfer environment manager.
        
        Args:
            config: Configuration settings
            display: Display interface for showing status messages
            sound_manager: Optional sound manager for playing sounds
        """
        self.config = config
        self.display = display
        self.sound_manager = sound_manager
        
    def setup(self, source_path: Path, destination_path: Path) -> Optional[Tuple[str, Path, Optional[Tuple]]]:
        """
        Set up transfer environment.
        
        Args:
            source_path: Source path for file transfer
            destination_path: Destination path for file transfer
            
        Returns:
            Optional[Tuple]: (timestamp, target_dir, mhl_data) if successful, None otherwise
        """
        with file_operation(self.display, self.sound_manager, "Setup Transfer Environment"):
            # Generate timestamp for this transfer session
            timestamp = self._generate_timestamp()
            
            # Create target directory
            try:
                from .directory_handler import DirectoryHandler
                directory_handler = DirectoryHandler(self.config)
                create_date_folders = getattr(self.config, 'create_date_folders', False)
                target_dir = directory_handler.create_organized_directory(
                    destination_path,
                    source_path,
                    timestamp if create_date_folders else None
                )
            except Exception as e:
                logger.error(f"Error creating directory structure: {e}")
                self.display.show_error("Dir Create Error")
                return None
                
            # Initialize MHL file if needed
            mhl_data = self._setup_mhl(timestamp, target_dir)
                
            return timestamp, target_dir, mhl_data
    
    def _generate_timestamp(self) -> str:
        """
        Generate timestamp for current transfer.
        
        Returns:
            Formatted timestamp string
        """
        format_str = getattr(self.config, 'timestamp_format', "%Y%m%d_%H%M%S")
        return datetime.now().strftime(format_str)
    
    def _setup_mhl(self, timestamp: str, target_dir: Path) -> Optional[Tuple]:
        """
        Set up MHL file if configured to do so.
        
        Args:
            timestamp: Timestamp string for current transfer
            target_dir: Target directory for MHL file
            
        Returns:
            Optional MHL data tuple or None if MHL is disabled or fails
        """
        if not getattr(self.config, 'create_mhl_files', False):
            return None
            
        try:
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)
            return (mhl_filename, tree, hashes)
        except Exception as e:
            logger.error(f"Failed to create MHL file: {e}")
            self.display.show_error("MHL Create Failed")
            return None


class FileProcessor:
    """Processes files for transfer"""
    
    def __init__(self, display: DisplayInterface, storage: StorageInterface, 
                 config: TransferConfig, sound_manager=None):
        """
        Initialize file processor.
        
        Args:
            display: Display interface for showing status messages
            storage: Storage interface for interacting with storage devices
            config: Configuration settings
            sound_manager: Optional sound manager for playing sounds
        """
        self.display = display
        self.storage = storage
        self.config = config
        self.sound_manager = sound_manager
        self.progress_tracker = ProgressTracker(display)
        
    def process_files(self, source_path: Path, target_dir: Path, log_file: Path = None) -> bool:
        """
        Process all files from source to target directory.
        
        Args:
            source_path: Source path
            target_dir: Target directory
            log_file: Optional path to log file
            
        Returns:
            bool: True if all files processed successfully
        """
        # Create transfer logger instance
        transfer_logger = TransferLogger(log_file)
        
        # Initialize tracking variables
        successful_files = 0
        start_time = datetime.now()
        failures = []
        
        # Set up MHL if enabled
        mhl_data = None
        if getattr(self.config, 'create_mhl', False):
            mhl_filename, tree, hashes = create_mhl(target_dir)
            mhl_data = (mhl_filename, tree, hashes)
            
        # Check if source path still exists before starting
        if not source_path.exists() or not os.path.ismount(str(source_path)):
            error_msg = f"Source drive removed before transfer could start: {source_path}"
            logger.error(error_msg)
            self.display.show_error("Source removed")
            if self.sound_manager:
                self.sound_manager.play_error()
            return False
        
        # Get all valid files to transfer
        try:
            files_to_transfer = get_valid_media_files(source_path, self.config)
        except (FileNotFoundError, PermissionError, OSError) as e:
            # These specific errors are likely caused by drive removal
            logger.error(f"Error getting files - drive may have been removed: {e}")
            self.display.show_error("Source removed")
            if self.sound_manager:
                self.sound_manager.play_error()
            return False
            
        total_files = len(files_to_transfer)
        
        # Calculate total size for progress tracking
        total_size = 0
        for file_path in files_to_transfer:
            try:
                total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError) as e:
                # Check if source drive was removed
                if not source_path.exists() or not os.path.ismount(str(source_path)):
                    logger.error(f"Source drive removed during size calculation: {source_path}")
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                    return False
                else:
                    # Skip files that can't be accessed for other reasons
                    logger.warning(f"Could not access file for size calculation: {file_path} - {e}")
        
        # Initialize progress tracking
        self.progress_tracker.start_transfer(total_files, total_size)
        self.progress_tracker.set_status(TransferStatus.COPYING)
        
        # Handle empty source directory
        if total_files == 0:
            logger.warning(f"No files to transfer from {source_path}")
            self.display.show_status("No files found")
            transfer_logger.log_message("No files to transfer")
            self.progress_tracker.complete_transfer(successful=True)
            return True
            
        # Log the start of the transfer
        #transfer_logger.log_message(f"Starting transfer of {total_files} files")
        
        # Process all files
        try:
            for file_number, file_path in enumerate(files_to_transfer, 1):
                # Check if source drive still exists before processing each file
                if not source_path.exists() or not os.path.ismount(str(source_path)):
                    error_msg = f"Source drive removed during transfer: {source_path}"
                    logger.error(error_msg)
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                    # Mark transfer as incomplete
                    self.progress_tracker.complete_transfer(successful=False)
                    # Log the interruption
                    transfer_logger.log_message(error_msg)
                    return False
                
                # Get file size for this file
                try:
                    file_size = file_path.stat().st_size
                except (OSError, FileNotFoundError) as e:
                    # Check if source drive was removed
                    if not source_path.exists() or not os.path.ismount(str(source_path)):
                        logger.error(f"Source drive removed while accessing file: {file_path} - {e}")
                        self.display.show_error("Source removed")
                        if self.sound_manager:
                            self.sound_manager.play_error()
                        # Mark transfer as incomplete
                        self.progress_tracker.complete_transfer(successful=False)
                        return False
                    else:
                        file_size = 0
                        logger.warning(f"Could not get size for file: {file_path} - {e}")
                
                # Calculate total transferred so far
                total_transferred_so_far = 0
                for idx, f in enumerate(files_to_transfer):
                    if idx < file_number - 1 and f not in failures:
                        try:
                            total_transferred_so_far += f.stat().st_size
                        except (OSError, FileNotFoundError):
                            pass
                
                # Start tracking this file
                self.progress_tracker.start_file(
                    file_path=file_path,
                    file_number=file_number,
                    total_files=total_files,
                    file_size=file_size,
                    total_size=total_size,
                    total_transferred=total_transferred_so_far
                )
                
                try:
                    success = self._process_single_file(
                        file_path, 
                        source_path, 
                        target_dir,
                        mhl_data,
                        transfer_logger
                    )
                except (FileNotFoundError, PermissionError, OSError) as e:
                    # These specific errors are likely caused by drive removal
                    logger.error(f"Error processing file - drive may have been removed: {e}")
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                    # Mark transfer as incomplete
                    self.progress_tracker.complete_transfer(successful=False)
                    return False
                
                if success:
                    successful_files += 1
                else:
                    failures.append(file_path)
                    
                # No need to update progress here as complete_file is called in _process_single_file
            
            # Complete transfer
            end_time = datetime.now()
            
            # Log transfer results
            transfer_logger.log_transfer_summary(
                source_path=source_path,
                destination_path=target_dir,
                start_time=start_time,
                end_time=end_time,
                total_files=total_files,
                successful_files=successful_files,
                failures=failures
            )
            
            # Finalize progress tracking
            self.progress_tracker.complete_transfer(successful=successful_files == total_files)
            
            # Play appropriate sound
            if self.sound_manager:
                if successful_files == total_files:
                    self.sound_manager.play_success()
                else:
                    self.sound_manager.play_error()
            
            return successful_files == total_files
            
        except Exception as e:
            logger.error(f"Error during file processing: {e}")
            
            # Check if it could be a drive removal error
            if not source_path.exists() or not os.path.ismount(str(source_path)):
                logger.error(f"Source drive seems to have been removed during transfer: {source_path}")
                self.display.show_error("Source removed")
            else:
                self.display.show_error("Transfer error")
                
            if self.sound_manager:
                self.sound_manager.play_error()
                
            self.progress_tracker.complete_transfer(successful=False)
            return False
    
    def _process_single_file(self, file_path: Path, source_root: Path, 
                           target_dir: Path, mhl_data, logger) -> bool:
        """
        Process a single file transfer.
        
        Args:
            file_path: Path to file to transfer
            source_root: Root source directory
            target_dir: Target directory
            mhl_data: Optional MHL data tuple
            logger: Transfer logger
            
        Returns:
            True if file transferred successfully, False otherwise
        """
        try:
            # Check if source path still exists before starting
            if not source_root.exists() or not os.path.ismount(str(source_root)):
                error_msg = f"Source drive removed before processing file: {file_path}"
                logger.error(error_msg)
                self.display.show_error("Source removed")
                if self.sound_manager:
                    self.sound_manager.play_error()
                return False
                
            # Check if file still exists
            if not file_path.exists():
                # Check if this could be due to drive removal
                if not source_root.exists() or not os.path.ismount(str(source_root)):
                    error_msg = f"Source drive removed before processing file: {file_path}"
                    logger.error(error_msg)
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                    return False
                else:
                    logger.warning(f"File disappeared before transfer: {file_path}")
                    return False
            
            # Calculate destination path
            rename_with_timestamp = getattr(self.config, 'rename_with_timestamp', False)
            preserve_original_filename = getattr(self.config, 'preserve_original_filename', True)
            timestamp_format = getattr(self.config, 'timestamp_format', "%Y%m%d_%H%M%S")
            filename_template = getattr(self.config, 'filename_template', "{original}_{timestamp}")
            
            dest_path = create_destination_path(
                file_path, 
                target_dir,
                source_root,
                rename_with_timestamp=rename_with_timestamp,
                preserve_original_filename=preserve_original_filename,
                timestamp_format=timestamp_format,
                filename_template=filename_template
            )
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get file size for progress tracking
            try:
                file_size = file_path.stat().st_size
            except (OSError, FileNotFoundError) as e:
                # Check if source drive was removed
                if not source_root.exists() or not os.path.ismount(str(source_root)):
                    logger.error(f"Source drive removed while getting file size: {file_path} - {e}")
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                    return False
                else:
                    file_size = 0
                    logger.warning(f"Could not get size for file: {file_path} - {e}")
            
            # Set status to copying
            self.progress_tracker.set_status(TransferStatus.COPYING)
            
            # Create progress callback for this file
            progress_callback = self.progress_tracker.create_progress_callback()
            
            # Transfer the file
            from .file_operations import FileOperations, TEMP_FILE_EXTENSION
            file_ops = FileOperations(self.display, self.storage, self.sound_manager)
            
            # Use copy_file_with_hash for checksumming
            xxh64_hash = None
            success = False
            
            try:
                if hasattr(self.config, 'verify_transfers') and self.config.verify_transfers:
                    from .checksum import ChecksumCalculator
                    calculator = ChecksumCalculator(self.display)
                    xxh64_hash = calculator.create_hash()
                    success, checksum = file_ops.copy_file_with_hash(
                        file_path, dest_path, xxh64_hash, progress_callback
                    )
                    
                    if success:
                        # Set status to checksumming
                        self.progress_tracker.set_status(TransferStatus.CHECKSUMMING)
                        
                        # Verify the checksum
                        self.progress_tracker.bytes_transferred = 0  # Reset for checksum progress
                        verify_result = file_ops.verify_checksum(
                            dest_path, checksum, progress_callback
                        )
                        
                        if not verify_result:
                            logger.error(f"Checksum verification failed for {dest_path}")
                            success = False
                else:
                    # Simple copy without checksumming
                    success = file_ops.copy_file(file_path, dest_path, progress_callback=progress_callback)
            except Exception as e:
                # Check if source drive was removed
                if not source_root.exists() or not os.path.ismount(str(source_root)):
                    logger.error(f"Source drive removed during file transfer: {e}")
                    self.display.show_error("Source removed")
                    if self.sound_manager:
                        self.sound_manager.play_error()
                else:
                    logger.error(f"Error during file transfer: {e}")
                    self.display.show_error("Transfer error")
                
                success = False
            
            if success and mhl_data:
                # Add to MHL if needed
                mhl_filename, tree, hashes = mhl_data
                add_file_to_mhl(file_path, dest_path, tree, hashes)
                
            # Log the transfer
            logger.log_file_transfer(
                source_file=file_path,
                dest_file=dest_path,
                success=success
            )
            
            # Mark the file as complete in progress tracker
            self.progress_tracker.complete_file(success=success)
            
            return success
        except Exception as e:
            # Check if it's a drive removal error
            if not source_root.exists() or not os.path.ismount(str(source_root)):
                logger.error(f"Source drive removed during file processing: {e}")
                self.display.show_error("Source removed")
                if self.sound_manager:
                    self.sound_manager.play_error()
            else:
                logger.error(f"Error processing file {file_path}: {e}")
                self.display.show_error("File error")
                
            self.progress_tracker.set_status(TransferStatus.ERROR)
            return False 