# src/platform/raspberry_pi/led_control.py

import time
from threading import Event, Thread
import logging
from enum import IntEnum
from typing import List, Optional, Dict
from .pi74HC595 import pi74HC595
from core.exceptions import HardwareError

logger = logging.getLogger(__name__)

class LEDControl(IntEnum):
    """LED pin assignments for shift register"""
    PROGRESS_LED = 0
    CHECKSUM_LED = 1
    SUCCESS_LED = 2
    ERROR_LED = 3
    # Bar graph LEDs
    BAR_GRAPH_START = 4
    BAR_GRAPH_END = 13

    @classmethod
    def get_bar_graph_leds(cls) -> List[int]:
        """Get list of bar graph LED positions"""
        return list(range(cls.BAR_GRAPH_START, cls.BAR_GRAPH_END + 1))

class LEDManager:
    """Manages LED states through shift register"""
    
    def __init__(self, ds_pin: int = 7, st_pin: int = 13, sh_pin: int = 19, daisy_chain: int = 2):
        """
        Initialize LED manager.
        
        Args:
            ds_pin: Data pin
            st_pin: Storage/latch pin
            sh_pin: Shift pin
            daisy_chain: Number of daisy-chained shift registers
        
        Raises:
            HardwareError: If initialization of shift register fails
        """
        try:
            self.shift_register = pi74HC595(DS=ds_pin, ST=st_pin, SH=sh_pin, daisy_chain=daisy_chain)
            self.led_state = [0] * 16
            self.cleanup_performed = False
            self._active_threads: List[Thread] = []
            self._blink_events: Dict[int, Event] = {}  # Track blink events for each LED
        except Exception as e:
            raise HardwareError(
                f"Failed to initialize LED manager: {str(e)}", 
                component="led",
                error_type="initialization"
            )

    def setup_leds(self) -> None:
        """
        Initialize all LEDs to off state
        
        Raises:
            HardwareError: If LED setup fails
        """
        try:
            self.led_state = [0] * 16
            self.shift_register.set_by_list(self.led_state)
            logger.info("LEDs setup completed")
        except Exception as e:
            raise HardwareError(
                f"LED setup failed: {str(e)}", 
                component="led",
                error_type="setup"
            )

    def set_led_state(self, led_index: int, state: bool) -> None:
        """
        Set specific LED state.
        
        Args:
            led_index: LED position in shift register
            state: True for on, False for off
            
        Raises:
            HardwareError: If setting LED state fails
        """
        try:
            if self.cleanup_performed:
                logger.debug("Ignoring LED state change after cleanup")
                return
                
            self.led_state[led_index] = 1 if state else 0
            self.shift_register.set_by_list(self.led_state)
            logger.debug(f"LED {led_index} set to {'ON' if state else 'OFF'}")
        except Exception as e:
            raise HardwareError(
                f"Failed to set LED {led_index}: {str(e)}", 
                component="led",
                error_type="state_change"
            )

    def start_led_blink(self, led_index: int, blink_speed: float = 0.5) -> None:
        """
        Start LED blinking in separate thread.
        
        Args:
            led_index: LED to blink
            blink_speed: Time between blinks in seconds
            
        Raises:
            HardwareError: If starting LED blink fails
        """
        try:
            # Stop any existing blink for this LED
            self.stop_led_blink(led_index)
            
            stop_event = Event()
            self._blink_events[led_index] = stop_event
            
            def blink_loop():
                while not stop_event.is_set() and not self.cleanup_performed:
                    try:
                        # Store original state of all LEDs
                        original_states = self.led_state.copy()
                        self.led_state[led_index] = 1
                        self.shift_register.set_by_list(self.led_state)
                        time.sleep(blink_speed)
                        if stop_event.is_set() or self.cleanup_performed:
                            break
                        self.led_state[led_index] = 0
                        self.shift_register.set_by_list(self.led_state)
                        time.sleep(blink_speed)
                    except Exception as e:
                        logger.error(f"Error in LED blink loop: {e}")
                        raise HardwareError(
                            f"LED blink loop failed: {str(e)}", 
                            component="led",
                            error_type="blink_operation"
                        )

            blink_thread = Thread(target=blink_loop)
            blink_thread.daemon = True
            blink_thread.start()
            self._active_threads.append(blink_thread)
            
        except Exception as e:
            raise HardwareError(
                f"Failed to start LED blink for LED {led_index}: {str(e)}", 
                component="led",
                error_type="blink_start"
            )

    def stop_led_blink(self, led_index: int) -> None:
        """Stop LED from blinking and turn it off"""
        if led_index in self._blink_events:
            self._blink_events[led_index].set()
            del self._blink_events[led_index]
        self.set_led_state(led_index, False)

    def stop_all_blinks(self) -> None:
        """Stop all blinking LEDs"""
        for led_index in list(self._blink_events.keys()):
            self.stop_led_blink(led_index)

    def all_leds_off_except(self, exception_led: Optional[int] = None) -> None:
        """Turn off all LEDs except the specified one"""
        self.stop_all_blinks()
        for i in range(4):  # Only the status LEDs
            if i != exception_led:
                self.set_led_state(i, False)
        if exception_led is not None:
            self.set_led_state(exception_led, True)

    def set_bar_graph(self, progress: float) -> None:
        """
        Set bar graph LEDs based on progress.
        
        Args:
            progress: Progress value (0-100)
            
        Raises:
            HardwareError: If setting bar graph fails
            ValueError: If progress value is invalid
        """
        try:
            if self.cleanup_performed:
                logger.debug("Ignoring bar graph update after cleanup")
                return
                
            if not 0 <= progress <= 100:
                raise ValueError(f"Progress value must be between 0 and 100, got {progress}")
                
            progress = max(0, min(100, progress))
            bar_leds = LEDControl.get_bar_graph_leds()
            num_leds = len(bar_leds)
            num_leds_on = int((progress / 100.0) * num_leds)
            
            logger.debug(f"Setting bar graph. Progress: {progress}%, LEDs on: {num_leds_on}")
            
            for i, led_pos in enumerate(bar_leds):
                self.led_state[led_pos] = 1 if i < num_leds_on else 0
                
            self.shift_register.set_by_list(self.led_state)
            
        except ValueError as e:
            raise e
        except Exception as e:
            raise HardwareError(
                f"Failed to update bar graph: {str(e)}", 
                component="led",
                error_type="bar_graph_update"
            )

    def cleanup(self) -> None:
        """
        Clean up LED resources
        
        Raises:
            HardwareError: If cleanup fails
        """
        if not self.cleanup_performed:
            try:
                # Stop all blinking threads
                for thread in self._active_threads:
                    if thread.is_alive():
                        logger.debug("Waiting for LED thread to finish")
                        thread.join(timeout=1.0)
                
                # Turn off all LEDs
                self.led_state = [0] * 16
                self.shift_register.set_by_list(self.led_state)
                self.shift_register.cleanup()
                
                logger.info("LED cleanup completed")
                self.cleanup_performed = True
                
            except Exception as e:
                raise HardwareError(
                    f"Error during LED cleanup: {str(e)}", 
                    component="led",
                    error_type="cleanup"
                )
        else:
            logger.debug("LED cleanup already performed")

# Create singleton instance
led_manager = LEDManager()

# Utility functions that use the manager instance
def setup_leds() -> None:
    """Initialize LED system"""
    led_manager.setup_leds()

def set_led_state(led_index: int, state: bool) -> None:
    """Set LED state"""
    led_manager.set_led_state(led_index, state)

def start_led_blink(led_index: int, blink_speed: float = 0.5) -> Event:
    """Start LED blinking"""
    return led_manager.start_led_blink(led_index, blink_speed)

def set_bar_graph(progress: float) -> None:
    """Update progress bar LEDs"""
    if not led_manager.cleanup_performed:
        led_manager.set_bar_graph(progress)
    else:
        logger.debug(f"Skipping bar graph update as cleanup has been performed")

def cleanup_leds() -> None:
    """Clean up LED resources"""
    led_manager.cleanup()