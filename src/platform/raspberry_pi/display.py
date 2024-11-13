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
    set_bar_graph 
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
        """
        Update both LCD display and LED indicators with transfer progress
        
        Args:
            progress: TransferProgress object containing current progress information
        """
        with self.display_lock:
            try:
                # Update LCD with current file info
                filename = lcd_display.shorten_filename(progress.current_file, 16)
                lcd_display.write(0, 0, filename)
                
                # Show file count and progress bar on second line
                lcd_display.write(0, 1, f"{progress.file_number}/{progress.total_files}")
                
                # Update LED indicators based on status
                self._update_leds(progress)
                
                # Update progress bar LEDs
                if progress.overall_progress > 0:
                    set_bar_graph(int(progress.overall_progress * 100))
                
            except Exception as e:
                logger.error(f"Error updating progress display: {e}")

    def show_error(self, message: str) -> None:
        """
        Display an error message and activate error LED
        
        Args:
            message: The error message to display
        """
        with self.display_lock:
            try:
                lcd_display.clear()
                # Split message across both lines if needed
                if len(message) > 16:
                    lcd_display.write(0, 0, message[:16])
                    lcd_display.write(0, 1, message[16:32])
                else:
                    lcd_display.write(0, 0, message)
                
                # Activate error LED
                set_led_state(LEDControl.ERROR_LED, True)
                logger.error(f"Error displayed: {message}")
            except Exception as e:
                logger.error(f"Error showing error message: {e}")

    def clear(self) -> None:
        """Clear both LCD display and LED indicators"""
        with self.display_lock:
            try:
                lcd_display.clear()
                # Reset all LEDs
                set_led_state(LEDControl.SUCCESS_LED, False)
                set_led_state(LEDControl.ERROR_LED, False)
                set_led_state(LEDControl.PROGRESS_LED, False)
                set_led_state(LEDControl.CHECKSUM_LED, False)
                set_bar_graph(0)
                logger.debug("Display and LEDs cleared")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")

    def _update_leds(self, progress: TransferProgress) -> None:
        """
        Update LED indicators based on transfer status
        
        Args:
            progress: TransferProgress object containing current status
        """
        # Reset status LEDs
        set_led_state(LEDControl.SUCCESS_LED, False)
        set_led_state(LEDControl.ERROR_LED, False)
        set_led_state(LEDControl.PROGRESS_LED, False)
        set_led_state(LEDControl.CHECKSUM_LED, False)
        
        # Set appropriate LED based on status
        if progress.status == TransferStatus.COPYING:
            set_led_state(LEDControl.PROGRESS_LED, True)
        elif progress.status == TransferStatus.CHECKSUMMING:
            set_led_state(LEDControl.CHECKSUM_LED, True)
        elif progress.status == TransferStatus.SUCCESS:
            set_led_state(LEDControl.SUCCESS_LED, True)
        elif progress.status == TransferStatus.ERROR:
            set_led_state(LEDControl.ERROR_LED, True)