# src/core/config_manager.py

import yaml
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, fields
from enum import Enum, auto

logger = logging.getLogger(__name__)

class VideoProxyQuality(Enum):
    """Video proxy generation quality settings"""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    DISABLED = auto()

@dataclass
class TransferConfig:
    """Configuration settings for TransferBox"""
    
    # Feature flags
    enable_checksum: bool = True
    enable_mhl: bool = True
    enable_led_indicators: bool = True
    enable_power_monitoring: bool = True
    
    # File handling
    rename_with_timestamp: bool = True
    preserve_original_filename: bool = True
    filename_template: str = "{original}_{timestamp}"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    
    # Video processing
    generate_proxies: bool = False
    proxy_quality: VideoProxyQuality = VideoProxyQuality.DISABLED
    proxy_subfolder: str = "proxies"
    
    # Directory structure
    create_date_folders: bool = True
    date_folder_format: str = "%Y/%m/%d"
    create_device_folders: bool = False
    device_folder_template: str = "{device_name}"
    
    # Transfer behavior
    verify_after_copy: bool = True
    unmount_after_transfer: bool = True
    shutdown_when_idle: bool = False
    idle_shutdown_minutes: int = 30
    
    # Display settings
    display_brightness: int = 100  # 0-100
    led_brightness: int = 100      # 0-100
    progress_update_interval: float = 0.5  # seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary with enum handling"""
        config_dict = asdict(self)
        # Convert enum to string
        config_dict['proxy_quality'] = self.proxy_quality.name
        return config_dict

class ConfigManager:
    """Manages configuration loading and validation for TransferBox"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file. If None,
                       uses default locations.
        """
        self.config_path = config_path
        self._config: Optional[TransferConfig] = None
        self._raw_config: Dict[str, Any] = {}
        
        # Default config locations in order of preference
        self.DEFAULT_CONFIG_PATHS = [
            Path("config.yml"),  # Current directory
            Path.home() / ".transferbox/config.yml",  # User's home directory
            Path("/etc/transferbox/config.yml"),      # System-wide configuration
        ]
    
    def _generate_default_config(self, path: Path) -> None:
        """
        Generate default configuration file with comments.
        
        Args:
            path: Path where to create the config file
        """
        # Create default config
        default_config = TransferConfig()
        
        # Convert to dictionary
        config_dict = default_config.to_dict()
        
        # Add section comments
        config_with_comments = {
            "# Feature flags - Enable/disable core functionality": None,
            "enable_checksum": config_dict["enable_checksum"],
            "enable_mhl": config_dict["enable_mhl"],
            "enable_led_indicators": config_dict["enable_led_indicators"],
            "enable_power_monitoring": config_dict["enable_power_monitoring"],
            
            "\n# File handling - Control how files are renamed and processed": None,
            "rename_with_timestamp": config_dict["rename_with_timestamp"],
            "preserve_original_filename": config_dict["preserve_original_filename"],
            "filename_template": config_dict["filename_template"],
            "timestamp_format": config_dict["timestamp_format"],
            
            "\n# Video processing - Settings for proxy generation": None,
            "generate_proxies": config_dict["generate_proxies"],
            "proxy_quality": config_dict["proxy_quality"],
            "proxy_subfolder": config_dict["proxy_subfolder"],
            
            "\n# Directory structure - Control how files are organized": None,
            "create_date_folders": config_dict["create_date_folders"],
            "date_folder_format": config_dict["date_folder_format"],
            "create_device_folders": config_dict["create_device_folders"],
            "device_folder_template": config_dict["device_folder_template"],
            
            "\n# Transfer behavior - Control transfer process": None,
            "verify_after_copy": config_dict["verify_after_copy"],
            "unmount_after_transfer": config_dict["unmount_after_transfer"],
            "shutdown_when_idle": config_dict["shutdown_when_idle"],
            "idle_shutdown_minutes": config_dict["idle_shutdown_minutes"],
            
            "\n# Display settings - Control LED and display behavior": None,
            "display_brightness": config_dict["display_brightness"],
            "led_brightness": config_dict["led_brightness"],
            "progress_update_interval": config_dict["progress_update_interval"]
        }
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write config with comments
        with open(path, 'w') as f:
            for key, value in config_with_comments.items():
                if value is None:  # This is a comment
                    f.write(f"\n{key}\n")
                else:
                    f.write(f"{key}: {value}\n")
        
        logger.info(f"Generated default configuration file at {path}")

    def load_config(self) -> TransferConfig:
        """
        Load and validate configuration from file.
        If no config file exists, generates default config.
        
        Returns:
            TransferConfig object with loaded settings
        """
        try:
            # Find or create configuration file
            config_file = self._find_or_create_config()
            
            # Load YAML configuration
            with open(config_file, 'r') as f:
                self._raw_config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded configuration from {config_file}")
            
            # Convert to TransferConfig object with validation
            config = self._parse_config(self._raw_config)
            self._config = config
            
            # Log active features
            self._log_active_configuration()
            
            return config
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Falling back to default configuration")
            return TransferConfig()
    
    def _find_or_create_config(self) -> Path:
        """
        Find existing config file or create default one.
        
        Returns:
            Path to configuration file
        """
        # Check specified path first
        if self.config_path:
            if not self.config_path.is_file():
                self._generate_default_config(self.config_path)
            return self.config_path
        
        # Search default locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.is_file():
                return path
        
        # No config found, create in first default location
        default_path = self.DEFAULT_CONFIG_PATHS[0]
        self._generate_default_config(default_path)
        return default_path
    
    def _parse_config(self, raw_config: Dict[str, Any]) -> TransferConfig:
        """
        Parse and validate raw configuration data.
        
        Args:
            raw_config: Dictionary of configuration values
            
        Returns:
            Validated TransferConfig object
        """
        # Start with default values
        config = TransferConfig()
        
        # Feature flags
        config.enable_checksum = raw_config.get('enable_checksum', config.enable_checksum)
        config.enable_mhl = raw_config.get('enable_mhl', config.enable_mhl)
        config.enable_led_indicators = raw_config.get('enable_led_indicators', 
                                                    config.enable_led_indicators)
        config.enable_power_monitoring = raw_config.get('enable_power_monitoring',
                                                      config.enable_power_monitoring)
        
        # File handling
        config.rename_with_timestamp = raw_config.get('rename_with_timestamp',
                                                    config.rename_with_timestamp)
        config.preserve_original_filename = raw_config.get('preserve_original_filename',
                                                         config.preserve_original_filename)
        config.filename_template = raw_config.get('filename_template',
                                                config.filename_template)
        config.timestamp_format = raw_config.get('timestamp_format',
                                               config.timestamp_format)
        
        # Video processing
        config.generate_proxies = raw_config.get('generate_proxies',
                                               config.generate_proxies)
        
        proxy_quality = raw_config.get('proxy_quality', 'DISABLED')
        try:
            config.proxy_quality = VideoProxyQuality[proxy_quality.upper()]
        except (KeyError, AttributeError):
            logger.warning(f"Invalid proxy quality '{proxy_quality}', using DISABLED")
            config.proxy_quality = VideoProxyQuality.DISABLED
            
        config.proxy_subfolder = raw_config.get('proxy_subfolder',
                                              config.proxy_subfolder)
        
        # Directory structure
        config.create_date_folders = raw_config.get('create_date_folders',
                                                  config.create_date_folders)
        config.date_folder_format = raw_config.get('date_folder_format',
                                                 config.date_folder_format)
        config.create_device_folders = raw_config.get('create_device_folders',
                                                    config.create_device_folders)
        config.device_folder_template = raw_config.get('device_folder_template',
                                                     config.device_folder_template)
        
        # Transfer behavior
        config.verify_after_copy = raw_config.get('verify_after_copy',
                                                config.verify_after_copy)
        config.unmount_after_transfer = raw_config.get('unmount_after_transfer',
                                                     config.unmount_after_transfer)
        config.shutdown_when_idle = raw_config.get('shutdown_when_idle',
                                                 config.shutdown_when_idle)
        config.idle_shutdown_minutes = raw_config.get('idle_shutdown_minutes',
                                                    config.idle_shutdown_minutes)
        
        # Display settings
        config.display_brightness = max(0, min(100, raw_config.get('display_brightness',
                                                                 config.display_brightness)))
        config.led_brightness = max(0, min(100, raw_config.get('led_brightness',
                                                             config.led_brightness)))
        config.progress_update_interval = max(0.1, raw_config.get('progress_update_interval',
                                                                config.progress_update_interval))
        
        return config
    
    def _log_active_configuration(self) -> None:
        """Log active configuration settings"""
        if not self._config:
            return
            
        logger.info("Active Configuration:")
        logger.info("Feature Flags:")
        logger.info(f"  Checksum: {self._config.enable_checksum}")
        logger.info(f"  MHL: {self._config.enable_mhl}")
        logger.info(f"  LED Indicators: {self._config.enable_led_indicators}")
        logger.info(f"  Power Monitoring: {self._config.enable_power_monitoring}")
        
        logger.info("File Handling:")
        logger.info(f"  Timestamp Renaming: {self._config.rename_with_timestamp}")
        logger.info(f"  Filename Template: {self._config.filename_template}")
        
        logger.info("Video Processing:")
        logger.info(f"  Proxy Generation: {self._config.generate_proxies}")
        logger.info(f"  Quality: {self._config.proxy_quality.name}")
        
        logger.info("Directory Structure:")
        logger.info(f"  Date Folders: {self._config.create_date_folders}")
        logger.info(f"  Device Folders: {self._config.create_device_folders}")
    
    def get_config(self) -> TransferConfig:
        """
        Get current configuration.
        
        Returns:
            Current TransferConfig object
        
        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._config
    
    def save_config(self, config: TransferConfig, path: Optional[Path] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: TransferConfig object to save
            path: Optional path to save to. If None, uses current config_path
            
        Raises:
            ValueError: If no path is specified and no current config_path
        """
        save_path = path or self.config_path
        if not save_path:
            raise ValueError("No configuration path specified")
            
        # Convert config to dictionary
        config_dict = {
            'enable_checksum': config.enable_checksum,
            'enable_mhl': config.enable_mhl,
            'enable_led_indicators': config.enable_led_indicators,
            'enable_power_monitoring': config.enable_power_monitoring,
            
            'rename_with_timestamp': config.rename_with_timestamp,
            'preserve_original_filename': config.preserve_original_filename,
            'filename_template': config.filename_template,
            'timestamp_format': config.timestamp_format,
            
            'generate_proxies': config.generate_proxies,
            'proxy_quality': config.proxy_quality.name,
            'proxy_subfolder': config.proxy_subfolder,
            
            'create_date_folders': config.create_date_folders,
            'date_folder_format': config.date_folder_format,
            'create_device_folders': config.create_device_folders,
            'device_folder_template': config.device_folder_template,
            
            'verify_after_copy': config.verify_after_copy,
            'unmount_after_transfer': config.unmount_after_transfer,
            'shutdown_when_idle': config.shutdown_when_idle,
            'idle_shutdown_minutes': config.idle_shutdown_minutes,
            
            'display_brightness': config.display_brightness,
            'led_brightness': config.led_brightness,
            'progress_update_interval': config.progress_update_interval,
        }
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file
        with open(save_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
            
        logger.info(f"Configuration saved to {save_path}")