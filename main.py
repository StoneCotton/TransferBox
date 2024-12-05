# main.py

import os
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from src.core.config_manager import ConfigManager
from src.core.platform_manager import PlatformManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface
from src.core.state_manager import StateManager
from src.core.file_transfer import FileTransfer
from src.core.logger_setup import setup_logging

# Initialize logging
logger = setup_logging()

class TransferBox:
    """Main application class for TransferBox"""
    
    def __init__(self):

        # Initialize config manager first
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        self.stop_event = Event()
        self.platform = PlatformManager.get_platform()
        logger.info(f"Initializing TransferBox on {self.platform} platform")
        
        # Initialize platform-specific components
        self.display: DisplayInterface = PlatformManager.create_display()
        self.storage: StorageInterface = PlatformManager.create_storage()
        
        # Initialize core components
        self.state_manager = StateManager(self.display)
        self.file_transfer = FileTransfer(
            state_manager=self.state_manager,
            display=self.display,
            storage=self.storage,
            config=self.config
        )
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Shutdown signal received")
        self.display.show_status("Shutting down...")
        self.stop_event.set()

    def setup(self):
            """Perform initial setup"""
            try:
                self.display.clear()
                self.display.show_status("TransferBox Ready")
                
                # Special handling for Raspberry Pi
                if self.platform == "raspberry_pi":
                    from src.platform.raspberry_pi.initializer import RaspberryPiInitializer
                    self.pi_initializer = RaspberryPiInitializer()
                    # Initialize all required components
                    self.pi_initializer.initialize_hardware()
                    self.pi_initializer.initialize_display()
                    self.pi_initializer.initialize_storage()
                    
                    # Initialize button handling
                    def menu_callback():
                        self.display.show_status("Menu Mode")
                        self.pi_initializer.handle_utility_mode(True)
                        
                    self.pi_initializer.initialize_buttons(
                        self.state_manager,
                        menu_callback
                    )
                
            except Exception as e:
                logger.error(f"Setup failed: {e}")
                self.display.show_error("Setup failed")
                raise

    def run(self):
        """Main application loop"""
        try:
            self.setup()
            
            if self.platform in ["darwin", "windows"]:  # macOS or Windows
                self.run_desktop_mode()
            else:  # Raspberry Pi
                self.run_embedded_mode()
                
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            self.display.show_error(f"Error: {str(e)}")
        finally:
            self.cleanup()

    def run_desktop_mode(self):
        """Run in desktop mode (macOS/Windows)"""
        while not self.stop_event.is_set():
            try:
                # Get destination path from user
                self.display.show_status("Enter destination path:")
                destination = input("Enter destination path for transfers: ").strip()
                destination_path = Path(destination)
                
                if not destination_path.exists():
                    self.display.show_error("Destination path does not exist")
                    continue
                    
                self.storage.set_dump_drive(destination_path)
                
                # Wait for source drive
                self.display.show_status("Waiting for source drive...")
                initial_drives = self.storage.get_available_drives()
                
                source_drive = self.storage.wait_for_new_drive(initial_drives)
                if not source_drive or self.stop_event.is_set():
                    continue
                
                # Start transfer
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = destination_path / f"transfer_log_{timestamp}.log"
                
                success = self.file_transfer.copy_sd_to_dump(
                    source_drive,
                    destination_path,
                    log_file
                )
                
                if success:
                    self.display.show_status("Transfer complete")
                else:
                    self.display.show_error("Transfer failed")
                
                # Wait for source drive removal
                self.storage.wait_for_drive_removal(source_drive)
                
            except KeyboardInterrupt:
                logger.info("Transfer interrupted by user")
                self.stop_event.set()
            except Exception as e:
                logger.error(f"Transfer error: {e}")
                self.display.show_error(str(e))

    def run_embedded_mode(self):
        """Run in embedded mode (Raspberry Pi)"""
        try:
            # Main transfer loop
            while not self.stop_event.is_set():
                try:
                    # Wait for dump drive
                    dump_drive = self.storage.get_dump_drive()
                    while not dump_drive and not self.stop_event.is_set():
                        self.display.show_status("Waiting for storage")
                        dump_drive = self.storage.get_dump_drive()
                        time.sleep(1)
                    
                    if self.stop_event.is_set():
                        break
                    
                    # Main SD card detection and transfer loop
                    while not self.stop_event.is_set():
                        # Ensure we're in standby state
                        self.state_manager.enter_standby()
                        self.display.show_status("Ready for transfer")
                        
                        # Wait for source drive
                        initial_drives = self.storage.get_available_drives()
                        source_drive = self.storage.wait_for_new_drive(initial_drives)
                        
                        if not source_drive or self.stop_event.is_set():
                            continue
                        
                        # Prepare for transfer
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        log_file = dump_drive / f"transfer_log_{timestamp}.log"
                        
                        try:
                            # Enter transfer state
                            self.state_manager.enter_transfer()
                            
                            # Perform transfer
                            success = self.file_transfer.copy_sd_to_dump(
                                source_drive,
                                dump_drive,
                                log_file
                            )
                            
                            if success:
                                self.display.show_status("Transfer complete")
                                # Safely eject the SD card
                                logger.info(f"Unmounting source drive: {source_drive}")
                                if self.storage.unmount_drive(source_drive):
                                    self.display.show_status("Safe to remove card")
                                else:
                                    self.display.show_error("Unmount failed")
                            else:
                                self.display.show_error("Transfer failed")
                                
                        except Exception as e:
                            logger.error(f"Transfer error: {e}")
                            self.display.show_error(str(e))
                        finally:
                            # Always wait for drive removal before continuing
                            self.storage.wait_for_drive_removal(source_drive)
                            time.sleep(1)  # Small delay to ensure clean state
                            
                            # Return to standby state
                            self.state_manager.enter_standby()
                            self.display.show_status("Insert next card")
                            
                except Exception as e:
                    logger.error(f"Main loop error: {e}")
                    self.display.show_error(str(e))
                    time.sleep(2)
                    self.state_manager.enter_standby()
                    
        finally:
            if hasattr(self, 'pi_initializer'):
                self.pi_initializer.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources")
        self.display.clear()
        
        if self.platform == "raspberry_pi":
            self.pi_initializer.cleanup()

def main():
    """Main entry point"""
    try:
        app = TransferBox()
        app.run()
    except Exception as e:
        logger.critical(f"Application failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()