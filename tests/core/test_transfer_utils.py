import pytest
from pathlib import Path
import tempfile
import shutil
import os
import platform
from datetime import datetime
from unittest.mock import patch
from src.core.transfer_utils import (
    get_transferable_files,
    calculate_transfer_totals,
    create_destination_path,
    create_directory_structure,
    validate_source_path,
    verify_space_requirements,
    log_transfer_results
)
from src.core.exceptions import FileTransferError

@pytest.fixture
def temp_source_dir():
    """Create a temporary directory for source files."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def temp_dest_dir():
    """Create a temporary directory for destination files."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def sample_files(temp_source_dir):
    """Create sample files in the source directory."""
    # Create some test files
    files = []
    for i in range(3):
        file_path = temp_source_dir / f"test{i}.txt"
        file_path.write_text(f"Test content {i}")
        files.append(file_path)
    
    # Create a media file
    media_file = temp_source_dir / "test.mp4"
    media_file.write_text("Media content")
    files.append(media_file)
    
    # Create a subdirectory with files
    subdir = temp_source_dir / "subdir"
    subdir.mkdir()
    for i in range(2):
        file_path = subdir / f"subtest{i}.txt"
        file_path.write_text(f"Subdir content {i}")
        files.append(file_path)
    
    return files

@pytest.fixture
def mock_storage():
    """Create a mock storage interface."""
    class MockStorage:
        def has_enough_space(self, path, required):
            return True
        
        def get_drive_info(self, path):
            return {'free': 1000000000}  # 1GB free
    
    return MockStorage()

class TestGetTransferableFiles:
    """Test suite for get_transferable_files function."""

    def test_get_all_files(self, temp_source_dir, sample_files):
        """Test getting all files when media_only is False."""
        files = get_transferable_files(temp_source_dir, media_only=False)
        assert len(files) == len(sample_files)
        assert all(isinstance(f, Path) for f in files)

    def test_get_media_files(self, temp_source_dir, sample_files):
        """Test getting only media files."""
        files = get_transferable_files(temp_source_dir, media_only=True, 
                                     media_extensions=['.mp4'])
        assert len(files) == 1
        assert files[0].suffix == '.mp4'

    def test_invalid_source_path(self):
        """Test with invalid source path."""
        with pytest.raises(FileTransferError):
            get_transferable_files(Path("/nonexistent/path"))

    def test_no_read_permission(self, temp_source_dir):
        """Test with directory without read permission."""
        if platform.system() != 'Windows':  # Skip on Windows
            os.chmod(temp_source_dir, 0o000)
            try:
                with pytest.raises(FileTransferError):
                    get_transferable_files(temp_source_dir)
            finally:
                os.chmod(temp_source_dir, 0o755)

class TestCalculateTransferTotals:
    """Test suite for calculate_transfer_totals function."""

    def test_calculate_totals(self, sample_files):
        """Test calculating transfer totals."""
        valid_files, total_size, total_files = calculate_transfer_totals(sample_files)
        assert len(valid_files) == len(sample_files)
        assert total_files == len(sample_files)
        assert total_size > 0

    def test_calculate_totals_with_missing_file(self, sample_files):
        """Test calculating totals with a missing file."""
        # Add a non-existent file to the list
        files = sample_files + [Path("/nonexistent/file.txt")]
        valid_files, total_size, total_files = calculate_transfer_totals(files)
        assert len(valid_files) == len(sample_files)
        assert total_files == len(sample_files)

class TestCreateDestinationPath:
    """Test suite for create_destination_path function."""

    def test_basic_destination_path(self, temp_source_dir, temp_dest_dir):
        """Test creating basic destination path."""
        source_file = temp_source_dir / "test.txt"
        source_file.write_text("Test content")
        
        dest_path = create_destination_path(
            source_file, temp_dest_dir, temp_source_dir
        )
        assert dest_path.parent == temp_dest_dir
        assert dest_path.name == "test.txt"

    def test_destination_path_with_timestamp(self, temp_source_dir, temp_dest_dir):
        """Test creating destination path with timestamp."""
        source_file = temp_source_dir / "test.txt"
        source_file.write_text("Test content")
        
        dest_path = create_destination_path(
            source_file, temp_dest_dir, temp_source_dir,
            rename_with_timestamp=True
        )
        assert dest_path.parent == temp_dest_dir
        assert dest_path.name != "test.txt"
        assert dest_path.name.endswith(".txt")

    def test_destination_path_with_subdir(self, temp_source_dir, temp_dest_dir):
        """Test creating destination path preserving directory structure."""
        subdir = temp_source_dir / "subdir"
        subdir.mkdir()
        source_file = subdir / "test.txt"
        source_file.write_text("Test content")
        
        dest_path = create_destination_path(
            source_file, temp_dest_dir, temp_source_dir
        )
        assert dest_path.parent == temp_dest_dir / "subdir"
        assert dest_path.name == "test.txt"

class TestCreateDirectoryStructure:
    """Test suite for create_directory_structure function."""

    def test_create_directory_structure(self, temp_source_dir, temp_dest_dir, sample_files):
        """Test creating directory structure."""
        result = create_directory_structure(sample_files, temp_source_dir, temp_dest_dir)
        assert result is True
        assert (temp_dest_dir / "subdir").exists()

    def test_create_directory_structure_with_invalid_path(self, temp_dest_dir):
        """Test creating directory structure with invalid path."""
        result = create_directory_structure(
            [Path("/nonexistent/file.txt")],
            Path("/nonexistent"),
            temp_dest_dir
        )
        assert result is True  # Should not fail, just skip invalid paths

class TestValidateSourcePath:
    """Test suite for validate_source_path function."""

    @patch('os.path.ismount')
    def test_valid_source_path(self, mock_ismount, temp_source_dir):
        """Test validating a valid source path."""
        mock_ismount.return_value = True
        assert validate_source_path(temp_source_dir) is True

    def test_nonexistent_source_path(self):
        """Test validating a nonexistent path."""
        assert validate_source_path(Path("/nonexistent/path")) is False

    def test_file_as_source_path(self, temp_source_dir):
        """Test validating a file as source path."""
        test_file = temp_source_dir / "test.txt"
        test_file.write_text("Test content")
        assert validate_source_path(test_file) is False

    def test_no_read_permission(self, temp_source_dir):
        """Test validating path without read permission."""
        if platform.system() != 'Windows':  # Skip on Windows
            os.chmod(temp_source_dir, 0o000)
            try:
                assert validate_source_path(temp_source_dir) is False
            finally:
                os.chmod(temp_source_dir, 0o755)

class TestVerifySpaceRequirements:
    """Test suite for verify_space_requirements function."""

    def test_sufficient_space(self, mock_storage, temp_dest_dir):
        """Test verifying sufficient space."""
        assert verify_space_requirements(mock_storage, temp_dest_dir, 500000000) is True

    def test_insufficient_space(self, mock_storage, temp_dest_dir):
        """Test verifying insufficient space."""
        # Mock storage to return insufficient space
        mock_storage.has_enough_space = lambda path, required: False
        assert verify_space_requirements(mock_storage, temp_dest_dir, 2000000000) is False

class TestLogTransferResults:
    """Test suite for log_transfer_results function."""

    def test_log_transfer_results(self, temp_dest_dir):
        """Test logging transfer results."""
        log_file = temp_dest_dir / "transfer.log"
        source_path = Path("/source")
        dest_path = Path("/dest")
        start_time = datetime.now()
        end_time = datetime.now()
        
        result = log_transfer_results(
            log_file, source_path, dest_path,
            start_time, end_time,
            10, 8, ["file1.txt", "file2.txt"]
        )
        
        assert result is True
        assert log_file.exists()
        
        content = log_file.read_text()
        assert str(source_path) in content
        assert str(dest_path) in content
        assert "Files transferred: 8/10" in content
        assert "file1.txt" in content
        assert "file2.txt" in content 