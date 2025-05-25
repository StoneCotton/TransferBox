# src/core/transfer_operation.py

import os
import logging
from datetime import datetime
from pathlib import Path

from .validation import ErrorMessages
from .context_managers import operation_context

logger = logging.getLogger(__name__)


class TransferOperation:
    """Handles the core transfer logic for both desktop and embedded modes"""
    
    def __init__(self, display, storage, file_transfer, sound_manager):
        self.display = display
        self.storage = storage
        self.file_transfer = file_transfer
        self.sound_manager = sound_manager
        self.source_removed_error_shown = False
        
    def execute_transfer(self, source_drive, destination_path):
        """Execute the transfer operation with proper error handling"""
        error_occurred = False
        
        # Prepare for transfer
        self.display.show_status(f"Preparing transfer...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = destination_path / f"transfer_log_{timestamp}.log"
        
        try:
            success = self.file_transfer.copy_sd_to_dump(
                source_drive,
                destination_path,
                log_file
            )
            
            if success:
                error_occurred = self._handle_successful_transfer(source_drive)
            else:
                error_occurred = self._handle_failed_transfer(source_drive)
                
        except Exception as e:
            error_occurred = self._handle_transfer_error(e, source_drive)
            
        return error_occurred
    
    def _handle_successful_transfer(self, source_drive):
        """Handle successful transfer completion"""
        self.display.show_status("Transfer complete")
        logger.info(f"Unmounting source drive: {source_drive}")
        if self.storage.unmount_drive(source_drive):
            self.display.show_status("Safe to remove card")
            return False
        else:
            self.display.show_error("Unmount failed")
            return True
    
    def _handle_failed_transfer(self, source_drive):
        """Handle failed transfer"""
        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
            if not self.source_removed_error_shown:
                self.display.show_error(ErrorMessages.SOURCE_REMOVED)
                self.source_removed_error_shown = True
            if self.sound_manager:
                self.sound_manager.play_error()
            return True
            
        if self.file_transfer.no_files_found:
            return False
            
        self.display.show_error("Transfer failed")
        logger.info(f"Attempting to unmount source drive after failed transfer: {source_drive}")
        try:
            if self.storage.unmount_drive(source_drive):
                self.display.show_status("Safe to remove card")
        except Exception as unmount_err:
            logger.warning(f"Failed to unmount drive after failed transfer: {unmount_err}")
        return True
    
    def _handle_transfer_error(self, error, source_drive):
        """Handle transfer error"""
        logger.error(f"Error during transfer: {error}", exc_info=True)
        
        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
            if not self.source_removed_error_shown:
                self.display.show_error(ErrorMessages.SOURCE_REMOVED)
                self.source_removed_error_shown = True
            if self.sound_manager:
                self.sound_manager.play_error()
        else:
            self.display.show_error(ErrorMessages.TRANSFER_ERROR)
        return True 