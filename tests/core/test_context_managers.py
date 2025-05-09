import pytest
from pathlib import Path
from src.core.context_managers import operation_context, TransferContext, file_transfer, safe_file_operation

def test_operation_context_happy_path(mocker):
    display = mocker.Mock()
    sound_manager = mocker.Mock()
    with operation_context(display=display, sound_manager=sound_manager, operation_name="TestOp"):
        pass
    display.show_status.assert_any_call("Starting: TestOp")
    display.show_status.assert_any_call("Completed: TestOp")
    sound_manager.play_error.assert_not_called()

def test_operation_context_error(mocker):
    display = mocker.Mock()
    sound_manager = mocker.Mock()
    on_error = mocker.Mock()
    with pytest.raises(ValueError):
        with operation_context(display=display, sound_manager=sound_manager, operation_name="TestOp", on_error=on_error):
            raise ValueError("fail")
    display.show_error.assert_called_once()
    sound_manager.play_error.assert_called_once()
    on_error.assert_called_once()

def test_transfer_context_happy_path(mocker):
    display = mocker.Mock()
    sound_manager = mocker.Mock()
    with TransferContext(display=display, sound_manager=sound_manager, operation_name="TransferTest"):
        pass
    display.show_status.assert_any_call("Starting: TransferTest")
    display.show_status.assert_any_call("Completed: TransferTest")
    sound_manager.play_error.assert_not_called()

def test_transfer_context_error_and_temp_cleanup(tmp_path, mocker):
    display = mocker.Mock()
    sound_manager = mocker.Mock()
    temp_file = tmp_path / "tempfile.txt"
    temp_file.write_text("temp")
    ctx = TransferContext(display=display, sound_manager=sound_manager, operation_name="TransferTest")
    ctx.register_temp_file(temp_file)
    with pytest.raises(RuntimeError):
        with ctx:
            raise RuntimeError("fail")
    assert not temp_file.exists()
    display.show_error.assert_called_once()
    sound_manager.play_error.assert_called_once()

def test_file_transfer_happy_path(mocker):
    display = mocker.Mock()
    sound_manager = mocker.Mock()
    with file_transfer(display=display, sound_manager=sound_manager, operation_name="FileXfer") as ctx:
        assert isinstance(ctx, TransferContext)
    display.show_status.assert_any_call("Starting: FileXfer")
    display.show_status.assert_any_call("Completed: FileXfer")

def test_safe_file_operation_success(tmp_path):
    file_path = tmp_path / "atomic.txt"
    with safe_file_operation(file_path, mode="w") as f:
        f.write("atomic write")
    assert file_path.exists()
    assert file_path.read_text() == "atomic write"

def test_safe_file_operation_error_cleanup(tmp_path):
    file_path = tmp_path / "atomic.txt"
    try:
        with safe_file_operation(file_path, mode="w") as f:
            f.write("fail")
            raise RuntimeError("fail")
    except RuntimeError:
        pass
    # Temp file should be cleaned up
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    assert not temp_path.exists()
    assert not file_path.exists() 