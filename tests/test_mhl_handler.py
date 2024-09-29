import os
import pytest
import xml.etree.ElementTree as ET
from unittest import mock
from datetime import datetime
from src.mhl_handler import initialize_mhl_file, add_file_to_mhl

@pytest.fixture
def mock_datetime_now(monkeypatch):
    """Fixture to mock datetime.now() in mhl_handler"""
    class MockDateTime(datetime):
        @classmethod
        def now(cls):
            return datetime(2024, 1, 1, 12, 0, 0)
    
    # Apply the patch to mhl_handler module where datetime is used
    monkeypatch.setattr('src.mhl_handler.datetime', MockDateTime)

@pytest.fixture
def mock_socket_gethostname(monkeypatch):
    """Fixture to mock socket.gethostname()"""
    monkeypatch.setattr('socket.gethostname', lambda: 'mock-hostname')

@pytest.fixture
def mock_os_path(monkeypatch):
    """Fixture to mock os.path.relpath and os.path.getmtime"""
    monkeypatch.setattr('os.path.relpath', lambda x: 'relative/path')
    monkeypatch.setattr('os.path.getmtime', lambda x: 1609459200)  # Fixed timestamp for 2021-01-01 00:00:00 UTC

def test_initialize_mhl_file(mock_datetime_now, mock_socket_gethostname):
    directory_name = "test_dir"
    target_dir = "/tmp"
    mhl_filename, tree, hashes = initialize_mhl_file(directory_name, target_dir)
    
    # Assert the MHL file name is correctly created
    assert mhl_filename == "/tmp/test_dir.mhl"
    
    # Parse the XML and assert the structure
    root = tree.getroot()
    assert root.tag == "hashlist"
    assert root.attrib["version"] == "2.0"
    
    # Assert creator info
    creator_info = root.find(".//creatorinfo")
    assert creator_info.find("creationdate").text == "2024-01-01T12:00:00"
    assert creator_info.find("hostname").text == "mock-hostname"

def test_add_file_to_mhl(mock_os_path):
    mhl_filename = "/tmp/test.mhl"
    tree = ET.ElementTree(ET.Element("hashlist"))
    hashes = tree.getroot().find("hashes")
    if hashes is None:
        hashes = ET.SubElement(tree.getroot(), "hashes")

    file_path = "/mock/path/to/file.txt"
    checksum = "1234567890abcdef"
    file_size = 1024
    
    add_file_to_mhl(mhl_filename, tree, hashes, file_path, checksum, file_size)
    
    # Assert the hash element is added correctly
    hash_element = hashes.find(".//hash")
    assert hash_element is not None
    assert hash_element.find("path").text == "relative/path"
    assert hash_element.find("xxh64").text == checksum
    assert hash_element.find("path").attrib["size"] == "1024"
    
    # Find the lastmodificationdate under the path
    path_element = hash_element.find("path")
    last_modification_date = path_element.find("lastmodificationdate")
    assert last_modification_date is not None
    
    # Assert using the correct UTC-based timestamp
    assert last_modification_date.text == "2020-12-31T19:00:00"  # UTC timestamp
