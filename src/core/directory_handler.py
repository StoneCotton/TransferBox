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
        if not isinstance(source_path, Path):
            logger.warning(f"Invalid source_path type: {type(source_path).__name__}")
            return "unknown_device"
            
        try:
            if platform.system().lower() == "windows":
                try:
                    import win32api
                    drive = str(source_path.drive)
                    if not drive.endswith('\\'):
                        drive += '\\'
                    volume_info = win32api.GetVolumeInformation(drive)
                    if volume_info[0]:
                        return self._sanitize_name(volume_info[0])
                except (ImportError, OSError, AttributeError) as e:
                    logger.debug(f"Unable to get Windows volume info: {e}")
            
            return self._sanitize_name(source_path.name)
                
        except Exception as e:
            logger.error(f"Error getting device name from {source_path}: {e}", exc_info=True)
            return "unknown_device"

    def _sanitize_name(self, name: str) -> str:
        """Create safe directory name from input"""
        if not isinstance(name, str):
            logger.warning(f"Invalid name type for sanitization: {type(name).__name__}")
            return "unnamed_device"
            
        try:
            sanitized = re.sub(r'[<>:"/\\|?*]', '', name).replace(' ', '_')
            return sanitized if sanitized else "unnamed_device"
        except (re.error, TypeError) as e:
            logger.error(f"Error sanitizing name '{name}': {e}")
            return "unnamed_device"
    
    def _ensure_directory_exists(self, path: Path) -> None:
        """Create directory if it doesn't exist, with error handling"""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise
    
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
            # Convert paths if needed
            base_path = Path(base_path) if not isinstance(base_path, Path) else base_path
            source_path = Path(source_path) if not isinstance(source_path, Path) else source_path
            
            target_dir = base_path
            self._ensure_directory_exists(base_path)
            
            # Create date-based directory if enabled
            if getattr(self.config, 'create_date_folders', False):
                date_format = getattr(self.config, 'date_folder_format', "%Y/%m/%d")
                folder_name = timestamp or datetime.now().strftime(date_format)
                target_dir = target_dir / folder_name
            
            # Create device-based directory if enabled
            if getattr(self.config, 'create_device_folders', False):
                device_name = self._get_device_name(source_path)
                template = getattr(self.config, 'device_folder_template', "{device_name}")
                device_folder = template.format(device_name=device_name)
                target_dir = target_dir / device_folder
            
            self._ensure_directory_exists(target_dir)
            logger.info(f"Final target directory: {target_dir}")
            return target_dir
            
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}", exc_info=True)
            try:
                self._ensure_directory_exists(base_path)
                return base_path
            except Exception as fallback_err:
                logger.critical(f"Cannot create fallback directory: {fallback_err}")
                return base_path