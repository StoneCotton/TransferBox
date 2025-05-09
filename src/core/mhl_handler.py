# src/core/mhl_handler.py

import logging
from pathlib import Path
from datetime import datetime
import socket
import xml.etree.ElementTree as ET
from typing import Tuple, Optional
import os
from src import __version__, __project_name__

logger = logging.getLogger(__name__)

def initialize_mhl_file(directory_name: str, target_dir: Path) -> Tuple[Path, ET.ElementTree, ET.Element]:
    """
    Initialize a new MHL (Media Hash List) file.
    
    Args:
        directory_name: Name of the directory being processed
        target_dir: Path to the target directory
        
    Returns:
        Tuple of (mhl_file_path, xml_tree, hashes_element)
        
    Raises:
        OSError: If file creation fails
        ValueError: If input parameters are invalid
    """
    # Validate input parameters
    if not directory_name:
        logger.error("Invalid directory name (empty)")
        raise ValueError("Directory name cannot be empty")
        
    if not isinstance(target_dir, Path):
        logger.error(f"Target directory must be a Path object, got {type(target_dir)}")
        raise ValueError(f"Invalid target directory type: {type(target_dir)}")
    
    try:
        # Check target directory exists and is writable
        if not target_dir.exists():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created target directory: {target_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating directory {target_dir}: {e}")
                raise OSError(f"Cannot create target directory: {e}")
            except OSError as e:
                logger.error(f"OS error creating directory {target_dir}: {e}")
                raise OSError(f"Failed to create target directory: {e}")
        
        if not os.access(target_dir, os.W_OK):
            logger.error(f"No write permission for target directory: {target_dir}")
            raise OSError(f"Cannot write to target directory: {target_dir}")
            
        # Create MHL filename
        try:
            # Sanitize directory name for filename
            safe_name = "".join(c for c in directory_name if c.isalnum() or c in "-_.")
            if not safe_name:
                safe_name = "transfer"  # Fallback if sanitization removes everything
                
            mhl_filename = target_dir / f"{safe_name}.mhl"
        except Exception as e:
            logger.error(f"Error creating MHL filename: {e}")
            raise OSError(f"Failed to create MHL filename: {e}")
        
        # Create XML structure with error handling
        try:
            # Create root element
            root = ET.Element("hashlist", version="2.0", xmlns="urn:ASC:MHL:v2.0")
            
            # Add creator info
            creator_info = ET.SubElement(root, "creatorinfo")
            creation_date = ET.SubElement(creator_info, "creationdate")
            creation_date.text = datetime.now().isoformat()
            
            # Handle potential socket hostname errors
            try:
                hostname_text = socket.gethostname()
            except Exception as e:
                logger.warning(f"Failed to get hostname: {e}")
                hostname_text = "unknown-host"
                
            hostname = ET.SubElement(creator_info, "hostname")
            hostname.text = hostname_text
            
            tool = ET.SubElement(creator_info, __project_name__, version=__version__)
            tool.text = __project_name__
            
            # Add process info
            process_info = ET.SubElement(root, "processinfo")
            process = ET.SubElement(process_info, "process")
            process.text = "in-place"
            roothash = ET.SubElement(process_info, "roothash")
            content = ET.SubElement(roothash, "content")
            structure = ET.SubElement(roothash, "structure")
            
            # Add ignore patterns
            ignore = ET.SubElement(process_info, "ignore")
            for pattern in [".DS_Store", "ascmhl", "ascmhl/"]:
                ignore_pattern = ET.SubElement(ignore, "pattern")
                ignore_pattern.text = pattern
                
            # Add hashes element
            hashes = ET.SubElement(root, "hashes")
            
        except Exception as e:
            logger.error(f"Error creating XML structure: {e}")
            raise OSError(f"Failed to create MHL XML structure: {e}")
        
        # Write the XML tree to file
        try:
            tree = ET.ElementTree(root)
            tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
        except PermissionError as e:
            logger.error(f"Permission denied writing MHL file {mhl_filename}: {e}")
            raise OSError(f"Cannot write MHL file due to permissions: {e}")
        except IOError as e:
            logger.error(f"I/O error writing MHL file {mhl_filename}: {e}")
            raise OSError(f"Failed to write MHL file: {e}")
            
        logger.info(f"Initialized MHL file: {mhl_filename}")
        return mhl_filename, tree, hashes
        
    except OSError as e:
        # Re-raise OSError exceptions as they're already properly formatted
        raise
    except Exception as e:
        logger.error(f"Unexpected error initializing MHL file: {e}", exc_info=True)
        raise OSError(f"Failed to create MHL file: {e}")

def add_file_to_mhl(
    mhl_filename: Path,
    tree: ET.ElementTree,
    hashes: ET.Element,
    file_path: Path,
    checksum: str,
    file_size: int
) -> None:
    """
    Add a file entry to the MHL file.
    
    Args:
        mhl_filename: Path to the MHL file
        tree: XML ElementTree object
        hashes: XML Element for hashes
        file_path: Path to the file being added
        checksum: File's checksum
        file_size: File size in bytes
        
    Raises:
        OSError: If writing to MHL file fails
        ValueError: If input parameters are invalid
    """
    # Validate input parameters
    if not isinstance(mhl_filename, Path) or not mhl_filename.exists():
        logger.error(f"Invalid MHL file path: {mhl_filename}")
        raise ValueError(f"MHL file does not exist: {mhl_filename}")
        
    if tree is None or not isinstance(tree, ET.ElementTree):
        logger.error("Invalid ElementTree object")
        raise ValueError("XML tree is required")
        
    if hashes is None or not isinstance(hashes, ET.Element):
        logger.error("Invalid hashes XML element")
        raise ValueError("Hashes element is required")
        
    if not isinstance(file_path, Path) or not file_path.exists():
        logger.error(f"Invalid file path: {file_path}")
        raise ValueError(f"File does not exist: {file_path}")
        
    if not checksum:
        logger.error("Empty checksum provided")
        raise ValueError("Valid checksum is required")
        
    if file_size <= 0:
        logger.error(f"Invalid file size: {file_size}")
        raise ValueError(f"File size must be positive: {file_size}")
    
    try:
        # Create hash element
        hash_element = ET.SubElement(hashes, "hash")
        
        # Add path element with size attribute
        path = ET.SubElement(hash_element, "path", size=str(file_size))
        
        # Calculate relative path with error handling
        try:
            logger.debug(f"Calculating relative path for {file_path} relative to {mhl_filename.parent}")
            rel_path = Path(file_path).relative_to(mhl_filename.parent)
            path.text = str(rel_path)
            logger.debug(f"Relative path calculated: {rel_path}")
        except ValueError as e:
            logger.warning(f"Could not determine relative path for {file_path}: {e}")
            # Fall back to filename only if relative path fails
            path.text = file_path.name
            logger.debug(f"Using filename only as fallback: {file_path.name}")
            
        # Add last modification date with error handling
        try:
            last_modification_date = ET.SubElement(path, "lastmodificationdate")
            mtime = file_path.stat().st_mtime
            last_modification_date.text = datetime.fromtimestamp(mtime).isoformat()
        except (OSError, ValueError) as e:
            logger.warning(f"Error getting modification time for {file_path}: {e}")
            # Use current time as fallback
            last_modification_date.text = datetime.now().isoformat()
            
        # Add checksum
        xxh64 = ET.SubElement(hash_element, "xxh64", action="original")
        xxh64.text = checksum
        
        # Get current timestamp with error handling
        try:
            timestamp = datetime.now().isoformat()
        except Exception as e:
            logger.warning(f"Error creating timestamp: {e}")
            timestamp = "unknown"
            
        xxh64.set("hashdate", timestamp)
        
        # Write updated tree with error handling
        try:
            logger.debug(f"Writing updated MHL file to {mhl_filename}")
            tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
        except PermissionError as e:
            logger.error(f"Permission denied writing to MHL file {mhl_filename}: {e}")
            raise OSError(f"Cannot write to MHL file (permission denied): {e}")
        except IOError as e:
            logger.error(f"I/O error writing to MHL file {mhl_filename}: {e}")
            raise OSError(f"Failed to write to MHL file: {e}")
            
        logger.debug(f"Added file to MHL: {file_path}")
        
    except (ET.ParseError, TypeError) as e:
        logger.error(f"XML error adding file to MHL: {e}")
        raise OSError(f"Failed to update MHL file structure: {e}")
    except OSError as e:
        # Re-raise OSError exceptions directly
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding file to MHL: {e}", exc_info=True)
        raise OSError(f"Failed to update MHL file: {e}")