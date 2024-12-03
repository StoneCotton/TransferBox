# tests/core/test_platform_manager.py

import pytest
import platform
import sys
from unittest.mock import patch, MagicMock
from src.core.platform_manager import PlatformManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface

# Mock classes for testing
class MockRaspberryPiDisplay(DisplayInterface):
    def show_status(self, message: str, line: int = 0) -> None:
        pass
    def show_progress(self, progress) -> None:
        pass
    def show_error(self, message: str) -> None:
        pass
    def clear(self) -> None:
        pass

class MockMacOSDisplay(DisplayInterface):
    def show_status(self, message: str, line: int = 0) -> None:
        pass
    def show_progress(self, progress) -> None:
        pass
    def show_error(self, message: str) -> None:
        pass
    def clear(self) -> None:
        pass

class MockWindowsDisplay(DisplayInterface):
    def show_status(self, message: str, line: int = 0) -> None:
        pass
    def show_progress(self, progress) -> None:
        pass
    def show_error(self, message: str) -> None:
        pass
    def clear(self) -> None:
        pass

class MockStorage(StorageInterface):
    def get_available_drives(self):
        return []
    def get_drive_info(self, path):
        return {}
    def is_drive_mounted(self, path):
        return True
    def unmount_drive(self, path):
        return True

# Test fixtures and patches
@pytest.fixture
def mock_platform_linux():
    with patch('platform.system', return_value='Linux'):
        yield

@pytest.fixture
def mock_platform_darwin():
    with patch('platform.system', return_value='Darwin'):
        yield

@pytest.fixture
def mock_platform_windows():
    with patch('platform.system', return_value='Windows'):
        yield

@pytest.fixture
def mock_raspberry_pi_detection():
    def mock_open(*args, **kwargs):
        return MagicMock(read=MagicMock(return_value='Hardware : Raspberry Pi'))
    with patch('builtins.open', mock_open):
        yield

@pytest.fixture
def mock_not_raspberry_pi():
    def mock_open(*args, **kwargs):
        return MagicMock(read=MagicMock(return_value='Hardware : Other Device'))
    with patch('builtins.open', mock_open):
        yield

# Tests for platform detection
def test_get_platform_windows(mock_platform_windows):
    """Test Windows platform detection"""
    assert PlatformManager.get_platform() == "windows"

def test_get_platform_macos(mock_platform_darwin):
    """Test macOS platform detection"""
    assert PlatformManager.get_platform() == "darwin"

def test_get_platform_raspberry_pi(mock_platform_linux, mock_raspberry_pi_detection):
    """Test Raspberry Pi detection"""
    with patch('builtins.open', mock_open := MagicMock()) as m:
        mock_open.return_value.__enter__.return_value.read.return_value = 'Hardware : BCM2835\nRevision : c03111\nSerial : 00000000904a7f26\nModel : Raspberry Pi'
        assert PlatformManager.get_platform() == "raspberry_pi"

def test_get_platform_linux_not_raspberry_pi(mock_platform_linux, mock_not_raspberry_pi):
    """Test Linux platform that's not Raspberry Pi"""
    with patch('builtins.open', side_effect=FileNotFoundError):
        # On non-Raspberry Pi Linux, should return "linux"
        assert PlatformManager.get_platform() == "linux"

# Tests for display creation
@pytest.mark.parametrize("platform_name,expected_display", [
    pytest.param("raspberry_pi", "RaspberryPiDisplay", 
                marks=pytest.mark.skipif(platform.system() != 'Linux', 
                reason="Raspberry Pi tests only run on Linux")),
    ("darwin", "MacOSDisplay"),
    ("windows", "WindowsDisplay")
])
def test_create_display(platform_name, expected_display):
    """Test display creation for different platforms"""
    with patch.object(PlatformManager, 'get_platform', return_value=platform_name):
        if platform_name == "raspberry_pi" and platform.system() != 'Linux':
            with pytest.raises(ModuleNotFoundError):
                PlatformManager.create_display()
        else:
            display = PlatformManager.create_display()
            assert expected_display in display.__class__.__name__

def test_create_display_unsupported_platform():
    """Test display creation for unsupported platform"""
    with patch.object(PlatformManager, 'get_platform', return_value="unsupported"):
        with pytest.raises(NotImplementedError):
            PlatformManager.create_display()

# Tests for storage creation
@pytest.mark.parametrize("platform_name,expected_storage", [
    pytest.param("raspberry_pi", "RaspberryPiStorage", 
                marks=pytest.mark.skipif(platform.system() != 'Linux', 
                reason="Raspberry Pi tests only run on Linux")),
    ("darwin", "MacOSStorage"),
    ("windows", "WindowsStorage")
])
def test_create_storage(platform_name, expected_storage):
    """Test storage creation for different platforms"""
    with patch.object(PlatformManager, 'get_platform', return_value=platform_name):
        if platform_name == "raspberry_pi" and platform.system() != 'Linux':
            with pytest.raises(ModuleNotFoundError):
                PlatformManager.create_storage()
        else:
            storage = PlatformManager.create_storage()
            assert expected_storage in storage.__class__.__name__

def test_create_storage_unsupported_platform():
    """Test storage creation for unsupported platform"""
    with patch.object(PlatformManager, 'get_platform', return_value="unsupported"):
        with pytest.raises(NotImplementedError):
            PlatformManager.create_storage()

# Integration tests
def test_platform_specific_components():
    """Test that platform-specific components are created correctly"""
    platform_name = PlatformManager.get_platform()
    
    # Create components
    display = PlatformManager.create_display()
    storage = PlatformManager.create_storage()
    
    # Verify interfaces
    assert isinstance(display, DisplayInterface)
    assert isinstance(storage, StorageInterface)
    
    # Verify platform-specific classes
    if platform_name == "windows":
        assert "Windows" in display.__class__.__name__
        assert "Windows" in storage.__class__.__name__
    elif platform_name == "darwin":
        assert "MacOS" in display.__class__.__name__
        assert "MacOS" in storage.__class__.__name__
    elif platform_name == "raspberry_pi":
        assert "RaspberryPi" in display.__class__.__name__
        assert "RaspberryPi" in storage.__class__.__name__

@pytest.mark.parametrize("test_platform", [
    pytest.param("raspberry_pi", 
                marks=pytest.mark.skipif(platform.system() != 'Linux', 
                reason="Raspberry Pi tests only run on Linux")),
    "windows",
    "darwin"
])
def test_component_creation_consistency(test_platform):
    """Test that components are created consistently for each platform"""
    with patch.object(PlatformManager, 'get_platform', return_value=test_platform):
        if test_platform == "raspberry_pi" and platform.system() != 'Linux':
            with pytest.raises(ModuleNotFoundError):
                PlatformManager.create_display()
        else:
            # Create multiple instances
            display1 = PlatformManager.create_display()
            display2 = PlatformManager.create_display()
            storage1 = PlatformManager.create_storage()
            storage2 = PlatformManager.create_storage()
            
            # Verify class consistency
            assert display1.__class__ == display2.__class__
            assert storage1.__class__ == storage2.__class__

def test_error_handling():
    """Test error handling for file system issues"""
    with patch('platform.system', return_value='Linux'):
        with patch('builtins.open', side_effect=PermissionError):
            # Should still return "linux" on error
            assert PlatformManager.get_platform() == "linux"

# Add skip markers for Raspberry Pi specific tests on non-Linux platforms
@pytest.mark.skipif(
    platform.system() != 'Linux',
    reason="Raspberry Pi tests only run on Linux"
)
@pytest.mark.parametrize("platform_name,expected_display", [
    ("raspberry_pi", "RaspberryPiDisplay"),
])
def test_create_display_raspberry_pi(platform_name, expected_display):
    """Test Raspberry Pi display creation"""
    with patch.object(PlatformManager, 'get_platform', return_value=platform_name):
        with pytest.raises(ModuleNotFoundError):
            PlatformManager.create_display()

# Similar skip for storage tests
@pytest.mark.skipif(
    platform.system() != 'Linux',
    reason="Raspberry Pi tests only run on Linux"
)
@pytest.mark.parametrize("platform_name,expected_storage", [
    ("raspberry_pi", "RaspberryPiStorage"),
])
def test_create_storage_raspberry_pi(platform_name, expected_storage):
    """Test Raspberry Pi storage creation"""
    with patch.object(PlatformManager, 'get_platform', return_value=platform_name):
        with pytest.raises(ModuleNotFoundError):
            PlatformManager.create_storage()