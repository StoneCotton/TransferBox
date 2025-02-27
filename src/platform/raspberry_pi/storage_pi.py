# src/platform/raspberry_pi/storage-pi.py

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
from src.core.path_utils import sanitize_path, get_safe_path
from src.core.interfaces.storage_inter import StorageInterface
from src.platform.raspberry_pi.led_control import LEDControl, set_led_state
from src.core.exceptions import StorageError, FileTransferError, ChecksumError


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
            
        Raises:
            StorageError: If there is an error accessing or listing drives
        """
        try:
            return self.get_mounted_drives_lsblk()
        except Exception as e:
            logger.error(f"Error getting available drives: {e}")
            raise StorageError(
                f"Failed to get available drives: {str(e)}", 
                error_type="mount",
                recovery_steps=[
                    "Check drive connections",
                    "Verify drive mounting",
                    "Check system mount points"
                ]
            )

    def get_drive_info(self, path: Path) -> Dict[str, int]:
        """
        Get information about a specific drive.
        
        Args:
            path: Path to the drive
            
        Returns:
            Dictionary containing 'total', 'used', and 'free' space in bytes
            
        Raises:
            StorageError: If there is an error getting drive information
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
        except OSError as e:
            logger.error(f"Error getting drive info for {path}: {e}")
            raise StorageError(
                f"Failed to get drive information: {str(e)}", 
                path=path,
                error_type="mount",
                recovery_steps=[
                    "Check if drive is mounted",
                    "Verify drive permissions",
                    "Check filesystem health"
                ]
            )
        except Exception as e:
            logger.error(f"Unexpected error getting drive info for {path}: {e}")
            raise StorageError(
                f"Failed to get drive information: {str(e)}", 
                path=path,
                error_type="unknown"
            )

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
            True if successful or already unmounted
            
        Raises:
            StorageError: If unmounting fails
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
                    error_msg = (
                        f"Unmount attempt {attempt + 1} failed:\n"
                        f"udisksctl error: {udisks_result.stderr if device_name else 'Not attempted'}\n"
                        f"umount error: {umount_result.stderr}"
                    )
                    logger.warning(error_msg)
                    
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
                    else:
                        raise StorageError(
                            f"Failed to unmount drive after {max_attempts} attempts: {str(e)}",
                            path=path,
                            error_type="mount",
                            recovery_steps=[
                                "Check if any programs are using the drive",
                                "Try force unmounting the drive",
                                "Restart the system if problems persist"
                            ]
                        )
            
            # Final check if the drive is actually unmounted
            if not path.exists() or not path.is_mount():
                logger.info(f"Drive {path} is now unmounted after all attempts")
                return True
                
            raise StorageError(
                f"Failed to unmount {path} after {max_attempts} attempts",
                path=path,
                error_type="mount",
                recovery_steps=[
                    "Check if any programs are using the drive",
                    "Try force unmounting the drive",
                    "Restart the system if problems persist"
                ]
            )
                    
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error during unmount of {path}: {e}")
            raise StorageError(
                f"Unexpected error unmounting drive: {str(e)}",
                path=path,
                error_type="unknown"
            )

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
        Wait for a new drive with improved path handling.
        Ensures proper handling of paths with spaces and special characters.
        
        Args:
            initial_drives: List of initially mounted drives
            
        Returns:
            Path to new drive if found, None otherwise
            
        Raises:
            StorageError: If there is an error detecting or accessing new drives
        """
        try:
            while True:
                time.sleep(2)
                current_drives = self.get_mounted_drives_lsblk()
                
                # Convert all paths to strings for comparison
                initial_paths = {str(d) for d in initial_drives}
                current_paths = {str(d) for d in current_drives}
                
                # Find new drives
                new_paths = current_paths - initial_paths
                
                for new_path in new_paths:
                    path = Path(new_path)
                    if "/media/" in str(path):
                        # Verify the path is actually accessible
                        try:
                            # Use sanitize_path for proper path handling
                            safe_path = sanitize_path(str(path))
                            # Basic accessibility check
                            if safe_path.exists() and os.access(safe_path, os.R_OK):
                                logger.info(f"New drive detected and verified: {safe_path}")
                                return safe_path
                            else:
                                logger.warning(f"Drive detected but not accessible: {safe_path}")
                                raise StorageError(
                                    f"New drive detected but not accessible: {safe_path}",
                                    path=safe_path,
                                    error_type="permission",
                                    recovery_steps=[
                                        "Check drive permissions",
                                        "Verify drive is properly mounted",
                                        "Check filesystem health"
                                    ]
                                )
                        except StorageError:
                            raise
                        except Exception as e:
                            logger.error(f"Error verifying drive access: {path}, {e}")
                            raise StorageError(
                                f"Error verifying new drive: {str(e)}",
                                path=path,
                                error_type="mount"
                            )
                            
                time.sleep(1)  # Short sleep to prevent busy-waiting
                
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error detecting new drive: {e}")
            raise StorageError(
                f"Unexpected error detecting new drive: {str(e)}",
                error_type="unknown"
            )

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
        Get list of mounted drives using lsblk command with improved path handling.
        Uses --pairs output format for reliable parsing and proper handling of spaces.
        """
        try:
            # Use --pairs format for reliable parsing
            result = subprocess.run(
                ['lsblk', '--pairs', '--output', 'MOUNTPOINT', '--noheadings'],
                stdout=subprocess.PIPE,
                text=True,
                check=True
            )
            
            mounted_drives = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                # Parse the key=value format
                try:
                    # Extract the value part of MOUNTPOINT="value"
                    mount = line.split('=')[1].strip('"')
                    if mount and mount != 'None':
                        # Convert to Path using our sanitize_path function
                        path = sanitize_path(mount)
                        if path.exists():
                            mounted_drives.append(path)
                            logger.debug(f"Found mounted drive: {path}")
                except (IndexError, ValueError) as e:
                    logger.debug(f"Skipping malformed lsblk output: {line}, {e}")
                    continue
                    
            return mounted_drives
            
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
            
        Raises:
            StorageError: If there is an error accessing file metadata
        """
        try:
            stat_info = os.stat(path, follow_symlinks=False)
            fs_type = self._get_filesystem_type(path)
            
            # Base metadata that exFAT supports
            metadata = {
                'filesystem': fs_type,
                'filename': path.name,
                'created_time': self._get_creation_time(path),
                'modified_time': stat_info.st_mtime,
                'accessed_time': stat_info.st_atime,
                'is_readonly': bool(stat_info.st_mode & stat.S_IREAD),
                'is_hidden': path.name.startswith('.'),
                'is_system': False,
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
            if fs_type != 'exfat':
                try:
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
                except Exception as e:
                    logger.warning(f"Could not get additional metadata for {path}: {e}")
            
            return metadata
            
        except OSError as e:
            logger.error(f"Error accessing metadata for {path}: {e}")
            raise StorageError(
                f"Failed to access file metadata: {str(e)}",
                path=path,
                error_type="permission",
                recovery_steps=[
                    "Check file permissions",
                    "Verify file exists",
                    "Check filesystem mount status"
                ]
            )
        except Exception as e:
            logger.error(f"Error getting metadata for {path}: {e}")
            raise StorageError(
                f"Unexpected error getting file metadata: {str(e)}",
                path=path,
                error_type="unknown"
            )
    
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

    def _verify_drive_access(self, path: Path) -> bool:
        """Verify that a drive path is accessible with proper error handling."""
        try:
            path = sanitize_path(str(path))
            if not path.exists():
                logger.debug(f"Path does not exist: {path}")
                return False
                
            if not path.is_mount():
                logger.debug(f"Path is not a mount point: {path}")
                return False
                
            if not os.access(path, os.R_OK):
                logger.debug(f"No read permission for path: {path}")
                return False
                
            # Try to list directory contents to verify access
            list(path.iterdir())
            return True
            
        except PermissionError:
            logger.debug(f"Permission denied accessing path: {path}")
            return False
        except Exception as e:
            logger.debug(f"Error verifying drive access: {path}, {e}")
            return False
        
    def _get_filesystem_type(self, path: Path) -> str:
        """
        Determine the filesystem type of a given path using findmnt command.
        
        This method uses the findmnt command which is more reliable than df -T
        for getting filesystem types, especially for removable media.
        
        Args:
            path: Path to check filesystem type
            
        Returns:
            String representing filesystem type (e.g., 'exfat', 'ext4', etc.)
        """
        try:
            # Use findmnt to get filesystem type
            result = subprocess.run(
                ['findmnt', '-no', 'FSTYPE', str(path)],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get the filesystem type and convert to lowercase
            fs_type = result.stdout.strip().lower()
            logger.debug(f"Filesystem type for {path}: {fs_type}")
            return fs_type
            
        except subprocess.CalledProcessError:
            # If findmnt fails, try using stat
            try:
                stat_info = os.statvfs(path)
                logger.debug(f"Using statvfs fallback for {path}")
                # Return a generic filesystem type
                return 'unknown'
            except Exception as e:
                logger.error(f"Error getting filesystem type using statvfs: {e}")
                return 'unknown'
        except Exception as e:
            logger.error(f"Error getting filesystem type for {path}: {e}")
            return 'unknown'

    def wait_for_drive_removal(self, path: Path) -> None:
        """
        Wait for a drive to be unmounted or removed.
        
        This method continuously checks if the drive is still mounted
        and accessible, waiting until it's removed or unmounted.
        
        Args:
            path: Path to the drive to monitor
        """
        try:
            # Convert to Path object if it isn't already
            path = Path(path)
            logger.info(f"Waiting for removal of drive: {path}")
            
            # Keep checking until the drive is gone
            while True:
                try:
                    # First check if path still exists
                    if not path.exists():
                        logger.info(f"Drive path no longer exists: {path}")
                        break
                        
                    # Then check if it's still mounted
                    if not path.is_mount():
                        logger.info(f"Drive is no longer mounted: {path}")
                        break
                        
                    # Short sleep to prevent excessive CPU usage
                    time.sleep(1)
                    
                except PermissionError:
                    # If we get permission error, drive might be in process of unmounting
                    logger.debug(f"Permission error checking {path}, might be unmounting")
                    time.sleep(1)
                    continue
                except Exception as e:
                    logger.warning(f"Error checking drive status: {e}")
                    # Wait a bit longer if we hit an error
                    time.sleep(2)
                    continue
                    
            logger.info(f"Confirmed drive removal: {path}")
            
        except Exception as e:
            logger.error(f"Error monitoring drive removal: {e}")