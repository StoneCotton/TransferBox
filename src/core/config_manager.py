# src/core/config_manager.py

import logging
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any, ClassVar
from pydantic import BaseModel, Field, field_validator
import sys
import os

from .exceptions import ConfigError
from src import __version__  # 1) Import program version

logger = logging.getLogger(__name__)

class TransferConfig(BaseModel):
    """Configuration settings for TransferBox using Pydantic for validation"""
    
    # Configuration sections for organized YAML output
    CONFIG_SECTIONS: ClassVar[Dict[str, List[str]]] = {
        "# File handling - Control how files are renamed and processed": [
            "version", "rename_with_timestamp", "preserve_original_filename", 
            "filename_template", "timestamp_format", "create_mhl_files"
        ],
        "# Media transfer settings": [
            "media_only_transfer", "preserve_folder_structure", 
            "transfer_destination", "media_extensions"
        ],
        "# Directory structure settings": [
            "create_date_folders", "date_folder_format", 
            "create_device_folders", "device_folder_template"
        ],
        "# Proxy generation settings": [
            "generate_proxies", "proxy_subfolder", 
            "include_proxy_watermark", "proxy_watermark_path"
        ],
        "# Sound settings": [
            "enable_sounds", "sound_volume", 
            "success_sound_path", "error_sound_path"
        ],
        "# Advanced settings": [
            "buffer_size", "verify_transfers", "max_transfer_threads"
        ],
        "# Logging settings": [
            "log_level", "log_file_rotation", "log_file_max_size"
        ],
        "# User Experience settings": [
            "tutorial_mode"
        ]
    }
    
    version: str = __version__  # 2) Add version field
    # File handling
    rename_with_timestamp: bool = False
    preserve_original_filename: bool = True
    filename_template: str = "{original}_{timestamp}"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    create_mhl_files: bool = False
    
    # Media transfer settings
    media_only_transfer: bool = True
    preserve_folder_structure: bool = True
    transfer_destination: str = "/media/transfer"  # Default destination path for embedded mode
    media_extensions: List[str] = Field(default_factory=lambda: [
        # Video formats
        '.mp4', '.mov', '.mxf', '.avi', '.braw', '.r3d',
        # Audio formats
        '.wav', '.aif', '.aiff',
        # Professional camera formats
        '.crm', '.arw', '.raw', '.cr2',
        # Image formats
        '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.dpx', '.exr',
        # Project/metadata files
        '.xml', '.cdl', '.cube'
    ])
    
    # Directory structure
    create_date_folders: bool = False
    date_folder_format: str = "%Y/%m/%d"
    create_device_folders: bool = False
    device_folder_template: str = "{device_name}"
    
    # Proxy generation
    generate_proxies: bool = False
    proxy_subfolder: str = "proxies"
    include_proxy_watermark: bool = True
    proxy_watermark_path: str = "assets/watermark.png"
    
    # Sound settings
    enable_sounds: bool = True
    sound_volume: int = 50  # 0-100
    success_sound_path: str = "sounds/success.mp3"
    error_sound_path: str = "sounds/error.mp3"
    
    # Advanced settings
    buffer_size: int = 1024 * 1024  # 1MB default
    verify_transfers: bool = True
    max_transfer_threads: int = 1
    
    # Logging settings
    log_level: str = "INFO"
    log_file_rotation: int = 5  # Number of log files to keep
    log_file_max_size: int = 10  # MB
    
    # User Experience settings
    tutorial_mode: bool = True
    
    @field_validator('media_extensions')
    def validate_media_extensions(cls, v):
        """Ensure all media extensions have a leading dot"""
        return [ext if ext.startswith('.') else f'.{ext}' for ext in v]
    
    @field_validator('buffer_size')
    def validate_buffer_size(cls, v):
        """Ensure buffer size is reasonable"""
        if v < 4096:  # 4KB minimum
            return 4096
        if v > 100 * 1024 * 1024:  # 100MB maximum
            return 100 * 1024 * 1024
        return v
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v = v.upper()
        if v not in valid_levels:
            return 'INFO'
        return v
    
    def to_dict(self) -> dict:
        """
        Convert config to dictionary for YAML saving using Pydantic's built-in serialization.
        
        Returns:
            Dictionary representation of config
        """
        return self.model_dump()
    
    def save_to_yaml_with_sections(self, file_handle):
        """
        Save configuration to YAML file with organized sections.
        This method eliminates DRY violations by automatically using the CONFIG_SECTIONS.
        
        Args:
            file_handle: Open file handle to write to
        """
        config_dict = self.to_dict()
        
        for section_comment, field_names in self.CONFIG_SECTIONS.items():
            # Write section header
            file_handle.write(f"\n{section_comment}\n")
            
            # Create section dictionary with only the fields for this section
            section_dict = {k: config_dict[k] for k in field_names if k in config_dict}
            
            # Write section fields
            yaml.dump(section_dict, file_handle, default_flow_style=False, sort_keys=False)
    
    def get(self, key, default=None):
        """
        Get configuration value with fallback.
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        return getattr(self, key, default)


class ConfigManager:
    """Simplified config manager using Pydantic"""
    
    @staticmethod
    def get_appdata_dir() -> Path:
        """
        Get the platform-appropriate appdata/config directory for TransferBox.
        Returns:
            Path: The directory path for storing user data (config, logs, etc.)
        """
        if sys.platform == "win32":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "TransferBox"
        elif sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "TransferBox"
        else:
            # Linux and other POSIX
            return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "transferbox"

    DEFAULT_CONFIG_PATHS = [
        get_appdata_dir.__func__() / "config.yml",
    ]
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.config = None
    
    def load_config(self) -> TransferConfig:
        """
        Load configuration from file or create default.
        
        Returns:
            TransferConfig: Validated configuration object
        """
        config_file = self._find_config_file()
        missing_fields = []
        try:
            if config_file and config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                # Remove comment entries which start with #
                if config_data:
                    config_data = {k: v for k, v in config_data.items() if not isinstance(k, str) or not k.startswith('#')}
                else:
                    config_data = {}
                # 4) Version check and migration
                file_version = config_data.get("version")
                if file_version != __version__:
                    # Backup before migration
                    self._backup_config(config_file)
                    logger.warning(f"Config version mismatch: file has {file_version}, program is {__version__}. Migrating config.")
                    config_data = self._migrate_config(config_data)
                    config_data["version"] = __version__
                    self.save_config(TransferConfig.model_validate(config_data))
                self.config = TransferConfig.model_validate(config_data or {})
                logger.info(f"Loaded configuration from {config_file}")
                # Check for missing fields
                model_fields = set(self.config.model_fields.keys())
                file_fields = set(config_data.keys())
                missing_fields = model_fields - file_fields
                if missing_fields:
                    logger.info(f"Adding missing config fields to {config_file}: {missing_fields}")
                    self.save_config()  # This will write all fields, preserving existing values
            else:
                self.config = TransferConfig()
                self._save_default_config(config_file)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = TransferConfig()
        return self.config
    
    def _backup_config(self, config_file: Path):
        """
        Backup the existing config file before migration.
        """
        try:
            backup_path = config_file.with_suffix(config_file.suffix + ".bak")
            if config_file.exists():
                import shutil
                shutil.copy2(config_file, backup_path)
                logger.info(f"Backed up config to {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
    
    def _migrate_config(self, config_data: dict) -> dict:
        """
        Migrate an old config dict to the latest version using the TransferConfig model.
        Removes unknown fields and fills in missing ones with defaults. Preserves user values unless invalid.
        """
        valid_fields = set(TransferConfig.model_fields.keys())
        migrated = {}
        # Validate and preserve user values if valid, else use default
        for k in valid_fields:
            if k in config_data:
                try:
                    # Validate single field using Pydantic
                    test_config = TransferConfig(**{k: config_data[k]})
                    migrated[k] = getattr(test_config, k)
                except Exception:
                    migrated[k] = getattr(TransferConfig(), k)
            else:
                migrated[k] = getattr(TransferConfig(), k)
        migrated["version"] = __version__
        return migrated
    
    def _find_config_file(self) -> Path:
        """
        Find existing config file from possible locations.
        
        Returns:
            Path to configuration file
        """
        if self.config_path:
            return self.config_path
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path
        # Use first default path if none found
        return self.DEFAULT_CONFIG_PATHS[0]
    
    def _save_default_config(self, config_file: Path):
        """
        Save default configuration.
        
        Args:
            config_file: Path to save configuration to
        """
        try:
            # Create parent directory if it doesn't exist
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                # Use the centralized method to save with sections
                self.config.save_to_yaml_with_sections(f)
                
            logger.info(f"Created default configuration at {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save default config: {e}", exc_info=True)
            
    def save_config(self, config: Optional[TransferConfig] = None):
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save, uses self.config if None
        """
        if config is not None:
            self.config = config
            
        if self.config is None:
            logger.error("No configuration to save")
            return
            
        config_file = self._find_config_file()
        
        try:
            # Create parent directory if it doesn't exist
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                # Use the centralized method to save with sections
                self.config.save_to_yaml_with_sections(f)
                
            logger.info(f"Saved configuration to {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}", exc_info=True)
            
    def update_config(self, updates: Dict[str, Any]):
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of key-value pairs to update
            
        Returns:
            TransferConfig: Updated configuration
        """
        if self.config is None:
            self.config = TransferConfig()
            
        # Convert current config to dict and update with new values
        config_dict = self.config.model_dump()
        config_dict.update(updates)
        
        # Validate and create new config
        self.config = TransferConfig.model_validate(config_dict)
        
        # Save the updated config
        self.save_config()
        
        return self.config