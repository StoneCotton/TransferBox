# src/platform/windows/storage.py

import os
import time
import subprocess
import logging
import ctypes
import string
from pathlib import Path
from typing import List, Dict, Optional
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
        Unmount a drive using Windows API
        Note: On Windows, drives can't be "unmounted" like in Unix,
        but we can eject removable drives
        """
        try:
            root_drive = Path(os.path.splitdrive(path)[0] + '\\')
            # Using built-in 'mountvol' command to unmount
            subprocess.run(['mountvol', str(root_drive), '/P'], check=True)
            logger.info(f"Successfully unmounted {path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to unmount {path}: {e}")
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
        Wait for a drive letter to be removed.
        
        Args:
            path: Path to the drive to monitor
        """
        try:
            while path.exists() and self.is_drive_mounted(path):
                logger.debug(f"Waiting for {path} to be removed...")
                time.sleep(5)
                
            logger.info(f"Drive {path} has been removed")
                
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