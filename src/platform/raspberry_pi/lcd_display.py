# src/platform/raspberry_pi/lcd_display.py

from src.core.exceptions import DisplayError, HardwareError
import smbus
import time
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LCDDisplay:
    """Hardware interface for 16x2 LCD display via I2C"""
    
    def __init__(self, i2c_bus: int = 1, address: int = 0x3f):
        """
        Initialize LCD display.
        
        Args:
            i2c_bus: I2C bus number
            address: I2C device address
            
        Raises:
            HardwareError: If SMBus initialization fails
        """
        try:
            self.bus = smbus.SMBus(i2c_bus)
        except Exception as e:
            raise HardwareError(
                f"Failed to initialize I2C bus {i2c_bus}: {str(e)}", 
                component="display",
                error_type="i2c"
            )
        self.BLEN = 1
        self.LCD_ADDR = address
        self.line_content = ["", ""]  # Track current content of each line
        self.i2c_bus_number = i2c_bus

    def write_word(self, addr: int, data: int) -> None:
        """Write a word to the LCD controller."""
        try:
            temp = data
            if self.BLEN == 1:
                temp |= 0x08
            else:
                temp &= 0xF7
            self.bus.write_byte(addr, temp)
        except Exception as e:
            raise DisplayError(
                f"Failed to write word to LCD: {str(e)}", 
                display_type="lcd",
                error_type="communication"
            )

    def send_command(self, comm: int) -> None:
        """Send a command to the LCD."""
        buf = comm & 0xF0
        buf |= 0x04
        self.write_word(self.LCD_ADDR, buf)
        time.sleep(0.002)
        buf &= 0xFB
        self.write_word(self.LCD_ADDR, buf)
        buf = (comm & 0x0F) << 4
        buf |= 0x04
        self.write_word(self.LCD_ADDR, buf)
        time.sleep(0.002)
        buf &= 0xFB
        self.write_word(self.LCD_ADDR, buf)

    def send_data(self, data: int) -> None:
        """Send data to the LCD."""
        buf = data & 0xF0
        buf |= 0x05
        self.write_word(self.LCD_ADDR, buf)
        time.sleep(0.002)
        buf &= 0xFB
        self.write_word(self.LCD_ADDR, buf)
        buf = (data & 0x0F) << 4
        buf |= 0x05
        self.write_word(self.LCD_ADDR, buf)
        time.sleep(0.002)
        buf &= 0xFB
        self.write_word(self.LCD_ADDR, buf)

    def i2c_scan(self) -> list[str]:
        """Scan I2C bus for devices."""
        try:
            # Avoid shell=True; run i2cdetect directly and honor configured bus
            result = subprocess.check_output(["i2cdetect", "-y", str(self.i2c_bus_number)], shell=False).decode()
            result = result.replace("\n", "").replace(" --", "")
            return result.split(' ')
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan I2C bus: {e}")
            return []
        except FileNotFoundError as e:
            logger.error(f"i2cdetect not found: {e}")
            return []

    def init_lcd(self, addr: Optional[int] = None, bl: int = 1) -> None:
        """
        Initialize the LCD display.
        
        Args:
            addr: Optional I2C address. If None, will try to detect
            bl: Backlight state (0 or 1)
        
        Raises:
            HardwareError: If LCD device not found on I2C bus
            DisplayError: If LCD initialization sequence fails
        """
        try:
            i2c_list = self.i2c_scan()
            if addr is None:
                if '3f' in i2c_list:
                    self.LCD_ADDR = 0x3f
                elif '27' in i2c_list:
                    self.LCD_ADDR = 0x27
                else:
                    raise HardwareError(
                        "LCD device not found on I2C bus",
                        component="display",
                        error_type="not_found"
                    )
            else:
                self.LCD_ADDR = addr
                if str(hex(addr)).strip('0x') not in i2c_list:
                    raise HardwareError(
                        f"LCD device not found at address {str(hex(addr))}",
                        component="display",
                        error_type="not_found"
                    )
                    
            self.BLEN = bl
            try:
                self.send_command(0x33)
                time.sleep(0.005)
                self.send_command(0x32)
                time.sleep(0.005)
                self.send_command(0x28)
                time.sleep(0.005)
                self.send_command(0x0C)
                time.sleep(0.005)
                self.send_command(0x01)
                self.send_command(0x06)
                self.clear()
                logger.info("LCD initialized successfully")
            except Exception as e:
                raise DisplayError(
                    f"LCD initialization sequence failed: {str(e)}",
                    display_type="lcd",
                    error_type="initialization"
                )
            
        except (HardwareError, DisplayError):
            raise
        except Exception as e:
            raise DisplayError(
                f"Unexpected error during LCD initialization: {str(e)}",
                display_type="lcd",
                error_type="unknown"
            )

    def clear(self) -> None:
        """Clear the LCD display."""
        self.send_command(0x01)
        self.line_content = ["", ""]

    def write(self, x: int, y: int, string: str) -> None:
        """
        Write text to the LCD at specified position.
        
        Args:
            x: Column position (0-15)
            y: Row position (0-1)
            string: Text to display
            
        Raises:
            DisplayError: If writing to LCD fails
        """
        try:
            x = max(0, min(15, x))
            y = max(0, min(1, y))
            
            addr = 0x80 + 0x40 * y + x
            self.send_command(addr)
            
            # Update line content tracking: overwrite from x onward up to width
            new_content = string[: max(0, 16 - x)]
            line = list((self.line_content[y] + " " * 16)[:16])
            for idx, ch in enumerate(new_content):
                if x + idx < 16:
                    line[x + idx] = ch
            self.line_content[y] = "".join(line)

            for char in new_content:
                self.send_data(ord(char))
                
        except Exception as e:
            raise DisplayError(
                f"Failed to write text to LCD: {str(e)}",
                display_type="lcd",
                error_type="write"
            )

    def set_backlight(self, state: bool) -> None:
        """
        Set the LCD backlight state.
        
        Args:
            state: True for on, False for off
            
        Raises:
            DisplayError: If setting backlight fails
        """
        try:
            self.BLEN = int(state)
            self.write_word(self.LCD_ADDR, 0x08 if state else 0x00)
        except Exception as e:
            raise DisplayError(
                f"Failed to set LCD backlight: {str(e)}",
                display_type="lcd",
                error_type="backlight"
            )

    def update_progress(self, file_number: int, file_count: int, 
                       progress: int, last_progress: int = 0) -> int:
        """
        Update progress display on LCD.
        
        Args:
            file_number: Current file number
            file_count: Total number of files
            progress: Current progress percentage
            last_progress: Last displayed progress percentage
            
        Returns:
            Current progress percentage
        """
        if abs(progress - last_progress) >= 10:
            lcd_progress = int(progress / 10)
            progress_bar = '#' * lcd_progress + ' ' * (10 - lcd_progress)
            self.write(0, 1, f"{file_number}/{file_count} {progress_bar}")
            return progress
        return last_progress

    @staticmethod
    def shorten_filename(filename: str, max_length: int = 16) -> str:
        """
        Shorten a filename to fit LCD display.
        
        Args:
            filename: Filename to shorten
            max_length: Maximum length
            
        Returns:
            Shortened filename
        """
        if len(filename) <= max_length:
            return filename
        part_length = (max_length - 3) // 2
        return filename[:part_length] + "..." + filename[-part_length:]

# Create singleton instance
lcd_display = LCDDisplay()

def setup_lcd() -> None:
    """
    Initialize the LCD display singleton.
    
    Raises:
        HardwareError: If LCD hardware initialization fails
        DisplayError: If LCD display initialization fails
    """
    try:
        lcd_display.init_lcd()
        logger.info("LCD initialized successfully")
    except (HardwareError, DisplayError) as e:
        logger.error(f"Failed to initialize LCD: {str(e)}")
        raise