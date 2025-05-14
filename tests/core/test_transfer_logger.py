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
        """Test logging successful transfer with new fields and multi-line format."""
        source_path = Path("/source/file.txt")
        dest_path = Path("/dest/file.txt")
        transfer_logger.start_transfer(source_path.parent, dest_path.parent, 1, 1024)
        transfer_logger.log_success(
            src_path=source_path,
            dst_path=dest_path,
            file_size=123456,
            duration=0.42,
            src_xxhash="abc123",
            dst_xxhash="abc123",
            retries=0,
            ext=".txt",
            src_mtime="2024-06-10 12:00:00",
            dst_mtime="2024-06-10 12:34:56",
            user="alice",
            src_perm="rw-r--r--",
            dst_perm="rw-r--r--"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Success:" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert "\n    size:" in content
            assert "\n    duration:" in content
            assert "\n    src_xxhash:" in content
            assert "\n    dst_xxhash:" in content
            assert "\n    retries:" in content
            assert "\n    ext:" in content
            assert "\n    src_mtime:" in content
            assert "\n    dst_mtime:" in content
            assert "\n    src_perm:" in content
            assert "\n    dst_perm:" in content
            assert "user:" not in content  # user should not be in per-file log

    def test_log_failure(self, transfer_logger):
        """Test logging failed transfer with new fields and multi-line format."""
        source_path = Path("/source/file.txt")
        dest_path = Path("/dest/file.txt")
        reason = "File not found"
        transfer_logger.start_transfer(source_path.parent, dest_path.parent, 1, 1024)
        transfer_logger.log_failure(
            src_path=source_path,
            dst_path=dest_path,
            reason=reason,
            file_size=0,
            duration=0.01,
            src_xxhash="def456",
            dst_xxhash=None,
            retries=2,
            ext=".txt",
            src_mtime="2024-06-10 12:01:00",
            dst_mtime=None,
            user="alice",
            src_perm="rw-r--r--",
            dst_perm=None,
            error_message=reason
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Failed:" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert reason in content
            assert "\n    size:" in content
            assert "\n    duration:" in content
            assert "\n    src_xxhash:" in content
            assert "\n    retries:" in content
            assert "\n    ext:" in content
            assert "\n    src_mtime:" in content
            assert "\n    src_perm:" in content
            assert "\n    error:" in content
            assert "user:" not in content  # user should not be in per-file log

    def test_complete_transfer(self, transfer_logger):
        """Test completing transfer with summary and new fields."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        transfer_logger.start_transfer(source_path, dest_path, 10, 1024)
        transfer_logger.complete_transfer(
            total_files=10,
            successful_files=8,
            failures=["file1.txt", "file2.txt"],
            total_data_transferred=123456789,
            average_file_size=1234567,
            average_speed=10.2,
            total_retries=4,
            skipped_files=1,
            error_breakdown={"Permission denied": 1, "Network error": 1},
            user="alice",
            duration_str="0:02:00"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Transfer completed at" in content
            assert "Duration:" in content
            assert "Files transferred: 8/10" in content
            assert "Failed files: 2" in content
            assert "file1.txt" in content
            assert "file2.txt" in content
            assert "Total data transferred:" in content
            assert "Average file size:" in content
            assert "Average speed:" in content
            assert "Total retries:" in content
            assert "Skipped files:" in content
            assert "Failures:" in content
            assert "User:" in content
            assert "0:02:00" in content

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
        """Test logging file transfer result with new fields."""
        source_file = Path("/source/file.txt")
        dest_file = Path("/dest/file.txt")
        # Test successful transfer
        transfer_logger.log_file_transfer(
            source_file=source_file,
            dest_file=dest_file,
            success=True,
            file_size=123456,
            duration=0.42,
            src_xxhash="abc123",
            dst_xxhash="abc123",
            retries=0,
            ext=".txt",
            src_mtime="2024-06-10 12:00:00",
            dst_mtime="2024-06-10 12:34:56",
            user="alice",
            src_perm="rw-r--r--",
            dst_perm="rw-r--r--"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Success:" in content
            assert str(source_file) in content
            assert str(dest_file) in content
            assert "size:" in content
            assert "duration:" in content
            assert "src_xxhash:" in content
            assert "dst_xxhash:" in content
            assert "retries:" in content
            assert "ext:" in content
            assert "src_mtime:" in content
            assert "dst_mtime:" in content
            assert "src_perm:" in content
            assert "dst_perm:" in content
        # Test failed transfer
        transfer_logger.log_file_transfer(
            source_file=source_file,
            dest_file=dest_file,
            success=False,
            file_size=0,
            duration=0.01,
            src_xxhash="def456",
            dst_xxhash=None,
            retries=2,
            ext=".txt",
            src_mtime="2024-06-10 12:01:00",
            dst_mtime=None,
            user="alice",
            src_perm="rw-r--r--",
            dst_perm=None,
            error_message="Transfer failed"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Failed:" in content
            assert "Transfer failed" in content
            assert "size:" in content
            assert "duration:" in content
            assert "src_xxhash:" in content
            assert "retries:" in content
            assert "ext:" in content
            assert "src_mtime:" in content
            assert "src_perm:" in content
            assert "error:" in content

    def test_log_transfer_summary(self, transfer_logger):
        """Test logging transfer summary with new fields."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        start_time = datetime.now()
        end_time = datetime.now()
        transfer_logger.log_transfer_summary(
            source_path=source_path,
            destination_path=dest_path,
            start_time=start_time,
            end_time=end_time,
            total_files=10,
            successful_files=8,
            failures=["file1.txt", "file2.txt"],
            total_data_transferred=123456789,
            average_file_size=1234567,
            average_speed=10.2,
            total_retries=4,
            skipped_files=1,
            error_breakdown={"Permission denied": 1, "Network error": 1},
            user="alice",
            duration_str="0:02:00"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Transfer Summary" in content
            assert str(source_path) in content
            assert str(dest_path) in content
            assert "Files transferred: 8/10" in content
            assert "Failed files: 2" in content
            assert "Total data transferred:" in content
            assert "Average file size:" in content
            assert "Average speed:" in content
            assert "Total retries:" in content
            assert "Skipped files:" in content
            assert "Failures:" in content
            assert "User:" in content
            assert "0:02:00" in content

    def test_log_multiple_files_and_summary(self, transfer_logger):
        """Test logging multiple files and correct summary stats."""
        source_path = Path("/source")
        dest_path = Path("/dest")
        transfer_logger.start_transfer(source_path, dest_path, 2, 246912)
        # Log two successful files
        transfer_logger.log_success(
            src_path=source_path/"file1.txt",
            dst_path=dest_path/"file1.txt",
            file_size=123456,
            duration=0.5,
            src_xxhash="hash1",
            dst_xxhash="hash1",
            retries=0,
            ext=".txt",
            src_mtime="2024-06-10 12:00:00",
            dst_mtime="2024-06-10 12:34:56",
            user="alice",
            src_perm="rw-r--r--",
            dst_perm="rw-r--r--"
        )
        transfer_logger.log_success(
            src_path=source_path/"file2.txt",
            dst_path=dest_path/"file2.txt",
            file_size=123456,
            duration=0.6,
            src_xxhash="hash2",
            dst_xxhash="hash2",
            retries=0,
            ext=".txt",
            src_mtime="2024-06-10 12:01:00",
            dst_mtime="2024-06-10 12:35:56",
            user="alice",
            src_perm="rw-r--r--",
            dst_perm="rw-r--r--"
        )
        # Complete transfer
        transfer_logger.complete_transfer(
            total_files=2,
            successful_files=2,
            failures=[],
            total_data_transferred=246912,
            average_file_size=123456,
            average_speed=10.0,
            user="alice",
            duration_str="0:00:01"
        )
        with open(transfer_logger.log_file, 'r') as f:
            content = f.read()
            assert "Success:" in content
            assert "\n    size:" in content
            assert "Transfer completed at" in content
            assert "Total data transferred: " in content
            assert "Average file size: " in content
            assert "Average speed: " in content
            assert "User: alice" in content

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