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
        """Get storage information for a path"""
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        return {'total': total, 'used': used, 'free': free}

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
        """Set the dump drive location"""
        try:
            path = Path(path)
            if not path.exists():
                raise ValueError(f"Path {path} does not exist")
            if not path.is_dir():
                raise ValueError(f"Path {path} is not a directory")
                
            # Verify the directory is writable
            if not os.access(path, os.W_OK):
                raise ValueError(f"Path {path} is not writable")
                    
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