# src/platform/raspberry_pi/button_handler.py

import time
import logging
from typing import Callable
from threading import Event
from gpiozero import Button
from src.core.state_manager import StateManager

logger = logging.getLogger(__name__)

class ButtonHandler:
    """Handles button input and menu activation for Raspberry Pi"""
    
    def __init__(
        self,
        back_button: Button,
        ok_button: Button,
        up_button: Button,
        down_button: Button,
        state_manager: StateManager,
        menu_callback: Callable[[], None]
    ):
        """
        Initialize button handler.
        
        Args:
            back_button: Back button GPIO instance
            ok_button: OK button GPIO instance
            up_button: Up button GPIO instance
            down_button: Down button GPIO instance
            state_manager: State management instance
            menu_callback: Callback function for menu activation
        """
        self.back_button = back_button
        self.ok_button = ok_button
        self.up_button = up_button
        self.down_button = down_button
        self.state_manager = state_manager
        self.menu_callback = menu_callback
        
        self.last_ok_time = 0.0
        self.ok_press_count = 0
        
    def button_listener(self, main_stop_event: Event) -> None:
        """
        Main button listening loop.
        
        Args:
            main_stop_event: Event to signal thread stop
        """
        logger.info("Button listener started")
        
        try:
            while not main_stop_event.is_set():
                self._handle_button_presses()
                time.sleep(0.1)  # Small delay to prevent CPU overuse
                
        except Exception as e:
            logger.error(f"Error in button listener: {e}")
            
        finally:
            logger.info("Button listener stopped")
            
    def _handle_button_presses(self) -> None:
        """Handle combination of button presses"""
        if self.back_button.is_pressed:
            logger.debug("Back button is held down")
            
            if self.ok_button.is_pressed:
                logger.debug("OK button is pressed")
                current_time = time.time()
                
                # Check if press is within time window
                if current_time - self.last_ok_time <= 2:
                    self.ok_press_count += 1
                    logger.debug(f"OK button press count: {self.ok_press_count}")
                else:
                    self.ok_press_count = 1
                    logger.debug("Reset press count due to timeout")
                    
                self.last_ok_time = current_time
                
                # Check for menu activation
                if self.ok_press_count >= 2:
                    self._try_activate_menu()
                    self.ok_press_count = 0
            else:
                logger.debug("OK button not pressed with back button")
        else:
            if self.ok_press_count > 0:
                logger.debug("Back button released, resetting count")
            self.ok_press_count = 0
            
    def _try_activate_menu(self) -> None:
        """Attempt to activate the utility menu"""
        if self.state_manager.is_standby():
            logger.info("Activating utility menu")
            try:
                self.state_manager.enter_utility()
                self.menu_callback()
            except Exception as e:
                logger.error(f"Failed to activate menu: {e}")
        else:
            logger.info("Cannot enter utility mode: not in standby mode")