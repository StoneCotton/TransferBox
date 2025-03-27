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
                self.display.show_error("Source removed")
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
                self.display.show_error("Source removed")
                self.source_removed_error_shown = True
            if self.sound_manager:
                self.sound_manager.play_error()
        else:
            self.display.show_error("Transfer error")
        return True

class BaseTransferBox:
    """Base class for TransferBox functionality"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Log application metadata
        logger.info(f"Starting {__project_name__} v{__version__} by {__author__}")
        
        # Initialize components
        self.sound_manager = SoundManager(self.config)
        self.stop_event = Event()
        self.platform = get_platform()
        logger.info(f"Initializing TransferBox on {self.platform} platform")
        
        # Create components with unified initialization
        self.display = PlatformManager.create_display()
        self.storage = PlatformManager.create_storage()
        self.state_manager = StateManager(self.display)
        
        # Initialize file transfer
        self.file_transfer = FileTransfer(
            state_manager=self.state_manager,
            display=self.display,
            storage=self.storage,
            config=self.config,
            sound_manager=self.sound_manager
        )
        
        # Initialize transfer operation handler
        self.transfer_op = TransferOperation(
            self.display,
            self.storage,
            self.file_transfer,
            self.sound_manager
        )
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        with operation_context(self.display, self.sound_manager, "Shutdown", 
                             on_error=lambda e: logger.critical(f"Critical error during shutdown: {e}")):
            signal_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM"
            }
            signal_name = signal_names.get(signum, f"Signal {signum}")
            logger.info(f"Shutdown signal received: {signal_name}")
            
            self.stop_event.set()
            self.cleanup()
            
            logger.info("Exiting program")
            sys.exit(0)

    def setup(self):
        """Perform initial setup"""
        with operation_context(self.display, self.sound_manager, "Setup"):
            self.display.clear()
            self.display.show_status("TransferBox Ready")

    def cleanup(self):
        """Cleanup resources"""
        with operation_context(self.display, None, "Cleanup", keep_error_display=True):
            logger.info("Cleaning up resources")
            try:
                self.sound_manager.cleanup()
            except Exception as e:
                logger.error(f"Sound manager cleanup error: {e}")

    def run(self):
        """Main application loop"""
        try:
            self.setup()
            self._run_impl()
        except Exception as e:
            logger.error(f"Critical runtime error: {e}", exc_info=True)
            self.display.show_error(f"Critical Error")
        finally:
            self.cleanup()
    
    def _run_impl(self):
        """Implementation specific run method to be overridden"""
        raise NotImplementedError

class DesktopTransferBox(BaseTransferBox):
    """Desktop-specific TransferBox implementation"""
    
    def _run_impl(self):
        """Desktop-specific run implementation"""
        while not self.stop_event.is_set():
            error_occurred = False
            
            with operation_context(self.display, self.sound_manager, "Desktop Mode", keep_error_display=True):
                # Get and validate destination path
                destination_path = self._get_destination_path()
                if not destination_path:
                    continue
                
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
        self.display.show_status("Enter destination path:")
        raw_destination = input()
        
        try:
            sanitized_destination = sanitize_path(raw_destination)
            is_valid, error_msg = validate_path(
                sanitized_destination, 
                must_exist=False, 
                must_be_writable=True
            )
            
            if not is_valid:
                self.display.show_error(error_msg)
                return None
            
            return sanitized_destination
        except Exception as e:
            logger.error(f"Error sanitizing path: {e}")
            self.display.show_error(f"Invalid path format")
            return None
    
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

def create_transfer_box_app():
    """Factory function to create the appropriate TransferBox instance"""
    platform = get_platform()
    if platform in ["darwin", "windows"]:
        return DesktopTransferBox()
    return EmbeddedTransferBox()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description=f"{__project_name__} v{__version__}")
    parser.add_argument("--benchmark", action="store_true", help="Run transfer benchmark")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB for benchmark")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB for benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark test")
    return parser.parse_args()

def run_benchmark(args):
    """Run benchmark with specified arguments"""
    from src.core.benchmark import run_benchmark_cli
    
    sys.argv = [sys.argv[0]]
    if args.buffer_sizes:
        sys.argv.extend(["--buffer-sizes", args.buffer_sizes])
    if args.file_sizes:
        sys.argv.extend(["--file-sizes", args.file_sizes])
    if args.iterations:
        sys.argv.extend(["--iterations", str(args.iterations)])
        
    return run_benchmark_cli()

def main():
    """Main entry point"""
    args = parse_arguments()
    
    if args.benchmark:
        return run_benchmark(args)
    
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