# src/core/platform_manager.py
import platform
import logging
from pathlib import Path
from typing import Dict
from .interfaces.display import DisplayInterface
from .interfaces.storage_inter import StorageInterface
from .exceptions import (
    TransferBoxError,
    HardwareError,
    ConfigError,
    DisplayError,
    StorageError
)

logger = logging.getLogger(__name__)

class PlatformManager:
    """Factory class for creating platform-specific implementations"""
    
    SUPPORTED_PLATFORMS = {"darwin", "windows", "linux", "raspberry_pi"}
    
    @staticmethod
    def get_platform() -> str:
        """
        Get the current platform identifier
        
        Returns:
            str: The platform identifier
            
        Raises:
            ConfigError: If running on an unsupported platform
        """
        try:
            system = platform.system().lower()
            
            # Special handling for Raspberry Pi detection
            if system == "linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        if 'Raspberry Pi' in f.read():
                            return "raspberry_pi"
                except (IOError, PermissionError) as e:
                    logger.warning(f"Could not check for Raspberry Pi: {str(e)}")
                    # Continue with regular Linux handling if Pi check fails
            
            if system not in PlatformManager.SUPPORTED_PLATFORMS:
                raise ConfigError(
                    f"Unsupported platform: {system}",
                    config_key="platform",
                    invalid_value=system,
                    recovery_steps=[
                        f"TransferBox currently supports: {', '.join(PlatformManager.SUPPORTED_PLATFORMS)}",
                        "Check if your platform is supported in the latest version"
                    ]
                )
            
            return system
            
        except Exception as e:
            if not isinstance(e, ConfigError):
                raise ConfigError(
                    f"Failed to detect platform: {str(e)}",
                    recovery_steps=[
                        "Verify system environment",
                        "Check platform detection permissions"
                    ]
                ) from e
            raise
    
    @classmethod
    def create_display(cls) -> DisplayInterface:
        """
        Create the appropriate display implementation for the current platform
        
        Returns:
            DisplayInterface: Platform-specific display implementation
            
        Raises:
            DisplayError: If display creation fails
        """
        try:
            platform_name = cls.get_platform()
            
            if platform_name == "raspberry_pi":
                try:
                    from src.platform.raspberry_pi.display import RaspberryPiDisplay
                    return RaspberryPiDisplay()
                except ImportError as e:
                    raise DisplayError(
                        "Failed to initialize Raspberry Pi display",
                        display_type="raspberry_pi",
                        error_type="initialization"
                    ) from e
            else:
                try:
                    from src.core.rich_display import RichDisplay
                    return RichDisplay()
                except ImportError as e:
                    raise DisplayError(
                        "Failed to initialize Rich display",
                        display_type="rich",
                        error_type="initialization"
                    ) from e
                
        except Exception as e:
            if not isinstance(e, (DisplayError, ConfigError)):
                raise DisplayError(
                    f"Unexpected error creating display: {str(e)}",
                    error_type="unknown"
                ) from e
            raise
    
    @classmethod
    def create_storage(cls) -> StorageInterface:
        """
        Create the appropriate storage implementation for the current platform
        
        Returns:
            StorageInterface: Platform-specific storage implementation
            
        Raises:
            StorageError: If storage creation fails
            ConfigError: If platform is not supported
        """
        try:
            platform_name = cls.get_platform()
            
            try:
                if platform_name == "raspberry_pi":
                    from src.platform.raspberry_pi.storage_pi import RaspberryPiStorage
                    return RaspberryPiStorage()
                elif platform_name == "darwin":
                    from src.platform.macos.storage_macos import MacOSStorage
                    return MacOSStorage()
                elif platform_name == "windows":
                    from src.platform.windows.storage_win import WindowsStorage
                    return WindowsStorage()
                else:
                    raise ConfigError(
                        f"No storage implementation for platform: {platform_name}",
                        config_key="storage_implementation",
                        invalid_value=platform_name,
                        recovery_steps=[
                            f"Implement storage for {platform_name}",
                            "Use a supported platform instead"
                        ]
                    )
            except ImportError as e:
                raise StorageError(
                    f"Failed to import storage implementation for {platform_name}",
                    error_type="import",
                    device=platform_name
                ) from e
                
        except Exception as e:
            if not isinstance(e, (StorageError, ConfigError)):
                raise StorageError(
                    f"Unexpected error creating storage: {str(e)}",
                    error_type="unknown"
                ) from e
            raise