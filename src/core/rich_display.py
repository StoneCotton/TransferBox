from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
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
from typing import Optional, Literal
from enum import Enum, auto

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.core.exceptions import DisplayError
from src import __version__

logger = logging.getLogger(__name__)

class DisplayMode(Enum):
    """Enum to represent different display modes"""
    NONE = auto()
    TRANSFER = auto()
    PROXY = auto()

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
        self.display_mode = DisplayMode.NONE
        self.setup_in_progress = False
        
        # Task IDs for different modes
        self.total_task_id = None
        self.copy_task_id = None
        self.checksum_task_id = None
        self.proxy_total_task_id = None
        self.proxy_current_task_id = None
        
        # Keep Live display initially set to None
        self.live = None
        self.progress = None
        
        # Clear the screen and display the header right away
        self.clear_screen()
        self.show_header()

    def clear_screen(self):
        """Clear the entire console screen."""
        self.console.clear()
        logger.debug("Screen cleared")

    def show_header(self):
        """Display the application header at the top of the console."""
        # Create a header panel with styling
        header = Panel(
            Text(f"TransferBox | v{__version__} | Made by Tyler Saari", style="bold blue", justify="center"),
            border_style="blue",
            padding=(0, 0)
        )
        
        # Print the header directly to the console
        self.console.print(header)
        logger.debug("Header displayed")

    def _create_progress_instance(self, style: str = "blue"):
        """
        Create a new Progress instance with standard columns.
        """
        return Progress(
            SpinnerColumn(),
            FileNameColumn(width=50),
            BarColumn(bar_width=100, complete_style=style),
            FileSizeColumn(),
            TextColumn("/"),
            TotalFileSizeColumn(),
            TransferSpeedColumn(),
            TextColumn("Elapsed:"),
            TextColumn("[cyan]{task.fields[elapsed]:>8}"),
            TextColumn("ETA:"),
            TimeRemainingColumn(),
            expand=True,
            console=self.console
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        # Format seconds as H:MM:SS
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02}:{s:02}"
        else:
            return f"{m}:{s:02}"

    def _initialize_display_mode(self, mode: DisplayMode):
        """
        Initialize progress bars for the specified mode.
        Creates entirely new Progress instance to ensure clean state.
        
        Args:
            mode: The display mode to initialize
        """
        # Ensure any previous display is fully cleaned up
        if self.live is not None:
            self._cleanup_progress()
        
        # Set the display mode
        self.display_mode = mode
        
        # Create a fresh Progress instance with appropriate style
        style = "green" if mode == DisplayMode.PROXY else "blue"
        self.progress = self._create_progress_instance(style)
        
        # Initialize progress tasks based on mode
        if mode == DisplayMode.PROXY:
            self._initialize_proxy_tasks()
        elif mode == DisplayMode.TRANSFER:
            self._initialize_transfer_tasks()
        
        # Clear screen and show header before starting live display
        self.clear_screen()
        self.show_header()
        
        # Create and start a Live display
        self.live = Live(
            self.progress,
            console=self.console,
            refresh_per_second=15,
            transient=False  # Don't clear the display when stopping
        )
        self.live.start()
        
        logger.debug(f"{mode.name} mode initialized with fresh progress display")

    def _initialize_proxy_tasks(self):
        """Initialize tasks for proxy generation mode."""
        default_fields = dict(elapsed="")
        if self._current_progress:
            self.proxy_total_task_id = self.progress.add_task(
                "Total Progress",
                total=self._current_progress.total_size,
                completed=self._current_progress.total_transferred,
                visible=True,
                **default_fields
            )
            
            self.proxy_current_task_id = self.progress.add_task(
                "Proxy Progress",
                total=self._current_progress.total_bytes,
                completed=self._current_progress.bytes_transferred,
                visible=True,
                **default_fields
            )
        else:
            # Fallback initialization if no progress info available
            self.proxy_total_task_id = self.progress.add_task("Total Progress", total=100, visible=True, **default_fields)
            self.proxy_current_task_id = self.progress.add_task("Proxy Progress", total=100, visible=True, **default_fields)

    def _initialize_transfer_tasks(self):
        """Initialize tasks for file transfer mode."""
        default_fields = dict(elapsed="")
        if self._current_progress:
            self.total_task_id = self.progress.add_task(
                "Total Progress",
                total=self._current_progress.total_size,
                completed=self._current_progress.total_transferred,
                visible=True,
                **default_fields
            )
            # Initialize current file progress
            self.copy_task_id = self.progress.add_task(
                "Copy Progress",
                total=self._current_progress.total_bytes,
                completed=self._current_progress.bytes_transferred,
                visible=True,
                **default_fields
            )
            # Initialize checksum progress
            self.checksum_task_id = self.progress.add_task(
                "Checksum Progress",
                total=self._current_progress.total_bytes,
                completed=0,
                visible=True,
                **default_fields
            )
        else:
            self.total_task_id = self.progress.add_task("Total Progress", total=100, visible=True, **default_fields)
            self.copy_task_id = self.progress.add_task("Copy Progress", total=100, visible=True, **default_fields)
            self.checksum_task_id = self.progress.add_task("Checksum Progress", total=100, visible=True, **default_fields)

    def _update_progress_task(self, task_id, progress, description, completed=None, total=None, elapsed=None):
        """
        Helper method to update a progress task with common parameters.
        """
        if task_id is None:
            return
        self.progress.update(
            task_id,
            completed=completed if completed is not None else progress.bytes_transferred,
            total=total if total is not None else progress.total_bytes,
            description=description,
            speed=progress.speed_bytes_per_sec if progress.speed_bytes_per_sec > 0 else None,
            time_remaining=progress.eta_seconds if progress.eta_seconds > 0 else None,
            elapsed=elapsed if elapsed is not None else "-:--:--"
        )

    def show_progress(self, progress: TransferProgress) -> None:
        """Update progress display with accurate size and speed tracking"""
        with self.display_lock:
            try:
                # Store current progress information
                self._current_progress = progress
                
                # Check for transfer completion
                if progress.status == TransferStatus.SUCCESS:
                    self._handle_transfer_success()
                    return

                # Initialize or update the mode based on progress status
                self._ensure_correct_display_mode(progress.status)
                
                # Update progress based on current mode and status
                if self.display_mode == DisplayMode.PROXY:
                    self._update_proxy_progress(progress)
                else:
                    self._update_transfer_progress(progress)

            except Exception as e:
                self._handle_exception("Error updating progress display", e, "progress_update")

    def _handle_transfer_success(self):
        """Handle successful transfer completion."""
        self._cleanup_progress()
        # Clear the screen and redisplay everything
        self.clear_screen()
        self.show_header()
        # Show a completion message
        self.console.print(Text("Transfer completed successfully!", style="green bold"))

    def _ensure_correct_display_mode(self, status):
        """Initialize or switch to the correct display mode if needed."""
        if status == TransferStatus.GENERATING_PROXY:
            if self.display_mode != DisplayMode.PROXY:
                self._initialize_display_mode(DisplayMode.PROXY)
        elif self.display_mode == DisplayMode.NONE:
            self._initialize_display_mode(DisplayMode.TRANSFER)

    def _update_proxy_progress(self, progress):
        """Update progress displays for proxy generation mode."""
        # Update the total progress task (show total elapsed time)
        self._update_progress_task(
            self.proxy_total_task_id,
            progress,
            f"Total Progress ({progress.proxy_file_number}/{progress.proxy_total_files})",
            completed=progress.total_transferred,
            total=progress.total_size,
            elapsed=self._format_time(progress.total_elapsed) if hasattr(progress, 'total_elapsed') and progress.total_elapsed > 0 else "-:--:--"
        )
        # Update the current file progress task (show file elapsed time)
        self._update_progress_task(
            self.proxy_current_task_id,
            progress,
            f"Generating: {progress.current_file}",
            elapsed=self._format_time(progress.file_elapsed) if hasattr(progress, 'file_elapsed') and progress.file_elapsed > 0 else "-:--:--"
        )

    def _update_transfer_progress(self, progress):
        """Update progress displays for file transfer mode."""
        # Update the total progress task (show total elapsed time)
        self._update_progress_task(
            self.total_task_id,
            progress,
            f"Total Progress ({progress.file_number}/{progress.total_files})",
            completed=progress.total_transferred,
            total=progress.total_size,
            elapsed=self._format_time(progress.total_elapsed) if hasattr(progress, 'total_elapsed') and progress.total_elapsed > 0 else "-:--:--"
        )
        # Update tasks based on current transfer status
        if progress.status == TransferStatus.COPYING:
            self._update_copy_progress(progress)
        elif progress.status == TransferStatus.CHECKSUMMING:
            self._update_checksum_progress(progress)

    def _update_copy_progress(self, progress):
        """Update progress displays during file copying."""
        # Update copy progress (show file elapsed time)
        self._update_progress_task(
            self.copy_task_id,
            progress,
            f"Copying: {progress.current_file}",
            elapsed=self._format_time(progress.file_elapsed) if hasattr(progress, 'file_elapsed') and progress.file_elapsed > 0 else "-:--:--"
        )
        # Reset checksum progress (blank elapsed)
        if self.checksum_task_id is not None:
            self.progress.update(
                self.checksum_task_id,
                completed=0,
                total=progress.total_bytes,
                description="Waiting for checksum",
                elapsed="-:--:--"
            )

    def _update_checksum_progress(self, progress):
        """Update progress displays during checksumming."""
        # Mark copy as complete (blank elapsed)
        if self.copy_task_id is not None:
            self.progress.update(
                self.copy_task_id,
                completed=progress.total_bytes,
                total=progress.total_bytes,
                description=f"Copied: {progress.current_file}",
                elapsed="-:--:--"
            )
        # Update checksum progress (show checksum elapsed time)
        checksum_completed = int(progress.current_file_progress * progress.total_bytes)
        self._update_progress_task(
            self.checksum_task_id,
            progress,
            f"Checksumming: {progress.current_file}",
            completed=checksum_completed,
            elapsed=self._format_time(progress.checksum_elapsed) if hasattr(progress, 'checksum_elapsed') and progress.checksum_elapsed > 0 else "-:--:--"
        )

    def _handle_exception(self, message, exception, error_type):
        """Centralized error handling for display operations."""
        error_msg = f"{message}: {str(exception)}"
        logger.error(error_msg)
        raise DisplayError(
            error_msg,
            display_type="rich",
            error_type=error_type
        ) from exception

    def _cleanup_progress(self, preserve_errors: bool = False) -> None:
        """
        Clean up progress display and reset state.
        This method ensures proper cleanup of the Rich Live display context
        and resets all associated state for a fresh start.
        
        Args:
            preserve_errors: When True, preserves any error messages that might be displayed
        """
        if self.display_mode != DisplayMode.NONE:
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
                if hasattr(self, 'progress') and self.progress:
                    self.progress.tasks.clear()
                
                # Reset all task IDs to ensure no stale references
                self.total_task_id = None
                self.copy_task_id = None
                self.checksum_task_id = None
                self.proxy_total_task_id = None
                self.proxy_current_task_id = None
                
                # Reset state flags
                self.display_mode = DisplayMode.NONE
                
                logger.debug("Progress display cleaned up successfully")
                
            except Exception as e:
                self._handle_exception("Error during progress display cleanup", e, "cleanup")

    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message."""
        try:
            # Log the setup message
            if message.startswith("Starting: Setup"):
                self.setup_in_progress = True
            
            if self.display_mode != DisplayMode.NONE:
                self._show_status_in_progress_mode(message)
            else:
                self._show_status_in_normal_mode(message)
            
            logger.debug(f"Status: {message}")
        except Exception as e:
            self._handle_exception("Error displaying status message", e, "status_update")

    def _show_status_in_progress_mode(self, message):
        """Show status when in a progress display mode."""
        # Stop the current live display if it exists
        if self.live and self.live.is_started:
            self.live.stop()
        # Clear screen and show header and status
        self.clear_screen()
        self.show_header()
        self.console.print(message, markup=True)
        # Restart the live display if we were in a progress mode
        if self.progress and self.display_mode != DisplayMode.NONE:
            self.live = Live(
                self.progress,
                console=self.console,
                refresh_per_second=15,
                transient=False
            )
            self.live.start()

    def _show_status_in_normal_mode(self, message):
        """Show status when not in a progress display mode."""
        if not self.setup_in_progress:
            # Clear screen and show header before displaying new status
            self.clear_screen()
            self.show_header()
        # Print the status message below the header
        self.console.print(message, markup=True)

    def show_error(self, message: str) -> None:
        """Display an error message."""
        try:
            # Make error message more prominent by printing it to console regardless of mode
            error_text = f"[bold red]❌ ERROR: {message}[/bold red]"
            if self.display_mode != DisplayMode.NONE:
                # Clean up any existing progress display first
                self._cleanup_progress(preserve_errors=True)
            # Clear screen and show header before displaying the error
            self.clear_screen()
            self.show_header()
            # Create an error panel and display it
            self.console.print(error_text, markup=True)
            logger.error(f"Display error: {message}")
        except Exception as e:
            self._handle_exception("Error displaying error message", e, "error_display")

    def clear(self, preserve_errors: bool = False) -> None:
        """
        Clear the display
        
        Args:
            preserve_errors: When True, preserves any error messages that might be displayed
        """
        with self.display_lock:
            try:
                # Skip clearing during setup to avoid hiding input prompts
                if self.setup_in_progress:
                    return
                
                # Clean up any existing progress display
                self._cleanup_progress(preserve_errors)
                
                # Clear the console and redisplay header
                if not preserve_errors:
                    self.clear_screen()
                    self.show_header()
                    logger.debug("Display cleared and header re-displayed")
                else:
                    logger.debug("Display clear skipped to preserve error messages")
            except Exception as e:
                self._handle_exception("Error clearing display", e, "clear")