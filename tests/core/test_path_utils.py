import pytest
import platform
from pathlib import Path
from src.core import path_utils
from src.core.exceptions import StorageError, FileTransferError

class DummyStorage:
    pass

# --- sanitize_path ---
def test_sanitize_path_basic_absolute(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    p = path_utils.sanitize_path("/tmp/testfile.txt")
    assert isinstance(p, Path)
    assert p.is_absolute()
    assert str(p).endswith("testfile.txt")

def test_sanitize_path_url_encoded(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    p = path_utils.sanitize_path("/tmp/te%73tfile.txt")
    assert "testfile.txt" in str(p)

def test_sanitize_path_quoted(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    p = path_utils.sanitize_path("'/tmp/testfile.txt'")
    assert str(p).endswith("testfile.txt")

def test_sanitize_path_invalid(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(FileTransferError):
        path_utils.sanitize_path(None)  # type: ignore

# --- get_safe_path ---
def test_get_safe_path_str(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    p = path_utils.get_safe_path("/tmp/testfile.txt")
    assert isinstance(p, Path)
    assert p.is_absolute()

def test_get_safe_path_path(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    p = path_utils.get_safe_path(Path("/tmp/testfile.txt"))
    assert isinstance(p, Path)
    assert p.is_absolute()

def test_get_safe_path_invalid(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(FileTransferError):
        path_utils.get_safe_path(None)  # type: ignore

# --- validate_destination_path ---
def test_validate_destination_path_linux_success(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    # Patch os.access to always return True
    monkeypatch.setattr(path_utils.os, "access", lambda p, m: True)
    p = path_utils.validate_destination_path(Path("/tmp/testfile.txt"), DummyStorage())
    assert isinstance(p, Path)

def test_validate_destination_path_linux_permission_error(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(path_utils.os, "access", lambda p, m: False)
    with pytest.raises(StorageError):
        path_utils.validate_destination_path(Path("/tmp/testfile.txt"), DummyStorage())

def test_validate_destination_path_unsupported(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Plan9")
    with pytest.raises(StorageError):
        path_utils.validate_destination_path(Path("/tmp/testfile.txt"), DummyStorage())

# --- Platform-specific: macOS and Windows (mocked) ---
def test_validate_destination_path_macos_success(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(path_utils.os, "access", lambda p, m: True)
    p = path_utils.validate_destination_path(Path("/Users/testuser/testfile.txt"), DummyStorage())
    assert isinstance(p, Path)

def test_validate_destination_path_windows_success(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(path_utils.os, "access", lambda p, m: True)
    # Patch Path.drive to return 'C:' for test
    class FakePath(Path):
        _flavour = type(Path())._flavour
        @property
        def drive(self):
            return "C:"
    p = path_utils.validate_destination_path(FakePath("C:/testfile.txt"), DummyStorage())
    assert isinstance(p, Path)

def test_validate_destination_path_windows_no_drive(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(path_utils.os, "access", lambda p, m: True)
    class FakePath(Path):
        _flavour = type(Path())._flavour
        @property
        def drive(self):
            return ""
    with pytest.raises(StorageError):
        path_utils.validate_destination_path(FakePath("testfile.txt"), DummyStorage()) 