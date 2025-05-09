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
from src.core.exceptions import DisplayError, HardwareError

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
            error_msg = f"Failed to initialize LCD display: {str(e)}"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="display",
                error_type="initialization"
            )

    def show_status(self, message: str, line: int = 0) -> None:
        """Display a status message on the LCD display"""
        with self.display_lock:
            try:
                # Handle specific status messages that need both lines
                if message.lower().startswith(("standby", "ready")):
                    lcd_display.clear()
                    lcd_display.write(0, 0, "Standby")
                    lcd_display.write(0, 1, "Input Card")
                elif message.lower().startswith("waiting for storage"):
                    lcd_display.clear()
                    lcd_display.write(0, 0, "Waiting for")
                    lcd_display.write(0, 1, "Storage")
                elif message.lower().startswith("safe to remove"):
                    lcd_display.clear()
                    lcd_display.write(0, 0, "Remove Card")
                elif message.lower().startswith("transfer complete"):
                    lcd_display.clear()
                    lcd_display.write(0, 0, "Transfer Done")
                else:
                    # For single line updates, don't clear the display
                    lcd_display.write(0, line, message[:16])
                
                logger.debug(f"Displayed status on line {line}: {message}")
            except Exception as e:
                error_msg = f"Error displaying status message: {str(e)}"
                logger.error(error_msg)
                raise DisplayError(
                    message=error_msg,
                    display_type="lcd",
                    error_type="write"
                )

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
                        
                    try:
                        lcd_display.write(0, 0, truncated)
                    except Exception as e:
                        error_msg = f"Failed to display filename: {str(e)}"
                        logger.error(error_msg)
                        raise DisplayError(
                            message=error_msg,
                            display_type="lcd",
                            error_type="filename_display"
                        )
                
                # Calculate available space for progress bar
                # Format: "3/26 #######   " (16 chars total)
                file_text = f"{progress.file_number}/{progress.total_files}"
                available_bar_space = 16 - len(file_text) - 1  # -1 for space after numbers
                
                # Calculate progress bar
                filled_chars = int(progress.current_file_progress * available_bar_space)
                progress_bar = "#" * filled_chars + " " * (available_bar_space - filled_chars)
                
                # Combine number and progress bar
                bottom_line = f"{file_text} {progress_bar}"
                try:
                    lcd_display.write(0, 1, bottom_line)
                except Exception as e:
                    error_msg = f"Failed to display progress bar: {str(e)}"
                    logger.error(error_msg)
                    raise DisplayError(
                        message=error_msg,
                        display_type="lcd",
                        error_type="progress_display"
                    )
                
                # Update LED status based on transfer state
                try:
                    self._update_led_status(progress.status)
                except HardwareError:
                    # Re-raise hardware errors as they're already properly formatted
                    raise
                except Exception as e:
                    error_msg = f"Failed to update LED status indicators: {str(e)}"
                    logger.error(error_msg)
                    raise HardwareError(
                        message=error_msg,
                        component="led",
                        error_type="progress_update"
                    )
                    
                # Update bar graph during active transfer states
                if progress.status in (TransferStatus.COPYING, TransferStatus.CHECKSUMMING):
                    try:
                        files_progress = (progress.file_number - 1) / progress.total_files * 100
                        set_bar_graph(files_progress)
                    except Exception as e:
                        error_msg = f"Failed to update progress bar graph: {str(e)}"
                        logger.error(error_msg)
                        raise HardwareError(
                            message=error_msg,
                            component="led",
                            error_type="bar_graph"
                        )
                
            except (DisplayError, HardwareError):
                # Re-raise these exceptions as they're already properly formatted
                raise
            except Exception as e:
                error_msg = f"Unexpected error updating progress display: {str(e)}"
                logger.error(error_msg)
                raise DisplayError(
                    message=error_msg,
                    display_type="lcd",
                    error_type="progress_update"
                )

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
                error_msg = f"Failed to display error message: {str(e)}"
                logger.error(error_msg)
                raise DisplayError(
                    message=error_msg,
                    display_type="lcd",
                    error_type="error_display"
                )

    def clear(self) -> None:
        """Clear both LCD and LEDs"""
        with self.display_lock:
            try:
                lcd_display.clear()
                # Stop any blinking LEDs
                for led in [LEDControl.PROGRESS_LED, LEDControl.CHECKSUM_LED]:
                    led_manager.stop_led_blink(led)
                led_manager.all_leds_off_except(None)
                set_bar_graph(0)
                self._current_file = None
                self._copying_led_started = False
                self._checksum_led_started = False
                logger.debug("Display and LEDs cleared")
            except Exception as e:
                error_msg = f"Failed to clear display and LEDs: {str(e)}"
                logger.error(error_msg)
                raise HardwareError(
                    message=error_msg,
                    component="display",
                    error_type="clear"
                )

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
            error_msg = f"Failed to update LED status: {str(e)}"
            logger.error(error_msg)
            raise HardwareError(
                message=error_msg,
                component="led",
                error_type="status_update"
            )