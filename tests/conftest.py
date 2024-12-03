# tests/conftest.py
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Shared fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for file operations"""
    return tmp_path

@pytest.fixture
def mock_logger():
    """Provide a mock logger for testing"""
    import logging
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger

@pytest.fixture
def sample_transfer_progress():
    """Provide sample transfer progress data"""
    from src.core.interfaces.types import TransferProgress, TransferStatus
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
