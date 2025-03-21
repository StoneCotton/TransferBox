# src/core/config_manager.py

import logging
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from .exceptions import ConfigError

logger = logging.getLogger(__name__)

class TransferConfig(BaseModel):
    """Configuration settings for TransferBox using Pydantic for validation"""
    
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
    create_date_folders: bool = True
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
    
    @validator('media_extensions')
    def validate_media_extensions(cls, v):
        """Ensure all media extensions have a leading dot"""
        return [ext if ext.startswith('.') else f'.{ext}' for ext in v]
    
    @validator('buffer_size')
    def validate_buffer_size(cls, v):
        """Ensure buffer size is reasonable"""
        if v < 4096:  # 4KB minimum
            return 4096
        if v > 100 * 1024 * 1024:  # 100MB maximum
            return 100 * 1024 * 1024
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v = v.upper()
        if v not in valid_levels:
            return 'INFO'
        return v
    
    def to_dict(self) -> dict:
        """
        Convert config to dictionary for YAML saving.
        
        Returns:
            Dictionary representation of config with comments
        """
        config_dict = {}
        
        # File handling
        config_dict["rename_with_timestamp"] = self.rename_with_timestamp
        config_dict["preserve_original_filename"] = self.preserve_original_filename
        config_dict["filename_template"] = self.filename_template
        config_dict["timestamp_format"] = self.timestamp_format
        config_dict["create_mhl_files"] = self.create_mhl_files
        
        # Media transfer settings
        config_dict["media_only_transfer"] = self.media_only_transfer
        config_dict["preserve_folder_structure"] = self.preserve_folder_structure
        config_dict["transfer_destination"] = self.transfer_destination
        config_dict["media_extensions"] = self.media_extensions
        
        # Directory structure
        config_dict["create_date_folders"] = self.create_date_folders
        config_dict["date_folder_format"] = self.date_folder_format
        config_dict["create_device_folders"] = self.create_device_folders
        config_dict["device_folder_template"] = self.device_folder_template
        
        # Proxy generation
        config_dict["generate_proxies"] = self.generate_proxies
        config_dict["proxy_subfolder"] = self.proxy_subfolder
        config_dict["include_proxy_watermark"] = self.include_proxy_watermark
        config_dict["proxy_watermark_path"] = self.proxy_watermark_path
        
        # Sound settings
        config_dict["enable_sounds"] = self.enable_sounds
        config_dict["sound_volume"] = self.sound_volume
        config_dict["success_sound_path"] = self.success_sound_path
        config_dict["error_sound_path"] = self.error_sound_path
        
        # Advanced settings
        config_dict["buffer_size"] = self.buffer_size
        config_dict["verify_transfers"] = self.verify_transfers
        config_dict["max_transfer_threads"] = self.max_transfer_threads
        
        # Logging settings
        config_dict["log_level"] = self.log_level
        config_dict["log_file_rotation"] = self.log_file_rotation
        config_dict["log_file_max_size"] = self.log_file_max_size
        
        return config_dict
    
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
    
    DEFAULT_CONFIG_PATHS = [
        Path("config.yml"),
        Path.home() / ".transferbox/config.yml",
        Path("/etc/transferbox/config.yml"),
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
        
        try:
            if config_file and config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    
                # Remove comment entries which start with #
                if config_data:
                    config_data = {k: v for k, v in config_data.items() if not isinstance(k, str) or not k.startswith('#')}
                    
                self.config = TransferConfig.model_validate(config_data or {})
                logger.info(f"Loaded configuration from {config_file}")
            else:
                self.config = TransferConfig()
                self._save_default_config(config_file)
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = TransferConfig()
            
        return self.config
    
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
            
            config_dict = self.config.to_dict()
            
            with open(config_file, 'w') as f:
                # Add section headers as comments
                f.write("# File handling - Control how files are renamed and processed\n")
                yaml.dump({k: config_dict[k] for k in ["rename_with_timestamp", "preserve_original_filename", "filename_template", "timestamp_format", "create_mhl_files"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Media transfer settings\n")
                yaml.dump({k: config_dict[k] for k in ["media_only_transfer", "preserve_folder_structure", "transfer_destination", "media_extensions"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Directory structure settings\n")
                yaml.dump({k: config_dict[k] for k in ["create_date_folders", "date_folder_format", "create_device_folders", "device_folder_template"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Proxy generation settings\n")
                yaml.dump({k: config_dict[k] for k in ["generate_proxies", "proxy_subfolder", "include_proxy_watermark", "proxy_watermark_path"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Sound settings\n")
                yaml.dump({k: config_dict[k] for k in ["enable_sounds", "sound_volume", "success_sound_path", "error_sound_path"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Advanced settings\n")
                yaml.dump({k: config_dict[k] for k in ["buffer_size", "verify_transfers", "max_transfer_threads"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Logging settings\n")
                yaml.dump({k: config_dict[k] for k in ["log_level", "log_file_rotation", "log_file_max_size"]}, f, default_flow_style=False, sort_keys=False)
                
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
            
            config_dict = self.config.to_dict()
            
            with open(config_file, 'w') as f:
                # Add section headers as comments
                f.write("# File handling - Control how files are renamed and processed\n")
                yaml.dump({k: config_dict[k] for k in ["rename_with_timestamp", "preserve_original_filename", "filename_template", "timestamp_format", "create_mhl_files"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Media transfer settings\n")
                yaml.dump({k: config_dict[k] for k in ["media_only_transfer", "preserve_folder_structure", "transfer_destination", "media_extensions"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Directory structure settings\n")
                yaml.dump({k: config_dict[k] for k in ["create_date_folders", "date_folder_format", "create_device_folders", "device_folder_template"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Proxy generation settings\n")
                yaml.dump({k: config_dict[k] for k in ["generate_proxies", "proxy_subfolder", "include_proxy_watermark", "proxy_watermark_path"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Sound settings\n")
                yaml.dump({k: config_dict[k] for k in ["enable_sounds", "sound_volume", "success_sound_path", "error_sound_path"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Advanced settings\n")
                yaml.dump({k: config_dict[k] for k in ["buffer_size", "verify_transfers", "max_transfer_threads"]}, f, default_flow_style=False, sort_keys=False)
                
                f.write("\n# Logging settings\n")
                yaml.dump({k: config_dict[k] for k in ["log_level", "log_file_rotation", "log_file_max_size"]}, f, default_flow_style=False, sort_keys=False)
                
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