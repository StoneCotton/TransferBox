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
            system = platform.system().lower()
            
            if system == "windows":
                # Try to get volume label
                try:
                    import win32api
                    drive = str(source_path.drive)
                    if not drive.endswith('\\'):
                        drive += '\\'
                        
                    try:
                        volume_info = win32api.GetVolumeInformation(drive)
                        name = volume_info[0]
                        if name:
                            return self._sanitize_name(name)
                    except (OSError, AttributeError) as win_err:
                        logger.debug(f"Unable to get Windows volume info: {win_err}")
                except ImportError as imp_err:
                    logger.debug(f"win32api not available: {imp_err}")
            
            # Fallback for all platforms: Use last part of mount point
            try:
                return self._sanitize_name(source_path.name)
            except AttributeError as attr_err:
                logger.warning(f"Unable to get path name: {attr_err}")
                return "unknown_device"
                
        except Exception as e:
            logger.error(f"Error getting device name from {source_path}: {e}", exc_info=True)
            return "unknown_device"

    def _sanitize_name(self, name: str) -> str:
        """Create safe directory name from input"""
        if not isinstance(name, str):
            logger.warning(f"Invalid name type for sanitization: {type(name).__name__}")
            return "unnamed_device"
            
        try:
            # Remove invalid characters
            sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
            
            # Replace spaces with underscores
            sanitized = sanitized.replace(' ', '_')
            
            # Ensure name isn't empty
            if not sanitized:
                logger.debug("Sanitization resulted in empty name")
                return "unnamed_device"
                
            return sanitized
            
        except (re.error, TypeError) as e:
            logger.error(f"Error sanitizing name '{name}': {e}")
            return "unnamed_device"
    
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
        # Validate input parameters
        if not isinstance(base_path, Path):
            logger.error(f"Invalid base_path type: {type(base_path).__name__}")
            try:
                base_path = Path(base_path)
            except Exception as e:
                logger.error(f"Failed to convert base_path to Path: {e}")
                return Path(str(base_path))  # Return as-is as fallback
                
        if not isinstance(source_path, Path):
            logger.error(f"Invalid source_path type: {type(source_path).__name__}")
            try:
                source_path = Path(source_path)
            except Exception as e:
                logger.error(f"Failed to convert source_path to Path: {e}")
                # Continue with original source_path
        
        # Log current configuration settings for debugging
        logger.info(f"Directory creation settings:")
        logger.info(f"  create_date_folders: {self.config.create_date_folders}")
        logger.info(f"  create_device_folders: {self.config.create_device_folders}")
        logger.info(f"  base_path: {base_path}")
        
        target_dir = base_path
        
        try:
            # Ensure base destination exists
            try:
                base_path.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.error(f"Permission denied creating base directory {base_path}: {e}")
                raise
            except OSError as e:
                logger.error(f"OS error creating base directory {base_path}: {e}")
                raise
                
            # If date folders enabled, create timestamp directory
            if self.config.create_date_folders:
                logger.info("Creating timestamp directory as create_date_folders is True")
                
                try:
                    # Use provided timestamp or generate new one
                    folder_name = timestamp or datetime.now().strftime(self.config.date_folder_format)
                    target_dir = target_dir / folder_name
                except (ValueError, TypeError) as e:
                    logger.error(f"Error creating date folder name: {e}")
                    # Skip date folder creation but continue with the rest
            else:
                logger.info("Skipping timestamp directory as create_date_folders is False")
            
            # If device folders enabled, add device folder
            if self.config.create_device_folders:
                logger.info("Creating device folder as create_device_folders is True")
                
                try:
                    device_name = self._get_device_name(source_path)
                    device_folder = self.config.device_folder_template.format(
                        device_name=device_name
                    )
                    target_dir = target_dir / device_folder
                except (AttributeError, KeyError, ValueError) as e:
                    logger.error(f"Error creating device folder name: {e}")
                    # Skip device folder creation but continue with rest
            
            # Create the final directory structure
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Final target directory: {target_dir}")
                return target_dir
            except PermissionError as e:
                logger.error(f"Permission denied creating target directory {target_dir}: {e}")
                raise
            except OSError as e:
                logger.error(f"OS error creating target directory {target_dir}: {e}")
                raise
                
        except (PermissionError, OSError) as e:
            logger.error(f"Could not create directory structure: {e}")
            # Try to create base path as fallback
            try:
                base_path.mkdir(parents=True, exist_ok=True)
                logger.warning(f"Using base path as fallback: {base_path}")
                return base_path
            except Exception as fallback_err:
                logger.critical(f"Cannot create fallback directory: {fallback_err}")
                # Last resort - return path even if we couldn't create it
                return base_path
        except Exception as e:
            logger.error(f"Unexpected error creating directory structure: {e}", exc_info=True)
            # Fallback to just the base path if anything goes wrong
            try:
                base_path.mkdir(parents=True, exist_ok=True)
            except Exception as mkdir_err:
                logger.error(f"Failed to create fallback directory: {mkdir_err}")
            return base_path