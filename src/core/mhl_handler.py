# src/core/mhl_handler.py

import logging
from pathlib import Path
from datetime import datetime
import socket
import xml.etree.ElementTree as ET
from typing import Tuple, Optional

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
    """
    try:
        mhl_filename = target_dir / f"{directory_name}.mhl"
        
        # Create root element
        root = ET.Element("hashlist", version="2.0", xmlns="urn:ASC:MHL:v2.0")
        
        # Add creator info
        creator_info = ET.SubElement(root, "creatorinfo")
        creation_date = ET.SubElement(creator_info, "creationdate")
        creation_date.text = datetime.now().isoformat()
        hostname = ET.SubElement(creator_info, "hostname")
        hostname.text = socket.gethostname()
        tool = ET.SubElement(creator_info, "TransferBox", version="0.1.0")
        tool.text = "TransferBox"
        
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
        
        # Create and write tree
        tree = ET.ElementTree(root)
        tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
        
        logger.info(f"Initialized MHL file: {mhl_filename}")
        return mhl_filename, tree, hashes
        
    except Exception as e:
        logger.error(f"Failed to initialize MHL file: {e}")
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
    """
    try:
        # Create hash element
        hash_element = ET.SubElement(hashes, "hash")
        
        # Add path element with size attribute
        path = ET.SubElement(hash_element, "path", size=str(file_size))
        path.text = str(Path(file_path).relative_to(mhl_filename.parent))
        
        # Add last modification date
        last_modification_date = ET.SubElement(path, "lastmodificationdate")
        last_modification_date.text = datetime.fromtimestamp(
            file_path.stat().st_mtime
        ).isoformat()
        
        # Add checksum
        xxh64 = ET.SubElement(hash_element, "xxh64", action="original")
        xxh64.text = checksum
        xxh64.set("hashdate", datetime.now().isoformat())
        
        # Write updated tree
        tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
        
        logger.debug(f"Added file to MHL: {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to add file to MHL: {e}")
        raise OSError(f"Failed to update MHL file: {e}")