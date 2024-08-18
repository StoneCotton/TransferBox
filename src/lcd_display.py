from src.LCD1602 import CharLCD1602

lcd1602 = CharLCD1602()
lcd1602.init_lcd(addr=0x3f, bl=1)
lcd1602.set_backlight(True)

def setup_lcd():
    lcd1602.clear()

def update_lcd_progress(file_number, file_count, progress, last_progress=0):
    if abs(progress - last_progress) >= 10:
        lcd_progress = int(progress / 10)
        progress_bar = '#' * lcd_progress + ' ' * (10 - lcd_progress)
        lcd1602.write(0, 1, f"{file_number}/{file_count} {progress_bar}")
        return progress
    return last_progress

def shorten_filename(filename, max_length=16):
    if len(filename) <= max_length:
        return filename
    part_length = (max_length - 3) // 2
    return filename[:part_length] + "..." + filename[-part_length:]
