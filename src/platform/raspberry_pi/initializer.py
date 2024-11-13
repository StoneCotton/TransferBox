# src/platform/raspberry_pi/initializer.py

import logging
from threading import Thread, Event
from gpiozero import Button
from src.core.interfaces.platform import PlatformInitializer
from .display import RaspberryPiDisplay
from .storage import RaspberryPiStorage
from .power_management import power_manager
from .led_control import setup_leds, cleanup_leds
from .lcd_display import setup_lcd
from .menu_setup import MenuManager

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
            logger.error(f"Hardware initialization failed: {e}")
            raise

    def initialize_display(self) -> None:
        """Initialize the display system"""
        self.display = RaspberryPiDisplay()
        self.display.clear()

    def initialize_storage(self) -> None:
        """Initialize the storage system"""
        self.storage = RaspberryPiStorage()

    def initialize_buttons(self, state_manager, menu_callback) -> None:
        """Initialize button handling"""
        from .button_handler import ButtonHandler
        from gpiozero import Button
        
        try:
            # Create buttons only once, when needed
            if self.back_button is None:
                self.back_button = Button(self.BACK_BUTTON_PIN)
                self.up_button = Button(self.UP_BUTTON_PIN)
                self.down_button = Button(self.DOWN_BUTTON_PIN)
                self.ok_button = Button(self.OK_BUTTON_PIN)
            
            # Initialize button handler with all required dependencies
            self.button_handler = ButtonHandler(
                self.back_button,
                self.ok_button,
                self.up_button,
                self.down_button,
                state_manager,
                menu_callback,
                self.display,
                self.storage
            )
            
            self.button_thread = Thread(
                target=self.button_handler.button_listener,
                args=(self.main_stop_event,)
            )
            self.button_thread.start()
            logger.info("Button handling initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize buttons: {e}")
            raise
        
    def cleanup(self) -> None:
        """Cleanup all Raspberry Pi specific resources"""
        try:
            # Signal button thread to stop
            if hasattr(self, 'main_stop_event'):
                self.main_stop_event.set()
                if self.button_thread and self.button_thread.is_alive():
                    self.button_thread.join(timeout=2)
            
            # Cleanup buttons
            if hasattr(self, 'back_button') and self.back_button:
                self.back_button.close()
            if hasattr(self, 'up_button') and self.up_button:
                self.up_button.close()
            if hasattr(self, 'down_button') and self.down_button:
                self.down_button.close()
            if hasattr(self, 'ok_button') and self.ok_button:
                self.ok_button.close()
            
            # Cleanup hardware
            cleanup_leds()
            power_manager.stop_monitoring()
            
            # Clear display
            if hasattr(self, 'display') and self.display:
                self.display.clear()
                
            logger.info("Raspberry Pi cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def handle_utility_mode(self, enable: bool) -> None:
        """
        Enable or disable utility mode button handlers
        
        Args:
            enable: True to enable utility mode, False to disable
        """
        if enable and self.button_handler:
            self.assign_menu_handlers()
        else:
            self.clear_button_handlers()

    def assign_menu_handlers(self) -> None:
        """Assign button handlers for menu navigation"""
        logger.debug("Assigning menu handlers")
        if self.button_handler:
            self.up_button.when_pressed = self.button_handler.navigate_up
            self.down_button.when_pressed = self.button_handler.navigate_down
            self.ok_button.when_pressed = self.button_handler.select_option
            self.back_button.when_pressed = self.button_handler.exit_menu

    def clear_button_handlers(self) -> None:
        """Clear all button handlers"""
        logger.debug("Clearing button handlers")
        self.up_button.when_pressed = None
        self.down_button.when_pressed = None
        self.ok_button.when_pressed = None
        self.back_button.when_pressed = None