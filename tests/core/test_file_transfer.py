import pytest
from pathlib import Path
from unittest import mock
from src.core.file_transfer import FileTransfer
from src.core.config_manager import TransferConfig

class DummyDisplay:
    def __init__(self): self.errors = []
    def show_error(self, msg): self.errors.append(msg)

class DummySoundManager:
    def __init__(self): self.played_success = False; self.played_error = False
    def play_success(self): self.played_success = True
    def play_error(self): self.played_error = True

class DummyStorage:
    pass

class DummyStateManager:
    def __init__(self, utility=False): self._utility = utility
    def is_utility(self): return self._utility

@pytest.fixture
def dummy_display():
    return DummyDisplay()

@pytest.fixture
def dummy_sound():
    return DummySoundManager()

@pytest.fixture
def dummy_storage():
    return DummyStorage()

@pytest.fixture
def dummy_state():
    return DummyStateManager()

@pytest.fixture
def dummy_config(tmp_path):
    return TransferConfig(
        transfer_destination=str(tmp_path),
        enable_sounds=True,
        proxy_subfolder="proxies",
        media_extensions=[".mp4"],
        log_level="INFO"
    )

@pytest.fixture
def file_transfer(dummy_state, dummy_display, dummy_storage, dummy_config, dummy_sound):
    return FileTransfer(
        state_manager=dummy_state,
        display=dummy_display,
        storage=dummy_storage,
        config=dummy_config,
        sound_manager=dummy_sound
    )

# --- _play_sound ---
def test_play_sound_success(file_transfer, dummy_sound):
    file_transfer._play_sound(success=True)
    assert dummy_sound.played_success
    file_transfer._play_sound(success=False)
    assert dummy_sound.played_error

# --- _check_utility_mode ---
def test_check_utility_mode_false(dummy_display, dummy_storage, dummy_config, dummy_sound):
    ft = FileTransfer(DummyStateManager(utility=True), dummy_display, dummy_storage, dummy_config, dummy_sound)
    assert not ft._check_utility_mode()
    assert "In utility mode" in dummy_display.errors[-1]

def test_check_utility_mode_true(dummy_state, dummy_display, dummy_storage, dummy_config, dummy_sound):
    ft = FileTransfer(dummy_state, dummy_display, dummy_storage, dummy_config, dummy_sound)
    assert ft._check_utility_mode() is True

# --- _validate_transfer_preconditions ---
def test_validate_transfer_preconditions_existing_dir(tmp_path, file_transfer):
    d = tmp_path / "dest"
    d.mkdir()
    assert file_transfer._validate_transfer_preconditions(d) is True

def test_validate_transfer_preconditions_no_dest(file_transfer):
    assert not file_transfer._validate_transfer_preconditions(None)
    assert "No destination" in file_transfer.display.errors[-1]

def test_validate_transfer_preconditions_invalid_type(file_transfer):
    assert not file_transfer._validate_transfer_preconditions(123)
    assert "Invalid path type" in file_transfer.display.errors[-1]

def test_validate_transfer_preconditions_not_dir(tmp_path, file_transfer):
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert not file_transfer._validate_transfer_preconditions(f)
    assert "Not a directory" in file_transfer.display.errors[-1]

def test_validate_transfer_preconditions_no_write(tmp_path, file_transfer, monkeypatch):
    d = tmp_path / "nowrite"
    d.mkdir()
    monkeypatch.setattr("os.access", lambda path, mode: False)
    assert not file_transfer._validate_transfer_preconditions(d)
    assert "Write permission denied" in file_transfer.display.errors[-1]

def test_validate_transfer_preconditions_create_dir(tmp_path, file_transfer):
    d = tmp_path / "newdir"
    assert file_transfer._validate_transfer_preconditions(d) is True
    assert d.exists()

def test_validate_transfer_preconditions_create_dir_fail(tmp_path, file_transfer, monkeypatch):
    d = tmp_path / "faildir"
    monkeypatch.setattr(Path, "mkdir", mock.Mock(side_effect=OSError("fail")))
    assert not file_transfer._validate_transfer_preconditions(d)
    assert "Create dir failed" in file_transfer.display.errors[-1]

# --- _prepare_for_transfer ---
def test_prepare_for_transfer_valid(tmp_path, file_transfer, monkeypatch):
    d = tmp_path / "dest"
    d.mkdir()
    monkeypatch.setattr("src.core.file_transfer.validate_source_path", lambda p: True)
    assert file_transfer._prepare_for_transfer(tmp_path, d) is True

def test_prepare_for_transfer_invalid_dest(file_transfer, monkeypatch):
    monkeypatch.setattr("src.core.file_transfer.validate_source_path", lambda p: True)
    assert not file_transfer._prepare_for_transfer("bad", 123)

def test_prepare_for_transfer_invalid_source(tmp_path, file_transfer, monkeypatch):
    d = tmp_path / "dest"
    d.mkdir()
    monkeypatch.setattr("src.core.file_transfer.validate_source_path", lambda p: False)
    assert not file_transfer._prepare_for_transfer(tmp_path, d)
    assert "Source Error" in file_transfer.display.errors[-1]

# --- _setup_transfer_environment ---
def test_setup_transfer_environment_success(tmp_path, file_transfer, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    monkeypatch.setattr(file_transfer.directory_handler, "create_organized_directory", lambda *a, **kw: dst)
    file_transfer.config.create_date_folders = False
    result = file_transfer._setup_transfer_environment(src, dst)
    assert result is not None
    assert result[1] == dst

def test_setup_transfer_environment_dir_fail(tmp_path, file_transfer, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    monkeypatch.setattr(file_transfer.directory_handler, "create_organized_directory", mock.Mock(side_effect=Exception("fail")))
    file_transfer.config.create_date_folders = False
    result = file_transfer._setup_transfer_environment(src, dst)
    assert result is None
    assert "Dir Create Error" in file_transfer.display.errors[-1]

# --- _prepare_files_for_transfer ---
def test_prepare_files_for_transfer_success(tmp_path, file_transfer, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    monkeypatch.setattr("src.core.file_transfer.get_transferable_files", lambda *a, **kw: [src / "a.mp4"])
    monkeypatch.setattr("src.core.file_transfer.calculate_transfer_totals", lambda files: (files, 100, 1))
    monkeypatch.setattr("src.core.file_transfer.verify_space_requirements", lambda *a, **kw: True)
    file_transfer.config.preserve_folder_structure = False
    result = file_transfer._prepare_files_for_transfer(src, dst, dst)
    assert result[1] == 100 and result[2] == 1

def test_prepare_files_for_transfer_no_files(tmp_path, file_transfer, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    monkeypatch.setattr("src.core.file_transfer.get_transferable_files", lambda *a, **kw: [])
    file_transfer.config.media_only_transfer = False
    result = file_transfer._prepare_files_for_transfer(src, dst, dst)
    assert result is None
    assert "No Files Found" in file_transfer.display.errors[-1]

def test_prepare_files_for_transfer_calc_totals_fail(tmp_path, file_transfer, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    monkeypatch.setattr("src.core.file_transfer.get_transferable_files", lambda *a, **kw: [src / "a.mp4"])
    monkeypatch.setattr("src.core.file_transfer.calculate_transfer_totals", mock.Mock(side_effect=Exception("fail")))
    result = file_transfer._prepare_files_for_transfer(src, dst, dst)
    assert result is None
    assert "Size Calc Error" in file_transfer.display.errors[-1] 