# src/platform/raspberry_pi/button_handler.py

import time
import logging
from typing import Callable
from threading import Event, Lock
from gpiozero import Button
from src.core.state_manager import StateManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface
from .led_control import LEDControl, led_manager
from .power_management import power_manager
from .lcd_display import lcd_display

logger = logging.getLogger(__name__)

class ButtonHandler:
    """Handles button input and menu activation for Raspberry Pi"""
    
    def __init__(
        self,
        state_manager: StateManager,
        display: DisplayInterface,
        storage: StorageInterface
    ):
        # Initialize buttons with pull_up
        self.back_button = Button(10, pull_up=True, bounce_time=0.05)
        self.ok_button = Button(8, pull_up=True, bounce_time=0.05)
        self.up_button = Button(9, pull_up=True, bounce_time=0.05)
        self.down_button = Button(11, pull_up=True, bounce_time=0.05)
        
        self.state_manager = state_manager
        self.display = display
        self.storage = storage
        
        # Menu state
        self.menu_index = 0
        self.menu_options = [
            "List Drives",
            "Format Drive", 
            "Unmount Drives",
            "Test LEDs",
            "Test Screen",
            "Shutdown",
            "Reboot",
            "Available Space",
            "Version Info"
        ]
        
        # Initialize lock and state
        self.lock = Lock()
        self._setup_button_handlers()
        
        logger.info("ButtonHandler initialized")
    
    def _setup_button_handlers(self) -> None:
        """Set up initial button handlers"""
        logger.debug("Setting up initial button handlers")
        
        # Clear existing handlers
        for button in [self.back_button, self.ok_button, self.up_button, self.down_button]:
            button.when_pressed = None
        
        # Reset menu state
        self.menu_sequence_active = False
        self.ok_press_count = 0
        self.last_ok_time = 0
        
        # Define button callbacks with logging
        def back_pressed():
            logger.debug("BACK button pressed (initial handler)")
            self._handle_back_press()
            
        def ok_pressed():
            logger.debug("OK button pressed (initial handler)")
            self._handle_ok_press()
        
        # Set initial handlers
        self.back_button.when_pressed = back_pressed
        self.ok_button.when_pressed = ok_pressed
        
        logger.info("Initial button handlers set up")
    
    def _handle_back_press(self) -> None:
        """Handle back button press"""
        with self.lock:
            if self.state_manager.is_utility():
                logger.info("Back pressed in menu - exiting menu")
                # Clear existing handlers
                self.up_button.when_pressed = None
                self.down_button.when_pressed = None
                self.ok_button.when_pressed = None
                self.back_button.when_pressed = None
                time.sleep(0.05)
                
                # Exit utility mode
                self.state_manager.exit_utility()
                
                # Reset menu state
                self.menu_sequence_active = False
                self.ok_press_count = 0
                
                # Restore initial button handlers
                self._setup_button_handlers()
                
                logger.info("Exited menu mode")
            else:
                # Start menu entry sequence
                self.menu_sequence_active = True
                logger.debug("Menu entry sequence started")
    
    def _handle_ok_press(self) -> None:
        """Handle OK button press"""
        with self.lock:
            if self.state_manager.is_utility():
                # If in menu, select current option
                logger.info(f"OK pressed in menu - selecting option: {self.menu_options[self.menu_index]}")
                self._execute_menu_option()
            elif self.menu_sequence_active:
                # Part of menu entry sequence
                current_time = time.time()
                if current_time - self.last_ok_time <= 2:
                    self.ok_press_count += 1
                    logger.debug(f"OK press count: {self.ok_press_count}")
                    if self.ok_press_count >= 2:
                        self._enter_menu()
                else:
                    self.ok_press_count = 1
                self.last_ok_time = current_time
    
    def _handle_back_release(self) -> None:
        """Handle back button release"""
        with self.lock:
            if not self.state_manager.is_utility():
                self.menu_sequence_active = False
                self.ok_press_count = 0
                logger.debug("Menu entry sequence cancelled")
    
    def _enter_menu(self) -> None:
        """Enter menu mode"""
        logger.info("Entering menu mode")
        try:
            # Reset menu index
            self.menu_index = 0
            
            # Enter utility state
            if not self.state_manager.enter_utility():
                logger.error("Failed to enter utility state")
                return
                
            # First, clear the display
            lcd_display.clear()
            time.sleep(0.05)
            
            # Write full lines with padding
            lcd_display.write(0, 0, "UTIL MENU" + " " * 8)  # Pad to 16 chars
            time.sleep(0.05)
            lcd_display.write(0, 1, self.menu_options[self.menu_index] + " " * (16 - len(self.menu_options[self.menu_index])))
            
            logger.info(f"Displaying menu - Top: UTIL MENU, Bottom: {self.menu_options[self.menu_index]}")
            
            # Define button callbacks with proper logging
            def up_pressed():
                logger.debug("UP button pressed")
                self._menu_up()
                
            def down_pressed():
                logger.debug("DOWN button pressed")
                self._menu_down()
                
            def ok_pressed():
                logger.debug("OK button pressed")
                self._execute_menu_option()
                
            def back_pressed():
                logger.debug("BACK button pressed")
                self._handle_back_press()
            
            # Set button handlers
            self.up_button.when_pressed = up_pressed
            self.down_button.when_pressed = down_pressed
            self.ok_button.when_pressed = ok_pressed
            self.back_button.when_pressed = back_pressed
            
            logger.info("Menu mode initialized with button handlers")
                
        except Exception as e:
            logger.error(f"Error entering menu mode: {e}")
            self.state_manager.enter_standby()
    
    def _exit_menu(self) -> None:
        """Exit menu mode"""
        with self.lock:
            logger.info("Exiting menu mode")
            
            # Reset button handlers
            self._setup_button_handlers()
            
            # Exit utility state (this will trigger standby mode)
            self.state_manager.exit_utility()
            
            # Clear display
            self.display.clear()
            time.sleep(0.05)
            
            # Show standby status
            self.display.show_status("Standby", line=0)
            time.sleep(0.05)
            self.display.show_status("Input Card", line=1)
            
            logger.info("Menu mode exited successfully")
    
    def _menu_up(self) -> None:
        """Handle up button in menu"""
        with self.lock:
            logger.debug("Menu up handler called")
            if self.state_manager.is_utility():
                self.menu_index = (self.menu_index - 1) % len(self.menu_options)
                
                # Direct LCD update with full line clearing
                lcd_display.write(0, 0, "UTIL MENU" + " " * 8)  # Pad to 16 chars
                time.sleep(0.05)
                lcd_display.write(0, 1, self.menu_options[self.menu_index] + " " * (16 - len(self.menu_options[self.menu_index])))
                
                logger.info(f"Menu navigated up to: {self.menu_options[self.menu_index]}")

    def _menu_down(self) -> None:
        """Handle down button in menu"""
        with self.lock:
            logger.debug("Menu down handler called")
            if self.state_manager.is_utility():
                self.menu_index = (self.menu_index + 1) % len(self.menu_options)
                
                # Direct LCD update with full line clearing
                lcd_display.write(0, 0, "UTIL MENU" + " " * 8)  # Pad to 16 chars
                time.sleep(0.05)
                lcd_display.write(0, 1, self.menu_options[self.menu_index] + " " * (16 - len(self.menu_options[self.menu_index])))
                
                logger.info(f"Menu navigated down to: {self.menu_options[self.menu_index]}")

    def _display_menu(self) -> None:
        """Display current menu option"""
        with self.lock:
            try:
                if not self.state_manager.is_utility():
                    logger.warning("Attempting to display menu while not in utility state")
                    return
                    
                lcd_display.clear()
                time.sleep(0.05)  # Short delay after clear
                
                # Write UTIL MENU directly to top line
                lcd_display.write(0, 0, "UTIL MENU")
                time.sleep(0.05)  # Small delay between lines
                
                # Write current option directly to bottom line
                current_option = self.menu_options[self.menu_index]
                lcd_display.write(0, 1, current_option[:16])
                
                logger.debug(
                    f"Menu display updated - Top: UTIL MENU, "
                    f"Bottom: {current_option}"
                )
                
            except Exception as e:
                logger.error(f"Error displaying menu: {e}")
    
    def _execute_menu_option(self) -> None:
        """Execute selected menu option"""
        option = self.menu_options[self.menu_index]
        logger.info(f"Executing menu option: {option}")
        
        try:
            # Implement menu options here
            if option == "List Drives":
                self._list_drives()
            elif option == "Format Drive":
                self._format_drive()
            elif option == "Unmount Drives":
                self._unmount_drives()
            elif option == "Test LEDs":
                self._test_leds()
            elif option == "Test Screen":
                self._test_screen()
            elif option == "Shutdown":
                self._shutdown_system()
            elif option == "Reboot":
                self._reboot_system()
            elif option == "Available Space":
                self._check_available_space()
            elif option == "Version Info":
                self._version_info()
                
        except Exception as e:
            logger.error(f"Error executing menu option {option}: {e}")
            self.display.show_error("Option Failed")
            time.sleep(2)
            self._display_menu()
    
    # Implement menu option methods here
    def _list_drives(self) -> None:
        """Display list of mounted drives"""
        drives = self.storage.get_available_drives()
        self.display.clear()
        if not drives:
            self.display.show_status("No drives found")
            time.sleep(2)
        else:
            for drive in drives:
                self.display.show_status(str(drive.name))
                time.sleep(2)
        self._display_menu()

    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("Cleaning up button handler")
        for button in [self.back_button, self.ok_button, self.up_button, self.down_button]:
            button.close()

    def _test_leds(self) -> None:
        """Test all LED indicators"""
        self.display.clear()
        self.display.show_status("Testing LEDs")
        
        # Test individual status LEDs
        for led in [LEDControl.PROGRESS_LED, LEDControl.CHECKSUM_LED, 
                    LEDControl.SUCCESS_LED, LEDControl.ERROR_LED]:
            led_manager.all_leds_off_except(led)
            time.sleep(0.5)
        
        # Test progress bar
        led_manager.all_leds_off_except(None)
        for progress in range(0, 101, 10):
            led_manager.set_bar_graph(progress)
            time.sleep(0.2)
        
        # Reset all LEDs
        led_manager.all_leds_off_except(None)
        led_manager.set_bar_graph(0)
        self.display.show_status("LED Test Done")
        time.sleep(2)
        self._display_menu()

    def _test_screen(self) -> None:
        """Test LCD screen functionality"""
        self.display.clear()
        self.display.show_status("Screen Test")
        time.sleep(1)
        
        # Test patterns
        patterns = [
            "----------------",  # Full line
            "################",  # Full blocks
            "0123456789ABCDEF",  # Numbers and letters
            "Test Line 1",       # Text
            "Test Line 2"        # Text
        ]
        
        for pattern in patterns:
            self.display.clear()
            self.display.show_status(pattern, line=0)
            self.display.show_status(pattern, line=1)
            time.sleep(1)
        
        self.display.clear()
        self.display.show_status("Screen Test Done")
        time.sleep(2)
        self._display_menu()

    def select_option(self) -> None:
        """Execute the selected menu option"""
        with self.lock:
            selected_option = self.menu_options[self.menu_index]
            logger.info(f"Selected menu option: {selected_option}")
            
            # Execute the handler if it exists
            handler_name = f"_{selected_option.lower().replace(' ', '_')}"
            handler = getattr(self, handler_name, None)
            
            if handler:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error executing menu option {selected_option}: {e}")
                    self.display.show_error("Option Failed")
                    time.sleep(2)
                finally:
                    self._display_menu()
            else:
                logger.error(f"No handler found for menu option: {selected_option}")
                self.display.show_error("Invalid Option")
                time.sleep(2)
