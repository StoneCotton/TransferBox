# src/platform/raspberry_pi/initializer.py

import logging
from threading import Thread, Event
from gpiozero import Button
from src.core.interfaces.platform import PlatformInitializer
from .display import RaspberryPiDisplay
from .storage_pi import RaspberryPiStorage
from .power_management import power_manager
from .led_control import setup_leds, cleanup_leds
from .lcd_display import setup_lcd
from .menu_setup import MenuManager
from .button_handler import ButtonHandler
from src.core.exceptions import HardwareError, DisplayError, StateError

logger = logging.getLogger(__name__)

class RaspberryPiInitializer(PlatformInitializer):
    """Handles Raspberry Pi specific initialization and hardware setup"""

    def __init__(self):
        """Initialize Raspberry Pi components"""
        super().__init__()
        # GPIO pins for buttons
        self.BACK_BUTTON_PIN = 10
        self.UP_BUTTON_PIN = 9
        self.DOWN_BUTTON_PIN = 11
        self.OK_BUTTON_PIN = 8
        
        # Initialize button attributes
        self.back_button = None
        self.up_button = None
        self.down_button = None
        self.ok_button = None
        
        # Initialize threading components
        self.main_stop_event = Event()
        self.button_thread = None
        self.button_handler = None
        
        # Initialize display and storage attributes
        self.display = None
        self.storage = None

    def initialize_hardware(self) -> None:
        """Initialize Raspberry Pi specific hardware"""
        try:
            setup_leds()
            setup_lcd()
            power_manager.start_monitoring()
            logger.info("Hardware initialization complete")
        except Exception as e:
            error_msg = f"Hardware initialization failed: {str(e)}"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="system",
                error_type="initialization"
            )

    def initialize_display(self) -> None:
        """Initialize the display system"""
        try:
            self.display = RaspberryPiDisplay()
            self.display.clear()
        except Exception as e:
            error_msg = f"Display initialization failed: {str(e)}"
            logger.error(error_msg)
            raise DisplayError(
                message=error_msg,
                display_type="lcd",
                error_type="initialization"
            )

    def initialize_storage(self) -> None:
        """Initialize the storage system"""
        self.storage = RaspberryPiStorage()

    def initialize_buttons(self, state_manager, menu_callback) -> None:
        """Initialize button handling"""
        try:
            # Create button handler
            self.button_handler = ButtonHandler(
                state_manager,
                self.display,
                self.storage
            )
            logger.info("Button handling initialized")
            
        except Exception as e:
            error_msg = f"Failed to initialize buttons: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise HardwareError(
                message=error_msg,
                component="button",
                error_type="initialization"
            )

    def cleanup(self) -> None:
        """Cleanup all Raspberry Pi specific resources"""
        cleanup_errors = []
        
        try:
            # Signal button thread to stop
            if hasattr(self, 'main_stop_event'):
                self.main_stop_event.set()
                if self.button_thread and self.button_thread.is_alive():
                    self.button_thread.join(timeout=2)
                    if self.button_thread.is_alive():
                        cleanup_errors.append("Button thread failed to stop")
            
            # Cleanup buttons
            for button_name in ['back_button', 'up_button', 'down_button', 'ok_button']:
                if hasattr(self, button_name) and getattr(self, button_name):
                    try:
                        getattr(self, button_name).close()
                    except Exception as e:
                        cleanup_errors.append(f"Failed to cleanup {button_name}: {str(e)}")
            
            # Cleanup hardware
            try:
                cleanup_leds()
            except Exception as e:
                cleanup_errors.append(f"Failed to cleanup LEDs: {str(e)}")
                
            try:
                power_manager.stop_monitoring()
            except Exception as e:
                cleanup_errors.append(f"Failed to stop power monitoring: {str(e)}")
            
            # Clear display
            if hasattr(self, 'display') and self.display:
                try:
                    self.display.clear()
                except Exception as e:
                    cleanup_errors.append(f"Failed to clear display: {str(e)}")
                
            if cleanup_errors:
                error_msg = "Multiple cleanup errors occurred: " + "; ".join(cleanup_errors)
                logger.error(error_msg)
                raise HardwareError(
                    message=error_msg,
                    component="system",
                    error_type="cleanup"
                )
                
            logger.info("Raspberry Pi cleanup completed")
            
        except HardwareError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error during cleanup: {str(e)}"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="system",
                error_type="cleanup"
            )

    def handle_utility_mode(self, enable: bool) -> None:
        """
        Enable or disable utility mode button handlers
        
        Args:
            enable: True to enable utility mode, False to disable
        """
        try:
            if enable and self.button_handler:
                logger.debug("Assigning menu handlers")
                self.assign_menu_handlers()
            else:
                logger.debug("Clearing menu handlers")
                self.clear_button_handlers()
        except Exception as e:
            error_msg = f"Error handling utility mode transition: {str(e)}"
            logger.error(error_msg)
            raise StateError(
                message=error_msg,
                current_state="normal" if not enable else "utility",
                target_state="utility" if enable else "normal"
            )

    def assign_menu_handlers(self) -> None:
        """Assign button handlers for menu navigation"""
        if not self.button_handler:
            error_msg = "Button handler not initialized"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="button",
                error_type="configuration"
            )

        try:
            logger.debug("Assigning menu handlers")
            self.up_button.when_pressed = self.button_handler.navigate_up
            self.down_button.when_pressed = self.button_handler.navigate_down
            self.ok_button.when_pressed = self.button_handler.select_option
            self.back_button.when_pressed = self.button_handler.exit_menu
        except Exception as e:
            error_msg = f"Failed to assign menu handlers: {str(e)}"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="button",
                error_type="configuration"
            )

    def clear_button_handlers(self) -> None:
        """Clear all button handlers"""
        logger.debug("Clearing button handlers")
        if hasattr(self, 'up_button') and self.up_button:
            self.up_button.when_pressed = None
        if hasattr(self, 'down_button') and self.down_button:
            self.down_button.when_pressed = None
        if hasattr(self, 'ok_button') and self.ok_button:
            self.ok_button.when_pressed = None
        if hasattr(self, 'back_button') and self.back_button:
            self.back_button.when_pressed = None

