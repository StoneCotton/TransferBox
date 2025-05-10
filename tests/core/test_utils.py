import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.core import utils
from src.core.exceptions import FileTransferError

@pytest.fixture
def temp_dir():
    d = Path(tempfile.mkdtemp())
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def temp_file(temp_dir):
    f = temp_dir / "file.txt"
    f.write_text("hello world")
    return f

def make_unwritable_dir(parent: Path) -> Path:
    unwritable = parent / "unwritable"
    unwritable.mkdir()
    os.chmod(unwritable, 0o400)
    return unwritable

def restore_permissions(path: Path, mode=0o700):
    os.chmod(path, mode)

class TestEnsureDirectory:
    def test_create_and_return(self, temp_dir):
        new_dir = temp_dir / "subdir"
        result = utils.ensure_directory(new_dir)
        assert new_dir.exists() and new_dir.is_dir(), "Directory should be created"
        assert result == new_dir, "Returned path should match input"
        # Should not raise if already exists
        result2 = utils.ensure_directory(new_dir)
        assert result2 == new_dir, "Should return same path if already exists"

    def test_ensure_directory_failure(self, temp_dir, monkeypatch):
        # Simulate mkdir failure
        bad_path = temp_dir / "bad"
        monkeypatch.setattr(Path, "mkdir", MagicMock(side_effect=OSError("fail")))
        with pytest.raises(FileTransferError) as excinfo:
            utils.ensure_directory(bad_path)
        assert "Failed to create directory" in str(excinfo.value)

class TestSafeCopy:
    def test_safe_copy_success(self, temp_file, temp_dir):
        dest = temp_dir / "copy.txt"
        assert utils.safe_copy(temp_file, dest), "Copy should succeed"
        assert dest.exists(), "Destination file should exist"
        assert dest.read_text() == "hello world", "Content should match"

    def test_safe_copy_overwrite(self, temp_file, temp_dir):
        dest = temp_dir / "copy.txt"
        dest.write_text("old")
        assert utils.safe_copy(temp_file, dest), "Overwrite should succeed"
        assert dest.read_text() == "hello world", "Content should be updated"

    def test_safe_copy_error_cleanup(self, temp_file, temp_dir):
        if os.name != 'nt':
            unwritable = make_unwritable_dir(temp_dir)
            dest = unwritable / "fail.txt"
            try:
                with pytest.raises(FileTransferError) as excinfo:
                    utils.safe_copy(temp_file, dest)
                assert "Failed to copy" in str(excinfo.value)
                assert excinfo.value.source == temp_file
                assert excinfo.value.destination == dest
                assert not any(f.suffix == ".tmp" for f in unwritable.iterdir()), "Temp file should be cleaned up"
            finally:
                restore_permissions(unwritable)

    def test_safe_copy_source_missing(self, temp_dir):
        src = temp_dir / "nope.txt"
        dest = temp_dir / "dest.txt"
        with pytest.raises(FileTransferError) as excinfo:
            utils.safe_copy(src, dest)
        assert "Failed to copy" in str(excinfo.value)
        assert excinfo.value.source == src
        assert excinfo.value.destination == dest

class TestFormatSize:
    @pytest.mark.parametrize("size,expected", [
        (0, "0.00 B"),
        (512, "512.00 B"),
        (1024, "1.00 KB"),
        (1024*1024, "1.00 MB"),
        (1024*1024*1024, "1.00 GB"),
        (1024*1024*1024*2, "2.00 GB"),
        (1024*1024*1024*1024, "1.00 TB"),
        (1024*1024*1024*1024*5, "5.00 TB"),
    ])
    def test_format_size(self, size, expected):
        assert utils.format_size(size) == expected, f"Expected {expected} for {size}"

class TestIsMediaFile:
    @pytest.mark.parametrize("suffix,media_exts,expected", [
        (".mp4", ['.mp4', '.mov'], True),
        (".txt", ['.mp4', '.mov'], False),
        (".JPG", ['.jpg', '.jpeg'], True),
        (".doc", ['.jpg', '.jpeg'], False),
    ])
    def test_is_media_file(self, temp_file, suffix, media_exts, expected):
        f = temp_file.with_suffix(suffix)
        assert utils.is_media_file(f, media_exts) is expected

class TestGetPlatform:
    @pytest.mark.parametrize("system,model,expected", [
        ("Darwin", None, "darwin"),
        ("Windows", None, "windows"),
        ("Linux", FileNotFoundError(), "linux"),
        ("Linux", "Raspberry Pi stuff", "raspberry_pi"),
    ])
    def test_get_platform(self, system, model, expected):
        with patch('platform.system', return_value=system):
            if model is None:
                assert utils.get_platform() == expected
            elif isinstance(model, Exception):
                with patch('builtins.open', side_effect=model):
                    assert utils.get_platform() == expected
            else:
                with patch('builtins.open', create=True) as m:
                    m.return_value.__enter__.return_value.read.return_value = model
                    assert utils.get_platform() == expected

class TestValidatePath:
    def test_none_path(self):
        valid, err = utils.validate_path(None)
        assert not valid and "None" in err
    def test_nonexistent(self, temp_dir):
        p = temp_dir / "nope"
        valid, err = utils.validate_path(p)
        assert not valid and "does not exist" in err
    def test_must_be_dir(self, temp_file):
        valid, err = utils.validate_path(temp_file, must_be_dir=True)
        assert not valid and "not a directory" in err
    def test_must_be_writable(self, temp_file):
        valid, err = utils.validate_path(temp_file, must_be_writable=True)
        assert valid
    def test_parent_not_exist(self, temp_dir):
        p = temp_dir / "nope" / "file.txt"
        valid, err = utils.validate_path(p, must_be_writable=True)
        assert not valid and "Path does not exist" in err
    def test_parent_not_writable(self, temp_dir):
        if os.name != 'nt':
            unwritable = make_unwritable_dir(temp_dir)
            p = unwritable / "file.txt"
            try:
                valid, err = utils.validate_path(p, must_be_writable=True)
                assert not valid and ("Permission denied" in err or "No write permission" in err)
            finally:
                restore_permissions(unwritable)
    def test_string_path(self, temp_dir):
        d = temp_dir / "dir"
        d.mkdir()
        valid, err = utils.validate_path(str(d), must_exist=True, must_be_dir=True)
        assert valid

class TestGenerateUniquePath:
    def test_unique_path(self, temp_dir):
        p = temp_dir / "file.txt"
        assert utils.generate_unique_path(p) == p
        p.write_text("x")
        unique = utils.generate_unique_path(p)
        assert unique != p
        for _ in range(3):
            unique.write_text("x")
            unique = utils.generate_unique_path(p)
        assert unique.name.startswith("file_") and unique.suffix == ".txt"
    def test_unique_path_multiple_dots(self, temp_dir):
        p = temp_dir / "file.name.txt"
        p.write_text("x")
        unique = utils.generate_unique_path(p)
        assert unique.name.startswith("file.name_") and unique.suffix == ".txt"

class TestGetFileSize:
    def test_file_size(self, temp_file):
        assert utils.get_file_size(temp_file) == len("hello world")
    def test_file_size_nonexistent(self, temp_dir):
        with pytest.raises(FileTransferError) as excinfo:
            utils.get_file_size(temp_dir / "nope.txt")
        assert "Error getting file size" in str(excinfo.value)

class TestGetDirectorySize:
    def test_directory_size(self, temp_dir):
        f1 = temp_dir / "a.txt"
        f2 = temp_dir / "b.txt"
        f1.write_text("abc")
        f2.write_text("defg")
        assert utils.get_directory_size(temp_dir) == 3 + 4
    def test_directory_size_empty(self, temp_dir):
        assert utils.get_directory_size(temp_dir) == 0
    def test_directory_size_nonexistent(self, temp_dir):
        with pytest.raises(FileTransferError) as excinfo:
            utils.get_directory_size(temp_dir / "nope")
        assert "Directory does not exist" in str(excinfo.value) 