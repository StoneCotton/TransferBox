# src/platform/raspberry_pi/lcd_display.py

import smbus
import time
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LCDDisplay:
    """Hardware interface for 16x2 LCD display via I2C"""
    
    def __init__(self, i2c_bus: int = 3, address: int = 0x3f):
        """
        Initialize LCD display.
        
        Args:
            i2c_bus: I2C bus number
            address: I2C device address
        """
        self.bus = smbus.SMBus(i2c_bus)
        self.BLEN = 1
        self.LCD_ADDR = address
        self.line_content = ["", ""]  # Track current content of each line

    def write_word(self, addr: int, data: int) -> None:
        """Write a word to the LCD controller."""
        temp = data
        if self.BLEN == 1:
            temp |= 0x08
        else:
            temp &= 0xF7
        self.bus.write_byte(addr, temp)

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
            cmd = "i2cdetect -y 3"
            result = subprocess.check_output(cmd, shell=True).decode()
            result = result.replace("\n", "").replace(" --", "")
            return result.split(' ')
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan I2C bus: {e}")
            return []

    def init_lcd(self, addr: Optional[int] = None, bl: int = 1) -> None:
        """
        Initialize the LCD display.
        
        Args:
            addr: Optional I2C address. If None, will try to detect
            bl: Backlight state (0 or 1)
        
        Raises:
            IOError: If LCD not found or initialization fails
        """
        try:
            i2c_list = self.i2c_scan()
            if addr is None:
                if '3f' in i2c_list:
                    self.LCD_ADDR = 0x3f
                elif '27' in i2c_list:
                    self.LCD_ADDR = 0x27
                else:
                    raise IOError("I2C address 0x27 or 0x3f not found.")
            else:
                self.LCD_ADDR = addr
                if str(hex(addr)).strip('0x') not in i2c_list:
                    raise IOError(f"I2C address {str(hex(addr))} not found.")
                    
            self.BLEN = bl
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
            logger.error(f"LCD initialization failed: {e}")
            raise

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
        """
        try:
            x = max(0, min(15, x))
            y = max(0, min(1, y))
            
            addr = 0x80 + 0x40 * y + x
            self.send_command(addr)
            
            # Update line content tracking
            line_start = 0 if x == 0 else len(self.line_content[y])
            new_content = string[:16-x]  # Limit to available space
            self.line_content[y] = (
                self.line_content[y][:line_start] + 
                new_content + 
                self.line_content[y][line_start+len(new_content):]
            )[:16]
            
            for char in string:
                self.send_data(ord(char))
                
        except Exception as e:
            logger.error(f"Failed to write to LCD: {e}")

    def set_backlight(self, state: bool) -> None:
        """
        Set the LCD backlight state.
        
        Args:
            state: True for on, False for off
        """
        self.BLEN = int(state)
        self.write_word(self.LCD_ADDR, 0x08 if state else 0x00)

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
    """Initialize the LCD display singleton."""
    try:
        lcd_display.init_lcd()
        logger.info("LCD initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LCD: {e}")
        raise