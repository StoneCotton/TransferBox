# src/platform/macos/storage.py

import os
import stat
import pwd
import grp
import time
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.core.interfaces.storage import StorageInterface

logger = logging.getLogger(__name__)

class MacOSStorage(StorageInterface):
    def __init__(self):
        self.dump_drive_mountpoint: Optional[Path] = None

    def get_available_drives(self) -> List[Path]:
        """Get list of mounted volumes"""
        volumes = Path("/Volumes")
        return [p for p in volumes.iterdir() if p.is_mount()]

    def get_drive_info(self, path: Path) -> Dict[str, int]:
        """
        Get storage information with improved NAS support for macOS.
        
        On macOS, we use 'df -k' which reports sizes in 1024-byte (1K) blocks,
        then convert to bytes for consistency with the rest of the system.
        
        Args:
            path: Path to check space on
            
        Returns:
            Dictionary containing total, used, and free space in bytes
        """
        try:
            # First try using df command - on macOS we use -k for 1K blocks
            result = subprocess.run(
                ['df', '-k', str(path)],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse df output - last line has our data
            # Format is: Filesystem 1K-blocks Used Available Capacity Mounted on
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:  # Header + data line
                fields = lines[-1].split()
                if len(fields) >= 4:
                    # Convert from 1K blocks to bytes
                    total = int(fields[1]) * 1024
                    used = int(fields[2]) * 1024
                    free = int(fields[3]) * 1024
                    
                    # Log the space information in a human-readable format
                    logger.info(f"Space check for {path}:")
                    logger.info(f"Total: {total / (1024**3):.2f} GB")
                    logger.info(f"Used: {used / (1024**3):.2f} GB")
                    logger.info(f"Free: {free / (1024**3):.2f} GB")
                    
                    return {
                        'total': total,
                        'used': used,
                        'free': free
                    }
            
            # Fallback to statvfs if df parsing fails
            logger.warning("Falling back to statvfs for space check")
            st = os.statvfs(path)
            total = st.f_blocks * st.f_frsize
            free = st.f_bfree * st.f_frsize
            used = total - free
            
            return {'total': total, 'used': used, 'free': free}
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running df command: {e}")
            # Try one more time with the parent directory if the target directory doesn't exist yet
            try:
                parent_path = path.parent
                logger.info(f"Retrying space check with parent directory: {parent_path}")
                return self.get_drive_info(parent_path)
            except Exception as parent_error:
                logger.error(f"Error checking parent directory space: {parent_error}")
                raise
        except Exception as e:
            logger.error(f"Error checking space on {path}: {e}")
            raise

    def is_drive_mounted(self, path: Path) -> bool:
        """Check if path is a mount point"""
        return path.is_mount()

    def unmount_drive(self, path: Path) -> bool:
        """Unmount a drive using diskutil"""
        try:
            # First sync to ensure all writes are complete
            subprocess.run(['sync'], check=True)
            
            # Try unmounting with diskutil
            subprocess.run(
                ['diskutil', 'unmount', str(path)], 
                check=True,
                capture_output=True,
                text=True
            )
            
            # Wait a moment to ensure unmount is complete
            time.sleep(1)
            
            logger.info(f"Successfully unmounted {path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to unmount {path}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error during unmount of {path}: {e}")
            return False

    def get_dump_drive(self) -> Optional[Path]:
        """Get the dump drive location"""
        return self.dump_drive_mountpoint

    def set_dump_drive(self, path: Path) -> None:
        """
        Set the dump drive location, validating the drive is accessible but allowing
        for directory creation.
        
        Args:
            path: Path to set as dump drive location
                
        Raises:
            ValueError: If path's drive is invalid or inaccessible
        """
        try:
            path = Path(path)
            
            # First validate that the volume/drive exists and is accessible
            drive_path = None
            
            # On macOS, check if the path starts with /Volumes/
            if str(path).startswith('/Volumes/'):
                volume_name = path.parts[2]  # Get the volume name
                drive_path = Path('/Volumes') / volume_name
            else:
                # For paths not in /Volumes, use the root
                drive_path = Path('/')
            
            # Check if the drive/volume is accessible
            if not drive_path.exists():
                raise ValueError(f"Volume {drive_path} is not accessible")
                
            # Verify the drive is writable by checking permissions on the volume root
            if not os.access(drive_path, os.W_OK):
                raise ValueError(f"Volume {drive_path} is not writable")
            
            # Store the target path - we don't need to verify it exists
            # as it will be created during transfer if needed
            self.dump_drive_mountpoint = path
            logger.info(f"Set dump drive to {path}")
            
        except Exception as e:
            logger.error(f"Error setting dump drive: {e}")
            raise ValueError(str(e))

    def wait_for_new_drive(self, initial_drives: List[Path]) -> Optional[Path]:
        """
        Wait for a new drive to be mounted in /Volumes.
        
        Args:
            initial_drives: List of initially mounted drives
            
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
                    logger.info(f"New drive detected: {new_drive}")
                    return new_drive
                    
        except Exception as e:
            logger.error(f"Error detecting new drive: {e}")
            return None

    def wait_for_drive_removal(self, path: Path) -> None:
        """
        Wait for a drive to be unmounted from /Volumes.
        
        Args:
            path: Path to the drive to monitor
        """
        try:
            while path.exists() and path.is_mount():
                logger.debug(f"Waiting for {path} to be removed...")
                time.sleep(5)
                
            logger.info(f"Drive {path} has been removed")
                
        except Exception as e:
            logger.error(f"Error monitoring drive removal: {e}")

    def has_enough_space(self, path: Path, required_size: int) -> bool:
        """
        Check if a path has enough free space with improved error handling.
        
        Args:
            path: Path to check
            required_size: Required space in bytes
            
        Returns:
            True if enough space available, False otherwise
        """
        try:
            drive_info = self.get_drive_info(path)
            free_space = drive_info['free']
            
            # Log space requirements
            logger.info(f"Space check results for {path}:")
            logger.info(f"Required: {required_size / (1024**3):.2f} GB")
            logger.info(f"Available: {free_space / (1024**3):.2f} GB")
            
            # Add 5% safety margin for filesystem overhead
            required_with_margin = int(required_size * 1.05)
            
            has_space = free_space >= required_with_margin
            if not has_space:
                needed = (required_with_margin - free_space) / (1024**3)
                logger.warning(f"Insufficient space - needs {needed:.2f} GB more")
            
            return has_space
            
        except Exception as e:
            logger.error(f"Error checking space on {path}: {e}")
            # If we can't check space reliably, we should warn but allow transfer
            logger.warning("Unable to verify space - proceeding with transfer")
            return True
        
    def get_file_metadata(self, path: Path) -> Dict[str, Any]:
        """Get file metadata using macOS native APIs"""
        try:
            stat_info = os.stat(path, follow_symlinks=False)
            
            # Basic metadata available through os.stat
            metadata = {
                'st_mode': stat_info.st_mode,  # File mode and permission bits
                'st_uid': stat_info.st_uid,    # User ID of owner
                'st_gid': stat_info.st_gid,    # Group ID of owner
                'st_atime': stat_info.st_atime, # Last access time
                'st_mtime': stat_info.st_mtime, # Last modification time
                'st_ctime': stat_info.st_ctime, # Creation time (actually metadata change time on Unix)
                'st_flags': stat_info.st_flags if hasattr(stat_info, 'st_flags') else None, # macOS specific flags
            }
            
            # Get extended attributes
            try:
                import xattr
                attrs = xattr.xattr(str(path))
                metadata['xattrs'] = {name: attrs[name] for name in attrs}
            except ImportError:
                logger.warning("xattr module not available - extended attributes won't be preserved")
                metadata['xattrs'] = {}
                
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata for {path}: {e}")
            return {}
            
    def set_file_metadata(self, path: Path, metadata: Dict[str, Any]) -> bool:
        """Set file metadata using macOS native APIs"""
        try:
            # Set basic attributes
            os.chmod(path, metadata['st_mode'])
            os.chown(path, metadata['st_uid'], metadata['st_gid'])
            
            # Set timestamps
            os.utime(path, (metadata['st_atime'], metadata['st_mtime']))
            
            # Set macOS specific flags if available
            if metadata['st_flags'] is not None:
                try:
                    import fcntl
                    fd = os.open(path, os.O_RDONLY)
                    try:
                        fcntl.fcntl(fd, fcntl.F_SETFL, metadata['st_flags'])
                    finally:
                        os.close(fd)
                except ImportError:
                    logger.warning("fcntl not available - file flags won't be preserved")
            
            # Set extended attributes
            if metadata['xattrs']:
                try:
                    import xattr
                    attrs = xattr.xattr(str(path))
                    for name, value in metadata['xattrs'].items():
                        attrs[name] = value
                except ImportError:
                    logger.warning("xattr module not available - extended attributes won't be preserved")
                    
            return True
            
        except Exception as e:
            logger.error(f"Error setting metadata for {path}: {e}")
            return False