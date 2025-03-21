from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
    FileSizeColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
    SpinnerColumn
)
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from datetime import datetime
from pathlib import Path
from threading import Lock
import logging
from typing import Optional

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.core.exceptions import DisplayError
from src import __version__

logger = logging.getLogger(__name__)

class FileNameColumn(TextColumn):
    """Custom column for displaying filename with consistent width"""
    def __init__(self, width: int = 30):
        super().__init__(f"{{task.description:.{width}s}}")

class RichDisplay(DisplayInterface):
    """Platform-agnostic display implementation using Rich library"""
    
    def __init__(self):
        self.display_lock = Lock()
        self.console = Console()
        self._current_progress: Optional[TransferProgress] = None
        self.in_transfer_mode = False
        self.in_proxy_mode = False
        
        # Create progress display with improved column configuration
        # Note: Rich's size columns automatically handle binary formatting
        self.progress = Progress(
            SpinnerColumn(),                              # Shows an animated spinner
            FileNameColumn(width=50),                     # Custom column for filename
            BarColumn(bar_width=100, complete_style="blue"), # Progress bar
            FileSizeColumn(),                             # Current size - automatically formats
            TextColumn("/"),                              # Separator
            TotalFileSizeColumn(),                        # Total size - automatically formats
            TransferSpeedColumn(),                        # Transfer speed - automatically formats
            TimeElapsedColumn(),                          # Time elapsed
            TextColumn("ETA:"),                           # ETA label
            TimeRemainingColumn(),                        # Time remaining
            expand=True,                                  # Allow the progress bar to expand
            console=self.console
        )
        
        # Task IDs for different modes
        self.total_task_id = None
        self.copy_task_id = None
        self.checksum_task_id = None
        self.proxy_total_task_id = None
        self.proxy_current_task_id = None
        
        # Create layout
        self.layout = Layout()
        self.layout.split_column(
            Layout(name=f"TransferBox | v{__version__} | Made by Tyler Saari", size=2),
            Layout(name="progress", size=6)
        )
        
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=15,
            transient=True
        )

    def _initialize_transfer_mode(self):
            """
            Initialize progress bars for file transfer mode with proper size tracking.
            Creates entirely new Progress instance to ensure clean state.
            """
            # Ensure any previous display is fully cleaned up
            if self.live is not None:
                self._cleanup_progress()
                
            # Create a completely new Progress instance instead of reusing the old one
            self.progress = Progress(
                SpinnerColumn(),
                FileNameColumn(width=50),
                BarColumn(bar_width=100, complete_style="blue"),
                FileSizeColumn(),
                TextColumn("/"),
                TotalFileSizeColumn(),
                TransferSpeedColumn(),
                TimeElapsedColumn(),
                TextColumn("ETA:"),
                TimeRemainingColumn(),
                expand=True,
                console=self.console
            )
            
            # Initialize total progress with correct total size
            if self._current_progress:
                self.total_task_id = self.progress.add_task(
                    "Total Progress",
                    total=self._current_progress.total_size,
                    completed=self._current_progress.total_transferred,
                    visible=True
                )
                
                # Initialize current file progress
                self.copy_task_id = self.progress.add_task(
                    "Copy Progress",
                    total=self._current_progress.total_bytes,
                    completed=self._current_progress.bytes_transferred,
                    visible=True
                )
                
                # Initialize checksum progress
                self.checksum_task_id = self.progress.add_task(
                    "Checksum Progress",
                    total=self._current_progress.total_bytes,
                    completed=0,
                    visible=True
                )
            else:
                # Fallback initialization if no progress info available
                self.total_task_id = self.progress.add_task("Total Progress", total=100, visible=True)
                self.copy_task_id = self.progress.add_task("Copy Progress", total=100, visible=True)
                self.checksum_task_id = self.progress.add_task("Checksum Progress", total=100, visible=True)
            
            # Create new live display with fresh layout
            self.layout = Layout()
            self.layout.split_column(
                Layout(name=f"TransferBox | v{__version__} | Made by Tyler Saari", size=2),
                Layout(name="progress", size=6)
            )
            
            # Update layout with new progress instance
            self.layout["progress"].update(self.progress)
            
            self.live = Live(
                self.layout,
                console=self.console,
                refresh_per_second=15,
                transient=True
            )
            self.live.start()
            
            self.in_transfer_mode = True
            self.in_proxy_mode = False
            
            logger.debug("Transfer mode initialized with completely fresh progress display")

    def show_progress(self, progress: TransferProgress) -> None:
        """Update progress display with accurate size and speed tracking"""
        with self.display_lock:
            try:
                # Store current progress information
                self._current_progress = progress
                
                # Handle mode initialization
                if not self.in_transfer_mode and not self.in_proxy_mode:
                    if progress.status == TransferStatus.GENERATING_PROXY:
                        self._initialize_proxy_mode()
                    else:
                        self._initialize_transfer_mode()
                    self.live.start()

                # Handle completion
                if progress.status == TransferStatus.SUCCESS:
                    self._cleanup_progress()
                    return

                # Update progress based on mode
                if progress.status == TransferStatus.GENERATING_PROXY:
                    if not self.in_proxy_mode:
                        self._initialize_proxy_mode()
                    
                    # Update proxy progress bars with correct sizes
                    self.progress.update(
                        self.proxy_total_task_id,
                        completed=progress.total_transferred,
                        total=progress.total_size,
                        description=f"Total Progress ({progress.proxy_file_number}/{progress.proxy_total_files})",
                        speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
                        time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None
                    )
                    
                    self.progress.update(
                        self.proxy_current_task_id,
                        completed=progress.bytes_transferred,
                        total=progress.total_bytes,
                        description=f"Generating: {progress.current_file}",
                        speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
                        time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None
                    )
                else:
                    # Update transfer progress bars with correct sizes
                    self.progress.update(
                        self.total_task_id,
                        completed=progress.total_transferred,
                        total=progress.total_size,
                        description=f"Total Progress ({progress.file_number}/{progress.total_files})",
                        speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
                        time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None
                    )

                    if progress.status == TransferStatus.COPYING:
                        self.progress.update(
                            self.copy_task_id,
                            completed=progress.bytes_transferred,
                            total=progress.total_bytes,
                            description=f"Copying: {progress.current_file}",
                            speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
                            time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None
                        )
                        # Reset checksum progress during copy
                        self.progress.update(
                            self.checksum_task_id,
                            completed=0,
                            total=progress.total_bytes,
                            description="Waiting for checksum"
                        )
                    elif progress.status == TransferStatus.CHECKSUMMING:
                        # Keep copy progress complete during checksum
                        self.progress.update(
                            self.copy_task_id,
                            completed=progress.total_bytes,
                            total=progress.total_bytes,
                            description=f"Copied: {progress.current_file}"
                        )
                        # Update checksum progress
                        checksum_completed = int(progress.current_file_progress * progress.total_bytes)
                        self.progress.update(
                            self.checksum_task_id,
                            completed=checksum_completed,
                            total=progress.total_bytes,
                            description=f"Checksumming: {progress.current_file}",
                            speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
                            time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None
                        )

                # Update the layout
                self.layout["progress"].update(self.progress)

            except Exception as e:
                error_msg = f"Error updating progress display: {str(e)}"
                logger.error(error_msg)
                raise DisplayError(
                    error_msg,
                    display_type="rich",
                    error_type="progress_update"
                ) from e

    def _cleanup_progress(self, preserve_errors: bool = False) -> None:
            """
            Clean up progress display and reset state.
            This method ensures proper cleanup of the Rich Live display context
            and resets all associated state for a fresh start.
            
            Args:
                preserve_errors: When True, preserves any error messages that might be displayed
            """
            if self.in_transfer_mode or self.in_proxy_mode:
                try:
                    # First properly stop the live display if it's running
                    if self.live and self.live.is_started:
                        # Do one final refresh to ensure clean state
                        self.live.refresh()
                        # Stop the live display
                        self.live.stop()
                        # Set to None to ensure complete cleanup
                        self.live = None

                    # Clear all progress tasks
                    if hasattr(self, 'progress'):
                        self.progress.tasks.clear()
                    
                    # Reset all task IDs to ensure no stale references
                    self.total_task_id = None
                    self.copy_task_id = None
                    self.checksum_task_id = None
                    self.proxy_total_task_id = None
                    self.proxy_current_task_id = None
                    
                    # Reset state flags
                    self.in_transfer_mode = False
                    self.in_proxy_mode = False
                    
                    # Clear the console to remove any leftover output
                    # Only if we're not preserving error messages
                    if not preserve_errors:
                        self.console.clear()
                    
                    # Create a fresh layout for next use
                    self.layout = Layout()
                    if preserve_errors:
                        # Keep a minimal layout for error display
                        self.layout.split_column(
                            Layout(name=f"TransferBox | v{__version__} | Made by Tyler Saari", size=2)
                        )
                    else:
                        # Full layout for normal operation
                        self.layout.split_column(
                            Layout(name=f"TransferBox | v{__version__} | Made by Tyler Saari", size=2),
                            Layout(name="progress", size=6)
                        )
                    
                    logger.debug("Progress display cleaned up successfully")
                    
                except Exception as e:
                    error_msg = f"Error during progress display cleanup: {str(e)}"
                    logger.error(error_msg)
                    raise DisplayError(
                        error_msg,
                        display_type="rich",
                        error_type="cleanup"
                    ) from e

    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message."""
        try:
            if self.in_transfer_mode or self.in_proxy_mode:
                # When in progress mode, show status in the status panel
                self.layout["progress"].update(
                    Panel(Text(message, style="blue"))
                )
            else:
                # When not in progress mode, print directly to console
                self.console.print(Text(message, style="blue"))
            
            logger.debug(f"Status: {message}")
        except Exception as e:
            error_msg = f"Error displaying status message: {str(e)}"
            logger.error(error_msg)
            raise DisplayError(
                error_msg,
                display_type="rich",
                error_type="status_update"
            ) from e

    def show_error(self, message: str) -> None:
        """Display an error message."""
        try:
            # Make error message more prominent by printing it to console regardless of mode
            error_text = Text(f"❌ ERROR: {message}", style="red bold")
            
            if self.in_transfer_mode or self.in_proxy_mode:
                # Clean up any existing progress display first
                self._cleanup_progress(preserve_errors=True)
                
                # When in progress mode, show error in the status panel
                self.layout[f"TransferBox | v{__version__} | Made by Tyler Saari"].update(
                    Panel(error_text, border_style="red")
                )
                
                # Print to console only once
                self.console.print("\n" + "=" * 60)
                self.console.print(error_text)
                self.console.print("=" * 60)
            else:
                # When not in progress mode, print directly to console with visual emphasis
                self.console.print("\n" + "=" * 60)
                self.console.print(error_text)
                self.console.print("=" * 60)
            
            logger.error(f"Display error: {message}")
        except Exception as e:
            error_msg = f"Error displaying error message: {str(e)}"
            logger.error(error_msg)
            raise DisplayError(
                error_msg,
                display_type="rich",
                error_type="error_display"
            ) from e

    def clear(self, preserve_errors: bool = False) -> None:
        """
        Clear the display
        
        Args:
            preserve_errors: When True, preserves any error messages that might be displayed
        """
        with self.display_lock:
            try:
                # Clean up any existing progress display
                self._cleanup_progress(preserve_errors)
                
                # Clear the console completely if not preserving errors
                if not preserve_errors:
                    self.console.clear()
                    logger.debug("Display cleared")
                else:
                    logger.debug("Display clear skipped to preserve error messages")
            except Exception as e:
                error_msg = f"Error clearing display: {str(e)}"
                logger.error(error_msg)
                raise DisplayError(
                    error_msg,
                    display_type="rich",
                    error_type="clear"
                ) from e