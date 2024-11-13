# src/core/interfaces/storage.py
from abc import ABC, abstractmethod
from typing import List, Dict
from pathlib import Path

class StorageInterface(ABC):
    """Abstract base class for storage operations"""
    
    @abstractmethod
    def get_available_drives(self) -> List[Path]:
        """Get list of available storage drives"""
        pass
    
    @abstractmethod
    def get_drive_info(self, path: Path) -> Dict[str, int]:
        """Get storage drive information (total, used, free space)"""
        pass
    
    @abstractmethod
    def is_drive_mounted(self, path: Path) -> bool:
        """Check if a drive is mounted"""
        pass
    
    @abstractmethod
    def unmount_drive(self, path: Path) -> bool:
        """Unmount a drive"""
        pass