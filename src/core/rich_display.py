# /src/core/rich_display.py

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
    SpinnerColumn,
    ProgressColumn
)
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus

logger = logging.getLogger(__name__)

class FileNameColumn(TextColumn):
    """Custom column for displaying filename with consistent width"""
    def __init__(self, width: int = 30):
        # Create format string that truncates filename to width
        super().__init__(f"{{task.description:.{width}s}}")

class RichDisplay(DisplayInterface):
    """Platform-agnostic display implementation using Rich library with enhanced progress bars"""
    
    def __init__(self):
        self.console = Console()
        self._current_progress: Optional[TransferProgress] = None
        self.in_transfer_mode = False
        
        # Create progress display with all requested columns
        self.progress = Progress(
            # Leading spinner shows active operation
            SpinnerColumn(),
            
            # Filename column with fixed width to prevent layout shifts
            FileNameColumn(width=30),
            
            # Main progress bar
            BarColumn(bar_width=40, complete_style="blue"),
            
            # File size progress
            FileSizeColumn(),
            TextColumn("/"),
            TotalFileSizeColumn(),
            
            # Numerical progress (e.g., "123/456")
            MofNCompleteColumn(),
            
            # Transfer speed
            TransferSpeedColumn(),
            
            # Time information
            TimeElapsedColumn(),
            TextColumn("ETA:"),
            TimeRemainingColumn(),
            
            # Ensure progress expands to terminal width
            expand=True,
            
            # Use console instance for consistent styling
            console=self.console
        )
        
        # Create tasks for different progress types
        self.total_task_id = None
        self.copy_task_id = None
        self.checksum_task_id = None
        
        # Create layout for status messages and progress
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="status", size=2),
            Layout(name="progress", size=6)  # Increased size to accommodate three progress bars
        )
        
        # Create live display with higher refresh rate for smoother updates
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=15,  # Increased for smoother updates
            transient=True  # Cleanup progress display when done
        )
    
    def _create_status_panel(self, message: str, error: bool = False) -> Panel:
        """Create a status panel with timestamp and appropriate styling"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        style = "red" if error else "blue"
        
        text = Text()
        text.append(f"[{timestamp}] ", style=style)
        text.append(message, style="bold" if error else "default")
        
        return Panel(text, border_style=style)
    
    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message"""
        try:
            # Handle transfer mode transitions
            if message.lower() in ["standby", "input card"] and self.in_transfer_mode:
                self.in_transfer_mode = False
                self._cleanup_progress()
            
            # Create status panel
            status_panel = self._create_status_panel(message)
            
            if self.in_transfer_mode:
                self.layout["status"].update(status_panel)
            else:
                # Direct console output when not in transfer mode
                self.console.print(status_panel)
            
            logger.debug(f"Status: {message}")
            
        except Exception as e:
            logger.error(f"Error showing status: {e}")

    def show_progress(self, progress: TransferProgress) -> None:
        """Update transfer progress display"""
        try:
            if not self.in_transfer_mode:
                self.in_transfer_mode = True
                self._initialize_progress_display(progress)
                self.live.start()
            
            # Handle completion
            if progress.status == TransferStatus.SUCCESS:
                self._cleanup_progress()
                return
            
            # Update total progress
            if self.total_task_id is not None:
                total_bytes = progress.total_files * progress.total_bytes
                completed_bytes = ((progress.file_number - 1) * progress.total_bytes +
                                (progress.bytes_transferred))
                
                self.progress.update(
                    self.total_task_id,
                    completed=completed_bytes,
                    total=total_bytes,
                    description=f"Total Progress"
                )
            
            # Update operation-specific progress based on status
            if progress.status == TransferStatus.COPYING:
                # Update copy progress
                if self.copy_task_id is not None:
                    self.progress.update(
                        self.copy_task_id,
                        completed=progress.bytes_transferred,
                        total=progress.total_bytes,
                        description=f"Copying: {progress.current_file}"
                    )
                # Reset checksum progress
                if self.checksum_task_id is not None:
                    self.progress.update(
                        self.checksum_task_id,
                        completed=0,
                        total=100,
                        description="Waiting for checksum"
                    )
                    
            elif progress.status == TransferStatus.CHECKSUMMING:
                # Keep copy at 100% during checksumming
                if self.copy_task_id is not None:
                    self.progress.update(
                        self.copy_task_id,
                        completed=progress.total_bytes,
                        total=progress.total_bytes,
                        description=f"Copied: {progress.current_file}"
                    )
                
                # Update checksum progress
                if self.checksum_task_id is not None:
                    if progress.current_file_progress <= 0.5:
                        # Source checksum phase (0-50%)
                        phase = "Source"
                        completed = progress.current_file_progress * 2 * progress.total_bytes
                    else:
                        # Destination checksum phase (50-100%)
                        phase = "Destination"
                        completed = (progress.current_file_progress - 0.5) * 2 * progress.total_bytes
                    
                    self.progress.update(
                        self.checksum_task_id,
                        description=f"Checksumming ({phase}): {progress.current_file}",
                        completed=completed,
                        total=progress.total_bytes
                    )
            
            # Update the layout
            self.layout["progress"].update(self.progress)
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def show_error(self, message: str) -> None:
        """Display an error message"""
        try:
            error_panel = self._create_status_panel(message, error=True)
            
            if self.in_transfer_mode:
                self.layout["status"].update(error_panel)
            else:
                self.console.print(error_panel)
            
            logger.error(f"Display error: {message}")
            
        except Exception as e:
            logger.error(f"Error showing error message: {e}")

    def clear(self) -> None:
        """Clear the display"""
        try:
            self._cleanup_progress()
            self.console.clear()
            logger.debug("Display cleared")
        except Exception as e:
            logger.error(f"Error clearing display: {e}")

    def _initialize_progress_display(self, progress: TransferProgress) -> None:
        """Initialize progress bars for a new transfer"""
        # Calculate total bytes for the entire transfer
        total_bytes = progress.total_files * progress.total_bytes
        
        # Create total progress task
        self.total_task_id = self.progress.add_task(
            description="Total Progress",
            total=total_bytes,
            completed=0
        )
        
        # Create copy progress task
        self.copy_task_id = self.progress.add_task(
            description=f"Copying: {progress.current_file}",
            total=progress.total_bytes,
            completed=0
        )
        
        # Create checksum progress task
        self.checksum_task_id = self.progress.add_task(
            description="Waiting for checksum",
            total=progress.total_bytes,
            completed=0
        )

    def _cleanup_progress(self) -> None:
        """Clean up progress display resources"""
        if self.in_transfer_mode:
            self.in_transfer_mode = False
            if hasattr(self, 'live') and self.live.is_started:
                self.live.stop()
            
            # Reset task IDs
            self.total_task_id = None
            self.copy_task_id = None
            self.checksum_task_id = None
            
            # Clear existing tasks
            self.progress.tasks.clear()