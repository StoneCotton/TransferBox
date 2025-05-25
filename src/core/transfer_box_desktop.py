# src/core/transfer_box_desktop.py

import os
import time
import logging

from .transfer_box_base import BaseTransferBox
from .context_managers import operation_context
from .tutorial import DestinationPathManager

logger = logging.getLogger(__name__)


class DesktopTransferBox(BaseTransferBox):
    """Desktop-specific TransferBox implementation"""
    
    def __init__(self, config_manager=None):
        super().__init__(config_manager)
        self.destination_path_manager = DestinationPathManager(self.display)
    
    def _run_impl(self):
        """Desktop-specific run implementation"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Desktop Mode", keep_error_display=True):
                # Get and validate destination path
                destination_path = self._get_destination_path()
                if not destination_path:
                    continue
                
                # Show the destination path to the user
                self.display.show_status(f"[bold yellow]Destination set to: {destination_path}[/bold yellow]")
                
                # Wait for source drive
                source_drive = self._wait_for_source_drive()
                if not source_drive:
                    continue
                
                # Execute transfer
                error_occurred = self.transfer_op.execute_transfer(source_drive, destination_path)
                
                # Wait for drive removal and handle errors
                self._handle_completion(source_drive, error_occurred)
    
    def _get_destination_path(self):
        """Get and validate destination path from user"""
        return self.destination_path_manager.get_destination_path(self.config)
    
    def _wait_for_source_drive(self):
        """Wait for source drive insertion"""
        self.display.show_status("Waiting for source drive...")
        initial_drives = self.storage.get_available_drives()
        source_drive = self.storage.wait_for_new_drive(initial_drives)
        
        if not source_drive or self.stop_event.is_set():
            return None
        
        return source_drive
    
    def _handle_completion(self, source_drive, error_occurred):
        """Handle transfer completion and cleanup"""
        if source_drive.exists() and os.path.ismount(str(source_drive)):
            self.storage.wait_for_drive_removal(source_drive)
        else:
            time.sleep(2)
        
        if error_occurred:
            print("\nTransfer failed. Press Enter to continue...")
            input()
            if self.display:
                self.display.clear(preserve_errors=False) 