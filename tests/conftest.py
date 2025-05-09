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
    Create a temporary valid configuration file with all fields from TransferConfig.
    Args:
        temp_config_dir: Temporary directory fixture for creating the config file.
    Yields:
        Path: Path to the valid configuration file.
    """
    config_path = temp_config_dir / "config.yml"

    config_data = {
        # File handling
        "rename_with_timestamp": True,
        "preserve_original_filename": True,
        "filename_template": "{original}_{timestamp}",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "create_mhl_files": False,
        # Media transfer settings
        "media_only_transfer": True,
        "preserve_folder_structure": True,
        "transfer_destination": "/media/transfer",
        "media_extensions": [
            ".mp4", ".mov", ".mxf", ".avi", ".braw", ".r3d",
            ".wav", ".aif", ".aiff", ".crm", ".arw", ".raw", ".cr2",
            ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".dpx", ".exr",
            ".xml", ".cdl", ".cube"
        ],
        # Directory structure
        "create_date_folders": True,
        "date_folder_format": "%Y/%m/%d",
        "create_device_folders": False,
        "device_folder_template": "{device_name}",
        # Proxy generation
        "generate_proxies": False,
        "proxy_subfolder": "proxies",
        "include_proxy_watermark": True,
        "proxy_watermark_path": "assets/watermark.png",
        # Sound settings
        "enable_sounds": True,
        "sound_volume": 50,
        "success_sound_path": "sounds/success.mp3",
        "error_sound_path": "sounds/error.mp3",
        # Advanced settings
        "buffer_size": 1048576,
        "verify_transfers": True,
        "max_transfer_threads": 1,
        # Logging settings
        "log_level": "INFO",
        "log_file_rotation": 5,
        "log_file_max_size": 10
    }

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
    Create a temporary configuration file with valid YAML but invalid config values for all fields.
    Args:
        temp_config_dir: Temporary directory fixture for creating the config file.
    Yields:
        Path: Path to the malformed configuration file.
    """
    config_path = temp_config_dir / "malformed_config.yml"

    config_data = {
        # File handling
        "rename_with_timestamp": "not_a_boolean",
        "preserve_original_filename": 123,
        "filename_template": 456,
        "timestamp_format": True,
        "create_mhl_files": "nope",
        # Media transfer settings
        "media_only_transfer": "yes",
        "preserve_folder_structure": None,
        "transfer_destination": 789,
        "media_extensions": 789,  # Should be list
        # Directory structure
        "create_date_folders": "sometimes",
        "date_folder_format": 12345,
        "create_device_folders": "false",
        "device_folder_template": False,
        # Proxy generation
        "generate_proxies": "sure",
        "proxy_subfolder": 999,
        "include_proxy_watermark": "maybe",
        "proxy_watermark_path": 0,
        # Sound settings
        "enable_sounds": "on",
        "sound_volume": "loud",
        "success_sound_path": 1,
        "error_sound_path": 2,
        # Advanced settings
        "buffer_size": "big",
        "verify_transfers": "absolutely",
        "max_transfer_threads": "many",
        # Logging settings
        "log_level": 100,
        "log_file_rotation": "lots",
        "log_file_max_size": "huge"
    }

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
    Create the default directory structure for config file locations, including platform-specific appdata/config dirs.
    Args:
        mock_home_dir: Mock home directory fixture.
    Returns:
        Dict: Dictionary with keys for different config locations and their paths.
    """
    import sys
    # Current directory config
    current_dir_config = Path.cwd() / "config.yml"
    # Home config (legacy)
    home_config_dir = mock_home_dir / ".transferbox"
    home_config_dir.mkdir(parents=True, exist_ok=True)
    home_config = home_config_dir / "config.yml"
    # Platform-specific appdata/config dir
    if sys.platform == "win32":
        appdata_dir = Path(os.getenv("APPDATA", mock_home_dir / "AppData" / "Roaming")) / "TransferBox"
    elif sys.platform == "darwin":
        appdata_dir = mock_home_dir / "Library" / "Application Support" / "TransferBox"
    else:
        appdata_dir = mock_home_dir / ".config" / "transferbox"
    appdata_dir.mkdir(parents=True, exist_ok=True)
    appdata_config = appdata_dir / "config.yml"
    # Create empty config files for default locations
    for cfg in [current_dir_config, home_config, appdata_config]:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.touch(exist_ok=True)
    return {
        "current_dir": current_dir_config,
        "home_dir": home_config,
        "appdata_dir": appdata_config,
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
def mocked_logging() -> Iterator[None]:
    """Fixture to patch logging for testing."""
    # Store original logger level
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.CRITICAL)
    yield
    logging.getLogger().setLevel(original_level)

@pytest.fixture
def mock_display_interface(mocker) -> Any:
    """
    Provide a mock DisplayInterface for checksum tests.
    Returns:
        Mocked DisplayInterface instance.
    """
    mock_display = mocker.Mock()
    mock_display.show_progress = mocker.Mock()
    mock_display.show_error = mocker.Mock()
    return mock_display