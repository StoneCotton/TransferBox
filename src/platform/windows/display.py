# src/platform/windows/display.py

import logging
import sys
import shutil
import time
from datetime import datetime
from typing import Optional
from colorama import init, Fore, Back, Style
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus

logger = logging.getLogger(__name__)

class WindowsDisplay(DisplayInterface):
    """
    Windows implementation of DisplayInterface using console output with colorama
    for colored text and progress bars.
    """
    
    def __init__(self):
        """Initialize Windows console display"""
        # Initialize colorama for Windows color support
        init(autoreset=True)
        
        # Get terminal size
        self.terminal_width = shutil.get_terminal_size().columns
        
        # Track current display state
        self.current_status: Optional[str] = None
        self.current_progress: Optional[TransferProgress] = None
        self._last_update = 0
        
        # Minimum time between updates (seconds) to prevent console flicker
        self._update_interval = 0.1
        
        logger.info("Windows display initialized")

    def _can_update(self) -> bool:
        """Check if enough time has passed for a new update"""
        current_time = time.time()
        if current_time - self._last_update >= self._update_interval:
            self._last_update = current_time
            return True
        return False

    def show_status(self, message: str, line: int = 0) -> None:
        """
        Display a status message in the console.
        
        Args:
            message: Message to display
            line: Line number (ignored in console output)
        """
        if not self._can_update():
            return
            
        self.current_status = message
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Clear line and print status
        sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        sys.stdout.write(f"{Fore.CYAN}[{timestamp}] {Fore.WHITE}{message}{Style.RESET_ALL}\n")
        sys.stdout.flush()
        
        logger.debug(f"Status: {message}")

    def show_progress(self, progress: TransferProgress) -> None:
        """
        Display transfer progress in the console.
        
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
        bar = ('█' * filled + '░' * (bar_width - filled))
        
        # Status-specific formatting
        status_colors = {
            TransferStatus.COPYING: Fore.BLUE,
            TransferStatus.CHECKSUMMING: Fore.YELLOW,
            TransferStatus.SUCCESS: Fore.GREEN,
            TransferStatus.ERROR: Fore.RED,
            TransferStatus.VERIFYING: Fore.MAGENTA
        }
        color = status_colors.get(progress.status, Fore.WHITE)
        
        # Clear line
        sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        
        # Show current operation
        sys.stdout.write(f"{color}{progress.status.name}: ")
        
        # Show progress bar
        percentage = progress.overall_progress * 100
        sys.stdout.write(f"{bar} {percentage:3.1f}%")
        
        # Show file progress
        if progress.current_file:
            sys.stdout.write(f"\n{Fore.CYAN}File: {progress.file_number}/{progress.total_files} - ")
            sys.stdout.write(f"{progress.current_file}")
            
            if progress.bytes_transferred > 0:
                mb_transferred = progress.bytes_transferred / (1024 * 1024)
                mb_total = progress.total_bytes / (1024 * 1024)
                sys.stdout.write(f" ({mb_transferred:.1f}MB/{mb_total:.1f}MB)")
        
        sys.stdout.write(Style.RESET_ALL)
        sys.stdout.flush()
        
        logger.debug(
            f"Progress update: {progress.overall_progress:.1%} - "
            f"File {progress.file_number}/{progress.total_files}"
        )

    def show_error(self, message: str) -> None:
        """
        Display an error message in the console.
        
        Args:
            message: Error message to display
        """
        if not self._can_update():
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Clear line and print error
        sys.stdout.write('\r' + ' ' * self.terminal_width + '\r')
        sys.stdout.write(
            f"{Fore.RED}[{timestamp}] ERROR: {message}{Style.RESET_ALL}\n"
        )
        sys.stdout.flush()
        
        logger.error(f"Display error: {message}")

    def clear(self) -> None:
        """Clear the console display"""
        if not self._can_update():
            return
            
        # Clear by printing newlines
        sys.stdout.write('\n' * 2)
        sys.stdout.flush()
        
        self.current_status = None
        self.current_progress = None
        
        logger.debug("Display cleared")