import pytest
import time
from unittest.mock import Mock
from src.core.progress_tracker import ProgressTracker
from src.core.interfaces.types import TransferStatus, TransferProgress
from pathlib import Path

@pytest.fixture
def mock_display():
    display = Mock()
    display.show_progress = Mock()
    return display

@pytest.fixture
def tracker(mock_display):
    return ProgressTracker(display=mock_display)

def test_init_state():
    pt = ProgressTracker()
    assert pt.status == TransferStatus.READY
    assert pt.total_files == 0
    assert pt.total_size == 0
    assert pt.overall_progress == 0.0

def test_start_transfer(tracker, mock_display):
    tracker.start_transfer(total_files=5, total_size=1000)
    assert tracker.total_files == 5
    assert tracker.total_size == 1000
    assert tracker.file_number == 0
    assert tracker.overall_progress == 0.0
    mock_display.show_progress.assert_called()

def test_start_file(tracker, mock_display):
    tracker.start_file(file_path=Path("file1.txt"), file_number=2, total_files=5, file_size=200, total_size=1000, total_transferred=100)
    assert tracker.current_file == "file1.txt"
    assert tracker.file_number == 2
    assert tracker.total_files == 5
    assert tracker.bytes_transferred == 0
    assert tracker.total_bytes == 200
    assert tracker.total_transferred == 100
    assert tracker.status == TransferStatus.COPYING
    mock_display.show_progress.assert_called()

def test_update_progress_bytes(tracker, mock_display, monkeypatch):
    tracker.start_transfer(2, 100)
    tracker.start_file(file_path=Path("file1.txt"), file_number=1, total_files=2, file_size=50, total_size=100, total_transferred=0)
    monkeypatch.setattr(time, "time", lambda: tracker.last_update_time + 1)
    tracker.update_progress(bytes_transferred=25)
    assert tracker.bytes_transferred == 25
    assert 0 < tracker.current_file_progress < 1
    assert tracker.overall_progress > 0
    mock_display.show_progress.assert_called()

def test_update_progress_files_processed(tracker, mock_display):
    tracker.start_transfer(2, 100)
    tracker.update_progress(files_processed=1)
    assert tracker.file_number == 1
    mock_display.show_progress.assert_called()

def test_set_status(tracker, mock_display):
    tracker.set_status(TransferStatus.ERROR)
    assert tracker.status == TransferStatus.ERROR
    mock_display.show_progress.assert_called()

def test_complete_file_success(tracker, mock_display):
    tracker.start_transfer(2, 100)
    tracker.start_file(file_path=Path("file1.txt"), file_number=1, total_files=2, file_size=50, total_size=100, total_transferred=0)
    tracker.complete_file(success=True)
    assert tracker.status == TransferStatus.SUCCESS
    assert tracker.current_file_progress == 1.0
    assert tracker.overall_progress > 0
    mock_display.show_progress.assert_called()

def test_complete_file_error(tracker, mock_display):
    tracker.start_transfer(2, 100)
    tracker.start_file(file_path=Path("file1.txt"), file_number=1, total_files=2, file_size=50, total_size=100, total_transferred=0)
    tracker.complete_file(success=False)
    assert tracker.status == TransferStatus.ERROR
    assert tracker.current_file_progress == 1.0
    mock_display.show_progress.assert_called()

def test_complete_transfer_success(tracker, mock_display):
    tracker.start_transfer(2, 100)
    tracker.complete_transfer(successful=True)
    assert tracker.status == TransferStatus.SUCCESS
    assert tracker.overall_progress == 1.0
    mock_display.show_progress.assert_called()

def test_complete_transfer_error(tracker, mock_display):
    tracker.start_transfer(2, 100)
    tracker.complete_transfer(successful=False)
    assert tracker.status == TransferStatus.ERROR
    assert tracker.overall_progress == 1.0
    mock_display.show_progress.assert_called()

def test_create_progress_callback(tracker):
    tracker.start_transfer(1, 10)
    tracker.start_file(file_path=Path("file1.txt"), file_number=1, total_files=1, file_size=10, total_size=10, total_transferred=0)
    cb = tracker.create_progress_callback()
    cb(5, 10)
    assert tracker.bytes_transferred == 5
    cb(10, 10)
    assert tracker.bytes_transferred == 10 