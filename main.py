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
from src.core.path_utils import sanitize_path, validate_destination_path
from src.core.exceptions import HardwareError, StorageError, StateError, FileTransferError
import argparse

# Initialize logging
logger = setup_logging()

class TransferBox:
    """Main application class for TransferBox"""
    
    def __init__(self):
        # Initialize config manager first
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Log application metadata
        logger.info(f"Starting {__project_name__} v{__version__} by {__author__}")
        
        # Initialize sound manager
        self.sound_manager = SoundManager(self.config)
        
        # Initialize other components
        self.stop_event = Event()
        self.platform = PlatformManager.get_platform()
        logger.info(f"Initializing TransferBox on {self.platform} platform")
        
        # Pass config and sound_manager to components that need them
        self.display = PlatformManager.create_display()
        self.storage = PlatformManager.create_storage()
        self.state_manager = StateManager(self.display)
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
        try:
            signal_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM"
            }
            signal_name = signal_names.get(signum, f"Signal {signum}")
            logger.info(f"Shutdown signal received: {signal_name}")
            
            # Inform user about shutdown
            try:
                self.display.show_status("Shutting down...")
            except Exception as e:
                logger.warning(f"Could not update display during shutdown: {e}")
            
            # Signal threads to stop
            self.stop_event.set()
            
            # Perform cleanup operations
            try:
                self.cleanup()
                logger.info("Cleanup completed successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                # Continue with shutdown despite cleanup errors
        except Exception as e:
            # Catch-all exception handler to ensure we always exit
            logger.critical(f"Critical error during shutdown: {e}")
        finally:
            # Always exit, even if there were errors in the shutdown process
            logger.info("Exiting program")
            sys.exit(0)

    def setup(self):
        """Perform initial setup with comprehensive error handling"""
        try:
            self.display.clear()
            self.display.show_status("TransferBox Ready")

            # Special handling for Raspberry Pi
            if self.platform == "raspberry_pi":
                try:
                    from src.platform.raspberry_pi.initializer_pi import RaspberryPiInitializer
                    self.pi_initializer = RaspberryPiInitializer()
                except ImportError as import_err:
                    logger.error(f"Failed to import RaspberryPiInitializer: {import_err}")
                    raise

                # Initialize hardware with specific error handling for each step
                try:
                    self.pi_initializer.initialize_hardware()
                except HardwareError as hw_err:
                    logger.error(f"Hardware initialization failed: {hw_err}")
                    self.display.show_error("Hardware Setup Failed")
                    raise

                try:
                    self.pi_initializer.initialize_display()
                except Exception as display_err:
                    logger.error(f"Display initialization failed: {display_err}")
                    self.display.show_error("Display Setup Failed")
                    raise

                try:
                    self.pi_initializer.initialize_storage()
                except StorageError as storage_err:
                    logger.error(f"Storage initialization failed: {storage_err}")
                    self.display.show_error("Storage Setup Failed")
                    raise

                # Initialize button handling
                def menu_callback():
                    self.display.show_status("Menu Mode")
                    self.pi_initializer.handle_utility_mode(True)

                try:
                    self.pi_initializer.initialize_buttons(
                        self.state_manager, 
                        menu_callback
                    )
                except StateError as state_err:
                    logger.error(f"Button initialization failed: {state_err}")
                    self.display.show_error("Button Setup Failed")
                    raise

        except Exception as e:
            logger.error(f"Critical setup failure: {e}")
            self.display.show_error("Critical Setup Error")
            raise

    def run(self):
        """Main application loop with comprehensive error handling"""
        try:
            self.setup()
            
            try:
                if self.platform == "darwin":
                    from src.platform.macos.initializer_macos import MacOSInitializer
                    self.mac_initializer = MacOSInitializer()
                    self.run_desktop_mode()
                elif self.platform == "windows":
                    from src.platform.windows.initializer_win import WindowsInitializer
                    self.win_initializer = WindowsInitializer()
                    self.run_desktop_mode()
                else:  # Raspberry Pi
                    self.run_embedded_mode()
            except ImportError as import_err:
                logger.error(f"Platform initialization failed: {import_err}")
                self.display.show_error("Platform Setup Error")
                raise
            except (StorageError, StateError) as platform_err:
                logger.error(f"Platform runtime error: {platform_err}")
                self.display.show_error(f"Platform Error: {str(platform_err)}")
                raise
        except Exception as e:
            logger.error(f"Critical runtime error: {e}", exc_info=True)
            self.display.show_error(f"Critical Error: {str(e)}")
        finally:
            self.cleanup()

    def run_desktop_mode(self):
        """Run in desktop mode (macOS/Windows)"""
        while not self.stop_event.is_set():
            try:
                # Get destination path from user
                self.display.show_status("Enter destination path:")
                raw_destination = input("Enter destination path for transfers: ")
                
                try:
                    # Sanitize and validate the input path
                    destination_path = sanitize_path(raw_destination)
                    logger.debug(f"Raw destination path: {raw_destination}")
                    destination_path = validate_destination_path(destination_path, self.storage)
                    logger.debug(f"Validated destination path: {destination_path}")
                    
                    # Let FileTransfer handle path validation and creation
                    self.storage.set_dump_drive(destination_path)
                except (ValueError, StorageError) as path_err:
                    self.display.show_error(str(path_err))
                    continue
                
                # Wait for source drive
                self.display.show_status("Waiting for source drive...")
                initial_drives = self.storage.get_available_drives()
                source_drive = self.storage.wait_for_new_drive(initial_drives)
                
                if not source_drive or self.stop_event.is_set():
                    continue
                
                # Start transfer
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = destination_path / f"transfer_log_{timestamp}.log"
                
                try:
                    success = self.file_transfer.copy_sd_to_dump(
                        source_drive,
                        destination_path,
                        log_file
                    )
                    
                    if success:
                        self.display.show_status("Transfer complete")
                    else:
                        self.display.show_error("Transfer failed")
                        # Log additional details about transfer failure
                        logger.warning(f"Transfer failed for source drive: {source_drive}")
                except FileTransferError as transfer_err:
                    logger.error(f"File transfer error: {transfer_err}")
                    self.display.show_error(f"Transfer Error: {str(transfer_err)}")
                
                # Wait for source drive removal
                self.storage.wait_for_drive_removal(source_drive)
                
            except KeyboardInterrupt:
                logger.info("Transfer interrupted by user")
                self.stop_event.set()
            except Exception as e:
                logger.error(f"Unexpected transfer error: {e}", exc_info=True)
                self.display.show_error(f"Unexpected Error: {str(e)}")

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
                        try:
                            self.state_manager.enter_standby()
                        except StateError as state_err:
                            logger.error(f"Failed to enter standby state: {state_err}")
                            self.display.show_error("State Error")
                            break
                        
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
                        
                        except (FileTransferError, StorageError) as transfer_err:
                            logger.error(f"Transfer error: {transfer_err}")
                            self.display.show_error(str(transfer_err))
                        
                        finally:
                            # Always wait for drive removal before continuing
                            self.storage.wait_for_drive_removal(source_drive)
                            time.sleep(1)  # Small delay to ensure clean state
                            
                            # Return to standby state
                            try:
                                self.state_manager.enter_standby()
                            except StateError as state_err:
                                logger.error(f"Failed to return to standby state: {state_err}")
                            
                            self.display.show_status("Insert next card")
                
                except Exception as e:
                    logger.error(f"Main loop error: {e}", exc_info=True)
                    self.display.show_error(str(e))
                    time.sleep(2)
                    
                    try:
                        self.state_manager.enter_standby()
                    except StateError as state_err:
                        logger.error(f"Failed to enter standby after main loop error: {state_err}")
        
        except Exception as global_err:
            logger.error(f"Global embedded mode error: {global_err}", exc_info=True)
        
        finally:
            if hasattr(self, 'pi_initializer'):
                try:
                    self.pi_initializer.cleanup()
                except Exception as cleanup_err:
                    logger.error(f"Cleanup error: {cleanup_err}")

    def cleanup(self):
        """Cleanup resources with comprehensive error handling"""
        logger.info("Cleaning up resources")
        try:
            self.display.clear()
        except Exception as display_err:
            logger.error(f"Display cleanup error: {display_err}")

        try:
            self.sound_manager.cleanup()
        except Exception as sound_err:
            logger.error(f"Sound manager cleanup error: {sound_err}")

        # Platform-specific cleanup
        try:
            if self.platform == "raspberry_pi" and hasattr(self, 'pi_initializer'):
                self.pi_initializer.cleanup()
            elif self.platform == "darwin" and hasattr(self, 'mac_initializer'):
                self.mac_initializer.cleanup()
            elif self.platform == "windows" and hasattr(self, 'win_initializer'):
                self.win_initializer.cleanup()
        except Exception as platform_cleanup_err:
            logger.error(f"Platform-specific cleanup error: {platform_cleanup_err}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=f"{__project_name__} v{__version__}")
    parser.add_argument("--benchmark", action="store_true", help="Run transfer benchmark")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB for benchmark")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB for benchmark")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark test")
    args = parser.parse_args()

    # Run benchmark if requested
    if args.benchmark:
        from src.core.benchmark import TransferBenchmark, BenchmarkConfig, run_benchmark_cli
        
        if any([args.buffer_sizes, args.file_sizes, args.iterations]):
            # Use CLI with passed arguments
            sys.argv = [sys.argv[0]]  # Reset argv
            if args.buffer_sizes:
                sys.argv.extend(["--buffer-sizes", args.buffer_sizes])
            if args.file_sizes:
                sys.argv.extend(["--file-sizes", args.file_sizes])
            if args.iterations:
                sys.argv.extend(["--iterations", str(args.iterations)])
            return run_benchmark_cli()
        else:
            # Run with default settings
            return run_benchmark_cli()
    
    # Normal application startup
    app = TransferBox()
    
    try:
        app.setup()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt")
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Unhandled exception")
        return 1
    finally:
        app.cleanup()
    
    return 0

if __name__ == "__main__":
    main()