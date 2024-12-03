# tests/core/test_mhl_handler.py

import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import socket
from src.core.mhl_handler import initialize_mhl_file, add_file_to_mhl

# Register the namespace for proper handling
NS = "urn:ASC:MHL:v2.0"
ET.register_namespace('', NS)  # Register default namespace

@pytest.fixture
def temp_mhl_dir(tmp_path):
    """Create a temporary directory for MHL files"""
    mhl_dir = tmp_path / "mhl_test"
    mhl_dir.mkdir()
    return mhl_dir

@pytest.fixture
def initialized_mhl(temp_mhl_dir):
    """Create and return an initialized MHL file with its components"""
    directory_name = "test_transfer"
    mhl_path, tree, hashes = initialize_mhl_file(directory_name, temp_mhl_dir)
    return mhl_path, tree, hashes

def validate_mhl_structure(root):
    """Helper function to validate basic MHL XML structure"""
    # Check root element and its namespace
    assert root.tag == "hashlist"  # Changed from namespaced version
    assert root.attrib.get("version") == "2.0"
    assert root.attrib.get("xmlns") == NS
    
    # Check required sections exist
    sections = ["creatorinfo", "processinfo", "hashes"]
    for section in sections:
        assert root.find(section) is not None, f"Missing section: {section}"
    
    # Validate creatorinfo
    creator_info = root.find("creatorinfo")
    assert creator_info.find("creationdate") is not None
    assert creator_info.find("hostname") is not None
    assert creator_info.find("hostname").text == socket.gethostname()
    
    # Validate processinfo
    process_info = root.find("processinfo")
    assert process_info.find("process").text == "in-place"
    assert process_info.find("roothash/content") is not None
    assert process_info.find("roothash/structure") is not None
    
    # Check ignore patterns
    ignore = process_info.find("ignore")
    assert ignore is not None
    patterns = [p.text for p in ignore.findall("pattern")]
    assert ".DS_Store" in patterns
    assert "ascmhl" in patterns

def test_initialize_mhl_file(temp_mhl_dir):
    """Test MHL file initialization"""
    directory_name = "test_transfer"
    mhl_path, tree, hashes = initialize_mhl_file(directory_name, temp_mhl_dir)
    
    # Check file creation
    assert mhl_path.exists()
    assert mhl_path.name == f"{directory_name}.mhl"
    
    # Validate XML structure
    root = tree.getroot()
    validate_mhl_structure(root)
    
    # Verify hashes element is empty initially
    assert len(hashes.findall("hash")) == 0

def test_add_file_to_mhl(initialized_mhl, temp_mhl_dir):
    """Test adding a file entry to MHL"""
    mhl_path, tree, hashes = initialized_mhl
    
    # Create a test file
    test_file = temp_mhl_dir / "test_file.txt"
    test_file.write_text("Test content")
    file_stat = test_file.stat()
    
    # Add file to MHL
    test_checksum = "0123456789abcdef"
    add_file_to_mhl(mhl_path, tree, hashes, test_file, test_checksum, file_stat.st_size)
    
    # Verify file entry
    hash_elements = hashes.findall("hash")
    assert len(hash_elements) == 1
    
    hash_element = hash_elements[0]
    path_element = hash_element.find("path")
    assert path_element is not None
    assert path_element.attrib["size"] == str(file_stat.st_size)
    assert path_element.text == str(test_file.relative_to(mhl_path.parent))
    
    # Verify checksum
    xxh64_element = hash_element.find("xxh64")
    assert xxh64_element is not None
    assert xxh64_element.text == test_checksum
    assert xxh64_element.attrib["action"] == "original"
    assert "hashdate" in xxh64_element.attrib

def test_add_multiple_files(initialized_mhl, temp_mhl_dir):
    """Test adding multiple files to MHL"""
    mhl_path, tree, hashes = initialized_mhl
    
    # Create test files
    files = []
    for i in range(3):
        test_file = temp_mhl_dir / f"test_file_{i}.txt"
        test_file.write_text(f"Test content {i}")
        files.append(test_file)
    
    # Add files to MHL
    for i, file in enumerate(files):
        add_file_to_mhl(
            mhl_path, tree, hashes,
            file, f"checksum_{i}",
            file.stat().st_size
        )
    
    # Verify all files were added
    hash_elements = hashes.findall("hash")
    assert len(hash_elements) == len(files)
    
    # Verify each file entry
    for i, hash_element in enumerate(hash_elements):
        xxh64_element = hash_element.find("xxh64")
        assert xxh64_element.text == f"checksum_{i}"

def test_file_paths_in_mhl(initialized_mhl, temp_mhl_dir):
    """Test handling of different file paths in MHL"""
    mhl_path, tree, hashes = initialized_mhl
    
    # Create nested directory structure
    nested_dir = temp_mhl_dir / "subdir" / "deeper"
    nested_dir.mkdir(parents=True)
    
    # Create test files at different paths
    test_files = [
        temp_mhl_dir / "root_file.txt",
        temp_mhl_dir / "subdir" / "sub_file.txt",
        nested_dir / "deep_file.txt"
    ]
    
    for file in test_files:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("Test content")
        add_file_to_mhl(
            mhl_path, tree, hashes,
            file, "test_checksum",
            file.stat().st_size
        )
    
    # Verify paths are stored correctly
    hash_elements = hashes.findall("hash")
    stored_paths = [
        h.find("path").text for h in hash_elements
    ]
    
    # Check that paths are relative to MHL file location
    for file, stored_path in zip(test_files, stored_paths):
        expected_path = str(file.relative_to(mhl_path.parent))
        assert stored_path == expected_path

def test_error_handling(temp_mhl_dir):
    """Test error handling in MHL operations"""
    # Test with non-existent directory
    bad_dir = temp_mhl_dir / "nonexistent"
    with pytest.raises(OSError):
        initialize_mhl_file("test", bad_dir)
    
    # Test with invalid file paths
    mhl_path, tree, hashes = initialize_mhl_file("test", temp_mhl_dir)
    with pytest.raises(OSError):
        add_file_to_mhl(
            mhl_path, tree, hashes,
            Path("nonexistent.txt"),
            "checksum", 100
        )

def test_timestamp_format(initialized_mhl):
    """Test timestamp formatting in MHL file"""
    mhl_path, tree, hashes = initialized_mhl
    root = tree.getroot()
    
    # Check creation date format
    creation_date = root.find(".//creationdate").text
    try:
        datetime.fromisoformat(creation_date)
    except ValueError as e:
        pytest.fail(f"Invalid creation date format: {e}")

@pytest.mark.parametrize("directory_name", [
    "simple_name",
    "name with spaces",
    "name_with_special_chars_@#$",
    "深いディレクトリ",  # Test Unicode support
    "very_long_name_" * 10
])
def test_directory_name_handling(temp_mhl_dir, directory_name):
    """Test handling of various directory names"""
    try:
        mhl_path, tree, hashes = initialize_mhl_file(directory_name, temp_mhl_dir)
        assert mhl_path.exists()
        assert mhl_path.name == f"{directory_name}.mhl"
    except Exception as e:
        pytest.fail(f"Failed to handle directory name '{directory_name}': {e}")