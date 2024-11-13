# src/platform/macos/display.py

import logging
import sys
import shutil
import time
from datetime import datetime
from typing import Optional
import os
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus

logger = logging.getLogger(__name__)

class MacOSDisplay(DisplayInterface):
    """
    macOS implementation of DisplayInterface using terminal output with
    native terminal colors and Unicode characters for better rendering.
    """
    
    # ANSI color codes - macOS Terminal supports these natively
    COLORS = {
        'RESET': '\033[0m',
        'BLACK': '\033[30m',
        'RED': '\033[31m',
        'GREEN': '\033[32m',
        'YELLOW': '\033[33m',
        'BLUE': '\033[34m',
        'MAGENTA': '\033[35m',
        'CYAN': '\033[36m',
        'WHITE': '\033[37m',
        'BRIGHT_BLACK': '\033[90m',
        'BRIGHT_RED': '\033[91m',
        'BRIGHT_GREEN': '\033[92m',
        'BRIGHT_YELLOW': '\033[93m',
        'BRIGHT_BLUE': '\033[94m',
        'BRIGHT_MAGENTA': '\033[95m',
        'BRIGHT_CYAN': '\033[96m',
        'BRIGHT_WHITE': '\033[97m',
    }
    
    def __init__(self):
        """Initialize macOS terminal display"""
        # Get terminal size
        self.terminal_width = shutil.get_terminal_size().columns
        
        # Track current display state
        self.current_status: Optional[str] = None
        self.current_progress: Optional[TransferProgress] = None
        self._last_update = 0
        
        # Minimum time between updates (seconds)
        self._update_interval = 0.1
        
        # Check if running in Terminal.app or iTerm
        self.is_iterm = 'ITERM_SESSION_ID' in os.environ
        
        # Use prettier Unicode blocks in iTerm
        self.block_char = '▇' if self.is_iterm else '█'
        self.empty_char = '▁' if self.is_iterm else '░'
        
        logger.info(f"macOS display initialized ({'iTerm' if self.is_iterm else 'Terminal.app'})")

    def _can_update(self) -> bool:
        """Check if enough time has passed for a new update"""
        current_time = time.time()
        if current_time - self._last_update >= self._update_interval:
            self._last_update = current_time
            return True
        return False

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}PB"

    def show_status(self, message: str, line: int = 0) -> None:
        """
        Display a status message in the terminal.
        
        Args:
            message: Message to display
            line: Line number (ignored in terminal output)
        """
        if not self._can_update():
            return
            
        self.current_status = message
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Clear line and print status
        sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        sys.stdout.write(
            f"{self.COLORS['CYAN']}[{timestamp}] "
            f"{self.COLORS['WHITE']}{message}"
            f"{self.COLORS['RESET']}\n"
        )
        sys.stdout.flush()
        
        logger.debug(f"Status: {message}")

    def show_progress(self, progress: TransferProgress) -> None:
        """
        Display transfer progress in the terminal.
        
        Args:
            progress: Transfer progress information
        """
        if not self._can_update():
            return
            
        self.current_progress = progress
        
        # Calculate progress bar width
        bar_width = min(50, self.terminal_width - 30)
        filled = int(progress.overall_progress * bar_width)
        
        # Create progress bar
        bar = (self.block_char * filled + self.empty_char * (bar_width - filled))
        
        # Status-specific formatting
        status_colors = {
            TransferStatus.COPYING: self.COLORS['BLUE'],
            TransferStatus.CHECKSUMMING: self.COLORS['YELLOW'],
            TransferStatus.SUCCESS: self.COLORS['GREEN'],
            TransferStatus.ERROR: self.COLORS['RED'],
            TransferStatus.VERIFYING: self.COLORS['MAGENTA']
        }
        color = status_colors.get(progress.status, self.COLORS['WHITE'])
        
        # Clear previous lines if showing file progress
        if progress.current_file:
            sys.stdout.write('\033[2K\033[1A\033[2K\r')
        else:
            sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        
        # Show current operation and progress bar
        sys.stdout.write(
            f"{color}{progress.status.name}: "
            f"{bar} {progress.overall_progress * 100:3.1f}%"
            f"{self.COLORS['RESET']}"
        )
        
        # Show file progress on next line
        if progress.current_file:
            transfer_rate = progress.bytes_transferred / max(time.time() - self._last_update, 0.1)
            sys.stdout.write(
                f"\n{self.COLORS['CYAN']}File {progress.file_number}/{progress.total_files}: "
                f"{progress.current_file} "
                f"({self._format_size(progress.bytes_transferred)}/"
                f"{self._format_size(progress.total_bytes)}) "
                f"[{self._format_size(transfer_rate)}/s]"
                f"{self.COLORS['RESET']}"
            )
        
        sys.stdout.flush()
        
        logger.debug(
            f"Progress update: {progress.overall_progress:.1%} - "
            f"File {progress.file_number}/{progress.total_files}"
        )

    def show_error(self, message: str) -> None:
        """
        Display an error message in the terminal.
        
        Args:
            message: Error message to display
        """
        if not self._can_update():
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Clear line and print error
        sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        sys.stdout.write(
            f"{self.COLORS['RED']}[{timestamp}] ⚠️  ERROR: {message}"
            f"{self.COLORS['RESET']}\n"
        )
        sys.stdout.flush()
        
        logger.error(f"Display error: {message}")

    def clear(self) -> None:
        """Clear the terminal display"""
        if not self._can_update():
            return
            
        # Use ANSI escape codes to clear screen
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()
        
        self.current_status = None
        self.current_progress = None
        
        logger.debug("Display cleared")