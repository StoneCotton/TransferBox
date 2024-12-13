# src/core/rich_display.py

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
        
        # Create progress display
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
        
        # Task IDs for different modes
        # Transfer mode tasks
        self.total_task_id = None
        self.copy_task_id = None
        self.checksum_task_id = None
        
        # Proxy mode tasks
        self.proxy_total_task_id = None
        self.proxy_current_task_id = None
        
        # Create layout
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="status", size=2),
            Layout(name="progress", size=6)  # Height for 3 progress bars
        )
        
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=15,
            transient=True
        )

    def _initialize_transfer_mode(self):
        """Initialize progress bars for file transfer mode."""
        self.progress.tasks.clear()
        self.total_task_id = self.progress.add_task(
            "Total Progress",
            total=100,
            visible=True
        )
        self.copy_task_id = self.progress.add_task(
            "Copy Progress",
            total=100,
            visible=True
        )
        self.checksum_task_id = self.progress.add_task(
            "Checksum Progress",
            total=100,
            visible=True
        )
        self.in_transfer_mode = True
        self.in_proxy_mode = False

    def _initialize_proxy_mode(self):
        """Initialize progress bars for proxy generation mode."""
        self.progress.tasks.clear()
        self.proxy_total_task_id = self.progress.add_task(
            "Total Proxy Progress",
            total=100,
            visible=True
        )
        self.proxy_current_task_id = self.progress.add_task(
            "Current Proxy",
            total=100,
            visible=True
        )
        self.in_transfer_mode = False
        self.in_proxy_mode = True

    def show_progress(self, progress: TransferProgress) -> None:
        """Update progress display based on current operation mode."""
        with self.display_lock:
            try:
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
                    
                    # Update proxy progress bars
                    self.progress.update(
                        self.proxy_total_task_id,
                        completed=((progress.proxy_file_number - 1) / progress.proxy_total_files) * 100,
                        description=f"Total Progress ({progress.proxy_file_number}/{progress.proxy_total_files})"
                    )
                    
                    self.progress.update(
                        self.proxy_current_task_id,
                        completed=progress.proxy_progress,
                        description=f"Generating: {progress.current_file}"
                    )
                else:
                    # Update transfer progress bars
                    self.progress.update(
                        self.total_task_id,
                        completed=(progress.total_transferred / progress.total_size) * 100,
                        description=f"Total Progress ({progress.file_number}/{progress.total_files})"
                    )

                    if progress.status == TransferStatus.COPYING:
                        self.progress.update(
                            self.copy_task_id,
                            completed=(progress.bytes_transferred / progress.total_bytes) * 100,
                            description=f"Copying: {progress.current_file}"
                        )
                        # Reset checksum progress during copy
                        self.progress.update(
                            self.checksum_task_id,
                            completed=0,
                            description="Waiting for checksum"
                        )
                    elif progress.status == TransferStatus.CHECKSUMMING:
                        # Keep copy progress complete during checksum
                        self.progress.update(
                            self.copy_task_id,
                            completed=100,
                            description=f"Copied: {progress.current_file}"
                        )
                        # Update checksum progress
                        self.progress.update(
                            self.checksum_task_id,
                            completed=progress.current_file_progress * 100,
                            description=f"Checksumming: {progress.current_file}"
                        )

                # Update the layout
                self.layout["progress"].update(self.progress)

            except Exception as e:
                logger.error(f"Error updating progress: {e}")

    def _cleanup_progress(self) -> None:
        """Clean up progress display."""
        if self.in_transfer_mode or self.in_proxy_mode:
            if self.live.is_started:
                self.live.stop()
            self.progress.tasks.clear()
            self.in_transfer_mode = False
            self.in_proxy_mode = False
            
            # Reset all task IDs
            self.total_task_id = None
            self.copy_task_id = None
            self.checksum_task_id = None
            self.proxy_total_task_id = None
            self.proxy_current_task_id = None

    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message."""
        try:
            if self.in_transfer_mode or self.in_proxy_mode:
                self.layout["status"].update(
                    Panel(Text(message, style="blue"))
                )
            else:
                self.console.print(message)
            
            logger.debug(f"Status: {message}")
        except Exception as e:
            logger.error(f"Error showing status: {e}")

    def show_error(self, message: str) -> None:
        """Display an error message."""
        try:
            if self.in_transfer_mode or self.in_proxy_mode:
                self.layout["status"].update(
                    Panel(Text(message, style="red bold"))
                )
            else:
                self.console.print(f"[red bold]Error: {message}[/]")
            
            logger.error(f"Display error: {message}")
        except Exception as e:
            logger.error(f"Error showing error message: {e}")

    def clear(self) -> None:
        """Clear the display."""
        try:
            self._cleanup_progress()
            self.console.clear()
            logger.debug("Display cleared")
        except Exception as e:
            logger.error(f"Error clearing display: {e}")