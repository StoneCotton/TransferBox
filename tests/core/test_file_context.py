import pytest
from pathlib import Path
from unittest import mock
from src.core.file_context import FileOperationContext, file_operation, error_handler
from src.core.exceptions import FileTransferError
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

# --- FileOperationContext ---
def test_file_operation_context_enter_exit_no_error(dummy_display, dummy_sound):
    with FileOperationContext(display=dummy_display, sound_manager=dummy_sound) as ctx:
        assert ctx.display is dummy_display
        assert ctx.sound_manager is dummy_sound
        assert ctx.temp_files == []
    # No error, so sound should not play
    assert not dummy_sound.played_error


def test_file_operation_context_exit_with_error(tmp_file, dummy_display, dummy_sound):
    ctx = FileOperationContext(display=dummy_display, sound_manager=dummy_sound)
    ctx.register_temp_file(tmp_file)
    # Simulate error in context
    class DummyError(Exception): pass
    with mock.patch.object(ctx, '_handle_exception') as handle_exc, \
         mock.patch.object(ctx, '_clean_up_temp_files') as clean_temp:
        ctx.__exit__(DummyError, DummyError("fail"), None)
        handle_exc.assert_called()
        clean_temp.assert_called()
    # Should play error sound
    ctx.sound_manager.played_error = False
    with FileOperationContext(display=dummy_display, sound_manager=dummy_sound) as ctx2:
        ctx2.register_temp_file(tmp_file)
        raise FileTransferError("fail")
    # Should play error sound
    assert dummy_sound.played_error


def test_file_operation_context_temp_file_cleanup(tmp_path):
    file = tmp_path / "tempfile.txt"
    file.write_text("temp")
    ctx = FileOperationContext()
    ctx.register_temp_file(file)
    assert file.exists()
    ctx._clean_up_temp_files()
    assert not file.exists()


def test_file_operation_context_validate_source(tmp_file):
    ctx = FileOperationContext()
    assert ctx.validate_source(tmp_file)
    # Not exists
    with pytest.raises(FileTransferError):
        ctx.validate_source(tmp_file.parent / "nope.txt")
    # Not a file
    with pytest.raises(FileTransferError):
        ctx.validate_source(tmp_file.parent)


def test_file_operation_context_prepare_copy(tmp_file, monkeypatch):
    ctx = FileOperationContext()
    # Patch ChecksumCalculator import via sys.modules
    fake_hash = object()
    class FakeCalculator:
        def __init__(self, display): pass
        def create_hash(self): return fake_hash
    fake_checksum_mod = type(sys)("fake_checksum_mod")
    fake_checksum_mod.ChecksumCalculator = FakeCalculator
    monkeypatch.setitem(sys.modules, "src.core.checksum", fake_checksum_mod)
    size, hash_obj = ctx.prepare_copy(tmp_file)
    assert size == tmp_file.stat().st_size
    assert hash_obj is fake_hash
    # OSError
    with pytest.raises(FileTransferError):
        ctx.prepare_copy(tmp_file.parent / "nope.txt")

# --- file_operation context manager ---
def test_file_operation_success(dummy_display, dummy_sound):
    with file_operation(display=dummy_display, sound_manager=dummy_sound, operation_name="TestOp"):
        pass
    assert not dummy_sound.played_error

def test_file_operation_filetransfererror(dummy_display, dummy_sound):
    with pytest.raises(FileTransferError):
        with file_operation(display=dummy_display, sound_manager=dummy_sound, operation_name="TestOp"):
            raise FileTransferError("fail")
    assert dummy_sound.played_error

def test_file_operation_other_exception(dummy_display, dummy_sound):
    with pytest.raises(FileTransferError):
        with file_operation(display=dummy_display, sound_manager=dummy_sound, operation_name="TestOp"):
            raise ValueError("fail")
    assert dummy_sound.played_error

# --- error_handler decorator ---
def test_error_handler_success():
    @error_handler
    def ok():
        return 42
    assert ok() == 42

def test_error_handler_filetransfererror():
    @error_handler
    def fail():
        raise FileTransferError("fail")
    with pytest.raises(FileTransferError):
        fail()

def test_error_handler_oserror():
    @error_handler
    def fail():
        raise OSError("fail")
    exc = None
    with pytest.raises(FileTransferError) as excinfo:
        fail()
    exc = excinfo.value
    assert "I/O error" in str(exc)

def test_error_handler_other():
    @error_handler
    def fail():
        raise RuntimeError("fail")
    exc = None
    with pytest.raises(FileTransferError) as excinfo:
        fail()
    exc = excinfo.value
    assert "Unexpected error" in str(exc) 