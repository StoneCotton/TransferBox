# src/core/interfaces/types.py
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

class TransferStatus(Enum):
    """Enum representing the current status of a transfer operation"""
    READY = auto()
    COPYING = auto()
    CHECKSUMMING = auto()
    VERIFYING = auto()
    SUCCESS = auto()
    ERROR = auto()

@dataclass
class TransferProgress:
    """Data class for transfer progress information"""
    current_file: str
    file_number: int
    total_files: int
    bytes_transferred: int
    total_bytes: int
    current_file_progress: float
    overall_progress: float  # This will now represent files completed / total files
    status: TransferStatus
    error_message: Optional[str] = None