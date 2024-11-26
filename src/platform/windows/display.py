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
    def __init__(self):
        init(autoreset=True)
        self.terminal_width = shutil.get_terminal_size().columns
        self.progress_bar_width = min(50, self.terminal_width - 30)
        
        # Track current display state
        self.current_status: Optional[str] = None
        self.current_progress: Optional[TransferProgress] = None
        self._last_update = 0
        # Increase update frequency
        self._update_interval = 0.01  # Changed from 0.1 to 0.01 for more frequent updates
        
        # Track display mode
        self.in_transfer_mode = False
        
        # Progress display layout
        self.STATUS_LINE = 0
        self.TOTAL_PROGRESS_LINE = 1
        self.FILE_INFO_LINE = 2
        self.COPY_PROGRESS_LINE = 3
        self.CHECKSUM_PROGRESS_LINE = 4
        self.TOTAL_LINES = 5
        
        # Track operation progress
        self.copy_progress = 0.0
        self.checksum_progress = 0.0
        
        logger.info("Windows display initialized")


    def _create_progress_bar(self, progress: float, width: int = None) -> str:
        """Create a progress bar string"""
        if width is None:
            width = self.progress_bar_width
        filled = int(progress * width)
        return '█' * filled + '░' * (width - filled)

    def _clear_screen(self):
        """Clear entire screen and reset cursor"""
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()

    def _move_to_line(self, line: int):
        """Move cursor to specific line"""
        sys.stdout.write(f'\033[{line + 1};0H')

    def _clear_line(self):
        """Clear current line"""
        sys.stdout.write('\033[2K\r')

    def _enter_transfer_mode(self):
        """Enter transfer display mode"""
        if not self.in_transfer_mode:
            self.in_transfer_mode = True
            self._clear_screen()
            # Disable console logging during transfer
            logging.getLogger().console_handler.transfer_mode = True
            # Initialize progress display
            sys.stdout.write('\n' * self.TOTAL_LINES)
            self.copy_progress = 0.0
            self.checksum_progress = 0.0

    def _exit_transfer_mode(self):
        """Exit transfer display mode"""
        if self.in_transfer_mode:
            self.in_transfer_mode = False
            self._clear_screen()
            # Re-enable console logging
            logging.getLogger().console_handler.transfer_mode = False
            # Show final status
            if self.current_status:
                print(f"{Fore.CYAN}[{datetime.now().strftime('%H:%M:%S')}]{Fore.WHITE} "
                      f"Transfer complete{Style.RESET_ALL}")

    def _can_update(self) -> bool:
        """Check if enough time has passed for update"""
        current_time = time.time()
        if current_time - self._last_update >= self._update_interval:
            self._last_update = current_time
            return True
        return False

    def show_status(self, message: str, line: int = 0) -> None:
        """Display status message"""
        if not self._can_update():
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if self.in_transfer_mode:
            # During transfer, only update the status line in the progress display
            self._move_to_line(self.STATUS_LINE)
            self._clear_line()
            sys.stdout.write(f"{Fore.CYAN}[{timestamp}] {Fore.WHITE}{message}{Style.RESET_ALL}")
        else:
            # Outside transfer, print normally
            print(f"{Fore.CYAN}[{timestamp}]{Fore.WHITE} {message}{Style.RESET_ALL}")
            
        sys.stdout.flush()
        logger.debug(f"Status: {message}")

    def show_progress(self, progress: TransferProgress) -> None:
        """Display transfer progress with consistent progress bars"""
        if not self._can_update():
            return

        self._enter_transfer_mode()

        # Check if transfer is complete
        if progress.status == TransferStatus.SUCCESS:
            self._exit_transfer_mode()
            return

        # Update total progress
        self._move_to_line(self.TOTAL_PROGRESS_LINE)
        self._clear_line()
        total_bar = self._create_progress_bar(progress.overall_progress)
        sys.stdout.write(
            f"Total Progress: {total_bar} "
            f"{progress.overall_progress * 100:3.1f}%"
        )

        # Update file info
        self._move_to_line(self.FILE_INFO_LINE)
        self._clear_line()
        if progress.current_file:
            size_mb = progress.total_bytes / (1024 * 1024)
            progress_mb = progress.bytes_transferred / (1024 * 1024)
            sys.stdout.write(
                f"File {progress.file_number}/{progress.total_files}: "
                f"{progress.current_file} ({progress_mb:.1f}MB/{size_mb:.1f}MB)"
            )

        # Update operation progress bars based on current state
        if progress.status == TransferStatus.COPYING:
            self.copy_progress = progress.current_file_progress
            self.checksum_progress = 0.0
        elif progress.status == TransferStatus.CHECKSUMMING:
            self.copy_progress = 1.0
            self.checksum_progress = progress.current_file_progress

        # Always show copy progress
        self._move_to_line(self.COPY_PROGRESS_LINE)
        self._clear_line()
        copy_bar = self._create_progress_bar(self.copy_progress)
        sys.stdout.write(
            f"{Fore.BLUE}Copying: {copy_bar} "
            f"{self.copy_progress * 100:3.1f}%{Style.RESET_ALL}"
        )

        # Always show checksum progress
        self._move_to_line(self.CHECKSUM_PROGRESS_LINE)
        self._clear_line()
        checksum_bar = self._create_progress_bar(self.checksum_progress)
        sys.stdout.write(
            f"{Fore.YELLOW}Checksumming: {checksum_bar} "
            f"{self.checksum_progress * 100:3.1f}%{Style.RESET_ALL}"
        )

        sys.stdout.flush()

    def show_error(self, message: str) -> None:
        """Display error message"""
        if not self._can_update():
            return

        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if self.in_transfer_mode:
            self._move_to_line(self.STATUS_LINE)
            self._clear_line()
            sys.stdout.write(
                f"{Fore.RED}[{timestamp}] ERROR: {message}{Style.RESET_ALL}"
            )
        else:
            print(f"{Fore.RED}[{timestamp}] ERROR: {message}{Style.RESET_ALL}")
            
        sys.stdout.flush()
        logger.error(f"Display error: {message}")

    def clear(self) -> None:
        """Clear display and exit transfer mode"""
        self._exit_transfer_mode()
        self.current_status = None
        self.current_progress = None
        self.copy_progress = 0.0
        self.checksum_progress = 0.0
        logger.debug("Display cleared")