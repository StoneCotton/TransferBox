import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
from src.core.transfer_logger import TransferLogger, create_transfer_log

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def transfer_logger(temp_log_dir):
    """Create a TransferLogger instance with a temporary log file."""
    log_file = temp_log_dir / "test_transfer.log"
    return TransferLogger(log_file)

class TestTransferLogger:
    """Test suite for TransferLogger class."""

    def test_init_without_log_file(self):
        """Test initialization without log file."""
        logger = TransferLogger()
        assert logger.log_file is None
        assert logger.start_time is None
        assert logger.is_open is False
        assert logger._file_handle is None

    def test_init_with_log_file(self, temp_log_dir):
        """Test initialization with log file."""
        log_file = temp_log_dir / "test.log"
        logger = TransferLogger(log_file)
        assert logger.log_file == log_file
        assert logger.start_time is None
        assert logger.is_open is False
        assert logger._file_handle is None

    def test_start_transfer(self, transfer_logger, temp_log_dir):
        """Test starting a transfer log."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        start_time = transfer_logger.start_transfer(source_path, dest_path, 10, 1024)
        
        assert isinstance(start_time, datetime)
        assert transfer_logger.start_time == start_time
        assert transfer_logger.is_open is True
        
        # Verify log file contents
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Transfer started at" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert "Files to transfer: 10" in content
            assert "Total size:" in content

    def test_log_success(self, transfer_logger):
        """Test logging successful transfer."""
        source_path = Path("/source/file.txt")
        dest_path = Path("/dest/file.txt")
        
        transfer_logger.start_transfer(source_path.parent, dest_path.parent, 1, 1024)
        transfer_logger.log_success(source_path, dest_path)
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Success:" in content
            assert str(source_path) in content
            assert str(dest_path) in content

    def test_log_failure(self, transfer_logger):
        """Test logging failed transfer."""
        source_path = Path("/source/file.txt")
        dest_path = Path("/dest/file.txt")
        reason = "File not found"
        
        transfer_logger.start_transfer(source_path.parent, dest_path.parent, 1, 1024)
        transfer_logger.log_failure(source_path, dest_path, reason)
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Failed:" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert reason in content

    def test_complete_transfer(self, transfer_logger):
        """Test completing transfer with summary."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        
        transfer_logger.start_transfer(source_path, dest_path, 10, 1024)
        transfer_logger.complete_transfer(10, 8, ["file1.txt", "file2.txt"])
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Transfer completed at" in content
            assert "Duration:" in content
            assert "Files transferred: 8/10" in content
            assert "Failed files: 2" in content
            assert "file1.txt" in content
            assert "file2.txt" in content

    def test_log_message(self, transfer_logger):
        """Test logging general message."""
        message = "Test message"
        transfer_logger.log_message(message)
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "[INFO]" in content
            assert message in content

    def test_error(self, transfer_logger):
        """Test logging error message."""
        error_message = "Test error"
        transfer_logger.error(error_message)
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "[ERROR]" in content
            assert error_message in content

    def test_log_file_transfer(self, transfer_logger):
        """Test logging file transfer result."""
        source_file = Path("/source/file.txt")
        dest_file = Path("/dest/file.txt")
        
        # Test successful transfer
        transfer_logger.log_file_transfer(source_file, dest_file, True)
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Success:" in content
            assert str(source_file) in content
            assert str(dest_file) in content
        
        # Test failed transfer
        transfer_logger.log_file_transfer(source_file, dest_file, False)
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Failed:" in content
            assert "Transfer failed" in content

    def test_log_transfer_summary(self, transfer_logger):
        """Test logging transfer summary."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        start_time = datetime.now()
        end_time = datetime.now()
        
        transfer_logger.log_transfer_summary(
            source_path, dest_path,
            start_time, end_time,
            10, 8, ["file1.txt", "file2.txt"]
        )
        
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Transfer Summary" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert "Files transferred: 8/10" in content
            assert "Failed files: 2" in content
            assert "Transfer rate:" in content

class TestCreateTransferLog:
    """Test suite for create_transfer_log function."""

    def test_create_transfer_log(self, temp_log_dir):
        """Test creating transfer log file path."""
        log_path = create_transfer_log(temp_log_dir)
        assert log_path.parent == temp_log_dir
        assert log_path.name.startswith("transfer_log_")
        assert log_path.suffix == ".log"

    def test_create_transfer_log_custom_prefix(self, temp_log_dir):
        """Test creating transfer log with custom prefix."""
        prefix = "custom_log"
        log_path = create_transfer_log(temp_log_dir, prefix)
        assert log_path.name.startswith(f"{prefix}_") 