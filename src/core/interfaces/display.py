# src/core/interfaces/display.py
from abc import ABC, abstractmethod
from .types import TransferProgress

class DisplayInterface(ABC):
    """Abstract base class for display implementations"""
    
    @abstractmethod
    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message"""
        pass
    
    @abstractmethod
    def show_progress(self, progress: TransferProgress) -> None:
        """Display transfer progress"""
        pass
    
    @abstractmethod
    def show_error(self, message: str) -> None:
        """Display an error message"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear the display"""
        pass