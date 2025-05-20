import pytest
from pathlib import Path
from unittest import mock
from src.core.directory_handler import DirectoryHandler
from src.core.config_manager import TransferConfig
import os
import sys

@pytest.fixture
def minimal_config():
    return TransferConfig(
        rename_with_timestamp=True,
        preserve_original_filename=True,
        filename_template="{original}_{timestamp}",
        timestamp_format="%Y%m%d_%H%M%S",
        create_mhl_files=False,
        media_only_transfer=True,
        preserve_folder_structure=True,
        transfer_destination="/tmp/transfer",
        media_extensions=[".mp4"],
        create_date_folders=False,
        date_folder_format="%Y/%m/%d",
        create_device_folders=False,
        device_folder_template="{device_name}",
        generate_proxies=False,
        proxy_subfolder="proxies",
        include_proxy_watermark=False,
        proxy_watermark_path="",
        enable_sounds=False,
        sound_volume=0,
        success_sound_path="",
        error_sound_path="",
        buffer_size=1024,
        verify_transfers=False,
        max_transfer_threads=1,
        log_level="INFO",
        log_file_rotation=1,
        log_file_max_size=1
    )

@pytest.mark.parametrize("input_name,expected", [
    ("My Device", "My_Device"),
    ("dev:ice*?", "device"),
    ("<bad>|name", "badname"),
    ("", "unnamed_device"),
    (None, "unnamed_device"),
    (123, "unnamed_device"),
])
def test_sanitize_name(input_name, expected, minimal_config):
    handler = DirectoryHandler(minimal_config)
    result = handler._sanitize_name(input_name)
    assert result == expected


def test_get_device_name_returns_sanitized(monkeypatch, minimal_config):
    handler = DirectoryHandler(minimal_config)
    fake_path = Path("/fake/device")
    # Should just return sanitized name of the path
    assert handler._get_device_name(fake_path) == "device"


def test_get_device_name_invalid_type(minimal_config):
    handler = DirectoryHandler(minimal_config)
    assert handler._get_device_name("not_a_path") == "unknown_device"


def test_ensure_directory_exists_creates(tmp_path, minimal_config):
    handler = DirectoryHandler(minimal_config)
    new_dir = tmp_path / "newdir"
    handler._ensure_directory_exists(new_dir)
    assert new_dir.exists() and new_dir.is_dir()


def test_ensure_directory_exists_permission_error(monkeypatch, minimal_config):
    handler = DirectoryHandler(minimal_config)
    with mock.patch.object(Path, "mkdir", side_effect=PermissionError):
        with pytest.raises(PermissionError):
            handler._ensure_directory_exists(Path("/root/forbidden"))


def test_create_organized_directory_base_only(tmp_path, minimal_config):
    handler = DirectoryHandler(minimal_config)
    result = handler.create_organized_directory(tmp_path, tmp_path)
    assert result == tmp_path
    assert tmp_path.exists()


def test_create_organized_directory_with_date(tmp_path, minimal_config):
    config = minimal_config.model_copy(update={"create_date_folders": True, "date_folder_format": "%Y-%m-%d"})
    handler = DirectoryHandler(config)
    result = handler.create_organized_directory(tmp_path, tmp_path, timestamp="2023-01-01")
    assert result == tmp_path / "2023-01-01"
    assert result.exists()


def test_create_organized_directory_with_device(tmp_path, minimal_config):
    config = minimal_config.model_copy(update={"create_device_folders": True})
    handler = DirectoryHandler(config)
    result = handler.create_organized_directory(tmp_path, tmp_path)
    expected = tmp_path / tmp_path.name
    assert result == expected
    assert result.exists()


def test_create_organized_directory_with_date_and_device(tmp_path, minimal_config):
    config = minimal_config.model_copy(update={"create_date_folders": True, "date_folder_format": "%Y-%m-%d", "create_device_folders": True})
    handler = DirectoryHandler(config)
    result = handler.create_organized_directory(tmp_path, tmp_path, timestamp="2023-01-01")
    # Should be tmp_path/2023-01-01/<device_name>
    expected = tmp_path / "2023-01-01" / tmp_path.name
    assert result == expected
    assert result.exists()


def test_create_organized_directory_error_fallback(tmp_path, minimal_config, monkeypatch):
    handler = DirectoryHandler(minimal_config)
    # Simulate error in _ensure_directory_exists for target_dir
    with mock.patch.object(handler, "_ensure_directory_exists", side_effect=[None, OSError, None]):
        result = handler.create_organized_directory(tmp_path, tmp_path)
        assert result == tmp_path 