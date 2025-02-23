# src/core/directory_handler.py

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import platform
import re
from .config_manager import TransferConfig

logger = logging.getLogger(__name__)

class DirectoryHandler:
    """Handles creation and management of organized directory structures"""
    
    def __init__(self, config: TransferConfig):
        """
        Initialize directory handler with configuration settings.
        
        Args:
            config: TransferConfig object containing directory organization settings
        """
        self.config = config
    
    def _get_device_name(self, source_path: Path) -> str:
        """Get device name from source drive if possible"""
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Try to get volume label
                import win32api
                drive = str(source_path.drive)
                try:
                    name = win32api.GetVolumeInformation(drive)[0]
                    if name:
                        return self._sanitize_name(name)
                except:
                    pass
            
            # Fallback: Use last part of mount point
            return self._sanitize_name(source_path.name)
            
        except Exception as e:
            logger.error(f"Error getting device name: {e}")
            return "unknown_device"
    
    def _sanitize_name(self, name: str) -> str:
        """Create safe directory name from input"""
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        name = name.replace(' ', '_')
        # Ensure name isn't empty
        return name if name else "unnamed_device"
    
    def create_organized_directory(
        self,
        base_path: Path,
        source_path: Path,
        timestamp: Optional[str] = None
    ) -> Path:
        """
        Create the appropriate directory structure based on configuration.
        
        Args:
            base_path: Base destination path (e.g., 'S:\Other\dest')
            source_path: Source drive path
            timestamp: Current timestamp string
            
        Returns:
            Path where files should be transferred
        """
        try:
            # Log current configuration settings for debugging
            logger.info(f"Directory creation settings:")
            logger.info(f"  create_date_folders: {self.config.create_date_folders}")
            logger.info(f"  create_device_folders: {self.config.create_device_folders}")
            logger.info(f"  base_path: {base_path}")
            
            # Ensure base destination exists
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Start with base destination path
            target_dir = base_path
            
            # If date folders enabled, create timestamp directory
            if self.config.create_date_folders:
                logger.info("Creating timestamp directory as create_date_folders is True")
                # Use provided timestamp or generate new one
                folder_name = timestamp or datetime.now().strftime(self.config.date_folder_format)
                target_dir = target_dir / folder_name
            else:
                logger.info("Skipping timestamp directory as create_date_folders is False")
            
            # If device folders enabled, add device folder
            if self.config.create_device_folders:
                logger.info("Creating device folder as create_device_folders is True")
                device_name = self._get_device_name(source_path)
                device_folder = self.config.device_folder_template.format(
                    device_name=device_name
                )
                target_dir = target_dir / device_folder
            
            # Create the final directory structure
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Final target directory: {target_dir}")
            
            return target_dir
            
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            # Fallback to just the base path if anything goes wrong
            base_path.mkdir(parents=True, exist_ok=True)
            return base_path