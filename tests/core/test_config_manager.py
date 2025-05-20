from operator import truediv
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

def test_tutorial_mode_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    # Explicitly set tutorial_mode True
    config_data = {"tutorial_mode": True}
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = mgr.load_config()
    assert config.tutorial_mode is True
    # Save and reload
    config.tutorial_mode = False
    mgr.save_config(config)
    mgr2 = ConfigManager()
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    loaded = mgr2.load_config()
    assert loaded.tutorial_mode is False
    # Default if not set
    config_path2 = tmp_path / "config2.yml"
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path2])
    mgr3 = ConfigManager()
    config3 = mgr3.load_config()
    assert config3.tutorial_mode is True

def test_config_version_added_and_migrated(tmp_path, monkeypatch, caplog):
    config_data = {"rename_with_timestamp": True, "media_only_transfer": False}  # No version
    config_path = tmp_path / "config.yml"
    write_yaml(config_path, config_data)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    with caplog.at_level("WARNING"):
        config = mgr.load_config()
    from src import __version__
    assert config.version == __version__
    assert "Migrating config" in caplog.text
    # Should add missing fields
    assert hasattr(config, "tutorial_mode")
    # Should remove unknown fields
    with open(config_path) as f:
        loaded = yaml.safe_load(f)
    assert "version" in loaded
    assert loaded["version"] == __version__

def test_config_old_version_triggers_migration(tmp_path, monkeypatch, caplog):
    config_data = {"version": "0.0.1", "rename_with_timestamp": True}
    config_path = tmp_path / "config.yml"
    write_yaml(config_path, config_data)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    with caplog.at_level("WARNING"):
        config = mgr.load_config()
    from src import __version__
    assert config.version == __version__
    assert "Migrating config" in caplog.text

def test_config_removes_unknown_fields(tmp_path, monkeypatch):
    config_data = {"rename_with_timestamp": True, "unknown_field": 123}
    config_path = tmp_path / "config.yml"
    write_yaml(config_path, config_data)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = mgr.load_config()
    assert not hasattr(config, "unknown_field")
    with open(config_path) as f:
        loaded = yaml.safe_load(f)
    assert "unknown_field" not in loaded

def test_config_saves_with_current_version(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    config = TransferConfig(rename_with_timestamp=True)
    mgr.save_config(config)
    from src import __version__
    with open(config_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded["version"] == __version__

def test_config_backup_and_preserve_values(tmp_path, monkeypatch):
    config_data = {"rename_with_timestamp": True, "sound_volume": 99, "buffer_size": 1}  # buffer_size is invalid
    config_path = tmp_path / "config.yml"
    write_yaml(config_path, config_data)
    monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATHS", [config_path])
    mgr = ConfigManager()
    backup_path = config_path.with_suffix(".yml.bak")
    if backup_path.exists():
        backup_path.unlink()  # Ensure clean state
    config = mgr.load_config()
    # Backup should exist
    assert backup_path.exists()
    # User value preserved
    assert config.rename_with_timestamp is True
    assert config.sound_volume == 99
    # Invalid value replaced with default
    assert config.buffer_size == 4096 