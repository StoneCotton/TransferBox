import pytest
import tempfile
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from src.core import mhl_handler

# --- Fixtures ---
@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def temp_file(temp_dir):
    f = temp_dir / "testfile.txt"
    f.write_text("hello world")
    return f

# --- Tests for initialize_mhl_file ---
def test_initialize_mhl_file_success(temp_dir):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    assert mhl_path.exists()
    assert isinstance(tree, ET.ElementTree)
    assert isinstance(hashes, ET.Element)
    # Check root and hashes tag
    root = tree.getroot()
    assert root.tag.endswith("hashlist")
    assert root.find(".//hashes") is not None

def test_initialize_mhl_file_empty_dirname(temp_dir):
    with pytest.raises(ValueError):
        mhl_handler.initialize_mhl_file("", temp_dir)

def test_initialize_mhl_file_non_path_target():
    with pytest.raises(ValueError):
        mhl_handler.initialize_mhl_file("testdir", "not_a_path")

def test_initialize_mhl_file_unwritable(tmp_path):
    import sys
    if sys.platform.startswith("win"):  # Windows cannot reliably make a directory unwritable with chmod
        import pytest
        pytest.skip("Skipping unwritable directory test on Windows due to platform limitations.")
    unwritable = tmp_path / "unwritable"
    unwritable.mkdir()
    unwritable.chmod(0o400)  # Read-only
    try:
        with pytest.raises(OSError):
            mhl_handler.initialize_mhl_file("testdir", unwritable)
    finally:
        unwritable.chmod(0o700)  # Restore for cleanup

# --- Tests for add_file_to_mhl ---
def test_add_file_to_mhl_success(temp_dir, temp_file):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    checksum = "deadbeef"
    file_size = temp_file.stat().st_size
    mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, temp_file, checksum, file_size)
    # Reload and check XML
    tree2 = ET.parse(mhl_path)
    root = tree2.getroot()
    # Extract namespace
    ns = root.tag[root.tag.find("{")+1:root.tag.find("}")] if "{" in root.tag else ""
    nsmap = {"mhl": ns} if ns else {}
    hashes2 = root.find(".//{{{}}}hashes".format(ns) if ns else "hashes")
    assert hashes2 is not None, "<hashes> element not found in XML"
    hash_elems = list(hashes2)
    assert hash_elems, "No hash elements found"
    hash_elem = hash_elems[0]
    assert hash_elem.find("{{{}}}path".format(ns) if ns else "path") is not None
    assert hash_elem.find("{{{}}}xxh64".format(ns) if ns else "xxh64").text == checksum

def test_add_file_to_mhl_invalid_mhl_path(temp_dir, temp_file):
    mhl_path = temp_dir / "nonexistent.mhl"
    tree = ET.ElementTree(ET.Element("root"))
    hashes = ET.Element("hashes")
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, temp_file, "abc", 1)

def test_add_file_to_mhl_invalid_tree(temp_dir, temp_file):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, None, hashes, temp_file, "abc", 1)

def test_add_file_to_mhl_invalid_hashes(temp_dir, temp_file):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, None, temp_file, "abc", 1)

def test_add_file_to_mhl_nonexistent_file(temp_dir):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    fake_file = temp_dir / "nofile.txt"
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, fake_file, "abc", 1)

def test_add_file_to_mhl_empty_checksum(temp_dir, temp_file):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, temp_file, "", 1)

def test_add_file_to_mhl_nonpositive_size(temp_dir, temp_file):
    mhl_path, tree, hashes = mhl_handler.initialize_mhl_file("testdir", temp_dir)
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, temp_file, "abc", 0)
    with pytest.raises(ValueError):
        mhl_handler.add_file_to_mhl(mhl_path, tree, hashes, temp_file, "abc", -1) 