# tests/platform/macos/test_storage.py

import pytest
import os
import platform
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.platform.macos.storage import MacOSStorage

# Skip all tests in this module if not on macOS
pytestmark = pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="MacOS storage tests can only run on macOS"
)

@pytest.fixture
def macos_storage():
    """Create a MacOSStorage instance"""
    return MacOSStorage()

@pytest.fixture
def mock_statvfs():
    """Mock statvfs for non-macOS systems"""
    class MockStatVFS:
        f_blocks = 1000000
        f_bsize = 4096
        f_frsize = 4096
        f_bfree = 500000
        
    if not hasattr(os, 'statvfs'):
        with patch('os.statvfs', return_value=MockStatVFS()):
            yield
    else:
        yield

@pytest.fixture
def mock_volumes(tmp_path):
    """Create mock volume structure"""
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    return volumes

def test_initialization(macos_storage):
    """Test storage initialization"""
    assert macos_storage.dump_drive_mountpoint is None

@patch('pathlib.Path.iterdir')
def test_get_available_drives(mock_iterdir, mock_volumes, macos_storage):
    """Test getting available drives"""
    # Create mock drives
    drive1 = MagicMock(spec=Path)
    drive1.is_mount.return_value = True
    drive2 = MagicMock(spec=Path)
    drive2.is_mount.return_value = False
    
    mock_iterdir.return_value = [drive1, drive2]
    
    drives = macos_storage.get_available_drives()
    assert len(drives) == 1
    assert drives[0] == drive1

def test_get_drive_info(macos_storage, tmp_path, mock_statvfs):
    """Test getting drive information"""
    with patch('os.statvfs') as mock_statvfs_fn:
        mock_statvfs_fn.return_value = MagicMock(
            f_blocks=1000000,
            f_bsize=4096,
            f_frsize=4096,
            f_bfree=500000
        )
        info = macos_storage.get_drive_info(tmp_path)
        assert 'total' in info
        assert 'used' in info
        assert 'free' in info
        assert info['total'] > 0
        assert info['free'] > 0
        assert info['used'] >= 0

def test_is_drive_mounted(macos_storage, tmp_path):
    """Test drive mount status check"""
    with patch.object(Path, 'is_mount') as mock_is_mount:
        mock_is_mount.return_value = True
        assert macos_storage.is_drive_mounted(tmp_path)
        
        mock_is_mount.return_value = False
        assert not macos_storage.is_drive_mounted(tmp_path)

@patch('subprocess.run')
@patch('time.sleep')
def test_unmount_drive_success(mock_sleep, mock_run, macos_storage, tmp_path):
    """Test successful drive unmounting"""
    mock_run.return_value = MagicMock(returncode=0)
    
    result = macos_storage.unmount_drive(tmp_path)
    assert result
    
    # Verify sync was called before unmount
    sync_call = mock_run.call_args_list[0]
    assert sync_call[0][0] == ['sync']
    
    # Verify diskutil unmount command
    unmount_call = mock_run.call_args_list[1]
    assert unmount_call[0][0] == ['diskutil', 'unmount', str(tmp_path)]

@patch('subprocess.run')
def test_unmount_drive_failure(mock_run, macos_storage, tmp_path):
    """Test failed drive unmounting"""
    mock_run.side_effect = subprocess.CalledProcessError(1, 'diskutil', stderr="Mock error")
    
    result = macos_storage.unmount_drive(tmp_path)
    assert not result

def test_get_dump_drive(macos_storage, tmp_path):
    """Test getting dump drive location"""
    assert macos_storage.get_dump_drive() is None
    
    macos_storage.dump_drive_mountpoint = tmp_path
    assert macos_storage.get_dump_drive() == tmp_path

def test_set_dump_drive_valid(macos_storage, tmp_path):
    """Test setting valid dump drive location"""
    macos_storage.set_dump_drive(tmp_path)
    assert macos_storage.dump_drive_mountpoint == tmp_path

def test_set_dump_drive_invalid(macos_storage):
    """Test setting invalid dump drive location"""
    with pytest.raises(ValueError):
        macos_storage.set_dump_drive(Path("/nonexistent/path"))

@patch('time.sleep')
def test_wait_for_new_drive(mock_sleep, macos_storage):
    """Test waiting for new drive"""
    initial_drives = [Path("/Volumes/Drive1")]
    new_drive = Path("/Volumes/NewDrive")
    
    # Mock get_available_drives to simulate drive appearance
    call_count = 0
    def mock_get_drives():
        nonlocal call_count
        call_count += 1
        if call_count > 2:  # Return new drive after 2 checks
            return initial_drives + [new_drive]
        return initial_drives
    
    with patch.object(macos_storage, 'get_available_drives', side_effect=mock_get_drives):
        detected_drive = macos_storage.wait_for_new_drive(initial_drives)
        assert detected_drive == new_drive
        assert mock_sleep.call_count >= 2

@patch('time.sleep')
def test_wait_for_drive_removal(mock_sleep, macos_storage, tmp_path):
    """Test waiting for drive removal"""
    drive_path = tmp_path / "test_drive"
    
    # Mock existence and mount status checks
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.is_mount') as mock_is_mount:
        mock_exists.side_effect = [True, True, False]
        mock_is_mount.side_effect = [True, True, False]
        
        macos_storage.wait_for_drive_removal(drive_path)
        assert mock_sleep.call_count >= 1

def test_has_enough_space(macos_storage, tmp_path, mock_statvfs):
    """Test space availability check"""
    with patch('os.statvfs') as mock_statvfs_fn:
        mock_statvfs_fn.return_value = MagicMock(
            f_blocks=1000000,
            f_bsize=4096,
            f_frsize=4096,
            f_bfree=500000
        )
        
        # Test with space requirements
        assert macos_storage.has_enough_space(tmp_path, 1024 * 1024)  # 1MB
        assert not macos_storage.has_enough_space(tmp_path, 1024 * 1024 * 1024 * 1024)  # 1TB

@pytest.mark.parametrize("mock_returncode,expected", [
    (0, True),   # Success
    (1, False),  # Failure
])
@patch('subprocess.run')
def test_unmount_drive_with_different_results(mock_run, mock_returncode, expected, macos_storage, tmp_path):
    """Test unmount drive with different return codes"""
    mock_result = MagicMock()
    mock_result.returncode = mock_returncode
    mock_result.stderr = "Mock error" if mock_returncode != 0 else ""
    mock_run.return_value = mock_result
    
    result = macos_storage.unmount_drive(tmp_path)
    assert result == expected

def test_get_removable_drives(macos_storage):
    """Test getting removable drives"""
    with patch.object(macos_storage, 'get_available_drives') as mock_get_drives:
        drive1 = Path("/Volumes/EXTERNAL1")
        drive2 = Path("/Volumes/EXTERNAL2")
        mock_get_drives.return_value = [drive1, drive2]
        
        drives = macos_storage.get_available_drives()
        assert len(drives) == 2
        assert drive1 in drives
        assert drive2 in drives