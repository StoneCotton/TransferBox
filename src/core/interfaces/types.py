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
    GENERATING_PROXY = auto()
    VERIFYING = auto()
    SUCCESS = auto()
    ERROR = auto()

@dataclass
class TransferProgress:
    current_file: str
    file_number: int
    total_files: int
    bytes_transferred: int     # Current file progress
    total_bytes: int          # Current file size
    total_transferred: int    # Total bytes transferred across all files
    total_size: int          # Total size of all files
    current_file_progress: float
    overall_progress: float
    status: TransferStatus
    error_message: Optional[str] = None