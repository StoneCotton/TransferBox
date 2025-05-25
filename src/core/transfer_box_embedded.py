# src/core/transfer_box_embedded.py

import os
import time
import logging

from .transfer_box_base import BaseTransferBox
from .context_managers import operation_context
from .path_utils import sanitize_path

logger = logging.getLogger(__name__)


class EmbeddedTransferBox(BaseTransferBox):
    """Embedded (Raspberry Pi) specific TransferBox implementation"""
    
    def setup(self):
        """Embedded-specific setup"""
        super().setup()
        self._setup_raspberry_pi()
    
    def _setup_raspberry_pi(self):
        """Setup specific to Raspberry Pi platform"""
        with operation_context(self.display, self.sound_manager, "Raspberry Pi Setup"):
            try:
                from src.platform.raspberry_pi.initializer_pi import RaspberryPiInitializer
                self.pi_initializer = RaspberryPiInitializer()
            except ImportError as import_err:
                logger.error(f"Failed to import RaspberryPiInitializer: {import_err}")
                self.display.show_error("Import Error")
                raise

            self.pi_initializer.initialize_hardware()
            self.pi_initializer.initialize_display()
            self.pi_initializer.initialize_storage()

            def menu_callback():
                self.display.show_status("Menu Mode")
                self.pi_initializer.handle_utility_mode(True)

            self.pi_initializer.initialize_buttons(
                self.state_manager, 
                menu_callback
            )
    
    def _run_impl(self):
        """Embedded-specific run implementation"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Embedded Mode", keep_error_display=True):
                try:
                    destination_path = sanitize_path(self.config.transfer_destination)
                except Exception as e:
                    logger.error(f"Error sanitizing destination path from config: {e}")
                    self.display.show_error("Invalid destination")
                    time.sleep(5)
                    continue
                
                source_drive = self._wait_for_source_drive()
                if not source_drive:
                    continue
                
                error_occurred = self.transfer_op.execute_transfer(source_drive, destination_path)
                
                self._handle_completion(source_drive, error_occurred)
    
    def _wait_for_source_drive(self):
        """Wait for source drive insertion"""
        self.display.show_status("Waiting for source...")
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
            print("\nTransfer failed. Waiting 5 seconds before continuing...")
            time.sleep(5)
            if self.display:
                self.display.clear(preserve_errors=False)
    
    def cleanup(self):
        """Embedded-specific cleanup"""
        super().cleanup()
        try:
            if hasattr(self, 'pi_initializer'):
                self.pi_initializer.cleanup()
        except Exception as e:
            logger.error(f"Platform-specific cleanup error: {e}") 