# src/core/config_manager.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
import logging
from datetime import datetime
from src.core.exceptions import ConfigError

logger = logging.getLogger(__name__)

@dataclass
class TransferConfig:
    """Configuration settings for TransferBox"""
    
    # File handling
    rename_with_timestamp: bool = False
    preserve_original_filename: bool = True
    filename_template: str = "{original}_{timestamp}"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    create_mhl_files: bool = False  # Whether to create MHL (Media Hash List) files for transfers
    
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
            "create_mhl_files": self.create_mhl_files,
            
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
            
        Raises:
            ConfigError: If unable to find or create configuration file
        """
        # Check specified path first
        if self.config_path:
            try:
                if not self.config_path.is_file():
                    self._generate_default_config(self.config_path)
                return self.config_path
            except PermissionError as e:
                raise ConfigError(
                    f"No permission to access or create config at {self.config_path}",
                    config_key=None,
                    recovery_steps=["Try a different location with appropriate permissions"]
                ) from e
            except OSError as e:
                raise ConfigError(
                    f"System error accessing or creating config at {self.config_path}: {e}",
                    config_key=None
                ) from e
        
        # Search default locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.is_file():
                return path
        
        # No config found, create in first default location
        default_path = self.DEFAULT_CONFIG_PATHS[0]
        try:
            self._generate_default_config(default_path)
            return default_path
        except PermissionError as e:
            # Try next default paths if first fails
            for path in self.DEFAULT_CONFIG_PATHS[1:]:
                try:
                    self._generate_default_config(path)
                    return path
                except Exception:
                    continue
                    
            # If all attempts fail, raise error with all attempted paths
            attempted_paths = ", ".join(str(p) for p in self.DEFAULT_CONFIG_PATHS)
            raise ConfigError(
                f"Permission denied creating configuration file at any default location. Tried: {attempted_paths}",
                recovery_steps=["Run with appropriate permissions", "Specify a writable config path"]
            ) from e
        except OSError as e:
            raise ConfigError(
                f"Failed to create default configuration: {e}",
                recovery_steps=["Check filesystem permissions", "Ensure parent directories exist"]
            ) from e

    def _generate_default_config(self, path: Path) -> None:
        """
        Generate default configuration file with all settings and comments.
        
        This method creates a new configuration file with default values and
        helpful comments explaining each section. It includes all available
        configuration options organized by category.
        
        Args:
            path: Path where to create the config file
            
        Raises:
            ConfigError: When unable to create configuration file
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
            "create_mhl_files": config_dict["create_mhl_files"],
            
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise ConfigError(
                f"Permission denied creating directory structure for config at {path.parent}",
                recovery_steps=["Run with appropriate permissions", "Choose a different config location"]
            ) from e
        except OSError as e:
            raise ConfigError(
                f"Failed to create directory for config: {e}",
                recovery_steps=["Check if the path is valid", "Verify the filesystem is writable"]
            ) from e
        
        # Write configuration with comments
        try:
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
        except PermissionError as e:
            raise ConfigError(
                f"Permission denied writing to config file at {path}",
                recovery_steps=["Run with appropriate permissions", "Choose a different config location"]
            ) from e
        except IOError as e:
            raise ConfigError(
                f"I/O error writing to config file: {e}",
                recovery_steps=["Check disk space", "Verify the filesystem is writable"]
            ) from e
            
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
            
        Raises:
            ConfigError: If validation fails for specific configuration options
        """
        # Start with default values
        config = TransferConfig()
        
        try:
            # File handling settings
            self._parse_bool_option(
                raw_config, 'rename_with_timestamp', config,
                lambda v: setattr(config, 'rename_with_timestamp', v)
            )
            
            self._parse_bool_option(
                raw_config, 'preserve_original_filename', config,
                lambda v: setattr(config, 'preserve_original_filename', v)
            )
            
            self._parse_string_option(
                raw_config, 'filename_template', config,
                lambda v: setattr(config, 'filename_template', v),
                "{original}_{timestamp}"
            )
            
            self._parse_string_option(
                raw_config, 'timestamp_format', config, 
                lambda v: setattr(config, 'timestamp_format', v),
                "%Y%m%d_%H%M%S"
            )
            
            # Media transfer settings
            self._parse_bool_option(
                raw_config, 'media_only_transfer', config,
                lambda v: setattr(config, 'media_only_transfer', v)
            )
            
            self._parse_bool_option(
                raw_config, 'preserve_folder_structure', config,
                lambda v: setattr(config, 'preserve_folder_structure', v)
            )
            
            # Parse media extensions
            self._parse_media_extensions(raw_config, config)
            
            # Directory structure settings
            self._parse_bool_option(
                raw_config, 'create_date_folders', config,
                lambda v: setattr(config, 'create_date_folders', v)
            )
            
            # Validate date format string
            date_format = raw_config.get('date_folder_format', config.date_folder_format)

            # First check if the format contains any invalid specifiers
            if not self._is_valid_date_format(date_format):
                logger.warning(f"Invalid date format '{date_format}', using default")
                raise ConfigError(
                    f"Invalid date format: {date_format}",
                    config_key="date_folder_format", 
                    invalid_value=date_format,
                    expected_type="valid strftime format string"
                )

            # Then also try using it with strftime as a second validation
            try:
                datetime.now().strftime(date_format)
                # If we get here, the format is valid
                config.date_folder_format = date_format
            except (ValueError, TypeError) as e:
                # This catches exceptions from strftime for invalid formats
                logger.warning(f"Invalid date format '{date_format}', using default")
                raise ConfigError(
                    f"Invalid date format: {date_format}",
                    config_key="date_folder_format", 
                    invalid_value=date_format,
                    expected_type="valid strftime format string"
                ) from e
            except Exception as e:
                # For any other exception, also raise a ConfigError
                logger.error(f"Unexpected error validating date format: {e}")
                raise ConfigError(
                    f"Invalid date format caused an unexpected error: {e}",
                    config_key="date_folder_format", 
                    invalid_value=date_format,
                    expected_type="valid strftime format string"
                ) from e
                
            self._parse_bool_option(
                raw_config, 'create_device_folders', config,
                lambda v: setattr(config, 'create_device_folders', v)
            )
            
            # Validate device folder template
            template = raw_config.get('device_folder_template', config.device_folder_template)
            if not '{device_name}' in template:
                logger.warning("Device folder template must contain {device_name}")
                raise ConfigError(
                    "Device folder template must contain {device_name} placeholder",
                    config_key="device_folder_template",
                    invalid_value=template
                )
            config.device_folder_template = template
            
            # Proxy generation settings
            self._parse_bool_option(
                raw_config, 'generate_proxies', config,
                lambda v: setattr(config, 'generate_proxies', v)
            )
            
            self._parse_string_option(
                raw_config, 'proxy_subfolder', config,
                lambda v: setattr(config, 'proxy_subfolder', v),
                "proxies"
            )
                                                
            # Sanitize proxy subfolder name
            config.proxy_subfolder = config.proxy_subfolder.strip().replace('/', '_')
            if not config.proxy_subfolder:
                config.proxy_subfolder = "proxies"
                
            self._parse_bool_option(
                raw_config, 'include_proxy_watermark', config,
                lambda v: setattr(config, 'include_proxy_watermark', v)
            )
            
            self._parse_string_option(
                raw_config, 'proxy_watermark_path', config,
                lambda v: setattr(config, 'proxy_watermark_path', v),
                "assets/watermark.png"
            )
            
            # Parse sound settings
            self._parse_bool_option(
                raw_config, 'enable_sounds', config,
                lambda v: setattr(config, 'enable_sounds', v)
            )
            
            self._parse_int_option(
                raw_config, 'sound_volume', config,
                lambda v: setattr(config, 'sound_volume', max(0, min(100, v))),
                50, 0, 100
            )
            
            self._parse_string_option(
                raw_config, 'success_sound_path', config,
                lambda v: setattr(config, 'success_sound_path', v),
                "sounds/success.mp3"
            )
            
            self._parse_string_option(
                raw_config, 'error_sound_path', config,
                lambda v: setattr(config, 'error_sound_path', v),
                "sounds/error.mp3"
            )
                
            return config
            
        except ConfigError:
            # Re-raise config errors for specific settings
            raise
        except Exception as e:
            logger.error(f"Error parsing configuration: {e}")
            # Rather than just logging and returning default config, raise
            # a proper ConfigError that can be handled upstream
            raise ConfigError(
                f"Unexpected error while parsing configuration: {e}",
                recovery_steps=["Verify configuration file format is valid YAML"]
            ) from e

    def _parse_bool_option(self, raw_config, key, config, setter, default=None):
        """Parse boolean option with validation"""
        if key in raw_config:
            value = raw_config[key]
            if default is None:
                default = getattr(config, key)
                
            if not isinstance(value, bool):
                try:
                    # Try to convert string "true"/"false" to boolean
                    if isinstance(value, str):
                        if value.lower() == "true":
                            value = True
                        elif value.lower() == "false":
                            value = False
                        else:
                            raise ValueError(f"Cannot convert '{value}' to boolean")
                    else:
                        # Convert numeric values (0=False, anything else=True)
                        value = bool(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid boolean value for {key}: {value}, using default {default}")
                    raise ConfigError(
                        f"Invalid boolean value: {value}",
                        config_key=key,
                        invalid_value=value,
                        expected_type="boolean"
                    ) from e
            
            setter(value)
            
    def _parse_int_option(self, raw_config, key, config, setter, default=None, min_val=None, max_val=None):
        """Parse integer option with validation and range checking"""
        if key in raw_config:
            value = raw_config[key]
            if default is None:
                default = getattr(config, key)
                
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid integer value for {key}: {value}, using default {default}")
                    raise ConfigError(
                        f"Invalid integer value: {value}",
                        config_key=key,
                        invalid_value=value,
                        expected_type="integer"
                    ) from e
                    
            # Apply range constraints if specified
            if min_val is not None and value < min_val:
                logger.warning(f"Value for {key} is below minimum ({value} < {min_val}), using minimum")
                value = min_val
                
            if max_val is not None and value > max_val:
                logger.warning(f"Value for {key} is above maximum ({value} > {max_val}), using maximum")
                value = max_val
                
            setter(value)
            
    def _parse_string_option(self, raw_config, key, config, setter, default=None):
        """Parse string option with validation"""
        if key in raw_config:
            value = raw_config[key]
            if default is None:
                default = getattr(config, key)
                
            if not isinstance(value, str):
                try:
                    value = str(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid string value for {key}: {value}, using default {default}")
                    raise ConfigError(
                        f"Invalid string value: {value}",
                        config_key=key,
                        invalid_value=value,
                        expected_type="string"
                    ) from e
                    
            setter(value)
            
    def _parse_media_extensions(self, raw_config, config):
        """Parse media extensions with validation"""
        extensions_str = raw_config.get('media_extensions', None)
        if extensions_str:
            try:
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
                else:
                    raise ConfigError(
                        f"Invalid media extensions format: {extensions_str}",
                        config_key="media_extensions",
                        invalid_value=extensions_str,
                        expected_type="comma-separated string or list"
                    )
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing media extensions: {e}")
                raise ConfigError(
                    f"Invalid media extensions: {extensions_str}",
                    config_key="media_extensions",
                    invalid_value=extensions_str
                ) from e

    def load_config(self) -> TransferConfig:
        """
        Load and validate configuration from file.
        
        Returns:
            TransferConfig object with loaded settings
            
        Raises:
            ConfigError: If unable to load or parse configuration
        """
        try:
            # Find or create configuration file
            config_file = self._find_or_create_config()
            
            # Load YAML configuration
            try:
                with open(config_file, 'r') as f:
                    self._raw_config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ConfigError(
                    f"Invalid YAML in configuration file: {e}",
                    recovery_steps=["Check configuration file syntax", "Use valid YAML format"]
                ) from e
            except PermissionError as e:
                raise ConfigError(
                    f"Permission denied reading configuration file: {config_file}",
                    recovery_steps=["Check file permissions", "Try running with elevated privileges"]
                ) from e
            except IOError as e:
                raise ConfigError(
                    f"I/O error reading configuration file: {e}",
                    recovery_steps=["Verify file exists and is accessible"]
                ) from e
            
            logger.info(f"Loaded configuration from {config_file}")
            
            # Convert to TransferConfig object with validation
            config = self._parse_config(self._raw_config)
            self._config = config
            
            # Log active configuration
            self._log_active_configuration()
            
            return config
            
        except ConfigError:
            # Re-raise ConfigError for proper handling upstream
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            logger.info("Falling back to default configuration")
            # Still provide a usable config, but log the issue
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
            ConfigError: If configuration hasn't been loaded
        """
        if self._config is None:
            raise ConfigError(
                "Configuration not loaded. Call load_config() first.",
                recovery_steps=["Call load_config() before accessing configuration"]
            )
        return self._config
    
    def save_config(self, config: TransferConfig, path: Optional[Path] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: TransferConfig object to save
            path: Optional path to save to. If None, uses current config_path
            
        Raises:
            ConfigError: If no path is specified and no current config_path,
                    or if unable to save configuration
        """
        save_path = path or self.config_path
        if not save_path:
            raise ConfigError(
                "No configuration path specified",
                config_key=None,
                recovery_steps=["Provide a path when calling save_config()"]
            )
            
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert the provided config to a dictionary
            config_dict = config.to_dict()
            
            # Define configuration structure with comments but use the provided config values
            config_with_comments = {
                "# File handling - Control how files are renamed and processed": None,
                "rename_with_timestamp": config.rename_with_timestamp,
                "preserve_original_filename": config.preserve_original_filename,
                "filename_template": config.filename_template,
                "timestamp_format": config.timestamp_format,
                
                "\n# Media transfer settings - Control which files are transferred": None,
                "media_only_transfer": config.media_only_transfer,
                "preserve_folder_structure": config.preserve_folder_structure,
                "media_extensions": config_dict["media_extensions"],  # This is already formatted in to_dict()
                
                "\n# Directory structure settings - Control how files are organized": None,
                "create_date_folders": config.create_date_folders,
                "date_folder_format": config.date_folder_format,
                "create_device_folders": config.create_device_folders,
                "device_folder_template": config.device_folder_template,
                
                "\n# Proxy generation settings - Control video proxy creation": None,
                "generate_proxies": config.generate_proxies,
                "proxy_subfolder": config.proxy_subfolder,
                "include_proxy_watermark": config.include_proxy_watermark,
                "proxy_watermark_path": config.proxy_watermark_path,
                
                "\n# Sound settings": None,
                "enable_sounds": config.enable_sounds,
                "sound_volume": config.sound_volume,
                "success_sound_path": config.success_sound_path,
                "error_sound_path": config.error_sound_path
            }
            
            # Write configuration with comments
            with open(save_path, 'w') as f:
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
                
            logger.info(f"Configuration saved to {save_path}")
            
        except PermissionError as e:
            raise ConfigError(
                f"Permission denied creating or writing to configuration file: {save_path}",
                config_key=None,
                recovery_steps=["Check file system permissions", "Try a different location"]
            ) from e
        except OSError as e:
            raise ConfigError(
                f"Failed to save configuration: {e}",
                config_key=None,
                recovery_steps=["Check disk space", "Verify path validity"]
            ) from e
        
    def _is_valid_date_format(self, format_string):
        """
        Validate a date format string by checking for valid format specifiers.
        
        Args:
            format_string: The date format string to validate
            
        Returns:
            bool: True if the format is valid, False otherwise
        """
        # Set of valid format specifiers for strftime
        valid_specifiers = {
            '%a', '%A', '%w', '%d', '%b', '%B', '%m', '%y', '%Y', '%H', '%I', '%p',
            '%M', '%S', '%f', '%z', '%Z', '%j', '%U', '%W', '%c', '%x', '%X', '%%'
        }
        
        # Check each potential format specifier in the string
        i = 0
        while i < len(format_string):
            if format_string[i] == '%' and i + 1 < len(format_string):
                # Found a potential format specifier
                spec = format_string[i:i+2]
                if spec not in valid_specifiers:
                    return False
                i += 2
            else:
                # Not a format specifier, just skip
                i += 1
        
        return True