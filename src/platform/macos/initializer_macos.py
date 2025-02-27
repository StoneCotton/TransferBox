# src/platform/macos/initializer-macos.py

import logging
from src.core.interfaces.platform import PlatformInitializer
from src.core.rich_display import RichDisplay
from .storage_macos import MacOSStorage
from src.core.exceptions import DisplayError, StorageError

logger = logging.getLogger(__name__)

class MacOSInitializer(PlatformInitializer):
    """Handles macOS specific initialization"""
    
    def initialize_hardware(self) -> None:
        """No hardware initialization needed for macOS"""
        try:
            logger.debug("MacOS hardware initialization (no-op)")
        except Exception as e:
            logger.error(f"Unexpected error in hardware initialization: {e}")

    def initialize_display(self) -> None:
        """Initialize Rich-based display"""
        try:
            logger.info("Initializing Rich display")
            self.display = RichDisplay()
            self.display.clear()
        except Exception as e:
            logger.error(f"Display initialization failed: {e}")
            raise DisplayError(f"Failed to initialize display: {e}")

    def initialize_storage(self) -> None:
        """Initialize storage detection"""
        try:
            logger.info("Initializing macOS storage")
            self.storage = MacOSStorage()
        except Exception as e:
            logger.error(f"Storage initialization failed: {e}")
            raise StorageError(f"Failed to initialize storage: {e}")

    def cleanup(self) -> None:
        """Perform cleanup with error handling"""
        try:
            logger.info("Performing macOS cleanup")
            if self.display:
                self.display.clear()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")