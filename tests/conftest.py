# tests/conftest.py
"""
Pytest configuration for TransferBox tests.
Defines fixtures used across multiple test modules.
"""
from pathlib import Path
from typing import Iterator, Dict, Any, Optional
import os
import tempfile
import shutil
import yaml
import pytest
from typing import TYPE_CHECKING
import logging
if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def temp_config_dir() -> Iterator[Path]:
    """
    Create a temporary directory for test configuration files.
    
    Yields:
        Path: Path to the temporary directory.
    """
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        # Clean up after test is complete
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def valid_config_file(temp_config_dir: Path) -> Iterator[Path]:
    """
    Create a temporary valid configuration file.
    
    Args:
        temp_config_dir: Temporary directory fixture for creating the config file.
        
    Yields:
        Path: Path to the valid configuration file.
    """
    config_path = temp_config_dir / "config.yml"
    
    # Sample configuration
    config_data = {
        "rename_with_timestamp": True,
        "preserve_original_filename": True,
        "filename_template": "{original}_{timestamp}",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "media_only_transfer": True,
        "preserve_folder_structure": True,
        "media_extensions": ".mp4,.mov,.jpg,.raw",
        "create_date_folders": True,
        "date_folder_format": "%Y/%m/%d",
        "create_device_folders": False,
        "device_folder_template": "{device_name}",
        "generate_proxies": False,
        "proxy_subfolder": "proxies",
        "include_proxy_watermark": True,
        "proxy_watermark_path": "assets/watermark.png",
        "enable_sounds": True,
        "sound_volume": 50,
        "success_sound_path": "sounds/success.mp3",
        "error_sound_path": "sounds/error.mp3"
    }
    
    # Write configuration to file
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
    
    yield config_path


@pytest.fixture
def invalid_config_file(temp_config_dir: Path) -> Iterator[Path]:
    """
    Create a temporary invalid configuration file.
    
    Args:
        temp_config_dir: Temporary directory fixture for creating the config file.
        
    Yields:
        Path: Path to the invalid configuration file.
    """
    config_path = temp_config_dir / "invalid_config.yml"
    
    # Invalid YAML syntax
    with open(config_path, 'w') as f:
        f.write("""
        rename_with_timestamp: true
        preserve_original_filename: true
        # This line has invalid indentation and a missing colon
          filename_template "{original}_{timestamp}"
        """)
    
    yield config_path


@pytest.fixture
def malformed_config_file(temp_config_dir: Path) -> Iterator[Path]:
    """
    Create a temporary configuration file with valid YAML but invalid config values.
    
    Args:
        temp_config_dir: Temporary directory fixture for creating the config file.
        
    Yields:
        Path: Path to the malformed configuration file.
    """
    config_path = temp_config_dir / "malformed_config.yml"
    
    # Sample configuration with incorrect value types
    config_data = {
        "rename_with_timestamp": "not_a_boolean",
        "preserve_original_filename": 123,  # Should be boolean
        "filename_template": 456,  # Should be string
        "timestamp_format": True,  # Should be string
        "media_only_transfer": "yes",  # Should be boolean
        "media_extensions": 789,  # Should be string
        "date_folder_format": "%Invalid Format%",  # Invalid date format
        "device_folder_template": "no_placeholder_here",  # Missing required placeholder
    }
    
    # Write configuration to file
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
    
    yield config_path


@pytest.fixture
def unreadable_config_dir(temp_config_dir: Path) -> Iterator[Path]:
    """
    Create a temporary directory with restricted permissions (read-only).
    
    Args:
        temp_config_dir: Temporary directory fixture for creating the config directory.
        
    Yields:
        Path: Path to the read-only directory.
    """
    # Create a subdirectory for restrictive permissions
    unreadable_dir = temp_config_dir / "restricted"
    unreadable_dir.mkdir(parents=True, exist_ok=True)
    
    # Make read-only if on POSIX system (Linux/macOS)
    if os.name == 'posix':
        os.chmod(unreadable_dir, 0o500)  # Read & execute for owner only
    
    yield unreadable_dir
    
    # Reset permissions to allow cleanup
    if os.name == 'posix':
        os.chmod(unreadable_dir, 0o700)  # Read, write, & execute for owner


@pytest.fixture
def mock_home_dir(temp_config_dir: Path, monkeypatch: "MonkeyPatch") -> Iterator[Path]:
    """
    Mock the user's home directory to point to a test directory.
    
    Args:
        temp_config_dir: Temporary directory fixture for creating the mock home.
        monkeypatch: PyTest monkeypatch fixture.
        
    Yields:
        Path: Path to the mock home directory.
    """
    mock_home = temp_config_dir / "mock_home"
    mock_home.mkdir(parents=True, exist_ok=True)
    
    # Create the .transferbox directory
    transfer_box_dir = mock_home / ".transferbox"
    transfer_box_dir.mkdir(parents=True, exist_ok=True)
    
    # Patch Path.home() to return our mock home
    monkeypatch.setattr(Path, "home", lambda: mock_home)
    
    yield mock_home


@pytest.fixture
def mock_default_config_structure(mock_home_dir: Path) -> Dict[str, Path]:
    """
    Create the default directory structure for config file locations.
    
    Args:
        mock_home_dir: Mock home directory fixture.
        
    Returns:
        Dict: Dictionary with keys for different config locations and their paths.
    """
    # Create directory structure and config files
    current_dir_config = Path.cwd() / "config.yml"
    home_config_dir = mock_home_dir / ".transferbox"
    home_config_dir.mkdir(parents=True, exist_ok=True)
    home_config = home_config_dir / "config.yml"
    
    # Create empty config files for default locations
    # Don't create system config - it would require higher privileges
    
    return {
        "current_dir": current_dir_config,
        "home_dir": home_config,
    }


@pytest.fixture
def custom_timestamp_format() -> str:
    """
    Provide a custom valid timestamp format for tests.
    
    Returns:
        str: A valid timestamp format string.
    """
    return "%Y-%m-%d_%H-%M-%S"


@pytest.fixture
def custom_device_template() -> str:
    """
    Provide a custom valid device template string for tests.
    
    Returns:
        str: A valid device template string.
    """
    return "device_{device_name}"

@pytest.fixture
def mocked_logging() -> None:
    """Fixture to patch logging for testing."""
    # Store original logger level
    original_level = logging.getLogger().level
    # Set level to suppress logs during tests
    logging.getLogger().setLevel(logging.CRITICAL)
    yield
    # Restore original level
    logging.getLogger().setLevel(original_level)