# src/platform/macos/initializer.py
from src.core.interfaces.platform import PlatformInitializer
from .display import MacOSDisplay
from .storage import MacOSStorage

class MacOSInitializer(PlatformInitializer):
    def initialize_hardware(self) -> None:
        """No hardware initialization needed for macOS"""
        pass
    
    def initialize_display(self) -> None:
        """Initialize terminal display"""
        self.display = MacOSDisplay()
        self.display.clear()
    
    def initialize_storage(self) -> None:
        """Initialize storage detection"""
        self.storage = MacOSStorage()
    
    def cleanup(self) -> None:
        """No special cleanup needed for macOS"""
        pass