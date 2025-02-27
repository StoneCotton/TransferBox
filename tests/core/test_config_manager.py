# tests/core/test_config_manager.py
"""
Tests for the ConfigManager class that handles configuration loading and validation.

This test module verifies that the ConfigManager:
1. Correctly loads configuration from various sources
2. Properly validates configuration values
3. Gracefully handles errors with appropriate recovery
4. Successfully saves configuration to disk
"""
import os
import logging
import pytest
import tempfile
import yaml
import shutil  # Added for directory cleanup
from pathlib import Path
from typing import List, Dict, Any, Optional, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

# Import the module to test
from src.core.config_manager import ConfigManager, TransferConfig
from src.core.exceptions import ConfigError


class TestTransferConfig:
    """Tests for the TransferConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that TransferConfig initializes with correct default values."""
        config = TransferConfig()
        
        # Check file handling defaults
        assert config.rename_with_timestamp is True
        assert config.preserve_original_filename is True
        assert config.filename_template == "{original}_{timestamp}"
        assert config.timestamp_format == "%Y%m%d_%H%M%S"
        
        # Check media transfer defaults
        assert config.media_only_transfer is True
        assert config.preserve_folder_structure is True
        assert len(config.media_extensions) > 0
        assert '.mp4' in config.media_extensions
        
        # Check directory structure defaults
        assert config.create_date_folders is True
        assert config.date_folder_format == "%Y/%m/%d"
        assert config.create_device_folders is False
        assert config.device_folder_template == "{device_name}"
        
        # Check proxy generation defaults
        assert config.generate_proxies is False
        assert config.proxy_subfolder == "proxies"
        assert config.include_proxy_watermark is True
        assert config.proxy_watermark_path == "assets/watermark.png"
        
        # Check sound settings defaults
        assert config.enable_sounds is True
        assert config.sound_volume == 50
        assert config.success_sound_path == "sounds/success.mp3"
        assert config.error_sound_path == "sounds/error.mp3"

    def test_to_dict_method(self) -> None:
        """Test that to_dict() returns correctly formatted dictionary with all settings."""
        config = TransferConfig()
        config_dict = config.to_dict()
        
        # Check that all config keys are present (ignoring comment keys)
        assert "rename_with_timestamp" in config_dict
        assert "preserve_original_filename" in config_dict
        assert "filename_template" in config_dict
        assert "timestamp_format" in config_dict
        assert "media_only_transfer" in config_dict
        assert "preserve_folder_structure" in config_dict
        assert "media_extensions" in config_dict
        assert "create_date_folders" in config_dict
        assert "date_folder_format" in config_dict
        assert "create_device_folders" in config_dict
        assert "device_folder_template" in config_dict
        assert "generate_proxies" in config_dict
        assert "proxy_subfolder" in config_dict
        assert "include_proxy_watermark" in config_dict
        assert "proxy_watermark_path" in config_dict
        
        # Check media extensions format
        assert isinstance(config_dict["media_extensions"], str)
        assert ".mp4" in config_dict["media_extensions"]
        
        # Verify some values match the config
        assert config_dict["rename_with_timestamp"] == config.rename_with_timestamp
        assert config_dict["filename_template"] == config.filename_template
        assert config_dict["date_folder_format"] == config.date_folder_format


class TestConfigManagerInitialization:
    """Tests for ConfigManager initialization."""

    def test_init_with_default_paths(self) -> None:
        """Test that ConfigManager initializes with default paths."""
        config_manager = ConfigManager()
        assert config_manager.config_path is None
        assert len(config_manager.DEFAULT_CONFIG_PATHS) > 0
        assert isinstance(config_manager.DEFAULT_CONFIG_PATHS[0], Path)

    def test_init_with_custom_path(self, temp_config_dir: Path) -> None:
        """Test that ConfigManager accepts custom path."""
        config_path = temp_config_dir / "custom_config.yml"
        config_manager = ConfigManager(config_path=config_path)
        assert config_manager.config_path == config_path


class TestConfigManagerFindOrCreate:
    """Tests for ConfigManager's _find_or_create_config method."""

    def test_find_existing_config(self, valid_config_file: Path) -> None:
        """Test that _find_or_create_config finds an existing config file."""
        config_manager = ConfigManager(config_path=valid_config_file)
        found_path = config_manager._find_or_create_config()
        assert found_path == valid_config_file

    def test_create_config_if_not_exists(self, temp_config_dir: Path, mocked_logging: None) -> None:
        """Test that _find_or_create_config creates a config file if it doesn't exist."""
        config_path = temp_config_dir / "new_config.yml"
        config_manager = ConfigManager(config_path=config_path)
        
        assert not config_path.exists()
        created_path = config_manager._find_or_create_config()
        
        assert created_path == config_path
        assert config_path.exists()
        assert config_path.is_file()

    def test_find_in_default_locations(
        self, 
        mock_default_config_structure: Dict[str, Path],
        monkeypatch: "MonkeyPatch"
    ) -> None:
        """Test that _find_or_create_config searches default locations."""
        # Create config in home directory for test
        home_config = mock_default_config_structure["home_dir"]
        home_config.parent.mkdir(parents=True, exist_ok=True)
        home_config.touch()
        
        # Ensure config doesn't exist in current dir
        current_dir_config = mock_default_config_structure["current_dir"]
        if current_dir_config.exists():
            current_dir_config.unlink()
        
        # Initialize manager without specific path
        config_manager = ConfigManager()
        found_path = config_manager._find_or_create_config()
        
        # Should find the one in home directory
        assert found_path == home_config

    def test_permission_denied_handling(
        self, 
        unreadable_config_dir: Path, 
        mocker: "MockerFixture"
    ) -> None:
        """Test handling of permission denied errors during config creation."""
        config_path = unreadable_config_dir / "config.yml"
        
        # Create a ConfigManager with the restricted path
        config_manager = ConfigManager(config_path=config_path)
        
        # Mock Path.parent.mkdir to simulate permission error
        mocker.patch.object(
            Path, 
            'mkdir',
            side_effect=PermissionError("Permission denied")
        )
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager._find_or_create_config()
        
        assert "Permission denied" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert len(exc_info.value.recovery_steps) > 0

    def test_fallback_to_defaults_when_specified_fails(
        self,
        unreadable_config_dir: Path,
        mock_home_dir: Path,
        monkeypatch: "MonkeyPatch",
        mocker: "MockerFixture"
    ) -> None:
        """Test falling back to default locations when specified path fails."""
        # First mock to make the specified path fail
        mock_open = mocker.patch('builtins.open')
        mock_open.side_effect = [
            PermissionError("Permission denied for specified path"),  # First attempt fails
            mocker.mock_open(read_data="").return_value  # Second attempt succeeds
        ]
        
        # Create home directory config path
        home_config_dir = mock_home_dir / ".transferbox"
        home_config_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize with a path that will fail
        bad_path = unreadable_config_dir / "config.yml"
        
        # Monkeypatch mkdir to avoid actually creating directories
        monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: None)
        
        # Call the method with patched functions
        with pytest.raises(ConfigError):
            config_manager = ConfigManager(config_path=bad_path)
            config_manager._find_or_create_config()


class TestConfigManagerGenerateDefaultConfig:
    """Tests for ConfigManager's _generate_default_config method."""

    def test_generate_default_config(self, temp_config_dir: Path) -> None:
        """Test that _generate_default_config creates a valid config file."""
        config_path = temp_config_dir / "generated_config.yml"
        
        # Create manager and generate config
        config_manager = ConfigManager()
        config_manager._generate_default_config(config_path)
        
        # Check that file exists
        assert config_path.exists()
        assert config_path.is_file()
        
        # Check that content is valid YAML
        with open(config_path, 'r') as f:
            content = f.read()
            config_data = yaml.safe_load(content)
        
        # Verify some expected content
        assert "rename_with_timestamp" in config_data
        assert "date_folder_format" in config_data

    def test_parent_directory_creation(self, temp_config_dir: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        nested_path = temp_config_dir / "nested" / "deeply" / "config.yml"
        
        # Ensure parent dirs don't exist
        if nested_path.parent.exists():
            shutil.rmtree(nested_path.parent)
        
        # Generate config
        config_manager = ConfigManager()
        config_manager._generate_default_config(nested_path)
        
        # Verify parent dirs were created
        assert nested_path.parent.exists()
        assert nested_path.exists()

    def test_permission_denied_handling(
        self, 
        unreadable_config_dir: Path,
        monkeypatch: "MonkeyPatch"
    ) -> None:
        """Test handling of permission denied errors."""
        # Skip test on Windows where permission handling is different
        if os.name == 'nt':
            pytest.skip("Permission tests not applicable on Windows")
        
        config_path = unreadable_config_dir / "forbidden_config.yml"
        
        # Ensure parent dir exists but is read-only
        config_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(config_path.parent, 0o500)  # Read & execute only
        
        config_manager = ConfigManager()
        
        try:
            # Should raise ConfigError
            with pytest.raises(ConfigError) as exc_info:
                config_manager._generate_default_config(config_path)
            
            assert "Permission denied" in str(exc_info.value)
            assert "recovery_steps" in dir(exc_info.value)
            assert "permissions" in str(exc_info.value.recovery_steps)
        finally:
            # Restore permissions to allow cleanup
            os.chmod(config_path.parent, 0o700)


class TestConfigManagerParseConfig:
    """Tests for ConfigManager's _parse_config method."""

    def test_parse_valid_config(self) -> None:
        """Test parsing valid configuration data."""
        valid_config_data = {
            "rename_with_timestamp": True,
            "preserve_original_filename": True,
            "filename_template": "{original}_{timestamp}",
            "timestamp_format": "%Y%m%d_%H%M%S",
            "media_only_transfer": True,
            "media_extensions": ".mp4,.mov,.jpg,.raw",
            "date_folder_format": "%Y/%m/%d",
            "device_folder_template": "camera_{device_name}"
        }
        
        config_manager = ConfigManager()
        config = config_manager._parse_config(valid_config_data)
        
        # Check parsed values
        assert config.rename_with_timestamp is True
        assert config.filename_template == "{original}_{timestamp}"
        assert config.media_extensions == ['.mp4', '.mov', '.jpg', '.raw']
        assert config.date_folder_format == "%Y/%m/%d"
        assert config.device_folder_template == "camera_{device_name}"

    def test_parse_bool_option(self) -> None:
        """Test parsing boolean options with validation."""
        config_manager = ConfigManager()
        config = TransferConfig()
        
        # Test with valid boolean
        config_manager._parse_bool_option(
            {"rename_with_timestamp": False}, 
            "rename_with_timestamp", 
            config, 
            lambda v: setattr(config, "rename_with_timestamp", v)
        )
        assert config.rename_with_timestamp is False
        
        # Test with string that can be converted
        config_manager._parse_bool_option(
            {"preserve_original_filename": "true"}, 
            "preserve_original_filename", 
            config, 
            lambda v: setattr(config, "preserve_original_filename", v)
        )
        assert config.preserve_original_filename is True
        
        # Test with invalid value
        with pytest.raises(ConfigError) as exc_info:
            config_manager._parse_bool_option(
                {"rename_with_timestamp": "invalid_bool"}, 
                "rename_with_timestamp", 
                config, 
                lambda v: setattr(config, "rename_with_timestamp", v)
            )
        assert "Invalid boolean value" in str(exc_info.value)
        assert exc_info.value.config_key == "rename_with_timestamp"

    def test_parse_int_option(self) -> None:
        """Test parsing integer options with validation."""
        config_manager = ConfigManager()
        config = TransferConfig()
        
        # Test with valid int
        config_manager._parse_int_option(
            {"sound_volume": 75}, 
            "sound_volume", 
            config, 
            lambda v: setattr(config, "sound_volume", v)
        )
        assert config.sound_volume == 75
        
        # Test with string that can be converted
        config_manager._parse_int_option(
            {"sound_volume": "25"}, 
            "sound_volume", 
            config, 
            lambda v: setattr(config, "sound_volume", v)
        )
        assert config.sound_volume == 25
        
        # Test with min/max range enforcement
        config_manager._parse_int_option(
            {"sound_volume": 150}, 
            "sound_volume", 
            config, 
            lambda v: setattr(config, "sound_volume", max(0, min(100, v))),
            min_val=0,
            max_val=100
        )
        assert config.sound_volume == 100  # Clamped to max
        
        # Test with invalid value
        with pytest.raises(ConfigError) as exc_info:
            config_manager._parse_int_option(
                {"sound_volume": "invalid_int"}, 
                "sound_volume", 
                config, 
                lambda v: setattr(config, "sound_volume", v)
            )
        assert "Invalid integer value" in str(exc_info.value)
        assert exc_info.value.config_key == "sound_volume"

    def test_parse_string_option(self) -> None:
        """Test parsing string options with validation."""
        config_manager = ConfigManager()
        config = TransferConfig()
        
        # Test with valid string
        config_manager._parse_string_option(
            {"filename_template": "custom_{original}"}, 
            "filename_template", 
            config, 
            lambda v: setattr(config, "filename_template", v)
        )
        assert config.filename_template == "custom_{original}"
        
        # Test with non-string that can be converted
        config_manager._parse_string_option(
            {"filename_template": 123}, 
            "filename_template", 
            config, 
            lambda v: setattr(config, "filename_template", v)
        )
        assert config.filename_template == "123"

    def test_parse_media_extensions(self) -> None:
        """Test parsing media extensions with validation."""
        config_manager = ConfigManager()
        config = TransferConfig()
        
        # Test with comma-separated string
        config_manager._parse_media_extensions(
            {"media_extensions": ".mp4,.mov,.jpg,.png"}, 
            config
        )
        assert config.media_extensions == ['.mp4', '.mov', '.jpg', '.png']
        
        # Test with list
        config_manager._parse_media_extensions(
            {"media_extensions": [".mp4", ".mov", ".jpg"]}, 
            config
        )
        assert config.media_extensions == ['.mp4', '.mov', '.jpg']
        
        # Test with extensions missing dots
        config_manager._parse_media_extensions(
            {"media_extensions": "mp4,mov,jpg"}, 
            config
        )
        assert config.media_extensions == ['.mp4', '.mov', '.jpg']
        
        # Test with invalid format
        with pytest.raises(ConfigError) as exc_info:
            config_manager._parse_media_extensions(
                {"media_extensions": 123}, 
                config
            )
        assert "Invalid media extensions format" in str(exc_info.value)

    def test_invalid_date_format(self) -> None:
        """Test handling invalid date format strings."""
        config_manager = ConfigManager()
        
        # Invalid date format should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager._parse_config({
                "date_folder_format": "%Y/%m/%Q"  # Invalid format specifier
            })
        
        assert "Invalid date format" in str(exc_info.value)
        assert exc_info.value.config_key == "date_folder_format"
        assert exc_info.value.invalid_value == "%Y/%m/%Q"
        assert exc_info.value.expected_type == "valid strftime format string"

    def test_invalid_device_template(self) -> None:
        """Test handling invalid device template strings."""
        config_manager = ConfigManager()
        
        # Device template missing {device_name} should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager._parse_config({
                "device_folder_template": "missing_placeholder"
            })
        
        assert "must contain {device_name}" in str(exc_info.value)
        assert exc_info.value.config_key == "device_folder_template"


class TestConfigManagerLoadConfig:
    """Tests for ConfigManager's load_config method."""
    

    def test_load_valid_config(self, valid_config_file: Path, mocked_logging: None) -> None:
        """Test loading a valid configuration file."""
        config_manager = ConfigManager(config_path=valid_config_file)
        config = config_manager.load_config()
        
        # Verify config was loaded
        assert config is not None
        assert isinstance(config, TransferConfig)
        
        # Verify the loaded custom values
        with open(valid_config_file, 'r') as f:
            raw_config = yaml.safe_load(f)
            
        # Check that a few values match what was in the file
        assert config.rename_with_timestamp == raw_config["rename_with_timestamp"]
        assert config.filename_template == raw_config["filename_template"]

    def test_load_invalid_yaml(self, invalid_config_file: Path, mocked_logging: None) -> None:
        """Test loading a file with invalid YAML syntax."""
        config_manager = ConfigManager(config_path=invalid_config_file)
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager.load_config()
        
        assert "Invalid YAML" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert "syntax" in " ".join(exc_info.value.recovery_steps)

    def test_load_with_invalid_values(self, malformed_config_file: Path, mocked_logging: None) -> None:
        """Test loading a config with valid YAML but invalid config values."""
        config_manager = ConfigManager(config_path=malformed_config_file)
        
        # Should raise ConfigError for first invalid value encountered
        with pytest.raises(ConfigError) as exc_info:
            config_manager.load_config()
        
        assert "Invalid" in str(exc_info.value)
        assert exc_info.value.config_key is not None
        assert "expected_type" in dir(exc_info.value)

    def test_create_config_if_not_exists(self, temp_config_dir: Path) -> None:
        """Test that load_config creates a config file if it doesn't exist."""
        config_path = temp_config_dir / "new_config.yml"
        config_manager = ConfigManager(config_path=config_path)
        
        # File doesn't exist yet
        assert not config_path.exists()
        
        # Load should create it
        config = config_manager.load_config()
        
        # File should now exist and config should be valid
        assert config_path.exists()
        assert isinstance(config, TransferConfig)
        
    def test_fall_back_to_defaults_on_error(
        self, 
        temp_config_dir: Path, 
        mocker: "MockerFixture", 
        mocked_logging: None
    ) -> None:
        """Test falling back to default config when parsing fails with unrecoverable error."""
        config_path = temp_config_dir / "corrupted_config.yml"
        
        # Create a ConfigManager with this path
        config_manager = ConfigManager(config_path=config_path)
        
        # Mock _parse_config to simulate unrecoverable error
        mocker.patch.object(
            config_manager, 
            '_parse_config',
            side_effect=Exception("Simulated unrecoverable error")
        )
        
        # Should return default config instead of raising
        config = config_manager.load_config()
        
        # Should be a valid config with default values
        assert isinstance(config, TransferConfig)
        # Verify some default values are present
        assert config.rename_with_timestamp is True
        assert config.filename_template == "{original}_{timestamp}"
        
    def test_permission_denied_on_load(
        self, 
        temp_config_dir: Path, 
        mocker: "MockerFixture", 
        mocked_logging: None
    ) -> None:
        """Test handling permission denied when loading config file."""
        config_path = temp_config_dir / "locked_config.yml"
        config_path.touch()
        
        # Create a ConfigManager with this path
        config_manager = ConfigManager(config_path=config_path)
        
        # Mock open to raise PermissionError
        mock_open = mocker.patch('builtins.open')
        mock_open.side_effect = PermissionError("Permission denied reading file")
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager.load_config()
        
        assert "Permission denied" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert "permissions" in str(" ".join(exc_info.value.recovery_steps))


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""
    
    def test_full_configuration_cycle(self, temp_config_dir: Path) -> None:
        """Test the complete lifecycle of configuration management."""
        # Create config path
        config_path = temp_config_dir / "lifecycle_config.yml"
        
        # 1. Initialize manager
        config_manager = ConfigManager(config_path=config_path)
        
        # 2. Load initial config (should create default)
        initial_config = config_manager.load_config()
        assert config_path.exists()
        assert initial_config.rename_with_timestamp is True  # Default value
        
        # 3. Modify configuration
        modified_config = TransferConfig()
        modified_config.rename_with_timestamp = False
        modified_config.preserve_original_filename = False
        modified_config.filename_template = "transfer_{timestamp}"
        modified_config.media_extensions = ['.mp4', '.mov']  # Limited set
        
        # 4. Save modified config
        config_manager.save_config(modified_config)
        
        # 5. Create new manager and load config
        new_manager = ConfigManager(config_path=config_path)
        loaded_config = new_manager.load_config()
        
        # 6. Verify changes were saved and loaded correctly
        assert loaded_config.rename_with_timestamp is False
        assert loaded_config.preserve_original_filename is False
        assert loaded_config.filename_template == "transfer_{timestamp}"
        assert loaded_config.media_extensions == ['.mp4', '.mov']
        
        # But other defaults should remain unchanged
        assert loaded_config.media_only_transfer is True
        assert loaded_config.create_date_folders is True
    
    def test_error_recovery_escalation(
        self, 
        temp_config_dir: Path, 
        mocker: "MockerFixture"
    ) -> None:
        """Test that ConfigManager properly escalates errors for handling."""
        config_path = temp_config_dir / "escalation_config.yml"
        
        # Set up a series of mock errors to test escalation
        parse_mock = mocker.patch('yaml.safe_load')
        parse_mock.side_effect = yaml.YAMLError("Invalid YAML syntax")
        
        # Create manager
        config_manager = ConfigManager(config_path=config_path)
        
        # Should raise ConfigError with details
        with pytest.raises(ConfigError) as exc_info:
            config_manager.load_config()
        
        # Error should be properly escalated with appropriate context
        assert "Invalid YAML" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert len(exc_info.value.recovery_steps) > 0
        
    def test_log_active_configuration(
        self,
        valid_config_file: Path,
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture"
    ) -> None:
        """Test that _log_active_configuration logs all configuration settings."""
        # Set log level to capture info logs
        caplog.set_level(logging.INFO)
        
        # Load a valid configuration
        config_manager = ConfigManager(config_path=valid_config_file)
        config = config_manager.load_config()
        
        # Manually trigger logging to ensure it's captured
        config_manager._log_active_configuration()
        
        # Check that important sections are logged
        assert "Active Configuration" in caplog.text
        assert "File Handling" in caplog.text
        assert "Media Transfer Settings" in caplog.text
        assert "Directory Structure" in caplog.text
        assert "Video Processing" in caplog.text
        
        # Check specific values
        log_text = caplog.text.lower()
        assert f"timestamp renaming: {str(config.rename_with_timestamp).lower()}" in log_text
        assert f"media only: {str(config.media_only_transfer).lower()}" in log_text
        
    def test_no_logging_when_config_is_none(
        self,
        mocker: "MockerFixture",
        caplog: "LogCaptureFixture"
    ) -> None:
        """Test that _log_active_configuration does nothing when _config is None."""
        # Set log level to capture all logs
        caplog.set_level(logging.DEBUG)
        
        # Create config manager but don't load config
        config_manager = ConfigManager()
        
        # Clear the log
        caplog.clear()
        
        # Call the method with no config loaded
        config_manager._log_active_configuration()
        
        # Should not generate any logs
        assert "Active Configuration" not in caplog.text
        assert "File Handling" not in caplog.text


class TestConfigManagerGetConfig:
    """Tests for ConfigManager's get_config method."""
    
    def test_get_config_after_load(self, valid_config_file: Path) -> None:
        """Test that get_config returns the loaded config."""
        config_manager = ConfigManager(config_path=valid_config_file)
        loaded_config = config_manager.load_config()
        
        # Get the config again
        retrieved_config = config_manager.get_config()
        
        # Should be the same object
        assert retrieved_config is loaded_config
        
    def test_get_config_before_load(self) -> None:
        """Test that get_config raises ConfigError if called before load_config."""
        config_manager = ConfigManager()
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager.get_config()
        
        assert "Configuration not loaded" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert "Call load_config()" in str(exc_info.value.recovery_steps)


class TestConfigManagerSaveConfig:
    """Tests for ConfigManager's save_config method."""
    
    def test_save_config(self, temp_config_dir: Path) -> None:
        """Test that save_config writes the config to disk."""
        config_path = temp_config_dir / "saved_config.yml"
        
        # Create manager and a modified config
        config_manager = ConfigManager(config_path=config_path)
        config = TransferConfig()
        config.rename_with_timestamp = False
        config.filename_template = "custom_{original}"
        
        # Save the modified config
        config_manager.save_config(config)
        
        # File should exist
        assert config_path.exists()
        
        # Load the saved config to verify
        new_manager = ConfigManager(config_path=config_path)
        loaded_config = new_manager.load_config()
        
        # Values should match what we saved
        assert loaded_config.rename_with_timestamp is False
        assert loaded_config.filename_template == "custom_{original}"
    
    def test_save_config_to_custom_path(self, temp_config_dir: Path) -> None:
        """Test saving config to a path different from the one in config_manager."""
        original_path = temp_config_dir / "original_config.yml"
        custom_path = temp_config_dir / "custom_path" / "config.yml"
        
        # Create manager with original path
        config_manager = ConfigManager(config_path=original_path)
        config = TransferConfig()
        
        # Save to custom path
        config_manager.save_config(config, path=custom_path)
        
        # Custom path should exist, original should not
        assert custom_path.exists()
        assert not original_path.exists()
    
    def test_save_without_path(self) -> None:
        """Test that save_config raises ConfigError if no path is available."""
        # Create manager without a path
        config_manager = ConfigManager()
        config = TransferConfig()
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager.save_config(config)
        
        assert "No configuration path specified" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert "Provide a path" in str(exc_info.value.recovery_steps)
    
    def test_save_permission_denied(
        self, 
        unreadable_config_dir: Path, 
        mocker: "MockerFixture"
    ) -> None:
        """Test handling permission denied when saving config."""
        # Skip test on Windows where permission handling is different
        if os.name == 'nt':
            pytest.skip("Permission tests not applicable on Windows")
            
        config_path = unreadable_config_dir / "config.yml"
        config_manager = ConfigManager(config_path=config_path)
        config = TransferConfig()
        
        # Mock to simulate permission error
        mocker.patch.object(
            Path, 
            'mkdir',
            side_effect=PermissionError("Permission denied creating directory")
        )
        
        # Should raise ConfigError
        with pytest.raises(ConfigError) as exc_info:
            config_manager.save_config(config)
        
        assert "Permission denied" in str(exc_info.value)
        assert "recovery_steps" in dir(exc_info.value)
        assert "permissions" in str(" ".join(exc_info.value.recovery_steps))