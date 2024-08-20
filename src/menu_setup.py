from time import sleep
from src.lcd_display import lcd1602
from src.drive_detection import get_mounted_drives_lsblk
from src.system_utils import unmount_drive
from src.led_control import setup_leds, LED_BAR_PINS, LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN
import logging
from threading import Lock

logger = logging.getLogger(__name__)

# Global lock for preventing simultaneous access
option_lock = Lock()

# State variables for button handling
menu_active = False
current_menu_index = 0
processing_option = False  # Flag to prevent double handling

# Menu options
menu_options = ["List Drives", "Format Drive", "Test LEDs"]

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

def select_option(ok_button, back_button, up_button, down_button, on_complete):
    global processing_option

    # Attempt to acquire the lock; if not possible, return early
    if not option_lock.acquire(blocking=False):
        return

    try:
        if processing_option:  # Skip if an option is already being processed
            return

        processing_option = True  # Set the flag
        logger.info(f"OK button pressed, selecting option at index {current_menu_index}.")

        selected_option = menu_options[current_menu_index]
        logger.info(f"Selected option: {selected_option}")
        lcd1602.clear()
        lcd1602.write(0, 0, selected_option)
        lcd1602.write(0, 1, "Running...")

        if selected_option == "List Drives":
            list_drives(ok_button, back_button, up_button, down_button)
        elif selected_option == "Format Drive":
            format_drive(ok_button, back_button, up_button, down_button)
        elif selected_option == "Test LEDs":
            test_leds(ok_button, back_button, up_button, down_button)

        # Ensure the OK button is not still pressed after completing an action
        while ok_button.is_pressed:
            logger.debug("Waiting for OK button to be released after action")
            sleep(0.1)

        logger.info("OK button released, returning to menu.")
        
        # Adding a debounce delay to prevent immediate re-trigger
        sleep(0.5)

    finally:
        processing_option = False  # Reset the flag only after ensuring the button is released and debounce delay is applied
        option_lock.release()  # Release the lock
        on_complete()

def handle_option_completion(on_complete):
    global processing_option
    logger.info("Action completed, waiting for OK button press to confirm.")

    lcd1602.clear()

    on_complete()

    display_menu()

def list_drives(ok_button, back_button, up_button, down_button):
    drives = get_mounted_drives_lsblk()
    lcd1602.clear()
    lcd1602.write(0, 0, "Mounted Drives:")
    for drive in drives:
        lcd1602.clear()
        lcd1602.write(0, 1, drive)
        sleep(2)  # Show each drive for 2 seconds
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion))

def format_drive(ok_button, back_button, up_button, down_button):
    # Implement drive formatting logic here
    lcd1602.clear()
    lcd1602.write(0, 0, "Formatting...")
    sleep(2)
    lcd1602.clear()
    lcd1602.write(0, 1, "Done")
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion))

def test_leds(ok_button, back_button, up_button, down_button):
    lcd1602.write(0, 0, "Testing LEDs")
    setup_leds()
    LED1_PIN.on()
    sleep(2)
    LED1_PIN.off()
    LED2_PIN.on()
    sleep(2)
    LED2_PIN.off()
    LED3_PIN.on()
    sleep(2)
    LED3_PIN.off()
    CHECKSUM_LED_PIN.on()
    sleep(2)
    CHECKSUM_LED_PIN.off()
    LED_BAR_PINS.on()
    sleep(2)
    LED_BAR_PINS.off()
    lcd1602.clear()
    lcd1602.write(0, 0, "LED Test Done")
    sleep(2)
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion))
