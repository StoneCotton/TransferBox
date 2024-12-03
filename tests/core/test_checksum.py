# tests/core/test_checksum.py
import pytest
from pathlib import Path
from src.core.checksum import ChecksumCalculator
from src.core.interfaces.types import TransferProgress, TransferStatus

class MockDisplay:
    def show_progress(self, progress):
        pass
    
    def show_error(self, message):
        pass

@pytest.fixture
def checksum_calculator():
    return ChecksumCalculator(MockDisplay())

@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file with known content"""
    file_path = temp_dir / "test.txt"
    file_path.write_text("Hello, World!")
    return file_path

def test_create_hash(checksum_calculator):
    """Test hash object creation"""
    hash_obj = checksum_calculator.create_hash()
    assert hash_obj is not None
    
def test_calculate_file_checksum(checksum_calculator, sample_file):
    """Test checksum calculation for a file"""
    # Calculate checksum
    checksum = checksum_calculator.calculate_file_checksum(sample_file)
    
    # Verify checksum is not None and has expected format
    assert checksum is not None
    assert isinstance(checksum, str)
    assert len(checksum) > 0
    
    # Calculate again to verify consistency
    checksum2 = checksum_calculator.calculate_file_checksum(sample_file)
    assert checksum == checksum2

def test_calculate_file_checksum_with_progress(checksum_calculator, sample_file):
    """Test checksum calculation with progress monitoring"""
    progress_updates = []
    
    def progress_callback(bytes_processed, total_bytes):
        progress_updates.append((bytes_processed, total_bytes))
    
    checksum = checksum_calculator.calculate_file_checksum(
        sample_file,
        progress_callback=progress_callback
    )
    
    assert checksum is not None
    assert len(progress_updates) > 0
    # Verify last progress update shows completion
    assert progress_updates[-1][0] == progress_updates[-1][1]

def test_verify_checksum(checksum_calculator, sample_file):
    """Test checksum verification"""
    # First calculate checksum
    original_checksum = checksum_calculator.calculate_file_checksum(sample_file)
    
    # Verify the same file
    assert checksum_calculator.verify_checksum(sample_file, original_checksum)
    
    # Verify with wrong checksum
    assert not checksum_calculator.verify_checksum(sample_file, "wrong_checksum")

def test_calculate_file_checksum_nonexistent_file(checksum_calculator, temp_dir):
    """Test handling of nonexistent file"""
    nonexistent_file = temp_dir / "nonexistent.txt"
    checksum = checksum_calculator.calculate_file_checksum(nonexistent_file)
    assert checksum is None

def test_calculate_file_checksum_with_transfer_progress(checksum_calculator, sample_file):
    """Test checksum calculation with TransferProgress updates"""
    progress = TransferProgress(
        current_file="test.txt",
        file_number=1,
        total_files=1,
        bytes_transferred=0,
        total_bytes=13,  # Length of "Hello, World!"
        current_file_progress=0.0,
        overall_progress=0.0,
        status=TransferStatus.CHECKSUMMING
    )
    
    checksum = checksum_calculator.calculate_file_checksum(
        sample_file,
        current_progress=progress
    )
    
    assert checksum is not None
    assert progress.bytes_transferred == 13
    assert progress.status == TransferStatus.CHECKSUMMING

@pytest.mark.parametrize("file_content,expected_different", [
    ("Hello, World!", False),
    ("Different content", True),
])
def test_verify_checksum_with_different_content(checksum_calculator, temp_dir, 
                                              file_content, expected_different):
    """Test checksum verification with different file contents"""
    # Create original file and get its checksum
    original_file = temp_dir / "original.txt"
    original_file.write_text("Hello, World!")
    original_checksum = checksum_calculator.calculate_file_checksum(original_file)
    
    # Create test file with parametrized content
    test_file = temp_dir / "test.txt"
    test_file.write_text(file_content)
    
    # Verify checksum
    result = checksum_calculator.verify_checksum(test_file, original_checksum)
    assert result != expected_different