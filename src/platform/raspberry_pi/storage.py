# src/platform/raspberry_pi/storage.py

import os
import subprocess
import logging
import subprocess
import time
import pwd
import grp
import stat
from xattr import xattr
from typing import List, Dict, Optional, Any
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
            True if successful or already unmounted, False if unmount fails
        """
        try:
            # Check if already unmounted
            if not path.exists() or not path.is_mount():
                logger.info(f"Drive {path} is already unmounted")
                return True

            # First sync multiple times to ensure all writes are complete
            for _ in range(3):
                subprocess.run(['sync'], check=True)
                time.sleep(0.5)
            
            # Find processes using the mount point
            try:
                lsof_output = subprocess.run(
                    ['lsof', str(path)],
                    capture_output=True,
                    text=True
                )
                if lsof_output.returncode == 0:  # Found processes using the mount
                    logger.warning(f"Found processes using {path}, attempting to terminate")
                    # Extract PIDs from lsof output and kill processes
                    pids = set()
                    for line in lsof_output.stdout.splitlines()[1:]:  # Skip header
                        try:
                            pids.add(int(line.split()[1]))
                        except (IndexError, ValueError):
                            continue
                    
                    for pid in pids:
                        try:
                            subprocess.run(['kill', str(pid)], check=False)
                        except Exception as e:
                            logger.warning(f"Failed to kill process {pid}: {e}")
                    
                    time.sleep(1)  # Give processes time to terminate
            except Exception as e:
                logger.warning(f"Error checking for processes using mount: {e}")

            # Get the device name from mount output
            try:
                mount_output = subprocess.check_output(['mount'], text=True)
                device_name = None
                for line in mount_output.split('\n'):
                    if str(path) in line:
                        device_name = line.split()[0]
                        break
            except Exception as e:
                logger.warning(f"Error getting device name: {e}")
                device_name = None
            
            # Try unmounting with udisks2 first
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Try udisksctl first if we have the device name
                    if device_name:
                        udisks_result = subprocess.run(
                            ['udisksctl', 'unmount', '-b', device_name],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        if udisks_result.returncode == 0:
                            logger.info(f"Successfully unmounted {path} with udisksctl")
                            time.sleep(1)
                            return True
                    
                    # If udisksctl fails or we don't have device name, try umount
                    umount_result = subprocess.run(
                        ['umount', str(path)],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if umount_result.returncode == 0:
                        logger.info(f"Successfully unmounted {path} with umount")
                        time.sleep(1)
                        return True
                    
                    # If both fail, log the error and try again
                    logger.warning(
                        f"Unmount attempt {attempt + 1} failed:\n"
                        f"udisksctl error: {udisks_result.stderr if device_name else 'Not attempted'}\n"
                        f"umount error: {umount_result.stderr}"
                    )
                    
                    # Check if the drive is actually unmounted despite the error
                    if not path.exists() or not path.is_mount():
                        logger.info(f"Drive {path} is now unmounted despite command failure")
                        return True
                    
                    if attempt < max_attempts - 1:
                        logger.info("Waiting before retry...")
                        subprocess.run(['sync'], check=False)
                        time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error during unmount attempt {attempt + 1}: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
            
            # Final check if the drive is actually unmounted
            if not path.exists() or not path.is_mount():
                logger.info(f"Drive {path} is now unmounted after all attempts")
                return True
                
            logger.error(f"Failed to unmount {path} after {max_attempts} attempts")
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

    def get_file_metadata(self, path: Path) -> Dict[str, Any]:
        """
        Get file metadata optimized for exFAT filesystem commonly used on SD cards.
        
        Args:
            path: Path to the file
            
        Returns:
            Dictionary containing available metadata
        """
        try:
            stat_info = os.stat(path, follow_symlinks=False)
            fs_type = self._get_filesystem_type(path)
            
            # Base metadata that exFAT supports
            metadata = {
                'filesystem': fs_type,
                'filename': path.name,  # exFAT supports long filenames up to 255 chars
                
                # exFAT has better timestamp resolution than FAT32
                # It supports timestamps from 1980 to 2116 with 10ms precision
                'created_time': self._get_creation_time(path),
                'modified_time': stat_info.st_mtime,
                'accessed_time': stat_info.st_atime,
                
                # exFAT supports these basic attributes
                'is_readonly': bool(stat_info.st_mode & stat.S_IREAD),
                'is_hidden': path.name.startswith('.'),
                'is_system': False,  # Rarely used on Linux
                'is_directory': path.is_dir()
            }
            
            # Get exFAT-specific attributes using fstools if available
            try:
                exfat_attrs = self._get_exfat_attributes(path)
                if exfat_attrs:
                    metadata.update(exfat_attrs)
            except Exception as e:
                logger.debug(f"Could not get exFAT-specific attributes: {e}")
            
            # If we're copying from a non-exFAT source, store additional metadata
            # that we might want to preserve in alternate ways
            if fs_type != 'exfat':
                metadata['original_mode'] = stat_info.st_mode
                metadata['original_uid'] = stat_info.st_uid
                metadata['original_gid'] = stat_info.st_gid
                
                # Store ownership information by name (more portable)
                try:
                    metadata['original_owner'] = pwd.getpwuid(stat_info.st_uid).pw_name
                    metadata['original_group'] = grp.getgrgid(stat_info.st_gid).gr_name
                except KeyError:
                    pass
                    
                # If source has extended attributes, store them for potential alternate preservation
                try:
                    import xattr
                    attrs = xattr.xattr(str(path))
                    if attrs:
                        metadata['original_xattrs'] = {name: attrs[name] for name in attrs}
                except ImportError:
                    pass
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata for {path}: {e}")
            return {}
    
    def set_file_metadata(self, path: Path, metadata: Dict[str, Any]) -> bool:
        """
        Set file metadata with optimized handling for exFAT filesystem.
        
        Args:
            path: Path to the file
            metadata: Dictionary of metadata to apply
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_fs = self._get_filesystem_type(path)
            
            if current_fs == 'exfat':
                # Set timestamps - exFAT has good timestamp precision
                os.utime(path, (
                    metadata['accessed_time'],
                    metadata['modified_time']
                ))
                
                # Set creation time if possible
                if metadata['created_time']:
                    self._set_creation_time(path, metadata['created_time'])
                
                # Set basic attributes
                if metadata['is_readonly']:
                    current_mode = os.stat(path).st_mode
                    os.chmod(path, current_mode & ~stat.S_IWRITE)
                
                # Set exFAT-specific attributes if we have them
                if any(key.startswith('exfat_') for key in metadata):
                    self._set_exfat_attributes(path, metadata)
                
            else:
                # We're copying to a non-exFAT filesystem
                # Try to preserve as much original metadata as possible
                if 'original_mode' in metadata:
                    try:
                        os.chmod(path, metadata['original_mode'])
                    except PermissionError:
                        logger.warning("Could not set exact permissions - insufficient privileges")
                
                # Try to restore ownership if we have it
                if 'original_owner' in metadata and 'original_group' in metadata:
                    try:
                        uid = pwd.getpwnam(metadata['original_owner']).pw_uid
                        gid = grp.getgrnam(metadata['original_group']).gr_gid
                        os.chown(path, uid, gid)
                    except (KeyError, PermissionError):
                        logger.warning("Could not restore original ownership")
                
                # Restore extended attributes if supported
                if current_fs in ('ext4', 'xfs') and 'original_xattrs' in metadata:
                    try:
                        import xattr
                        attrs = xattr.xattr(str(path))
                        for name, value in metadata['original_xattrs'].items():
                            try:
                                attrs[name] = value
                            except OSError:
                                logger.debug(f"Could not set xattr {name}")
                    except ImportError:
                        pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting metadata for {path}: {e}")
            return False
    
    def _get_creation_time(self, path: Path) -> Optional[float]:
        """Get creation time using platform-specific methods."""
        try:
            # Try using statx if available (Linux 4.11+)
            statx_output = subprocess.check_output(
                ['stat', '--format=%W', str(path)],
                stderr=subprocess.PIPE,
                text=True
            )
            return float(statx_output.strip())
        except (subprocess.CalledProcessError, ValueError):
            return None
    
    def _set_creation_time(self, path: Path, timestamp: float) -> bool:
        """Set creation time if possible."""
        try:
            # Attempt to set creation time using available tools
            subprocess.run(
                ['setctime', str(path), str(int(timestamp))],
                check=True,
                capture_output=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("Could not set creation time - tool not available")
            return False
            
    def _get_exfat_attributes(self, path: Path) -> Dict[str, Any]:
        """Get exFAT-specific attributes using exfatprogs tools."""
        try:
            result = subprocess.run(
                ['exfatfsck', '--verbose', str(path)],
                capture_output=True,
                text=True
            )
            
            attrs = {}
            # Parse output for exFAT-specific attributes
            # This is a placeholder - actual parsing would depend on tool output
            return attrs
            
        except FileNotFoundError:
            logger.debug("exfatprogs tools not installed")
            return {}
            
    def _set_exfat_attributes(self, path: Path, metadata: Dict[str, Any]) -> None:
        """Set exFAT-specific attributes using exfatprogs tools."""
        try:
            # Use exfatprogs tools to set attributes
            # This is a placeholder - actual implementation would depend on available tools
            pass
        except FileNotFoundError:
            logger.debug("exfatprogs tools not installed")