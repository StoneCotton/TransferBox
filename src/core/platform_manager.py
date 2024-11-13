# src/core/platform_manager.py
import platform
import logging
from pathlib import Path
from typing import Dict
from .interfaces.display import DisplayInterface
from .interfaces.storage import StorageInterface

logger = logging.getLogger(__name__)

class PlatformManager:
    """Factory class for creating platform-specific implementations"""
    
    @staticmethod
    def get_platform() -> str:
        """Get the current platform identifier"""
        system = platform.system().lower()
        if system == "linux":
            # Check if we're on a Raspberry Pi
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    if 'Raspberry Pi' in f.read():
                        return "raspberry_pi"
            except:
                pass
        return system
    
    @classmethod
    def create_display(cls) -> DisplayInterface:
        """Create the appropriate display implementation for the current platform"""
        platform_name = cls.get_platform()
        
        if platform_name == "raspberry_pi":
            from src.platform.raspberry_pi.display import RaspberryPiDisplay
            return RaspberryPiDisplay()
        elif platform_name == "darwin":  # macOS
            from src.platform.macos.display import MacOSDisplay
            return MacOSDisplay()
        elif platform_name == "windows":
            from src.platform.windows.display import WindowsDisplay
            return WindowsDisplay()
        else:
            raise NotImplementedError(f"Platform {platform_name} is not supported")
    
    @classmethod
    def create_storage(cls) -> StorageInterface:
        """Create the appropriate storage implementation for the current platform"""
        platform_name = cls.get_platform()
        
        if platform_name == "raspberry_pi":
            from src.platform.raspberry_pi.storage import RaspberryPiStorage
            return RaspberryPiStorage()
        elif platform_name == "darwin":  # macOS
            from src.platform.macos.storage import MacOSStorage
            return MacOSStorage()
        elif platform_name == "windows":
            from src.platform.windows.storage import WindowsStorage
            return WindowsStorage()
        else:
            raise NotImplementedError(f"Platform {platform_name} is not supported")