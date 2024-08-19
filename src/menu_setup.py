from time import sleep
from src.lcd_display import lcd1602
from src.drive_detection import get_mounted_drives_lsblk
from src.system_utils import unmount_drive
from src.led_control import setup_leds, LED_BAR_PINS, LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN
import logging

logger = logging.getLogger(__name__)

# State variables for button handling
menu_active = False
current_menu_index = 0

# Menu options
menu_options = ["List Drives", "Format Drive", "Test LEDs"]

def display_menu():
    lcd1602.clear()
    lcd1602.write(0, 0, "UTIL MENU")
    lcd1602.write(0, 1, menu_options[current_menu_index])

def navigate_up():
    global current_menu_index
    logger.debug("Up button pressed in menu.")
    current_menu_index = (current_menu_index - 1) % len(menu_options)
    display_menu()

def navigate_down():
    global current_menu_index
    logger.debug("Down button pressed in menu.")
    current_menu_index = (current_menu_index + 1) % len(menu_options)
    display_menu()

def select_option():
    selected_option = menu_options[current_menu_index]
    logger.info(f"Selected option: {selected_option}")
    lcd1602.clear()
    lcd1602.write(0, 0, selected_option)
    lcd1602.write(0, 1, "Running...")

    if selected_option == "List Drives":
        list_drives()
    elif selected_option == "Format Drive":
        format_drive()
    elif selected_option == "Test LEDs":
        test_leds()

    # After executing, return to the menu
    display_menu()

def list_drives():
    drives = get_mounted_drives_lsblk()
    lcd1602.clear()
    lcd1602.write(0, 0, "Mounted Drives:")
    for drive in drives:
        lcd1602.clear()
        lcd1602.write(0, 1, drive)
        sleep(2)  # Show each drive for 2 seconds
    display_menu()

def format_drive():
    # Implement drive formatting logic here
    lcd1602.clear()
    lcd1602.write(0, 0, "Formatting...")
    sleep(2)
    lcd1602.clear()
    lcd1602.write(0, 1, "Done")
    display_menu()

def test_leds():
    setup_leds()
    for pin in LED_BAR_PINS + [LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN]:
        pin.on()
        sleep(0.5)
        pin.off()
    lcd1602.clear()
    lcd1602.write(0, 0, "LED Test Done")
    sleep(2)
    display_menu()

def exit_menu():
    global menu_active
    logger.info("Exiting menu.")
    menu_active = False
    lcd1602.clear()
    lcd1602.write(0, 0, "Exiting Menu")
    sleep(1)
    lcd1602.clear()
    lcd1602.write(0, 0, "Menu Existed.")

    # You can add logic here to restore the previous screen or state
