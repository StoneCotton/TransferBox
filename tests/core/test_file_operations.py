import pytest
from pathlib import Path
from unittest import mock
from src.core.file_operations import FileOperations, TEMP_FILE_EXTENSION
from src.core.exceptions import FileTransferError, ChecksumError
import sys

class DummyDisplay:
    def __init__(self):
        self.errors = []
    def show_error(self, msg):
        self.errors.append(msg)

class DummySoundManager:
    def __init__(self):
        self.played_error = False
    def play_error(self):
        self.played_error = True

class DummyStorage:
    def __init__(self):
        self.metadata = {}
    def set_file_metadata(self, path, metadata):
        self.metadata[path] = metadata
        return True
    def get_file_metadata(self, path):
        return self.metadata.get(path, None)

@pytest.fixture
def tmp_file(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("data")
    return file

@pytest.fixture
def dummy_display():
    return DummyDisplay()

@pytest.fixture
def dummy_sound():
    return DummySoundManager()

@pytest.fixture
def dummy_storage():
    return DummyStorage()

# --- copy_file_with_hash ---
def test_copy_file_with_hash(tmp_file, tmp_path, dummy_display, dummy_sound):
    dst = tmp_path / "out.txt"
    # Dummy hash object
    class DummyHash:
        def __init__(self): self._data = b""
        def update(self, chunk): self._data += chunk
        def hexdigest(self): return "hash123"
    hash_obj = DummyHash()
    ops = FileOperations(display=dummy_display, sound_manager=dummy_sound)
    success, checksum = ops.copy_file_with_hash(tmp_file, dst, hash_obj)
    assert success is True
    assert checksum == "hash123"
    assert dst.exists()
    assert dst.read_text() == "data"

# --- verify_checksum ---
def test_verify_checksum_success(tmp_file, dummy_display, monkeypatch):
    ops = FileOperations(display=dummy_display)
    # Patch ChecksumCalculator
    class FakeCalculator:
        def __init__(self, display): pass
        def verify_checksum(self, file_path, expected, progress_callback=None):
            return expected == "ok"
    fake_checksum_mod = type(sys)("fake_checksum_mod")
    fake_checksum_mod.ChecksumCalculator = FakeCalculator
    monkeypatch.setitem(sys.modules, "src.core.checksum", fake_checksum_mod)
    assert ops.verify_checksum(tmp_file, "ok") is True
    assert ops.verify_checksum(tmp_file, "bad") is False

# --- verify_checksum: ChecksumError ---
def test_verify_checksum_checksumerror(tmp_file, dummy_display, monkeypatch):
    ops = FileOperations(display=dummy_display)
    class FakeCalculator:
        def __init__(self, display): pass
        def verify_checksum(self, file_path, expected, progress_callback=None):
            raise ChecksumError("fail")
    fake_checksum_mod = type(sys)("fake_checksum_mod")
    fake_checksum_mod.ChecksumCalculator = FakeCalculator
    monkeypatch.setitem(sys.modules, "src.core.checksum", fake_checksum_mod)
    assert ops.verify_checksum(tmp_file, "fail") is False

# --- apply_metadata ---
def test_apply_metadata_success(tmp_file, dummy_storage):
    ops = FileOperations(storage=dummy_storage)
    assert ops.apply_metadata(tmp_file, {"foo": "bar"}) is True
    assert dummy_storage.metadata[tmp_file] == {"foo": "bar"}

def test_apply_metadata_no_storage(tmp_file):
    ops = FileOperations()
    assert ops.apply_metadata(tmp_file, {"foo": "bar"}) is False

def test_apply_metadata_no_metadata(tmp_file, dummy_storage):
    ops = FileOperations(storage=dummy_storage)
    assert ops.apply_metadata(tmp_file, None) is False

# --- get_metadata ---
def test_get_metadata_success(tmp_file, dummy_storage):
    dummy_storage.metadata[tmp_file] = {"foo": "bar"}
    ops = FileOperations(storage=dummy_storage)
    assert ops.get_metadata(tmp_file) == {"foo": "bar"}

def test_get_metadata_no_storage(tmp_file):
    ops = FileOperations()
    assert ops.get_metadata(tmp_file) is None

# --- ensure_directory_exists ---
def test_ensure_directory_exists(tmp_path):
    ops = FileOperations()
    new_dir = tmp_path / "newdir"
    assert ops.ensure_directory_exists(new_dir) is True
    assert new_dir.exists()

def test_ensure_directory_exists_error(monkeypatch):
    ops = FileOperations()
    with mock.patch.object(Path, "mkdir", side_effect=OSError("fail")):
        with pytest.raises(FileTransferError):
            ops.ensure_directory_exists(Path("/forbidden"))

# --- cleanup_temp_files ---
def test_cleanup_temp_files(tmp_path):
    ops = FileOperations()
    # Create temp files
    f1 = tmp_path / ("a" + TEMP_FILE_EXTENSION)
    f2 = tmp_path / ("b" + TEMP_FILE_EXTENSION)
    f1.write_text("1")
    f2.write_text("2")
    count = ops.cleanup_temp_files(tmp_path)
    assert count == 2
    assert not f1.exists() and not f2.exists()

def test_cleanup_temp_files_error(monkeypatch, tmp_path):
    ops = FileOperations()
    with mock.patch.object(Path, "glob", side_effect=Exception("fail")):
        with pytest.raises(FileTransferError):
            ops.cleanup_temp_files(tmp_path)

# --- copy_file ---
def test_copy_file_success(tmp_file, tmp_path):
    dst = tmp_path / "out.txt"
    ops = FileOperations()
    assert ops.copy_file(tmp_file, dst) is True
    assert dst.exists() and dst.read_text() == "data"

def test_copy_file_source_missing(tmp_path):
    ops = FileOperations()
    src = tmp_path / "nope.txt"
    dst = tmp_path / "out.txt"
    with pytest.raises(FileTransferError):
        ops.copy_file(src, dst)

def test_copy_file_ioerror(tmp_file, tmp_path, monkeypatch):
    ops = FileOperations()
    dst = tmp_path / "out.txt"
    # Patch open to raise OSError
    with mock.patch("builtins.open", side_effect=OSError("fail")):
        assert ops.copy_file(tmp_file, dst) is None 