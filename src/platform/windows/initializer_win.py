# src/platform/windows/initializer.py

import logging
from src.core.interfaces.platform import PlatformInitializer
from src.core.rich_display import RichDisplay
from .storage_win import WindowsStorage

logger = logging.getLogger(__name__)

class WindowsInitializer(PlatformInitializer):
    """Handles Windows specific initialization"""
    
    def initialize_hardware(self) -> None:
        """No hardware initialization needed for Windows"""
        logger.debug("Windows hardware initialization (no-op)")
        pass
    
    def initialize_display(self) -> None:
        """Initialize Rich-based display"""
        logger.info("Initializing Rich display")
        self.display = RichDisplay()
        self.display.clear()
    
    def initialize_storage(self) -> None:
        """Initialize storage detection"""
        logger.info("Initializing Windows storage")
        self.storage = WindowsStorage()
    
    def cleanup(self) -> None:
        """Perform any necessary cleanup"""
        logger.info("Performing Windows cleanup")
        if self.display:
            self.display.clear()