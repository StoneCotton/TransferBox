# src/platform/windows/storage.py

import os
import time
import subprocess
import logging
import ctypes
import string
import win32file
import win32con
import win32security
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.core.interfaces.storage import StorageInterface

logger = logging.getLogger(__name__)

class WindowsStorage(StorageInterface):
    def __init__(self):
        self.dump_drive_mountpoint: Optional[Path] = None

    def get_available_drives(self) -> List[Path]:
        """Get list of available drive letters"""
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = Path(f"{letter}:\\")
                if drive_path.exists():
                    drives.append(drive_path)
            bitmask >>= 1
        return drives

    def get_drive_info(self, path: Path) -> Dict[str, int]:
        """Get storage information for a drive"""
        try:
            # Get the root drive of the given path
            root_drive = Path(os.path.splitdrive(path)[0] + '\\')
            total, used, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
            ret = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                str(root_drive),
                ctypes.byref(free),
                ctypes.byref(total),
                None
            )
            if ret == 0:
                raise OSError("Failed to get drive information")
            return {
                'total': total.value,
                'free': free.value,
                'used': total.value - free.value
            }
        except Exception as e:
            logger.error(f"Error getting drive info for {path}: {e}")
            raise

    def is_drive_mounted(self, path: Path) -> bool:
        """Check if drive is mounted"""
        try:
            root_drive = Path(os.path.splitdrive(path)[0] + '\\')
            return root_drive.exists()
        except Exception:
            return False

    def unmount_drive(self, path: Path) -> bool:
        """
        Safely eject a drive in Windows using direct Windows API calls.
        
        Args:
            path: Path to the drive to eject
                
        Returns:
            True if successful, False otherwise
        """
        try:
            # First sync to ensure all writes are complete
            subprocess.run(['fsutil', 'volume', 'flush', str(path)], check=True, capture_output=True)
            
            # Allow system time to complete flush
            time.sleep(2)  # Increased from 1 to 2 seconds
            
            # Get volume name (e.g., "F:" from "F:\" or "F:/")
            volume_name = str(path.drive).rstrip(':\\/')
            
            # Use Windows API directly through ctypes
            import ctypes
            import ctypes.wintypes
            
            # Define necessary Windows API constants
            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ = 0x1
            FILE_SHARE_WRITE = 0x2
            OPEN_EXISTING = 0x3
            IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808

            # Create device path
            device_path = f"\\\\.\\{volume_name}:"

            # Open device
            h_device = ctypes.windll.kernel32.CreateFileW(
                device_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None
            )

            if h_device == -1:
                logger.error(f"Failed to open device {device_path}")
                return False

            try:
                # Send eject command
                bytes_returned = ctypes.wintypes.DWORD()
                result = ctypes.windll.kernel32.DeviceIoControl(
                    h_device,
                    IOCTL_STORAGE_EJECT_MEDIA,
                    None,
                    0,
                    None,
                    0,
                    ctypes.byref(bytes_returned),
                    None
                )

                if result == 0:
                    error = ctypes.get_last_error()
                    logger.error(f"DeviceIoControl failed with error {error}")
                    return False

                # Give the system more time to process the eject command
                time.sleep(3)  # Increased from 2 to 3 seconds

                # Multiple verification attempts with longer delays
                max_attempts = 5  # Increased from 3 to 5 attempts
                for attempt in range(max_attempts):
                    if not self.is_drive_mounted(path):
                        logger.info(f"Successfully ejected {path} on attempt {attempt + 1}")
                        return True
                    logger.debug(f"Eject verification attempt {attempt + 1} of {max_attempts}")
                    time.sleep(1.5)  # Increased from 1 to 1.5 seconds between checks

                logger.error(f"Drive {path} still accessible after {max_attempts} verification attempts")
                return False

            finally:
                # Always close the device handle
                ctypes.windll.kernel32.CloseHandle(h_device)

        except Exception as e:
            logger.error(f"Error during ejection of {path}: {e}")
            return False

    def get_dump_drive(self) -> Optional[Path]:
        """Get the dump drive location"""
        return self.dump_drive_mountpoint

    def set_dump_drive(self, path: Path) -> None:
        """Set the dump drive location"""
        try:
            path = Path(path)
            if not path.exists():
                raise ValueError(f"Path {path} does not exist")
            if not path.is_dir():
                raise ValueError(f"Path {path} is not a directory")
            
            # Verify the drive is accessible
            root_drive = Path(os.path.splitdrive(path)[0] + '\\')
            if not root_drive.exists():
                raise ValueError(f"Drive {root_drive} is not accessible")
                
            self.dump_drive_mountpoint = path
            logger.info(f"Set dump drive to {path}")
        except Exception as e:
            logger.error(f"Error setting dump drive: {e}")
            raise ValueError(str(e))

    @staticmethod
    def get_drive_type(path: Path) -> str:
        """Get the type of drive (e.g., removable, fixed, network)"""
        drive_types = {
            0: "UNKNOWN",
            1: "NO_ROOT_DIR",
            2: "REMOVABLE",
            3: "FIXED",
            4: "NETWORK",
            5: "CDROM",
            6: "RAMDISK"
        }
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(str(path))
        return drive_types.get(drive_type, "UNKNOWN")

    def wait_for_new_drive(self, initial_drives: List[Path]) -> Optional[Path]:
        """
        Wait for a new drive letter to appear.
        
        Args:
            initial_drives: List of initially mounted drive paths
            
        Returns:
            Path to new drive if detected, None if timeout or error
        """
        try:
            while True:
                time.sleep(2)
                current_drives = self.get_available_drives()
                logger.debug(f"Current drives: {current_drives}")
                
                new_drives = set(current_drives) - set(initial_drives)
                if new_drives:
                    new_drive = next(iter(new_drives))
                    drive_type = self.get_drive_type(new_drive)
                    
                    # Only consider removable or fixed drives
                    if drive_type in ["REMOVABLE", "FIXED"]:
                        logger.info(f"New drive detected: {new_drive} (Type: {drive_type})")
                        return new_drive
                    else:
                        logger.debug(f"Ignoring drive {new_drive} of type {drive_type}")
                        
        except Exception as e:
            logger.error(f"Error detecting new drive: {e}")
            return None

    def wait_for_drive_removal(self, path: Path) -> None:
        """
        Wait for a drive to be removed, with proper Windows path handling.
        
        Args:
            path: Path to the drive to monitor
        """
        try:
            # Get just the drive letter part (e.g., "F:")
            drive_letter = str(path.drive).rstrip('\\/')
            
            while True:
                # Check if drive is in list of available drives
                if drive_letter not in [d.drive for d in self.get_available_drives()]:
                    logger.info(f"Drive {drive_letter} has been removed")
                    break
                
                logger.debug(f"Waiting for {drive_letter} to be removed...")
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Error monitoring drive removal: {e}")

    def has_enough_space(self, path: Path, required_size: int) -> bool:
        """
        Check if a drive has enough free space.
        
        Args:
            path: Path to the drive
            required_size: Required space in bytes
            
        Returns:
            True if enough space available, False otherwise
        """
        try:
            drive_info = self.get_drive_info(path)
            return drive_info['free'] >= required_size
        except Exception as e:
            logger.error(f"Error checking available space: {e}")
            return False

    def get_removable_drives(self) -> List[Path]:
        """
        Get list of removable drives only.
        
        Returns:
            List of paths to removable drives
        """
        return [
            drive for drive in self.get_available_drives()
            if self.get_drive_type(drive) == "REMOVABLE"
        ]
    
    def get_file_metadata(self, path: Path) -> Dict[str, Any]:
        """Get file metadata using Windows APIs"""
        try:
            # Get file handle
            handle = win32file.CreateFile(
                str(path),
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            try:
                # Get basic info
                basic_info = win32file.GetFileInformationByHandle(handle)
                
                # Get security info
                security_info = win32security.GetFileSecurity(
                    str(path),
                    win32security.OWNER_SECURITY_INFORMATION |
                    win32security.GROUP_SECURITY_INFORMATION |
                    win32security.DACL_SECURITY_INFORMATION
                )
                
                # Get timestamps
                creation_time, access_time, write_time = win32file.GetFileTime(handle)
                
                metadata = {
                    'attributes': basic_info[0],  # File attributes
                    'creation_time': self._filetime_to_datetime(creation_time),
                    'access_time': self._filetime_to_datetime(access_time),
                    'write_time': self._filetime_to_datetime(write_time),
                    'security_descriptor': security_info.GetSecurityDescriptorOwner(),
                    'acl': security_info.GetSecurityDescriptorDacl()
                }
                
                # Get alternative data streams
                try:
                    metadata['streams'] = self._get_alternative_streams(path)
                except Exception as e:
                    logger.warning(f"Could not get alternative streams: {e}")
                    metadata['streams'] = {}
                    
                return metadata
                
            finally:
                win32file.CloseHandle(handle)
                
        except Exception as e:
            logger.error(f"Error getting metadata for {path}: {e}")
            return {}
            
    def set_file_metadata(self, path: Path, metadata: Dict[str, Any]) -> bool:
        """Set file metadata using Windows APIs"""
        try:
            # Get file handle
            handle = win32file.CreateFile(
                str(path),
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            try:
                # Set file attributes
                win32file.SetFileAttributes(str(path), metadata['attributes'])
                
                # Set timestamps
                win32file.SetFileTime(
                    handle,
                    self._datetime_to_filetime(metadata['creation_time']),
                    self._datetime_to_filetime(metadata['access_time']),
                    self._datetime_to_filetime(metadata['write_time'])
                )
                
                # Set security descriptor
                security_info = win32security.GetFileSecurity(
                    str(path),
                    win32security.OWNER_SECURITY_INFORMATION |
                    win32security.GROUP_SECURITY_INFORMATION |
                    win32security.DACL_SECURITY_INFORMATION
                )
                
                security_info.SetSecurityDescriptorOwner(metadata['security_descriptor'])
                security_info.SetSecurityDescriptorDacl(1, metadata['acl'], 0)
                
                win32security.SetFileSecurity(
                    str(path),
                    win32security.OWNER_SECURITY_INFORMATION |
                    win32security.GROUP_SECURITY_INFORMATION |
                    win32security.DACL_SECURITY_INFORMATION,
                    security_info
                )
                
                # Restore alternative data streams
                if metadata['streams']:
                    self._set_alternative_streams(path, metadata['streams'])
                
                return True
                
            finally:
                win32file.CloseHandle(handle)
                
        except Exception as e:
            logger.error(f"Error setting metadata for {path}: {e}")
            return False
            
    def _filetime_to_datetime(self, filetime) -> datetime:
        """Convert Windows FILETIME to datetime"""
        if filetime is None:
            return None
        return datetime.fromtimestamp((filetime - 116444736000000000) / 10000000)
        
    def _datetime_to_filetime(self, dt) -> int:
        """Convert datetime to Windows FILETIME"""
        if dt is None:
            return None
        return int((dt.timestamp() * 10000000) + 116444736000000000)
        
    def _get_alternative_streams(self, path: Path) -> Dict[str, bytes]:
        """Get alternative data streams"""
        streams = {}
        try:
            find_stream_data = win32file.FindFirstStreamW(str(path))
            while True:
                stream_name = find_stream_data[0]
                if stream_name != '::$DATA':  # Skip default stream
                    with open(f"{path}:{stream_name}", 'rb') as f:
                        streams[stream_name] = f.read()
                try:
                    find_stream_data = win32file.FindNextStreamW(find_stream_data[1])
                except:
                    break
        except Exception as e:
            logger.warning(f"Error reading alternative streams: {e}")
        return streams
        
    def _set_alternative_streams(self, path: Path, streams: Dict[str, bytes]) -> None:
        """Restore alternative data streams"""
        for stream_name, data in streams.items():
            with open(f"{path}:{stream_name}", 'wb') as f:
                f.write(data)