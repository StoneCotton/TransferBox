# src/platform/raspberry_pi/display.py

import logging
from typing import Optional
from threading import Lock
from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.platform.raspberry_pi.lcd_display import lcd_display  # Import the existing LCD display
from src.platform.raspberry_pi.led_control import (
    LEDControl, 
    set_led_state, 
    set_bar_graph, led_manager 
)

logger = logging.getLogger(__name__)

class RaspberryPiDisplay(DisplayInterface):
    """
    Raspberry Pi implementation of DisplayInterface that manages both
    LCD display and LED indicators
    """
    
    def __init__(self):
        self.display_lock = Lock()
        self._setup_display()
        
    def _setup_display(self) -> None:
        """Initialize the LCD display and LED controls"""
        try:
            # The lcd_display is already a singleton instance
            lcd_display.clear()
            logger.info("LCD display initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LCD display: {e}")
            raise

    def show_status(self, message: str, line: int = 0) -> None:
        """
        Display a status message on the LCD display
        
        Args:
            message: The message to display
            line: The line number (0 or 1) to display the message on
        """
        with self.display_lock:
            try:
                # Ensure line is within bounds
                line = max(0, min(1, line))
                
                # Truncate message to fit 16 character display if needed
                if len(message) > 16:
                    message = lcd_display.shorten_filename(message, 16)
                
                lcd_display.write(0, line, message)
                logger.debug(f"Displayed status on line {line}: {message}")
            except Exception as e:
                logger.error(f"Error displaying status message: {e}")

    def show_progress(self, progress: TransferProgress) -> None:
        with self.display_lock:
            try:
                # Update LCD with current file info
                filename = lcd_display.shorten_filename(progress.current_file, 16)
                lcd_display.write(0, 0, filename)
                
                # Show file count on second line
                lcd_display.write(0, 1, f"{progress.file_number}/{progress.total_files}")
                
                # Update LED indicators based on status
                self._update_leds(progress)
                
                # Update progress bar LEDs with overall progress
                if progress.overall_progress > 0:
                    set_bar_graph(int(progress.overall_progress * 100))
                
            except Exception as e:
                logger.error(f"Error updating progress display: {e}")

    def show_error(self, message: str) -> None:
        with self.display_lock:
            try:
                lcd_display.clear()
                if len(message) > 16:
                    lcd_display.write(0, 0, message[:16])
                    lcd_display.write(0, 1, message[16:32])
                else:
                    lcd_display.write(0, 0, message)
                
                # Error state: only ERROR_LED on
                led_manager.all_leds_off_except(LEDControl.ERROR_LED)
                logger.error(f"Error displayed: {message}")
            except Exception as e:
                logger.error(f"Error showing error message: {e}")

    def clear(self) -> None:
        with self.display_lock:
            try:
                lcd_display.clear()
                # Turn off all LEDs and stop any blinking
                led_manager.all_leds_off_except(None)
                set_bar_graph(0)
                logger.debug("Display and LEDs cleared")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")

    def _update_leds(self, progress: TransferProgress) -> None:
        """Update LED indicators based on transfer status"""
        try:
            if progress.status == TransferStatus.ERROR:
                # Error state: only ERROR_LED on
                led_manager.all_leds_off_except(LEDControl.ERROR_LED)
                
            elif progress.status == TransferStatus.COPYING:
                # Copying state: blink PROGRESS_LED
                led_manager.all_leds_off_except(None)
                led_manager.start_led_blink(LEDControl.PROGRESS_LED)
                
            elif progress.status == TransferStatus.CHECKSUMMING:
                # Checksumming state: blink CHECKSUM_LED
                led_manager.stop_led_blink(LEDControl.PROGRESS_LED)
                led_manager.start_led_blink(LEDControl.CHECKSUM_LED)
                
            elif progress.status == TransferStatus.SUCCESS:
                # Success state: solid SUCCESS_LED
                led_manager.all_leds_off_except(LEDControl.SUCCESS_LED)
                
        except Exception as e:
            logger.error(f"Error updating LEDs: {e}")