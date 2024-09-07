from time import sleep
from src.lcd_display import lcd1602
from src.drive_detection import get_mounted_drives_lsblk
from src.system_utils import unmount_drive
from src.led_control import setup_leds, set_led_state, PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED, BAR_GRAPH_LEDS
import logging
from threading import Lock
import os
import time

logger = logging.getLogger(__name__)

# Global lock for preventing simultaneous access
option_lock = Lock()

# State variables for button handling
menu_active = False
current_menu_index = 0
processing_option = False  # Flag to prevent double handling

# Menu options
menu_options = ["List Drives", "Format Drive", "Unmount Drives", "Test LEDs", "Test Screen", "Shutdown", "Reboot", "Availble Space", "Version Info", "Update Firmware", "Reset to Factory"]

def display_menu():
    global processing_option
    processing_option = False  # Reset the flag when displaying the menu
    lcd1602.clear()
    lcd1602.write(0, 0, "UTIL MENU")
    lcd1602.write(0, 1, menu_options[current_menu_index])

def navigate_up():
    global current_menu_index, processing_option
    if processing_option:  # Skip if an option is being processed
        return
    logger.debug("Up button pressed in menu.")
    current_menu_index = (current_menu_index - 1) % len(menu_options)
    display_menu()

def navigate_down():
    global current_menu_index, processing_option
    if processing_option:  # Skip if an option is being processed
        return
    logger.debug("Down button pressed in menu.")
    current_menu_index = (current_menu_index + 1) % len(menu_options)
    display_menu()

def select_option(ok_button, back_button, up_button, down_button, on_complete, clear_handlers, assign_handlers):
    global processing_option

    if not option_lock.acquire(blocking=False):
        return

    try:
        if processing_option:
            return

        processing_option = True
        logger.info(f"OK button pressed, selecting option at index {current_menu_index}.")

        selected_option = menu_options[current_menu_index]
        logger.info(f"Selected option: {selected_option}")
        lcd1602.clear()
        lcd1602.write(0, 0, selected_option)
        lcd1602.write(0, 1, "Running...")

        if selected_option == "List Drives":
            list_drives(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Format Drive":
            format_drive(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Test LEDs":
            test_leds(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Test Screen":
            test_screen(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Shutdown":
            shutdown_system(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Reboot":
            reboot_system(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        elif selected_option == "Version Info":
            version_number(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
        while ok_button.is_pressed:
            logger.debug("Waiting for OK button to be released after action")
            sleep(0.1)

        logger.info("OK button released, returning to menu.")
        sleep(0.5)

    finally:
        processing_option = False
        option_lock.release()
        on_complete()

def handle_option_completion(on_complete):
    global processing_option
    logger.info("Action completed, waiting for OK button press to confirm.")

    lcd1602.clear()

    on_complete()

    display_menu()

def list_drives(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    drives = get_mounted_drives_lsblk()
    for drive in drives:
        # Get the last part of the path
        drive_name = os.path.basename(drive)
        lcd1602.clear()
        lcd1602.write(0, 0, "Mounted Drives:")
        lcd1602.write(0, 1, drive_name)
        time.sleep(2)  # Pause to display each drive for 2 seconds
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def format_drive(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    # Implement drive formatting logic here
    lcd1602.clear()
    lcd1602.write(0, 0, "Formatting...")
    sleep(2)
    lcd1602.clear()
    lcd1602.write(0, 1, "Done")
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def test_leds(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    """Test all LEDs by turning them on/off."""
    lcd1602.write(0, 0, "Testing LEDs")
    setup_leds()
    
    leds = [PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED] + BAR_GRAPH_LEDS
    
    for led in leds:
        set_led_state(led, True)
        sleep(0.5)
        set_led_state(led, False)

    lcd1602.clear()
    lcd1602.write(0, 0, "LED Test Done")
    sleep(2)
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def test_screen(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    lcd1602.write(0, 0, "Testing Screen")
    sleep(2)
    lcd1602.clear()
    sleep(2)

    # Test upper case alphabet on both lines
    for i in range(1, 27):  # 26 letters in the alphabet
        lcd1602.clear()
        if i <= 16:
            lcd1602.write(0, 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:i])
        else:
            lcd1602.write(0, 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:16])
            lcd1602.write(0, 1, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[16:i])
        sleep(0.1)  # Adding a small delay to see the changes

    sleep(2)
    lcd1602.clear()
    sleep(2)

    # Test lower case alphabet on both lines
    for i in range(1, 27):  # 26 letters in the alphabet
        lcd1602.clear()
        if i <= 16:
            lcd1602.write(0, 0, "abcdefghijklmnopqrstuvwxyz"[:i])
        else:
            lcd1602.write(0, 0, "abcdefghijklmnopqrstuvwxyz"[:16])
            lcd1602.write(0, 1, "abcdefghijklmnopqrstuvwxyz"[16:i])
        sleep(0.1)  # Adding a small delay to see the changes

    sleep(2)
    lcd1602.clear()
    sleep(2)

    # Test digits and special characters on both lines
    for i in range(1, 21):  # 10 digits plus 10 special characters
        lcd1602.clear()
        if i <= 10:
            lcd1602.write(0, 0, "0123456789"[:i])
        else:
            lcd1602.write(0, 0, "0123456789")
            lcd1602.write(0, 1, ".,:;!?/()@#$%^&*"[0:i-10])
        sleep(0.1)  # Adding a small delay to see the changes

    sleep(2)
    lcd1602.clear()
    sleep(2)

    # Test special character pattern on both lines
    for i in range(1, 33):  # 32 `#` characters
        lcd1602.clear()
        if i <= 16:
            lcd1602.write(0, 0, "################################"[:i])
        else:
            lcd1602.write(0, 0, "################################"[:16])
            lcd1602.write(0, 1, "################################"[16:i])
        sleep(0.1)  # Adding a small delay to see the changes

    sleep(2)
    lcd1602.clear()

    lcd1602.write(0, 0, "Screen Test Done")
    sleep(2)
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def shutdown_system(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    logger.info("Shutting down the system...")
    lcd1602.clear()
    lcd1602.write(0, 0, "Shutting Down...")
    lcd1602.write(0, 1, "Wait 60 Seconds.")
    sleep(5)
    lcd1602.set_backlight(False)
    os.system('sudo shutdown now')

def reboot_system(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    logger.info("Rebooting the system...")
    lcd1602.clear()
    lcd1602.write(0, 0, "Rebooting...")
    lcd1602.write(0, 1, "Wait 60 Seconds.")
    sleep(5)
    lcd1602.set_backlight(False)
    os.system('sudo reboot now')

def version_number(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    logger.info("Version Number: v0.0.1")
    lcd1602.clear()
    lcd1602.write(0, 0, "Version Number:")
    lcd1602.write(0, 1, "v0.0.1 240820")
    sleep(5)
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))
