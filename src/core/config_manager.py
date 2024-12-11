# src/core/config_manager.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TransferConfig:
    """Configuration settings for TransferBox"""
    
    # File handling
    rename_with_timestamp: bool = True
    preserve_original_filename: bool = True
    filename_template: str = "{original}_{timestamp}"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    
    # Media transfer settings
    media_only_transfer: bool = True
    preserve_folder_structure: bool = True
    media_extensions: List[str] = field(default_factory=lambda: [
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

    def to_dict(self) -> dict:
        """Convert config to dictionary for YAML saving"""
        config_dict = {
            "# File handling - Control how files are renamed and processed": None,
            "rename_with_timestamp": self.rename_with_timestamp,
            "preserve_original_filename": self.preserve_original_filename,
            "filename_template": self.filename_template,
            "timestamp_format": self.timestamp_format,
            
            "\n# Media transfer settings": None,
            "media_only_transfer": self.media_only_transfer,
            "preserve_folder_structure": self.preserve_folder_structure,
            "media_extensions": ','.join(self.media_extensions),
            
            "\n# Directory structure settings": None,
            "create_date_folders": self.create_date_folders,
            "date_folder_format": self.date_folder_format,
            "create_device_folders": self.create_device_folders,
            "device_folder_template": self.device_folder_template,
            
            "\n# Proxy generation settings": None,
            "generate_proxies": self.generate_proxies,
            "proxy_subfolder": self.proxy_subfolder,
            "include_proxy_watermark": self.include_proxy_watermark,
            "proxy_watermark_path": self.proxy_watermark_path
        }
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

    def _generate_default_config(self, path: Path) -> None:
        """
        Generate default configuration file with all settings and comments.
        
        This method creates a new configuration file with default values and
        helpful comments explaining each section. It includes all available
        configuration options organized by category.
        
        Args:
            path: Path where to create the config file
        """
        # Create default config instance
        default_config = TransferConfig()
        
        # Convert to dictionary for initial values
        config_dict = default_config.to_dict()
        
        # Define configuration structure with comments
        config_with_comments = {
            "# File handling - Control how files are renamed and processed": None,
            "rename_with_timestamp": config_dict["rename_with_timestamp"],
            "preserve_original_filename": config_dict["preserve_original_filename"],
            "filename_template": config_dict["filename_template"],
            "timestamp_format": config_dict["timestamp_format"],
            
            "\n# Media transfer settings - Control which files are transferred": None,
            "media_only_transfer": config_dict["media_only_transfer"],
            "preserve_folder_structure": config_dict["preserve_folder_structure"],
            "media_extensions": config_dict["media_extensions"],
            
            "\n# Directory structure settings - Control how files are organized": None,
            "create_date_folders": True,  # Set default to True
            "date_folder_format": "%Y/%m/%d",  # Default format
            "create_device_folders": False,  # Default to False
            "device_folder_template": "{device_name}",  # Default template
            
            "\n# Proxy generation settings - Control video proxy creation": None,
            "generate_proxies": False,  # Default to disabled
            "proxy_subfolder": "proxies",  # Default subfolder name
            "include_proxy_watermark": True,  # Default to include watermark
            "proxy_watermark_path": "assets/adobe_proxy_logo.png"  # Default watermark path
        }
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration with comments
        with open(path, 'w') as f:
            for key, value in config_with_comments.items():
                if value is None:  # This is a section comment
                    f.write(f"{key}\n")
                else:
                    # Format the value appropriately
                    if isinstance(value, str):
                        # Quote string values that contain special characters
                        if any(char in value for char in '{}%'):
                            formatted_value = f'"{value}"'
                        else:
                            formatted_value = value
                    else:
                        formatted_value = str(value).lower()  # Convert True/False to lowercase
                        
                    f.write(f"{key}: {formatted_value}\n")
        
        logger.info(f"Generated default configuration file at {path}")

    def _parse_config(self, raw_config: Dict[str, Any]) -> TransferConfig:
        """
        Parse and validate raw configuration data from the YAML file.
        
        This method carefully processes each configuration option, applying validation
        and providing appropriate default values when needed. It handles all settings
        including file handling, media transfer, directory structure, and proxy generation.
        
        Args:
            raw_config: Dictionary of configuration values from YAML file
                
        Returns:
            Validated TransferConfig object
        """
        # Start with default values
        config = TransferConfig()
        
        try:
            # File handling settings
            config.rename_with_timestamp = raw_config.get('rename_with_timestamp', 
                                                        config.rename_with_timestamp)
            config.preserve_original_filename = raw_config.get('preserve_original_filename',
                                                            config.preserve_original_filename)
            config.filename_template = raw_config.get('filename_template',
                                                    config.filename_template)
            config.timestamp_format = raw_config.get('timestamp_format',
                                                config.timestamp_format)
            
            # Media transfer settings
            config.media_only_transfer = raw_config.get('media_only_transfer',
                                                    config.media_only_transfer)
            config.preserve_folder_structure = raw_config.get('preserve_folder_structure',
                                                            config.preserve_folder_structure)
            
            # Parse media extensions
            extensions_str = raw_config.get('media_extensions', '')
            if extensions_str:
                if isinstance(extensions_str, str):
                    # Split comma-separated string and clean up extensions
                    extensions = [ext.strip().lower() for ext in extensions_str.split(',')]
                    # Ensure all extensions start with a dot
                    config.media_extensions = [
                        ext if ext.startswith('.') else f'.{ext}' 
                        for ext in extensions
                    ]
                elif isinstance(extensions_str, list):
                    # Handle case where YAML parser already gave us a list
                    config.media_extensions = [
                        ext if ext.startswith('.') else f'.{ext}'
                        for ext in extensions_str
                    ]
            
            # Directory structure settings (newly added parsing)
            config.create_date_folders = raw_config.get('create_date_folders',
                                                    config.create_date_folders)
            config.date_folder_format = raw_config.get('date_folder_format',
                                                    config.date_folder_format)
            
            # Validate date format string
            try:
                # Test the date format string
                datetime.now().strftime(config.date_folder_format)
            except ValueError as e:
                logger.warning(f"Invalid date format '{config.date_folder_format}', using default")
                config.date_folder_format = "%Y/%m/%d"
                
            config.create_device_folders = raw_config.get('create_device_folders',
                                                        config.create_device_folders)
            config.device_folder_template = raw_config.get('device_folder_template',
                                                        config.device_folder_template)
            
            # Validate device folder template
            if not '{device_name}' in config.device_folder_template:
                logger.warning("Device folder template must contain {device_name}")
                config.device_folder_template = "{device_name}"
            
            # Proxy generation settings (newly added parsing)
            config.generate_proxies = raw_config.get('generate_proxies',
                                                config.generate_proxies)
            config.proxy_subfolder = raw_config.get('proxy_subfolder',
                                                config.proxy_subfolder)
                                                
            # Sanitize proxy subfolder name
            config.proxy_subfolder = config.proxy_subfolder.strip().replace('/', '_')
            if not config.proxy_subfolder:
                config.proxy_subfolder = "proxies"
                
            config.include_proxy_watermark = raw_config.get('include_proxy_watermark',
                                                        config.include_proxy_watermark)
            config.proxy_watermark_path = raw_config.get('proxy_watermark_path',
                                                    config.proxy_watermark_path)
            
            # Validate watermark path format
            if not isinstance(config.proxy_watermark_path, str):
                logger.warning("Invalid watermark path format")
                config.proxy_watermark_path = "assets/watermark.png"
                
            return config
            
        except Exception as e:
            logger.error(f"Error parsing configuration: {e}")
            logger.info("Falling back to default configuration")
            return TransferConfig()

    def load_config(self) -> TransferConfig:
        """
        Load and validate configuration from file.
        
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
            
            # Log active configuration
            self._log_active_configuration()
            
            return config
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Falling back to default configuration")
            return TransferConfig()

    def _log_active_configuration(self) -> None:
        """Log active configuration settings"""
        if not self._config:
            return
            
        logger.info("Active Configuration:")
        logger.info("Feature Flags:")

        logger.info("File Handling:")
        logger.info(f"  Timestamp Renaming: {self._config.rename_with_timestamp}")
        logger.info(f"  Filename Template: {self._config.filename_template}")
        logger.info(f"  Timestamp Format: {self._config.timestamp_format}")
        logger.info(f"  Preserve Original: {self._config.preserve_original_filename}")

        logger.info("Media Transfer Settings:")
        logger.info(f"  Media Only: {self._config.media_only_transfer}")
        logger.info(f"  Preserve Structure: {self._config.preserve_folder_structure}")
        logger.info(f"  Extensions: {', '.join(self._config.media_extensions)}")
        
        logger.info("Directory Structure:")
        logger.info(f"  Date Folders: {self._config.create_date_folders}")
        logger.info(f"  Date Folder Format: {self._config.date_folder_format}")
        logger.info(f"  Device Folders: {self._config.create_device_folders}")
        logger.info(f"  Device Folder Template: {self._config.device_folder_template}")

        logger.info("Video Processing:")
        logger.info(f"  Proxy Generation: {self._config.generate_proxies}")
        logger.info(f"  Proxy Subfolder: {self._config.proxy_subfolder}")
        logger.info(f"  Watermark: {self._config.include_proxy_watermark}")
        logger.info(f"  Watermark Path: {self._config.proxy_watermark_path}")


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
        config_dict = config.to_dict()
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file with comments preserved
        self._generate_default_config(save_path)
            
        logger.info(f"Configuration saved to {save_path}")