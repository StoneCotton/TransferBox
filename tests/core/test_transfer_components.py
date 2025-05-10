import pytest
from pathlib import Path
import os
import tempfile
import shutil
from datetime import datetime
from src.core.transfer_components import (
    get_valid_media_files,
    TransferValidator,
    TransferEnvironment,
    FileProcessor
)
from src.core.interfaces.types import TransferStatus
from src.core.exceptions import FileTransferError, StorageError
from unittest.mock import Mock, patch

class MockTransferLogger:
    def __init__(self):
        self.messages = []
        self.transfers = []

    def log_message(self, message):
        self.messages.append(message)

    def log_file_transfer(self, source_file, dest_file, success):
        self.transfers.append((source_file, dest_file, success))

@pytest.fixture
def mock_transfer_logger():
    return MockTransferLogger()

@pytest.fixture
def temp_source_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock mount point
        with patch('os.path.ismount', return_value=True):
            yield Path(tmpdir)

@pytest.fixture
def temp_dest_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

class TestGetValidMediaFiles:
    """Test suite for get_valid_media_files function."""

    def test_get_valid_media_files_all(self, temp_source_dir, mock_config):
        """Test getting all files when media_only is False."""
        mock_config.media_only_transfer = False
        with patch('os.path.ismount', return_value=True):
            files = get_valid_media_files(temp_source_dir, mock_config)
            assert isinstance(files, list)

    def test_get_valid_media_files_media_only(self, temp_source_dir, mock_config):
        """Test getting only media files when media_only is True."""
        mock_config.media_only_transfer = True
        mock_config.media_extensions = ['.mp4', '.mov', '.mxf']
        with patch('os.path.ismount', return_value=True):
            files = get_valid_media_files(temp_source_dir, mock_config)
            assert isinstance(files, list)

    def test_get_valid_media_files_nonexistent(self, mock_config):
        """Test handling of nonexistent directory."""
        with pytest.raises(FileTransferError):
            get_valid_media_files(Path("/nonexistent"), mock_config)

class TestTransferValidator:
    """Test suite for TransferValidator class."""

    def test_validate_transfer_utility_mode(self, mock_display_interface, mock_storage_interface, mock_state_manager):
        """Test validation in utility mode."""
        validator = TransferValidator(mock_display_interface, mock_storage_interface, mock_state_manager)
        mock_state_manager.is_utility.return_value = True
        with patch('os.path.ismount', return_value=True), patch.object(Path, 'exists', return_value=True):
            assert validator.validate_transfer(Path("/source"), Path("/dest")) is False

    def test_validate_transfer_valid_paths(self, mock_display_interface, mock_storage_interface, mock_state_manager):
        """Test validation with valid paths."""
        validator = TransferValidator(mock_display_interface, mock_storage_interface, mock_state_manager)
        mock_state_manager.is_utility.return_value = False
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch('os.path.ismount', return_value=True), \
             patch('os.access', return_value=True), \
             patch.object(Path, 'iterdir', return_value=iter([])):
            assert validator.validate_transfer(Path("/source"), Path("/dest")) is True

    def test_validate_destination_none(self, mock_display_interface, mock_storage_interface, mock_state_manager):
        """Test validation with None destination."""
        validator = TransferValidator(mock_display_interface, mock_storage_interface, mock_state_manager)
        assert validator.validate_transfer(Path("/source"), None) is False

class TestTransferEnvironment:
    """Test suite for TransferEnvironment class."""

    def test_setup_transfer_environment(self, mock_display_interface, mock_storage_interface, mock_config):
        """Test setting up transfer environment."""
        env = TransferEnvironment(mock_config, mock_display_interface, mock_storage_interface)
        with patch('os.path.ismount', return_value=True):
            result = env.setup(Path("/source"), Path("/dest"))
            assert result is not None

    def test_setup_with_mhl(self, mock_display_interface, mock_storage_interface, mock_config):
        """Test setting up environment with MHL creation."""
        mock_config.create_mhl_files = True
        env = TransferEnvironment(mock_config, mock_display_interface, mock_storage_interface)
        with patch('os.path.ismount', return_value=True):
            result = env.setup(Path("/source"), Path("/dest"))
            assert result is not None

class TestFileProcessor:
    """Test suite for FileProcessor class."""

    def test_process_files_success(self, mock_display_interface, mock_storage_interface,
                                 mock_config, temp_source_dir, temp_dest_dir, mock_transfer_logger):
        """Test successful file processing."""
        processor = FileProcessor(mock_display_interface, mock_storage_interface, mock_config)
        mock_config.media_only_transfer = True
        mock_config.media_extensions = ['.mp4', '.mov']

        # Create a test file
        test_file = temp_source_dir / "test.mp4"
        test_file.touch()

        # Mock the storage interface to simulate successful copy
        mock_storage_interface.copy_file.return_value = True

        with patch('os.path.ismount', return_value=True):
            result = processor.process_files(temp_source_dir, temp_dest_dir)
            assert result is True

    def test_process_files_empty_source(self, mock_display_interface, mock_storage_interface,
                                      mock_config, temp_dest_dir, mock_transfer_logger):
        """Test processing with empty source directory."""
        processor = FileProcessor(mock_display_interface, mock_storage_interface, mock_config)
        empty_dir = Path(tempfile.mkdtemp())
        try:
            with patch('os.path.ismount', return_value=True):
                result = processor.process_files(empty_dir, temp_dest_dir)
                assert result is False
                assert processor.no_files_found
        finally:
            empty_dir.rmdir()

    def test_process_files_verify_transfers(self, mock_display_interface, mock_storage_interface,
                                          mock_config, temp_source_dir, temp_dest_dir, mock_transfer_logger):
        """Test file processing with transfer verification enabled."""
        processor = FileProcessor(mock_display_interface, mock_storage_interface, mock_config)
        mock_config.verify_transfers = True
        mock_config.media_only_transfer = True
        mock_config.media_extensions = ['.mp4', '.mov']

        # Create a test file
        test_file = temp_source_dir / "test.mp4"
        test_file.touch()

        # Mock the storage interface to simulate successful copy and verification
        mock_storage_interface.copy_file_with_hash.return_value = (True, "test_hash")
        mock_storage_interface.verify_checksum.return_value = True

        with patch('os.path.ismount', return_value=True):
            result = processor.process_files(temp_source_dir, temp_dest_dir)
            assert result is True

    def test_process_single_file_success(self, mock_display_interface, mock_storage_interface,
                                       mock_config, temp_source_dir, temp_dest_dir, mock_transfer_logger):
        """Test successful processing of a single file."""
        processor = FileProcessor(mock_display_interface, mock_storage_interface, mock_config)
        test_file = temp_source_dir / "test.mp4"
        test_file.touch()

        # Mock the storage interface
        mock_storage_interface.copy_file.return_value = True

        with patch('os.path.ismount', return_value=True):
            result = processor._process_single_file(
                test_file,
                temp_source_dir,
                temp_dest_dir,
                None,  # No MHL data
                mock_transfer_logger
            )
            assert result is True

    def test_process_single_file_metadata(self, mock_display_interface, mock_storage_interface,
                                        mock_config, temp_source_dir, temp_dest_dir, mock_transfer_logger):
        """Test file processing with metadata copying."""
        processor = FileProcessor(mock_display_interface, mock_storage_interface, mock_config)
        test_file = temp_source_dir / "test.mp4"
        test_file.touch()

        # Mock the storage interface
        mock_storage_interface.copy_file.return_value = True
        mock_storage_interface.get_metadata.return_value = {"test": "metadata"}
        mock_storage_interface.apply_metadata.return_value = True

        with patch('os.path.ismount', return_value=True):
            result = processor._process_single_file(
                test_file,
                temp_source_dir,
                temp_dest_dir,
                None,  # No MHL data
                mock_transfer_logger
            )
            assert result is True 