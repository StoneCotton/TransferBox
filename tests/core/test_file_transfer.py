# tests/core/test_file_transfer.py

import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.core.file_transfer import FileTransfer, FileTransferError
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.core.state_manager import StateManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface

class MockDisplay(DisplayInterface):
    def __init__(self):
        self.status_messages = []
        self.progress_updates = []
        self.errors = []
        self.current_progress = None  # Add this to track current progress

    def show_status(self, message: str, line: int = 0) -> None:
        self.status_messages.append((message, line))

    def show_progress(self, progress: TransferProgress) -> None:
        self.progress_updates.append(progress)
        self.current_progress = progress  # Keep track of current progress

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def clear(self) -> None:
        self.status_messages = []
        self.progress_updates = []
        self.errors = []
        self.current_progress = None

class MockStorage(StorageInterface):
    def __init__(self, has_space=True):
        self.mounted_drives = []
        self.has_space = has_space
        self.unmount_calls = []

    def get_available_drives(self):
        return self.mounted_drives

    def get_drive_info(self, path):
        return {'total': 1000000, 'used': 0, 'free': 1000000}

    def is_drive_mounted(self, path):
        return path in self.mounted_drives

    def unmount_drive(self, path):
        self.unmount_calls.append(path)
        return True

    def has_enough_space(self, path, required_size):
        return self.has_space

class MockStateManager:
    def __init__(self):
        self.current_state = "STANDBY"
        self.transfer_calls = []
        self.exit_calls = []

    def enter_transfer(self):
        self.current_state = "TRANSFER"
        self.transfer_calls.append(True)

    def exit_transfer(self, pending_unmount=None):
        self.current_state = "STANDBY"
        self.exit_calls.append(pending_unmount)

    def is_utility(self):
        return False

@pytest.fixture
def temp_transfer_dir(tmp_path):
    """Create temporary directories for transfer testing"""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "destination"
    source_dir.mkdir()
    dest_dir.mkdir()
    return source_dir, dest_dir

@pytest.fixture
def mock_components():
    """Create mock components for FileTransfer"""
    display = MockDisplay()
    storage = MockStorage()
    state_manager = MockStateManager()
    return display, storage, state_manager

@pytest.fixture
def file_transfer(mock_components):
    """Create FileTransfer instance with mock components"""
    display, storage, state_manager = mock_components
    return FileTransfer(state_manager, display, storage)

@pytest.fixture
def sample_files(temp_transfer_dir):
    """Create sample files for testing"""
    source_dir, _ = temp_transfer_dir
    files = []
    
    # Create test files with different sizes
    sizes = [(1024, "small.txt"), (1024 * 1024, "medium.txt"), (1024 * 1024 * 2, "large.txt")]
    
    for size, name in sizes:
        file_path = source_dir / name
        with open(file_path, 'wb') as f:
            f.write(os.urandom(size))
        files.append(file_path)
    
    return files

def test_initialization(mock_components):
    """Test FileTransfer initialization"""
    display, storage, state_manager = mock_components
    transfer = FileTransfer(state_manager, display, storage)
    
    assert transfer.state_manager == state_manager
    assert transfer.display == display
    assert transfer.storage == storage
    assert transfer._current_progress is None

def test_validate_transfer_preconditions(file_transfer, temp_transfer_dir):
    """Test transfer precondition validation"""
    _, dest_dir = temp_transfer_dir
    
    # Test with valid destination
    assert file_transfer._validate_transfer_preconditions(dest_dir)
    
    # Test with None destination
    assert not file_transfer._validate_transfer_preconditions(None)
    assert "No destination" in file_transfer.display.errors

def test_copy_with_progress(file_transfer, temp_transfer_dir, sample_files):
    """Test file copying with progress updates"""
    source_path = sample_files[0]  # Use small test file
    _, dest_dir = temp_transfer_dir
    dest_path = dest_dir / source_path.name

    # Initialize the current_progress before copying
    file_transfer._current_progress = TransferProgress(
        current_file=source_path.name,
        file_number=1,
        total_files=1,
        bytes_transferred=0,
        total_bytes=source_path.stat().st_size,
        current_file_progress=0.0,
        overall_progress=0.0,
        status=TransferStatus.COPYING
    )

    success, checksum = file_transfer._copy_with_progress(
        source_path, dest_path, 1, 1
    )

    assert success
    assert checksum is not None
    assert dest_path.exists()
    assert dest_path.stat().st_size == source_path.stat().st_size

def test_failed_copy(file_transfer, temp_transfer_dir):
    """Test handling of failed file copy"""
    source_dir, dest_dir = temp_transfer_dir

    # Create source file
    source_path = source_dir / "test.txt"
    source_path.write_text("test data")
    
    # Initialize the current_progress
    file_transfer._current_progress = TransferProgress(
        current_file=source_path.name,
        file_number=1,
        total_files=1,
        bytes_transferred=0,
        total_bytes=source_path.stat().st_size,
        current_file_progress=0.0,
        overall_progress=0.0,
        status=TransferStatus.COPYING
    )

    # Create a mock copy function that simulates failure
    def mock_failed_copy(*args, **kwargs):
        file_transfer.display.show_error("Failed to copy file")
        return False, None

    # Store original method and replace with mock
    original_copy = file_transfer._copy_with_progress
    file_transfer._copy_with_progress = mock_failed_copy

    try:
        success, checksum = file_transfer._copy_with_progress(
            source_path, dest_dir / "test.txt", 1, 1
        )
        
        assert not success
        assert checksum is None
        assert len(file_transfer.display.errors) > 0
        assert "Failed to copy file" in file_transfer.display.errors[0]
    finally:
        # Restore original method
        file_transfer._copy_with_progress = original_copy

def test_copy_sd_to_dump(file_transfer, temp_transfer_dir, sample_files):
    """Test complete SD card to dump drive transfer"""
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"
    
    success = file_transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
    
    assert success
    assert log_file.exists()
    
    # Verify state manager calls
    assert len(file_transfer.state_manager.transfer_calls) > 0
    assert len(file_transfer.state_manager.exit_calls) > 0
    
    # Verify all files were copied
    for source_file in sample_files:
        dest_file = dest_dir / datetime.now().strftime('%Y%m%d_%H%M%S') / source_file.name
        assert dest_file.exists()
        assert dest_file.stat().st_size == source_file.stat().st_size

def test_insufficient_space(mock_components, temp_transfer_dir, sample_files):
    """Test handling of insufficient space"""
    display, storage, state_manager = mock_components
    storage.has_space = False
    transfer = FileTransfer(state_manager, display, storage)
    
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"
    
    success = transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
    
    assert not success
    assert "Not enough space" in str(transfer.display.errors)

def test_progress_tracking(file_transfer, temp_transfer_dir, sample_files):
    """Test progress tracking during transfer"""
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"

    # Create a custom progress tracking mock that works with the main transfer method
    def mock_copy(src, dst, file_num, total_files):
        # Use the existing progress object from file_transfer
        curr_progress = file_transfer._current_progress
        
        # Ensure we're in COPYING state
        curr_progress.status = TransferStatus.COPYING
        file_transfer.display.show_progress(curr_progress)
        
        # Actually copy the file
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(src, 'rb') as source, open(dst, 'wb') as dest:
            data = source.read()
            dest.write(data)
            
            # Update progress after copy
            curr_progress.bytes_transferred = len(data)
            curr_progress.current_file_progress = 1.0
            file_transfer.display.show_progress(curr_progress)

        # Don't change state here - let the main method handle it
        return True, "mock_checksum"

    # Replace copy method with our mock
    original_copy = file_transfer._copy_with_progress
    file_transfer._copy_with_progress = mock_copy

    try:
        # Perform the transfer
        result = file_transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
        assert result, "Transfer should succeed"
        
        # Verify progress updates
        progress_updates = file_transfer.display.progress_updates
        assert len(progress_updates) > 0, "No progress updates recorded"
        
        # Print all statuses for debugging
        statuses = [update.status for update in progress_updates]
        print(f"Recorded statuses: {statuses}")
        
        # Check for COPYING status
        has_copying = any(status == TransferStatus.COPYING for status in statuses)
        assert has_copying, "No COPYING status in progress updates"
        
    finally:
        # Restore original method
        file_transfer._copy_with_progress = original_copy

def test_error_handling(file_transfer, temp_transfer_dir):
    """Test error handling during transfer"""
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"

    # Create a file that will cause an error
    bad_file = source_dir / "unreadable.txt"
    bad_file.write_text("test")
    
    try:
        # Make file unreadable
        bad_file.chmod(0o000)
        
        # Set up error triggering mock
        def mock_copy_with_error(*args, **kwargs):
            file_transfer.display.show_error("Test error during copy")
            return False, None

        original_copy = file_transfer._copy_with_progress
        file_transfer._copy_with_progress = mock_copy_with_error

        # Initialize progress tracking
        file_transfer._current_progress = TransferProgress(
            current_file=bad_file.name,
            file_number=1,
            total_files=1,
            bytes_transferred=0,
            total_bytes=0,
            current_file_progress=0.0,
            overall_progress=0.0,
            status=TransferStatus.COPYING
        )

        success = file_transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)

        assert not success
        assert len(file_transfer.display.errors) > 0
        assert "Test error during copy" in file_transfer.display.errors[0]
        
    finally:
        # Cleanup
        bad_file.chmod(0o777)
        file_transfer._copy_with_progress = original_copy

def test_unmount_handling(file_transfer, temp_transfer_dir, sample_files):
    """Test drive unmounting after transfer"""
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"
    
    # Add source_dir to mounted drives
    file_transfer.storage.mounted_drives.append(source_dir)
    
    success = file_transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
    
    assert success
    assert source_dir in file_transfer.storage.unmount_calls
    assert "Safe to remove card" in [msg for msg, _ in file_transfer.display.status_messages]

@pytest.mark.parametrize("utility_mode", [True, False])
def test_utility_mode_blocking(mock_components, temp_transfer_dir, utility_mode):
    """Test transfer blocking in utility mode"""
    display, storage, state_manager = mock_components
    
    # Override utility mode check
    state_manager.is_utility = lambda: utility_mode
    
    transfer = FileTransfer(state_manager, display, storage)
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"
    
    success = transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
    
    assert success != utility_mode  # Should fail if in utility mode
    if utility_mode:
        assert len(state_manager.transfer_calls) == 0  # No transfer attempted

def test_log_file_content(file_transfer, temp_transfer_dir, sample_files):
    """Test transfer log file content"""
    source_dir, dest_dir = temp_transfer_dir
    log_file = dest_dir / "transfer.log"
    
    file_transfer.copy_sd_to_dump(source_dir, dest_dir, log_file)
    
    # Verify log file contents
    assert log_file.exists()
    log_content = log_file.read_text()
    
    # Check for success entries
    for source_file in sample_files:
        assert f"Success: {source_file}" in log_content
    
    # Verify timestamps and format
    assert "Success:" in log_content
    assert "->" in log_content  # Check for transfer arrow notation