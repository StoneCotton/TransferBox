import smbus
import time
import subprocess
import logging

logger = logging.getLogger(__name__)

class LCDDisplay:
    def __init__(self, i2c_bus=3, address=0x3f):
        self.bus = smbus.SMBus(i2c_bus)
        self.BLEN = 1
        self.LCD_ADDR = address

    def write_word(self, addr, data):
        temp = data
        if self.BLEN == 1:
            temp |= 0x08
        else:
            temp &= 0xF7
        self.bus.write_byte(addr, temp)

    def send_command(self, comm):
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

    def send_data(self, data):
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

    def i2c_scan(self):
        cmd = "i2cdetect -y 3"
        result = subprocess.check_output(cmd, shell=True).decode()
        result = result.replace("\n", "").replace(" --", "")
        i2c_list = result.split(' ')
        return i2c_list

    def init_lcd(self, addr=None, bl=1):
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

    def clear(self):
        self.send_command(0x01)

    def write(self, x, y, string):
        if x < 0:
            x = 0
        if x > 15:
            x = 15
        if y < 0:
            y = 0
        if y > 1:
            y = 1
        addr = 0x80 + 0x40 * y + x
        self.send_command(addr)
        for char in string:
            self.send_data(ord(char))

    def set_backlight(self, state):
        self.BLEN = state
        self.write_word(self.LCD_ADDR, 0x08 if state else 0x00)

    def update_progress(self, file_number, file_count, progress, last_progress=0):
        if abs(progress - last_progress) >= 10:
            lcd_progress = int(progress / 10)
            progress_bar = '#' * lcd_progress + ' ' * (10 - lcd_progress)
            self.write(0, 1, f"{file_number}/{file_count} {progress_bar}")
            return progress
        return last_progress

    @staticmethod
    def shorten_filename(filename, max_length=16):
        if len(filename) <= max_length:
            return filename
        part_length = (max_length - 3) // 2
        return filename[:part_length] + "..." + filename[-part_length:]

# Create a single instance of LCDDisplay to be used throughout the application
lcd_display = LCDDisplay()

def setup_lcd():
    try:
        lcd_display.init_lcd()
        logger.info("LCD initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LCD: {e}")

# You can add more utility functions here if needed