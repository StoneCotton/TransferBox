# src/platform/raspberry_pi/button_handler.py

import time
import logging
from typing import Callable
from threading import Event, Lock
from gpiozero import Button
from src.core.state_manager import StateManager
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface

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
        # Clear any existing handlers
        for button in [self.back_button, self.ok_button, self.up_button, self.down_button]:
            button.when_pressed = None
            button.when_released = None
        
        # Set up menu entry sequence detection
        self.menu_sequence_active = False
        self.ok_press_count = 0
        self.last_ok_time = 0
        
        # Initial button handlers for menu entry
        self.back_button.when_pressed = self._handle_back_press
        self.ok_button.when_pressed = self._handle_ok_press
        
        logger.info("Button handlers initialized")
    
    def _handle_back_press(self) -> None:
        """Handle back button press"""
        with self.lock:
            if self.state_manager.is_utility():
                # If in menu, exit menu
                logger.info("Back pressed in menu - exiting menu")
                self._exit_menu()
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
            # Enter utility state
            self.state_manager.enter_utility()
            
            # Reset menu index
            self.menu_index = 0
            
            # Update button handlers for menu navigation
            self.up_button.when_pressed = self._menu_up
            self.down_button.when_pressed = self._menu_down
            self.ok_button.when_pressed = self._handle_ok_press
            self.back_button.when_pressed = self._handle_back_press
            
            # Display menu
            self._display_menu()
            
            logger.info("Menu mode entered successfully")
            
        except Exception as e:
            logger.error(f"Error entering menu mode: {e}")
            self.state_manager.enter_standby()
    
    def _exit_menu(self) -> None:
        """Exit menu mode"""
        logger.info("Exiting menu mode")
        try:
            # Reset button handlers
            self._setup_button_handlers()
            
            # Exit utility state
            self.state_manager.exit_utility()
            
            logger.info("Menu mode exited successfully")
            
        except Exception as e:
            logger.error(f"Error exiting menu mode: {e}")
            self.state_manager.enter_standby()
    
    def _menu_up(self) -> None:
        """Handle up button in menu"""
        with self.lock:
            if self.state_manager.is_utility():
                self.menu_index = (self.menu_index - 1) % len(self.menu_options)
                self._display_menu()
                logger.debug(f"Menu navigated up to: {self.menu_options[self.menu_index]}")
    
    def _menu_down(self) -> None:
        """Handle down button in menu"""
        with self.lock:
            if self.state_manager.is_utility():
                self.menu_index = (self.menu_index + 1) % len(self.menu_options)
                self._display_menu()
                logger.debug(f"Menu navigated down to: {self.menu_options[self.menu_index]}")
    
    def _display_menu(self) -> None:
        """Display current menu option"""
        self.display.clear()
        self.display.show_status("UTIL MENU", line=0)
        self.display.show_status(self.menu_options[self.menu_index], line=1)
        logger.debug(f"Displayed menu option: {self.menu_options[self.menu_index]}")
    
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