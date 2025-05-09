import pytest
import yaml
from pathlib import Path
from src.core.config_manager import ConfigManager, TransferConfig

def write_yaml(path: Path, data: dict):
    with open(path, 'w') as f:
        yaml.dump(data, f)

def test_load_valid_config(tmp_path, monkeypatch):
    config_data = {"rename_with_timestamp": True, "media_only_transfer": False}
    config_path = tmp_path / "config.yml"
    write_yaml(config_path, config_data)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = mgr.load_config()
    assert config.rename_with_timestamp is True
    assert config.media_only_transfer is False
    assert isinstance(config, TransferConfig)

def test_load_creates_default_if_missing(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = mgr.load_config()
    assert config_path.exists()
    assert isinstance(config, TransferConfig)

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = TransferConfig(rename_with_timestamp=True, media_only_transfer=False)
    mgr.save_config(config)
    mgr2 = ConfigManager()
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    loaded = mgr2.load_config()
    assert loaded.rename_with_timestamp is True
    assert loaded.media_only_transfer is False

def test_load_malformed_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    # Write malformed YAML
    with open(config_path, 'w') as f:
        f.write("rename_with_timestamp: true\n  bad_indent\n: value\n")
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = mgr.load_config()
    # Should fallback to defaults
    assert isinstance(config, TransferConfig)
    assert hasattr(config, "rename_with_timestamp")

def test_update_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    mgr.load_config()
    updated = mgr.update_config({"rename_with_timestamp": True, "sound_volume": 99})
    assert updated.rename_with_timestamp is True
    assert updated.sound_volume == 99
    # Ensure persisted
    mgr2 = ConfigManager()
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    loaded = mgr2.load_config()
    assert loaded.rename_with_timestamp is True
    assert loaded.sound_volume == 99

def test_media_extensions_validator():
    config = TransferConfig(media_extensions=["mp4", ".mov", "jpg"])
    assert all(ext.startswith(".") for ext in config.media_extensions)
    assert ".mp4" in config.media_extensions
    assert ".jpg" in config.media_extensions

def test_buffer_size_validator():
    config = TransferConfig(buffer_size=1)  # Too small
    assert config.buffer_size == 4096
    config = TransferConfig(buffer_size=200 * 1024 * 1024)  # Too large
    assert config.buffer_size == 100 * 1024 * 1024
    config = TransferConfig(buffer_size=1024 * 1024)
    assert config.buffer_size == 1024 * 1024

def test_log_level_validator():
    config = TransferConfig(log_level="debug")
    assert config.log_level == "DEBUG"
    config = TransferConfig(log_level="invalid")
    assert config.log_level == "INFO"
    config = TransferConfig(log_level="ERROR")
    assert config.log_level == "ERROR" 