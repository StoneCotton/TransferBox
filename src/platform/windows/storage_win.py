# src/platform/windows/storage_win.py

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
from typing import List, Dict, Optional, Any, Union
from src.core.interfaces.storage_inter import StorageInterface
from src.core.path_utils import sanitize_path, validate_destination_path
from src.core.exceptions import StorageError, ConfigError, FileTransferError

logger = logging.getLogger(__name__)

class WindowsStorage(StorageInterface):
    def __init__(self):
        self.dump_drive_mountpoint: Optional[Path] = None

    def set_dump_drive(self, path: Union[Path, str]) -> None:
        """
        Set the dump drive location for Windows, with improved path validation.
        
        Args:
            path: Path to set as dump drive location
                
        Raises:
            StorageError: If drive is invalid, inaccessible, or has insufficient space
            ConfigError: If path configuration is invalid
        """
        try:
            # Sanitize the path if it's a string
            if isinstance(path, str):
                path = sanitize_path(path)
                
            # Validate the path using our improved validation
            path = validate_destination_path(path, self)
            
            # Additional Windows-specific checks
            drive_path = Path(path.drive + '\\')
            
            # Verify it's a proper storage drive using Windows API
            try:
                drive_type = win32file.GetDriveType(str(drive_path))
                valid_types = [win32file.DRIVE_FIXED, win32file.DRIVE_REMOVABLE]
                
                if drive_type not in valid_types:
                    drive_type_names = {
                        win32file.DRIVE_UNKNOWN: "Unknown",
                        win32file.DRIVE_NO_ROOT_DIR: "No Root Directory",
                        win32file.DRIVE_REMOVABLE: "Removable",
                        win32file.DRIVE_FIXED: "Fixed",
                        win32file.DRIVE_REMOTE: "Network",
                        win32file.DRIVE_CDROM: "CD-ROM",
                        win32file.DRIVE_RAMDISK: "RAM Disk"
                    }
                    type_name = drive_type_names.get(drive_type, f"Unknown Type ({drive_type})")
                    raise StorageError(
                        f"Drive {drive_path} is not a valid storage drive (Type: {type_name})",
                        path=drive_path,
                        device=type_name,
                        error_type="mount"
                    )
                
                # Get drive free space
                sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                    win32file.GetDiskFreeSpace(str(drive_path))
                
                free_bytes = sectors_per_cluster * bytes_per_sector * free_clusters
                if free_bytes < 1024 * 1024 * 100:  # 100MB minimum
                    free_gb = free_bytes / (1024 * 1024 * 1024)
                    raise StorageError(
                        f"Drive {drive_path} has insufficient space ({free_gb:.2f} GB free)",
                        path=drive_path,
                        error_type="space"
                    )
                
            except ImportError:
                logger.warning("win32file not available - skipping detailed drive checks")
            except StorageError:
                raise
            except Exception as e:
                raise StorageError(
                    f"Failed to validate drive {drive_path}: {str(e)}",
                    path=drive_path,
                    error_type="mount"
                )
            
            # Store the validated path
            self.dump_drive_mountpoint = path
            logger.info(f"Set dump drive to {path}")
            
        except StorageError:
            raise
        except Exception as e:
            raise ConfigError(
                f"Invalid dump drive configuration: {str(e)}",
                config_key="dump_drive",
                invalid_value=str(path)
            )

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
                raise StorageError(
                    f"Failed to get drive information for {root_drive}",
                    path=root_drive,
                    error_type="mount"
                )
            return {
                'total': total.value,
                'free': free.value,
                'used': total.value - free.value
            }
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error getting drive info for {path}: {e}")
            raise StorageError(
                f"Failed to get drive information: {str(e)}",
                path=path,
                error_type="mount"
            )

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
            True if successful
            
        Raises:
            StorageError: If drive ejection fails
        """
        try:
            # First sync to ensure all writes are complete
            try:
                subprocess.run(['fsutil', 'volume', 'flush', str(path)], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                raise StorageError(
                    f"Failed to flush drive {path}: {e.stderr.decode()}",
                    path=path,
                    error_type="mount"
                )
            
            # Allow system time to complete flush
            time.sleep(2)
            
            # Get volume name (e.g., "F:" from "F:\" or "F:/")
            volume_name = str(path.drive).rstrip(':\\/')
            
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
                raise StorageError(
                    f"Failed to open device {device_path}",
                    path=path,
                    device=device_path,
                    error_type="mount"
                )

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
                    raise StorageError(
                        f"Failed to eject drive {path} (Error: {error})",
                        path=path,
                        error_type="mount"
                    )

                # Give the system more time to process the eject command
                time.sleep(3)

                # Multiple verification attempts with longer delays
                max_attempts = 5
                for attempt in range(max_attempts):
                    if not self.is_drive_mounted(path):
                        logger.info(f"Successfully ejected {path} on attempt {attempt + 1}")
                        return True
                    logger.debug(f"Eject verification attempt {attempt + 1} of {max_attempts}")
                    time.sleep(1.5)

                raise StorageError(
                    f"Drive {path} still accessible after {max_attempts} verification attempts",
                    path=path,
                    error_type="mount"
                )

            finally:
                ctypes.windll.kernel32.CloseHandle(h_device)

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Error during ejection of {path}: {str(e)}",
                path=path,
                error_type="mount"
            )

    def get_dump_drive(self) -> Optional[Path]:
        """Get the dump drive location"""
        return self.dump_drive_mountpoint

    def get_drive_type(self, path: Path) -> str:
        """
        Get the type of drive (e.g., removable, fixed, network).
        
        Args:
            path: Path to check drive type
            
        Returns:
            String representing the drive type
        """
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
        """Get file metadata using Windows APIs with proper timestamp handling"""
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
                
                # Get timestamps and convert properly
                creation_time, access_time, write_time = win32file.GetFileTime(handle)
                
                metadata = {
                    'attributes': basic_info[0],  # File attributes
                    'creation_time': creation_time,  # Store raw Windows time
                    'access_time': access_time,      # Store raw Windows time
                    'write_time': write_time,        # Store raw Windows time
                    'security_descriptor': security_info.GetSecurityDescriptorOwner(),
                    'acl': security_info.GetSecurityDescriptorDacl()
                }
                
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
                try:
                    win32file.SetFileAttributes(str(path), metadata['attributes'])
                except Exception as e:
                    raise StorageError(
                        f"Failed to set file attributes: {str(e)}",
                        path=path,
                        error_type="permission"
                    )
                
                # Set timestamps
                try:
                    win32file.SetFileTime(
                        handle,
                        self._datetime_to_filetime(metadata['creation_time']),
                        self._datetime_to_filetime(metadata['access_time']),
                        self._datetime_to_filetime(metadata['write_time'])
                    )
                except Exception as e:
                    raise StorageError(
                        f"Failed to set file timestamps: {str(e)}",
                        path=path,
                        error_type="permission"
                    )
                
                # Set security descriptor
                try:
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
                except Exception as e:
                    raise StorageError(
                        f"Failed to set file security: {str(e)}",
                        path=path,
                        error_type="permission"
                    )
                
                # Restore alternative data streams
                if metadata.get('streams'):
                    try:
                        self._set_alternative_streams(path, metadata['streams'])
                    except Exception as e:
                        raise StorageError(
                            f"Failed to set alternative streams: {str(e)}",
                            path=path,
                            error_type="io"
                        )
                
                return True
                
            finally:
                win32file.CloseHandle(handle)
                
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Error setting metadata for {path}: {str(e)}",
                path=path,
                error_type="permission"
            )
        
    def _datetime_to_filetime(self, dt) -> int:
        """Convert datetime to Windows FILETIME"""
        if dt is None:
            return None
        return int((dt.timestamp() * 10000000) + 116444736000000000)

    def _windows_time_to_datetime(self, windows_time) -> Optional[datetime]:
        """Safely convert Windows FILETIME to Python datetime"""
        try:
            if windows_time is None:
                return None
            # Convert to 100-nanosecond intervals since January 1, 1601
            windows_nano = int(windows_time)
            # Convert to seconds and adjust epoch
            seconds_since_1601 = windows_nano / 10000000
            # Adjust to Unix epoch (seconds between 1601-01-01 and 1970-01-01)
            seconds_since_1970 = seconds_since_1601 - 11644473600
            return datetime.fromtimestamp(seconds_since_1970)
        except Exception as e:
            logger.error(f"Error converting Windows time: {e}")
            return None

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