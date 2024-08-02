import smbus
import subprocess
from time import sleep

class CharLCD1602(object):
    def __init__(self):
        self.bus = smbus.SMBus(1)
        self.BLEN = 1  # turn on/off background light
        self.PCF8574_address = 0x27  # I2C address of the PCF8574 chip.
        self.PCF8574A_address = 0x3f  # I2C address of the PCF8574A chip.
        self.LCD_ADDR = self.PCF8574A_address  # Set default address

    def write_word(self, addr, data):
        temp = data
        if self.BLEN == 1:
            temp |= 0x08
        else:
            temp &= 0xF7
        self.bus.write_byte(addr, temp)

    def send_command(self, comm):
        buf = comm & 0xF0
        buf |= 0x04  # RS = 0, RW = 0, EN = 1
        self.write_word(self.LCD_ADDR, buf)
        sleep(0.002)
        buf &= 0xFB  # Make EN = 0
        self.write_word(self.LCD_ADDR, buf)
        buf = (comm & 0x0F) << 4
        buf |= 0x04  # RS = 0, RW = 0, EN = 1
        self.write_word(self.LCD_ADDR, buf)
        sleep(0.002)
        buf &= 0xFB  # Make EN = 0
        self.write_word(self.LCD_ADDR, buf)

    def send_data(self, data):
        buf = data & 0xF0
        buf |= 0x05  # RS = 1, RW = 0, EN = 1
        self.write_word(self.LCD_ADDR, buf)
        sleep(0.002)
        buf &= 0xFB  # Make EN = 0
        self.write_word(self.LCD_ADDR, buf)
        buf = (data & 0x0F) << 4
        buf |= 0x05  # RS = 1, RW = 0, EN = 1
        self.write_word(self.LCD_ADDR, buf)
        sleep(0.002)
        buf &= 0xFB  # Make EN = 0
        self.write_word(self.LCD_ADDR, buf)

    def i2c_scan(self):
        cmd = "i2cdetect -y 1 |awk 'NR>1 {$1=\"\";print}'"
        result = subprocess.check_output(cmd, shell=True).decode()
        result = result.replace("\n", "").replace(" --", "")
        i2c_list = result.split(' ')
        return i2c_list

    def init_lcd(self, addr=None, bl=1):
        i2c_list = self.i2c_scan()
        if addr is None:
            if '27' in i2c_list:
                self.LCD_ADDR = self.PCF8574_address
            elif '3f' in i2c_list:
                self.LCD_ADDR = self.PCF8574A_address
            else:
                raise IOError("I2C address 0x27 or 0x3f not found.")
        else:
            self.LCD_ADDR = addr
            if str(hex(addr)).strip('0x') not in i2c_list:
                raise IOError(f"I2C address {str(hex(addr))} not found.")
        self.BLEN = bl
        self.send_command(0x33)  # Must initialize to 8-line mode first
        sleep(0.005)
        self.send_command(0x32)  # Then initialize to 4-line mode
        sleep(0.005)
        self.send_command(0x28)  # 2 Lines & 5*7 dots
        sleep(0.005)
        self.send_command(0x0C)  # Enable display without cursor
        sleep(0.005)
        self.send_command(0x01)  # Clear Screen

    def clear(self):
        self.send_command(0x01)  # Clear Screen

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
