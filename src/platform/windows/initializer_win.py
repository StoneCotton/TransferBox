# src/platform/windows/initializer.py

import logging
from src.core.interfaces.platform import PlatformInitializer
from src.core.rich_display import RichDisplay
from src.core.exceptions import HardwareError, DisplayError, StorageError
from .storage_win import WindowsStorage

logger = logging.getLogger(__name__)

class WindowsInitializer(PlatformInitializer):
    """Handles Windows specific initialization"""
    
    def initialize_hardware(self) -> None:
        """No hardware initialization needed for Windows"""
        try:
            logger.debug("Windows hardware initialization (no-op)")
        except Exception as e:
            raise HardwareError(
                f"Unexpected error during Windows hardware initialization: {str(e)}",
                component="system",
                error_type="initialization"
            )
    
    def initialize_display(self) -> None:
        """Initialize Rich-based display"""
        try:
            logger.info("Initializing Rich display")
            self.display = RichDisplay()
            self.display.clear()
        except Exception as e:
            raise DisplayError(
                f"Failed to initialize Rich display: {str(e)}",
                display_type="rich",
                error_type="initialization"
            )
    
    def initialize_storage(self) -> None:
        """Initialize storage detection"""
        try:
            logger.info("Initializing Windows storage")
            self.storage = WindowsStorage()
        except Exception as e:
            raise StorageError(
                f"Failed to initialize Windows storage: {str(e)}",
                error_type="initialization"
            )
    
    def cleanup(self) -> None:
        """Perform any necessary cleanup"""
        try:
            logger.info("Performing Windows cleanup")
            if hasattr(self, 'display') and self.display:
                self.display.clear()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            # We don't raise here since cleanup should not throw errors
            # but we log the issue for debugging purposes