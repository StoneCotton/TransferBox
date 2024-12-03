# tests/platform/macos/test_display.py

import pytest
import platform
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.platform.macos.display import MacOSDisplay

# Skip all tests in this module if not on macOS
pytestmark = pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="MacOS display tests can only run on macOS"
)

@pytest.fixture
def macos_display():
    """Create a MacOSDisplay instance for testing"""
    return MacOSDisplay()

@pytest.fixture
def sample_progress():
    """Create a sample TransferProgress object"""
    return TransferProgress(
        current_file="test.txt",
        file_number=1,
        total_files=3,
        bytes_transferred=1024,
        total_bytes=2048,
        current_file_progress=0.5,
        overall_progress=0.33,
        status=TransferStatus.COPYING
    )

@pytest.fixture
def mock_stdout():
    """Mock sys.stdout to capture output without terminal control sequences"""
    class MockStdout:
        def __init__(self):
            self.written = []
        
        def write(self, text):
            self.written.append(text)
            
        def flush(self):
            pass
            
    mock_out = MockStdout()
    with patch('sys.stdout', mock_out):
        yield mock_out

def test_initialization(macos_display):
    """Test display initialization"""
    assert macos_display.in_transfer_mode == False
    assert macos_display.progress_bar_width > 0
    assert macos_display.copy_progress == 0.0
    assert macos_display.checksum_progress == 0.0

def test_show_status(macos_display, mock_stdout):
    """Test status message display"""
    message = "Test status"
    macos_display.show_status(message)
    assert any(message in text for text in mock_stdout.written)

def test_show_error(macos_display, mock_stdout):
    """Test error message display"""
    error_msg = "Test error"
    macos_display.show_error(error_msg)
    assert any(error_msg in text for text in mock_stdout.written)
    assert any("ERROR" in text for text in mock_stdout.written)

def test_progress_bar_creation(macos_display):
    """Test progress bar creation"""
    bar = macos_display._create_progress_bar(0.5, width=10)
    assert len(bar) == 10
    assert '█' in bar
    assert '░' in bar

def test_progress_state_transitions(macos_display, sample_progress, mock_stdout):
    """Test progress state transitions"""
    # Test COPYING state
    sample_progress.status = TransferStatus.COPYING
    macos_display.show_progress(sample_progress)
    assert any("Copying" in "".join(mock_stdout.written))
    mock_stdout.written.clear()
    
    # Test CHECKSUMMING state
    sample_progress.status = TransferStatus.CHECKSUMMING
    macos_display.show_progress(sample_progress)
    assert any("Checksumming" in "".join(mock_stdout.written))

@pytest.mark.parametrize("status", [
    TransferStatus.COPYING,
    TransferStatus.CHECKSUMMING,
    TransferStatus.SUCCESS,
    TransferStatus.ERROR
])
def test_status_specific_formatting(macos_display, sample_progress, mock_stdout, status):
    """Test formatting for different transfer statuses"""
    sample_progress.status = status
    macos_display.show_progress(sample_progress)
    
    # Join all written content for searching
    output = "".join(mock_stdout.written)
    
    if status == TransferStatus.ERROR:
        assert "ERROR" in output or any("ERROR" in text for text in mock_stdout.written)
    elif status == TransferStatus.COPYING:
        assert "Copying" in output
    elif status == TransferStatus.CHECKSUMMING:
        assert "Checksumming" in output
    elif status == TransferStatus.SUCCESS:
        assert not macos_display.in_transfer_mode

def test_clear(macos_display):
    """Test display clearing"""
    macos_display.clear()
    assert macos_display.current_status is None
    assert macos_display.current_progress is None
    assert macos_display.copy_progress == 0.0
    assert macos_display.checksum_progress == 0.0
    assert not macos_display.in_transfer_mode

def test_display_update_throttling(macos_display):
    """Test display update throttling"""
    assert macos_display._can_update()
    assert not macos_display._can_update()  # Should throttle

def test_transfer_mode_transitions(macos_display, sample_progress, mock_stdout):
    """Test transfer mode state transitions"""
    assert not macos_display.in_transfer_mode
    macos_display.show_progress(sample_progress)
    assert macos_display.in_transfer_mode
    
    sample_progress.status = TransferStatus.SUCCESS
    macos_display.show_progress(sample_progress)
    assert not macos_display.in_transfer_mode