# main.py

import os
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from src import __version__, __project_name__, __author__
from src.core.config_manager import ConfigManager
from src.core.platform_manager import PlatformManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage_inter import StorageInterface
from src.core.state_manager import StateManager
from src.core.file_transfer import FileTransfer
from src.core.logger_setup import setup_logging
from src.core.sound_manager import SoundManager
from src.core.utils import validate_path, get_platform
from src.core.path_utils import sanitize_path
from src.core.exceptions import HardwareError, StorageError, StateError, FileTransferError
from src.core.context_managers import operation_context
import argparse

# Initialize configuration first
config_manager = ConfigManager()
config = config_manager.load_config()

# Now initialize logging with config settings
logger = setup_logging(
    log_level=getattr(logging, config.log_level),  # Convert string level to logging constant
    log_format='%(message)s',
    log_file_rotation=config.log_file_rotation,
    log_file_max_size=config.log_file_max_size
)

class TransferBox:
    """Main application class for TransferBox"""
    
    def __init__(self):
        # Use already loaded configuration
        self.config_manager = config_manager
        self.config = config
        
        # Log application metadata
        logger.info(f"Starting {__project_name__} v{__version__} by {__author__}")
        
        # Initialize sound manager
        self.sound_manager = SoundManager(self.config)
        
        # Initialize other components
        self.stop_event = Event()
        self.platform = get_platform()
        logger.info(f"Initializing TransferBox on {self.platform} platform")
        
        # Create components with unified initialization
        self.display = PlatformManager.create_display()
        self.storage = PlatformManager.create_storage()
        self.state_manager = StateManager(self.display)
        
        # Initialize file transfer with new component-based architecture
        self.file_transfer = FileTransfer(
            state_manager=self.state_manager,
            display=self.display,
            storage=self.storage,
            config=self.config,
            sound_manager=self.sound_manager
        )
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """
        Handle shutdown signals gracefully by cleaning up resources and exiting.
        
        Args:
            signum: Signal number that triggered this handler
            frame: Current stack frame
        """
        with operation_context(self.display, self.sound_manager, "Shutdown", 
                             on_error=lambda e: logger.critical(f"Critical error during shutdown: {e}")):
            signal_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM"
            }
            signal_name = signal_names.get(signum, f"Signal {signum}")
            logger.info(f"Shutdown signal received: {signal_name}")
            
            # Signal threads to stop
            self.stop_event.set()
            
            # Perform cleanup
            self.cleanup()
            
            # Always exit
            logger.info("Exiting program")
            sys.exit(0)

    def setup(self):
        """Perform initial setup with comprehensive error handling"""
        with operation_context(self.display, self.sound_manager, "Setup"):
            self.display.clear()
            self.display.show_status("TransferBox Ready")

            # Special handling for Raspberry Pi
            if self.platform == "raspberry_pi":
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

            # Initialize hardware with specific error handling for each step
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

    def run(self):
        """Main application loop with comprehensive error handling"""
        try:
            self.setup()
            
            if self.platform in ["darwin", "windows"]:
                self._run_desktop_mode()
            else:  # Raspberry Pi
                self._run_embedded_mode()
        except Exception as e:
            logger.error(f"Critical runtime error: {e}", exc_info=True)
            self.display.show_error(f"Critical Error")
        finally:
            self.cleanup()

    def _run_desktop_mode(self):
        """Run in desktop mode (macOS/Windows)"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Desktop Mode", keep_error_display=True):
                # Get destination path from user
                if error_occurred:
                    # Explicitly clear the display if continuing after an error
                    self.display.clear()
                    
                self.display.show_status("Enter destination path:")
                raw_destination = input()  # Get input without prompt since we're using display
                
                # Sanitize the path before validation
                try:
                    sanitized_destination = sanitize_path(raw_destination)
                    
                    # Validate the destination path
                    is_valid, error_msg = validate_path(
                        sanitized_destination, 
                        must_exist=False, 
                        must_be_writable=True
                    )
                    
                    if not is_valid:
                        self.display.show_error(error_msg)
                        continue
                    
                    destination_path = sanitized_destination
                except Exception as e:
                    logger.error(f"Error sanitizing path: {e}")
                    self.display.show_error(f"Invalid path format")
                    continue
                
                # Wait for source drive
                self.display.show_status("Waiting for source drive...")
                initial_drives = self.storage.get_available_drives()
                source_drive = self.storage.wait_for_new_drive(initial_drives)
                
                if not source_drive or self.stop_event.is_set():
                    continue
                
                # Prepare for transfer
                self.display.show_status(f"Preparing transfer...")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = destination_path / f"transfer_log_{timestamp}.log"
                
                # Flag to track if we've already shown a source removed error
                source_removed_error_shown = False
                
                # Start transfer
                try:
                    success = self.file_transfer.copy_sd_to_dump(
                        source_drive,
                        destination_path,
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
                            error_occurred = True
                    else:
                        # Check if source drive was removed
                        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
                            self.display.show_error("Source removed")
                            source_removed_error_shown = True
                            error_occurred = True
                            if self.sound_manager:
                                self.sound_manager.play_error()
                        else:
                            # Only show transfer failed if it wasn't due to source removal
                            self.display.show_error("Transfer failed")
                            error_occurred = True
                except Exception as e:
                    # Log the error
                    logger.error(f"Error during transfer: {e}", exc_info=True)
                    error_occurred = True
                    
                    # Check if the source drive was removed
                    if not source_drive.exists() or not os.path.ismount(str(source_drive)):
                        if not source_removed_error_shown:
                            self.display.show_error("Source removed")
                            source_removed_error_shown = True
                        if self.sound_manager:
                            self.sound_manager.play_error()
                    else:
                        self.display.show_error("Transfer error")
                
                # Wait for source drive removal if it still exists
                if source_drive.exists() and os.path.ismount(str(source_drive)):
                    self.storage.wait_for_drive_removal(source_drive)
                else:
                    # Short pause if drive was already removed
                    time.sleep(2)
            
            # After the operation context, pause if an error occurred so user can see error message
            if error_occurred:
                # Make sure the error message stays visible
                # Display a message to press Enter to continue
                print("\nTransfer failed. Press Enter to continue...")
                input()  # Wait for user to press Enter
                # Manually clear the display after the user has seen the error
                if self.display:
                    self.display.clear(preserve_errors=False)  # Clear everything after user acknowledgment

    def _run_embedded_mode(self):
        """Run in embedded mode (Raspberry Pi)"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Embedded Mode", keep_error_display=True):
                # Get destination path from user
                if error_occurred:
                    # Explicitly clear the display if continuing after an error
                    self.display.clear(preserve_errors=False)
                
                # Display waiting message
                self.display.show_status("Waiting for source...")
                
                # Get configuration
                config = self.config_manager.config
                
                try:
                    # Sanitize the destination path from config
                    destination_path = sanitize_path(config.transfer_destination)
                except Exception as e:
                    logger.error(f"Error sanitizing destination path from config: {e}")
                    self.display.show_error("Invalid destination")
                    time.sleep(5)  # Show error for 5 seconds
                    continue
                
                # Wait for new drive
                initial_drives = self.storage.get_available_drives()
                source_drive = self.storage.wait_for_new_drive(initial_drives)
                
                if not source_drive or self.stop_event.is_set():
                    continue
                
                # Prepare for transfer
                self.display.show_status("Preparing transfer...")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = destination_path / f"transfer_log_{timestamp}.log"
                
                # Flag to track if we've already shown a source removed error
                source_removed_error_shown = False
                
                # Start transfer
                try:
                    success = self.file_transfer.copy_sd_to_dump(
                        source_drive,
                        destination_path,
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
                            error_occurred = True
                    else:
                        # Check if source drive was removed
                        if not source_drive.exists() or not os.path.ismount(str(source_drive)):
                            self.display.show_error("Source removed")
                            source_removed_error_shown = True
                            error_occurred = True
                            if self.sound_manager:
                                self.sound_manager.play_error()
                        else:
                            # Only show transfer failed if it wasn't due to source removal
                            self.display.show_error("Transfer failed")
                            error_occurred = True
                except Exception as e:
                    # Log the error
                    logger.error(f"Error during transfer: {e}", exc_info=True)
                    error_occurred = True
                    
                    # Check if the source drive was removed
                    if not source_drive.exists() or not os.path.ismount(str(source_drive)):
                        if not source_removed_error_shown:
                            self.display.show_error("Source removed")
                            source_removed_error_shown = True
                        if self.sound_manager:
                            self.sound_manager.play_error()
                    else:
                        self.display.show_error("Transfer error")
                
                # Wait for source drive removal if it still exists
                if source_drive.exists() and os.path.ismount(str(source_drive)):
                    self.storage.wait_for_drive_removal(source_drive)
                else:
                    # Short pause if drive was already removed
                    time.sleep(2)
            
            # After the operation context, pause if an error occurred so user can see error message
            if error_occurred:
                # In embedded mode we'll just add a longer pause rather than waiting for input
                print("\nTransfer failed. Waiting 5 seconds before continuing...")
                time.sleep(5)  # Wait 5 seconds so user can see the error
                # Manually clear the display after the pause
                if self.display:
                    self.display.clear(preserve_errors=False)  # Clear everything after timeout

    def cleanup(self):
        """Cleanup resources with comprehensive error handling"""
        with operation_context(self.display, None, "Cleanup", keep_error_display=True):
            logger.info("Cleaning up resources")
            
            # Display cleanup
            try:
                # Don't clear the display - this might hide error messages
                # Instead, let the operation context manage display clearing
                pass
            except Exception as e:
                logger.error(f"Display cleanup error: {e}")

            # Sound manager cleanup
            try:
                self.sound_manager.cleanup()
            except Exception as e:
                logger.error(f"Sound manager cleanup error: {e}")

            # Platform-specific cleanup
            try:
                if self.platform == "raspberry_pi" and hasattr(self, 'pi_initializer'):
                    self.pi_initializer.cleanup()
            except Exception as e:
                logger.error(f"Platform-specific cleanup error: {e}")

def create_transfer_box_app():
    """
    Factory function to create properly configured TransferBox instance.
    
    Returns:
        TransferBox: Configured application instance
    """
    return TransferBox()

def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description=f"{__project_name__} v{__version__}")
    parser.add_argument("--benchmark", action="store_true", help="Run transfer benchmark")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB for benchmark")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB for benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark test")
    return parser.parse_args()

def run_benchmark(args):
    """
    Run benchmark with specified arguments.
    
    Args:
        args: Command line arguments
        
    Returns:
        int: Exit code
    """
    from src.core.benchmark import run_benchmark_cli
    
    sys.argv = [sys.argv[0]]  # Reset argv
    if args.buffer_sizes:
        sys.argv.extend(["--buffer-sizes", args.buffer_sizes])
    if args.file_sizes:
        sys.argv.extend(["--file-sizes", args.file_sizes])
    if args.iterations:
        sys.argv.extend(["--iterations", str(args.iterations)])
        
    return run_benchmark_cli()

def main():
    """
    Main entry point with improved error handling and organization.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Handle benchmark mode
    if args.benchmark:
        return run_benchmark(args)
    
    # Create and run application
    try:
        app = create_transfer_box_app()
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Unhandled exception")
        return 1

if __name__ == "__main__":
    sys.exit(main())