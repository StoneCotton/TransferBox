# src/core/transfer_box_base.py

import logging
import signal
import sys
from threading import Event

from src import __version__, __project_name__, __author__
from .config_manager import ConfigManager
from .platform_manager import PlatformManager
from .state_manager import StateManager
from .file_transfer import FileTransfer
from .sound_manager import SoundManager
from .utils import get_platform
from .context_managers import operation_context
from .transfer_operation import TransferOperation

logger = logging.getLogger(__name__)


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
            config_manager=self.config_manager,
            display=self.display,
            storage=self.storage,
            state_manager=self.state_manager,
            sound_manager=self.sound_manager,
            stop_event=self.stop_event
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
            setup_success = self.setup()
            if not setup_success:
                logger.error("Setup failed. Exiting.")
                return
            self._run_impl()
        except Exception as e:
            logger.error(f"Critical runtime error: {e}", exc_info=True)
            self.display.show_error(f"Critical Error")
        finally:
            self.cleanup()
    
    def _run_impl(self):
        """Implementation specific run method to be overridden"""
        raise NotImplementedError 