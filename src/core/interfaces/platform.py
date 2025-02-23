# src/core/interfaces/platform.py
from abc import ABC, abstractmethod
from typing import Optional
from .display import DisplayInterface
from .storage_inter import StorageInterface

class PlatformInitializer(ABC):
    """Abstract base class for platform-specific initialization"""
    
    def __init__(self):
        self.display: Optional[DisplayInterface] = None
        self.storage: Optional[StorageInterface] = None
    
    @abstractmethod
    def initialize_hardware(self) -> None:
        """Initialize any platform-specific hardware"""
        pass
    
    @abstractmethod
    def initialize_display(self) -> None:
        """Initialize the display system"""
        pass
    
    @abstractmethod
    def initialize_storage(self) -> None:
        """Initialize the storage system"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources before shutdown"""
        pass
    
    def initialize(self) -> tuple[DisplayInterface, StorageInterface]:
        """
        Initialize all platform components in the correct order
        Returns the display and storage interfaces
        """
        self.initialize_hardware()
        self.initialize_display()
        self.initialize_storage()
        return self.display, self.storage