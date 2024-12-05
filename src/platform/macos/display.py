# # src/platform/macos/display.py

# import logging
# import sys
# import shutil
# import time
# from datetime import datetime
# from typing import Optional
# import os
# from src.core.interfaces.display import DisplayInterface
# from src.core.interfaces.types import TransferProgress, TransferStatus

# logger = logging.getLogger(__name__)

# class MacOSDisplay(DisplayInterface):
#     """
#     macOS implementation of DisplayInterface using terminal output with
#     native terminal colors and advanced progress display.
#     """
    
#     # ANSI color codes for macOS Terminal
#     COLORS = {
#         'RESET': '\033[0m',
#         'BLACK': '\033[30m',
#         'RED': '\033[31m',
#         'GREEN': '\033[32m',
#         'YELLOW': '\033[33m',
#         'BLUE': '\033[34m',
#         'MAGENTA': '\033[35m',
#         'CYAN': '\033[36m',
#         'WHITE': '\033[37m',
#         'BRIGHT_BLACK': '\033[90m',
#         'BRIGHT_RED': '\033[91m',
#         'BRIGHT_GREEN': '\033[92m',
#         'BRIGHT_YELLOW': '\033[93m',
#         'BRIGHT_BLUE': '\033[94m',
#         'BRIGHT_MAGENTA': '\033[95m',
#         'BRIGHT_CYAN': '\033[96m',
#         'BRIGHT_WHITE': '\033[97m',
#     }
    
#     def __init__(self):
#         """Initialize macOS terminal display"""
#         self.terminal_width = shutil.get_terminal_size().columns
#         self.progress_bar_width = min(50, self.terminal_width - 30)
        
#         # Track current display state
#         self.current_status: Optional[str] = None
#         self.current_progress: Optional[TransferProgress] = None
#         self._last_update = 0
#         self._update_interval = 0.01  # Match Windows refresh rate
        
#         # Track display mode
#         self.in_transfer_mode = False
        
#         # Progress display layout
#         self.STATUS_LINE = 0
#         self.TOTAL_PROGRESS_LINE = 1
#         self.FILE_INFO_LINE = 2
#         self.COPY_PROGRESS_LINE = 3
#         self.CHECKSUM_PROGRESS_LINE = 4
#         self.TOTAL_LINES = 5
        
#         # Track operation progress
#         self.copy_progress = 0.0
#         self.checksum_progress = 0.0
        
#         logger.info(f"macOS display initialized ({'iTerm' if 'ITERM_SESSION_ID' in os.environ else 'Terminal.app'})")

#     def _create_progress_bar(self, progress: float, width: int = None) -> str:
#         """Create a progress bar string"""
#         if width is None:
#             width = self.progress_bar_width
#         filled = int(progress * width)
#         # Use Unicode blocks for better-looking progress bars
#         return '█' * filled + '░' * (width - filled)

#     def _clear_screen(self):
#         """Clear entire screen and reset cursor"""
#         sys.stdout.write('\033[2J\033[H')
#         sys.stdout.flush()

#     def _move_to_line(self, line: int):
#         """Move cursor to specific line"""
#         sys.stdout.write(f'\033[{line + 1};0H')

#     def _clear_line(self):
#         """Clear current line"""
#         sys.stdout.write('\033[2K\r')

#     def _enter_transfer_mode(self):
#         """Enter transfer display mode"""
#         if not self.in_transfer_mode:
#             self.in_transfer_mode = True
#             self._clear_screen()
#             # Disable console logging during transfer
#             logging.getLogger().console_handler.transfer_mode = True
#             # Initialize progress display
#             sys.stdout.write('\n' * self.TOTAL_LINES)
#             self.copy_progress = 0.0
#             self.checksum_progress = 0.0

#     def _exit_transfer_mode(self):
#         """Exit transfer display mode"""
#         if self.in_transfer_mode:
#             self.in_transfer_mode = False
#             self._clear_screen()
#             # Re-enable console logging
#             logging.getLogger().console_handler.transfer_mode = False
#             self.copy_progress = 0.0
#             self.checksum_progress = 0.0

#     def enter_standby(self):
#         """Handle entering standby state"""
#         if self.in_transfer_mode:
#             self._exit_transfer_mode()
#         # Show standby status on clean screen
#         timestamp = datetime.now().strftime('%H:%M:%S')
#         print(f"{self.COLORS['CYAN']}[{timestamp}]{self.COLORS['WHITE']} Standby{self.COLORS['RESET']}")

#     def _can_update(self) -> bool:
#         """Check if enough time has passed for update"""
#         current_time = time.time()
#         if current_time - self._last_update >= self._update_interval:
#             self._last_update = current_time
#             return True
#         return False

#     def show_status(self, message: str, line: int = 0) -> None:
#         """Display status message"""
#         if not self._can_update():
#             return
            
#         timestamp = datetime.now().strftime('%H:%M:%S')
        
#         # If entering standby from transfer mode, handle state transition
#         if message.lower() in ["standby", "input card"] and self.in_transfer_mode:
#             self.enter_standby()
            
#         elif self.in_transfer_mode:
#             # During transfer, only update the status line in the progress display
#             self._move_to_line(self.STATUS_LINE)
#             self._clear_line()
#             sys.stdout.write(
#                 f"{self.COLORS['CYAN']}[{timestamp}] "
#                 f"{self.COLORS['WHITE']}{message}"
#                 f"{self.COLORS['RESET']}"
#             )
#         else:
#             # Outside transfer, print normally
#             print(
#                 f"{self.COLORS['CYAN']}[{timestamp}]"
#                 f"{self.COLORS['WHITE']} {message}"
#                 f"{self.COLORS['RESET']}"
#             )
            
#         sys.stdout.flush()
#         logger.debug(f"Status: {message}")

#     def show_progress(self, progress: TransferProgress) -> None:
#         """Display transfer progress with consistent progress bars"""
#         if not self._can_update():
#             return

#         self._enter_transfer_mode()

#         # Check if transfer is complete
#         if progress.status == TransferStatus.SUCCESS:
#             self._exit_transfer_mode()
#             return

#         # Update total progress
#         self._move_to_line(self.TOTAL_PROGRESS_LINE)
#         self._clear_line()
#         total_bar = self._create_progress_bar(progress.overall_progress)
#         sys.stdout.write(
#             f"Total Progress: {total_bar} "
#             f"{progress.overall_progress * 100:3.1f}%"
#         )

#         # Update file info
#         self._move_to_line(self.FILE_INFO_LINE)
#         self._clear_line()
#         if progress.current_file:
#             size_mb = progress.total_bytes / (1024 * 1024)
#             progress_mb = progress.bytes_transferred / (1024 * 1024)
#             sys.stdout.write(
#                 f"File {progress.file_number}/{progress.total_files}: "
#                 f"{progress.current_file} ({progress_mb:.1f}MB/{size_mb:.1f}MB)"
#             )

#         # Update operation progress bars based on current state
#         if progress.status == TransferStatus.COPYING:
#             self.copy_progress = progress.current_file_progress
#             # Reset checksum progress when starting new copy
#             self.checksum_progress = 0.0
#         elif progress.status == TransferStatus.CHECKSUMMING:
#             # Keep copy progress at 100% during checksumming
#             self.copy_progress = 1.0
#             if progress.current_file_progress <= 0.5:
#                 checksum_message = "Source"
#                 self.checksum_progress = progress.current_file_progress * 2
#             else:
#                 checksum_message = "Destination"
#                 self.checksum_progress = (progress.current_file_progress - 0.5) * 2

#         # Show copy progress
#         self._move_to_line(self.COPY_PROGRESS_LINE)
#         self._clear_line()
#         copy_bar = self._create_progress_bar(self.copy_progress)
#         sys.stdout.write(
#             f"{self.COLORS['BLUE']}Copying: {copy_bar} "
#             f"{self.copy_progress * 100:3.1f}%{self.COLORS['RESET']}"
#         )

#         # Show checksum progress
#         self._move_to_line(self.CHECKSUM_PROGRESS_LINE)
#         self._clear_line()
#         checksum_bar = self._create_progress_bar(self.checksum_progress)
#         if progress.status == TransferStatus.CHECKSUMMING:
#             sys.stdout.write(
#                 f"{self.COLORS['YELLOW']}Checksumming ({checksum_message}): {checksum_bar} "
#                 f"{self.checksum_progress * 100:3.1f}%{self.COLORS['RESET']}"
#             )
#         else:
#             sys.stdout.write(
#                 f"{self.COLORS['YELLOW']}Checksumming: {checksum_bar} "
#                 f"{self.checksum_progress * 100:3.1f}%{self.COLORS['RESET']}"
#             )

#         sys.stdout.flush()

#     def show_error(self, message: str) -> None:
#         """Display error message"""
#         if not self._can_update():
#             return

#         timestamp = datetime.now().strftime('%H:%M:%S')
        
#         if self.in_transfer_mode:
#             self._move_to_line(self.STATUS_LINE)
#             self._clear_line()
#             sys.stdout.write(
#                 f"{self.COLORS['RED']}[{timestamp}] ERROR: {message}"
#                 f"{self.COLORS['RESET']}"
#             )
#         else:
#             print(
#                 f"{self.COLORS['RED']}[{timestamp}] ERROR: {message}"
#                 f"{self.COLORS['RESET']}"
#             )
            
#         sys.stdout.flush()
#         logger.error(f"Display error: {message}")

#     def clear(self) -> None:
#         """Clear display and exit transfer mode"""
#         self._exit_transfer_mode()
#         self.current_status = None
#         self.current_progress = None
#         self.copy_progress = 0.0
#         self.checksum_progress = 0.0
#         logger.debug("Display cleared")