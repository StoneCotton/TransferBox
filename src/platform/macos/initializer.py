# src/platform/macos/initializer.py

import logging
from src.core.interfaces.platform import PlatformInitializer
from .display import MacOSDisplay
from .storage import MacOSStorage

logger = logging.getLogger(__name__)

class MacOSInitializer(PlatformInitializer):
    """Handles macOS specific initialization"""
    
    def initialize_hardware(self) -> None:
        """No hardware initialization needed for macOS"""
        logger.debug("MacOS hardware initialization (no-op)")
        pass
    
    def initialize_display(self) -> None:
        """Initialize terminal display"""
        logger.info("Initializing macOS display")
        self.display = MacOSDisplay()
        self.display.clear()
    
    def initialize_storage(self) -> None:
        """Initialize storage detection"""
        logger.info("Initializing macOS storage")
        self.storage = MacOSStorage()
    
    def cleanup(self) -> None:
        """Perform any necessary cleanup"""
        logger.info("Performing macOS cleanup")
        if self.display:
            self.display.clear()