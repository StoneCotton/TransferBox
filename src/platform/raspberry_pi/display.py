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
        self._current_file = None
        self._copying_led_started = False
        self._checksum_led_started = False
        
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
        """Display a status message on the LCD display"""
        with self.display_lock:
            try:
                # Clear the display first to prevent residual characters
                lcd_display.clear()
                
                # Handle specific status messages
                if message.lower().startswith(("standby", "ready")):
                    lcd_display.write(0, 0, "Standby")
                    lcd_display.write(0, 1, "Input Card")
                elif message.lower().startswith("waiting for storage"):
                    lcd_display.write(0, 0, "Waiting for")
                    lcd_display.write(0, 1, "Storage")
                elif message.lower().startswith("safe to remove"):
                    lcd_display.write(0, 0, "Remove Card")
                elif message.lower().startswith("transfer complete"):
                    lcd_display.write(0, 0, "Transfer Done")
                else:
                    # Keep messages to 16 chars
                    lcd_display.write(0, 0, message[:16])
                
                logger.debug(f"Displayed status on line {line}: {message}")
            except Exception as e:
                logger.error(f"Error displaying status message: {e}")

    def show_progress(self, progress: TransferProgress) -> None:
        """Update both LCD display and LED indicators with transfer progress"""
        with self.display_lock:
            try:
                # Don't clear display every time, only when the filename changes
                if progress.current_file != self._current_file:
                    lcd_display.clear()
                    self._current_file = progress.current_file
                    
                    # Show current file name on top line (truncated if needed)
                    max_length = 16
                    filename = progress.current_file
                    if len(filename) > max_length:
                        name_parts = filename.rsplit('.', 1)
                        if len(name_parts) == 2:
                            name, ext = name_parts
                            available_space = max_length - len(ext) - 4
                            if available_space > 0:
                                truncated = name[:available_space] + "..." + "." + ext
                            else:
                                truncated = filename[:max_length-3] + "..."
                        else:
                            truncated = filename[:max_length-3] + "..."
                    else:
                        truncated = filename
                        
                    lcd_display.write(0, 0, truncated)
                
                # Always update queue counter on bottom line
                queue_text = f"({progress.file_number}/{progress.total_files})"
                # Center the queue text
                padding = (16 - len(queue_text)) // 2
                lcd_display.write(padding, 1, queue_text)
                
                # Update LED status without affecting display
                self._update_led_status(progress.status)
                
                # Update bar graph during COPYING status
                if progress.status == TransferStatus.COPYING:
                    files_progress = (progress.file_number - 1) / progress.total_files * 100
                    set_bar_graph(files_progress)
                
            except Exception as e:
                logger.error(f"Error updating progress display: {e}")

    def show_error(self, message: str) -> None:
        """Display error message on LCD"""
        with self.display_lock:
            try:
                lcd_display.clear()
                lcd_display.write(0, 0, "Error:")
                lcd_display.write(0, 1, message[:16])  # Truncate to 16 chars
                led_manager.all_leds_off_except(LEDControl.ERROR_LED)
                logger.error(f"Error displayed: {message}")
            except Exception as e:
                logger.error(f"Error showing error message: {e}")

    def clear(self) -> None:
        """Clear both LCD and LEDs"""
        with self.display_lock:
            try:
                lcd_display.clear()
                led_manager.all_leds_off_except(None)
                set_bar_graph(0)
                self._current_file = None
                self._copying_led_started = False
                self._checksum_led_started = False
                logger.debug("Display and LEDs cleared")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")

    def _update_led_status(self, status: TransferStatus) -> None:
        """Update LED status without affecting display"""
        try:
            if status == TransferStatus.ERROR:
                led_manager.all_leds_off_except(LEDControl.ERROR_LED)
                self._copying_led_started = False
                self._checksum_led_started = False
            elif status == TransferStatus.COPYING:
                if not self._copying_led_started:
                    led_manager.all_leds_off_except(None)
                    led_manager.start_led_blink(LEDControl.PROGRESS_LED)
                    self._copying_led_started = True
                    self._checksum_led_started = False
            elif status == TransferStatus.CHECKSUMMING:
                if not self._checksum_led_started:
                    led_manager.stop_led_blink(LEDControl.PROGRESS_LED)
                    led_manager.start_led_blink(LEDControl.CHECKSUM_LED)
                    self._copying_led_started = False
                    self._checksum_led_started = True
            elif status == TransferStatus.SUCCESS:
                led_manager.all_leds_off_except(LEDControl.SUCCESS_LED)
                self._copying_led_started = False
                self._checksum_led_started = False
                
        except Exception as e:
            logger.error(f"Error updating LED status: {e}")