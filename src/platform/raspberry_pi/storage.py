# src/platform/raspberry_pi/storage.py

import os
import subprocess
import logging
import subprocess
import time
from typing import List, Dict, Optional
from pathlib import Path

from src.core.interfaces.storage import StorageInterface
from src.platform.raspberry_pi.led_control import LEDControl, set_led_state


logger = logging.getLogger(__name__)

class RaspberryPiStorage(StorageInterface):
    """
    Raspberry Pi implementation of StorageInterface that handles drive detection,
    mounting, and management specific to the Raspberry Pi hardware setup.
    """
    
    def __init__(self):
        self.dump_drive_mountpoint = None
        self._update_dump_drive_mountpoint()

    def _update_dump_drive_mountpoint(self) -> None:
        """Update the current DUMP_DRIVE mountpoint."""
        username = os.getenv("USER")
        possible_mountpoints = [
            Path(f'/media/{username}/DUMP_DRIVE'),
            Path(f'/media/{username}/DUMP_DRIVE1')
        ]
        
        for mountpoint in possible_mountpoints:
            if mountpoint.is_mount():
                self.dump_drive_mountpoint = mountpoint
                logger.info(f"DUMP_DRIVE found at {mountpoint}")
                return

        # If not found in expected locations, search all mounted drives
        try:
            mount_output = subprocess.check_output(['mount'], text=True)
            for line in mount_output.split('\n'):
                if 'DUMP_DRIVE' in line:
                    mountpoint = Path(line.split()[2])
                    self.dump_drive_mountpoint = mountpoint
                    logger.info(f"DUMP_DRIVE found at {mountpoint}")
                    return
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking mounts: {e}")

        logger.warning("DUMP_DRIVE not found")
        self.dump_drive_mountpoint = None

    def get_available_drives(self) -> List[Path]:
        """
        Get a list of all available mounted drives.
        
        Returns:
            List of Paths to mounted drives
        """
        try:
            return self.get_mounted_drives_lsblk()
        except Exception as e:
            logger.error(f"Error getting available drives: {e}")
            return []

    def get_drive_info(self, path: Path) -> Dict[str, int]:
        """
        Get information about a specific drive.
        
        Args:
            path: Path to the drive
            
        Returns:
            Dictionary containing 'total', 'used', and 'free' space in bytes
        """
        try:
            statvfs = os.statvfs(path)
            total = statvfs.f_blocks * statvfs.f_frsize
            free = statvfs.f_bfree * statvfs.f_frsize
            used = total - free
            
            return {
                'total': total,
                'used': used,
                'free': free
            }
        except Exception as e:
            logger.error(f"Error getting drive info for {path}: {e}")
            return {'total': 0, 'used': 0, 'free': 0}

    def is_drive_mounted(self, path: Path) -> bool:
        """
        Check if a specific drive is mounted.
        
        Args:
            path: Path to check
            
        Returns:
            True if mounted, False otherwise
        """
        return path.is_mount()

    def unmount_drive(self, path: Path) -> bool:
        """
        Safely unmount a drive using system unmount command.
        
        Args:
            path: Path to the drive to unmount
                
        Returns:
            True if successful, False otherwise
        """
        try:
            # First sync to ensure all writes are complete
            subprocess.run(['sync'], check=True)
            
            # Try unmounting with udisks2 first (handles cleanup better)
            try:
                subprocess.run(
                    ['udisksctl', 'unmount', '-b', str(path)], 
                    check=True, 
                    stderr=subprocess.PIPE,
                    text=True
                )
            except subprocess.CalledProcessError:
                # Fall back to umount if udisksctl fails
                subprocess.run(['umount', str(path)], check=True)
            
            # Wait a moment to ensure unmount is complete
            time.sleep(1)
            
            logger.info(f"Successfully unmounted {path}")
            return True
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to unmount {path}: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                logger.error(f"Unmount error details: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error during unmount of {path}: {e}")
            return False

    def get_dump_drive(self) -> Optional[Path]:
        """
        Get the current DUMP_DRIVE mountpoint.
        
        Returns:
            Path to DUMP_DRIVE if available, None otherwise
        """
        self._update_dump_drive_mountpoint()
        return self.dump_drive_mountpoint


    def wait_for_new_drive(self, initial_drives: List[Path]) -> Optional[Path]:
        """
        Wait for a new drive to be connected and return its mountpoint.
        
        Args:
            initial_drives: List of initially mounted drives
                
        Returns:
            Path to the new drive if detected, None if timeout or error
        """
        try:
            while True:
                time.sleep(2)
                current_drives = self.get_mounted_drives_lsblk()
                new_drives = set(current_drives) - set(initial_drives)
                
                for drive in new_drives:
                    if "/media/" in str(drive) or "/mnt" in str(drive):
                        logger.info(f"New drive detected: {drive}")
                        return drive
                        
        except Exception as e:
            logger.error(f"Error detecting new drive: {e}")
            return None

    def wait_for_drive_removal(self, path: Path) -> None:
        """
        Wait for a specific drive to be removed.
        
        Args:
            path: Path to the drive to monitor
        """
        try:
            while path.exists() and path.is_mount():
                logger.debug(f"Waiting for {path} to be removed...")
                time.sleep(1)
            logger.info(f"Drive {path} has been removed")
        except Exception as e:
            logger.error(f"Error waiting for drive removal: {e}")

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

    def get_mounted_drives_lsblk(self) -> List[Path]:
        """
        Get list of mounted drives using lsblk command.
        Replaces DriveDetection.get_mounted_drives_lsblk()
        
        Returns:
            List of paths to mounted drives
        """
        try:
            result = subprocess.run(
                ['lsblk', '-o', 'MOUNTPOINT', '-nr'],
                stdout=subprocess.PIPE,
                text=True,
                check=True
            )
            return [Path(drive) for drive in result.stdout.strip().split('\n') if drive]
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running lsblk: {e}")
            return []