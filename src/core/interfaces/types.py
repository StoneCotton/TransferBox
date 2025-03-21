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
    bytes_transferred: int
    total_bytes: int
    total_transferred: int
    total_size: int
    current_file_progress: float
    overall_progress: float
    status: TransferStatus
    proxy_progress: float = 0.0
    proxy_file_number: int = 0
    proxy_total_files: int = 0
    speed_bytes_per_sec: float = 0.0
    eta_seconds: float = 0.0