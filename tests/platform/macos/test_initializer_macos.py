import pytest
from unittest import mock
from src.platform.macos.initializer_macos import MacOSInitializer
from src.core.exceptions import DisplayError, StorageError

def test_initialize_hardware_logs(caplog):
    init = MacOSInitializer()
    with caplog.at_level('DEBUG'):
        init.initialize_hardware()
    assert "MacOS hardware initialization" in caplog.text

def test_initialize_display_success(monkeypatch):
    init = MacOSInitializer()
    fake_display = mock.Mock()
    monkeypatch.setattr('src.platform.macos.initializer_macos.RichDisplay', lambda: fake_display)
    init.initialize_display()
    assert hasattr(init, 'display')
    fake_display.clear.assert_called_once()

def test_initialize_display_failure(monkeypatch):
    init = MacOSInitializer()
    monkeypatch.setattr('src.platform.macos.initializer_macos.RichDisplay', mock.Mock(side_effect=Exception('fail')))
    with pytest.raises(DisplayError) as excinfo:
        init.initialize_display()
    assert "Failed to initialize display" in str(excinfo.value)

def test_initialize_storage_success(monkeypatch):
    init = MacOSInitializer()
    fake_storage = mock.Mock()
    monkeypatch.setattr('src.platform.macos.initializer_macos.MacOSStorage', lambda: fake_storage)
    init.initialize_storage()
    assert hasattr(init, 'storage')

def test_initialize_storage_failure(monkeypatch):
    init = MacOSInitializer()
    monkeypatch.setattr('src.platform.macos.initializer_macos.MacOSStorage', mock.Mock(side_effect=Exception('fail')))
    with pytest.raises(StorageError) as excinfo:
        init.initialize_storage()
    assert "Failed to initialize storage" in str(excinfo.value)

def test_cleanup_success(monkeypatch, caplog):
    init = MacOSInitializer()
    fake_display = mock.Mock()
    init.display = fake_display
    with caplog.at_level('INFO'):
        init.cleanup()
    fake_display.clear.assert_called_once()
    assert "Performing macOS cleanup" in caplog.text

def test_cleanup_no_display(caplog):
    init = MacOSInitializer()
    init.display = None
    with caplog.at_level('INFO'):
        init.cleanup()
    assert "Performing macOS cleanup" in caplog.text

def test_cleanup_error(monkeypatch, caplog):
    init = MacOSInitializer()
    fake_display = mock.Mock()
    fake_display.clear.side_effect = Exception('fail')
    init.display = fake_display
    with caplog.at_level('ERROR'):
        init.cleanup()
    assert "Cleanup error" in caplog.text 