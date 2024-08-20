from src.logger_setup import setup_logging
from src.drive_detection import get_mounted_drives_lsblk, detect_new_drive, wait_for_drive_removal
from src.mhl_handler import initialize_mhl_file, add_file_to_mhl
from src.file_transfer import copy_sd_to_dump, create_timestamped_dir, rsync_dry_run, rsync_copy, copy_file_with_checksum_verification
from src.lcd_display import setup_lcd, update_lcd_progress, shorten_filename, lcd1602
from src.led_control import setup_leds, blink_led, LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN, set_led_bar_graph
from src.system_utils import get_dump_drive_mountpoint, unmount_drive
from src.menu_setup import navigate_up, navigate_down, select_option, display_menu, handle_option_completion
import os
import time
from datetime import datetime
from threading import Thread, Event
from gpiozero import Button

logger = setup_logging()
DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()

# GPIO pins for buttons
BACK_BUTTON_PIN = 4
UP_BUTTON_PIN = 10
DOWN_BUTTON_PIN = 9
OK_BUTTON_PIN = 11

# Initialize buttons
back_button = Button(BACK_BUTTON_PIN)
up_button = Button(UP_BUTTON_PIN)
down_button = Button(DOWN_BUTTON_PIN)
ok_button = Button(OK_BUTTON_PIN)

def assign_menu_handlers():
    """Assign the correct handlers for when the menu is active."""
    logger.debug("Assigning menu handlers from main.py.")
    clear_button_handlers()  # Ensure previous handlers are cleared
    up_button.when_pressed = navigate_up
    down_button.when_pressed = navigate_down
    ok_button.when_pressed = lambda: select_option(ok_button, back_button, up_button, down_button, assign_menu_handlers)
    back_button.when_pressed = exit_menu_to_transfer_mode

def clear_button_handlers():
    """Clear button event handlers to avoid unintended behavior."""
    logger.debug("Clearing button handlers to prevent unintended actions from main.py.")
    up_button.when_pressed = None
    down_button.when_pressed = None
    ok_button.when_pressed = None
    back_button.when_pressed = None

# State variables
last_ok_time = 0
ok_press_count = 0
transfer_in_progress = False
menu_active = False
current_mode = "transfer"  # Either 'transfer' or 'utility'

def button_listener():
    global last_ok_time, ok_press_count, menu_active, current_mode

    while True:
        if back_button.is_pressed:
            logger.debug("Back button is held down.")

            if ok_button.is_pressed:
                logger.debug("OK button is pressed.")
                current_time = time.time()

                if current_time - last_ok_time <= 2:
                    ok_press_count += 1
                    logger.debug(f"OK button press count: {ok_press_count}")
                else:
                    ok_press_count = 1  # Reset counter if more than 2 seconds passed
                    logger.debug("Resetting OK button press count due to timeout.")

                last_ok_time = current_time

                if ok_press_count >= 2:
                    logger.info("Menu activated.")
                    menu_active = True
                    current_mode = "utility"
                    display_menu()
                    assign_menu_handlers()  # No arguments are needed here now
                    ok_press_count = 0  # Reset count after activation
            else:
                logger.debug("OK button is not pressed after back button.")
        else:
            if ok_press_count > 0:
                logger.debug("Back button released, resetting OK press count.")
            ok_press_count = 0

        time.sleep(0.1)  # Small delay to avoid overwhelming the logs

def exit_menu_to_transfer_mode():
    """Exit the utility menu and return to transfer mode."""
    global menu_active, current_mode
    logger.info("Exiting utility menu, returning to transfer mode from main.py.")
    menu_active = False
    current_mode = "transfer"
    lcd1602.clear()
    lcd1602.write(0, 0, "Returning to")
    lcd1602.write(0, 1, "Transfer Mode")
    time.sleep(1)
    clear_button_handlers()
    display_transfer_mode_screen()

def display_transfer_mode_screen():
    """Display the default transfer mode screen."""
    lcd1602.clear()
    if not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
        lcd1602.write(0, 0, "Storage Missing")
    else:
        lcd1602.write(0, 0, "Storage Detected")
        lcd1602.write(0, 1, "Load Media")

def main():
    global transfer_in_progress, menu_active

    setup_leds()
    setup_lcd()
    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Missing")

    button_thread = Thread(target=button_listener, daemon=True)
    button_thread.start()

    while not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
        time.sleep(2)

    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Detected")
    lcd1602.write(0, 1, "Load Media")

    LED3_PIN.off()

    try:
        while True:
            if not transfer_in_progress and current_mode == "transfer":
                # Ensure no menu handlers are active
                clear_button_handlers()

                # Start the transfer process
                initial_drives = get_mounted_drives_lsblk()
                logger.debug(f"Initial mounted drives: {initial_drives}")

                logger.info("Waiting for SD card to be plugged in...")
                sd_mountpoint = detect_new_drive(initial_drives)
                if sd_mountpoint:
                    transfer_in_progress = True
                    logger.info(f"SD card detected at {sd_mountpoint}.")
                    logger.debug(f"Updated state of drives: {get_mounted_drives_lsblk()}")

                    LED3_PIN.off()
                    LED2_PIN.off()

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    target_dir = create_timestamped_dir(DUMP_DRIVE_MOUNTPOINT, timestamp)
                    log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")

                    stop_event = Event()
                    blink_thread = Thread(target=blink_led, args=(LED1_PIN, stop_event))
                    blink_thread.start()

                    try:
                        success = copy_sd_to_dump(sd_mountpoint, DUMP_DRIVE_MOUNTPOINT, log_file, stop_event, blink_thread)
                        if success:
                            LED3_PIN.on()
                            LED1_PIN.off()
                            CHECKSUM_LED_PIN.off()
                            lcd1602.clear()
                            lcd1602.write(0, 0, "Transfer Done")
                            lcd1602.write(0, 1, "Load New Media")
                    finally:
                        stop_event.set()
                        blink_thread.join()

                    unmount_drive(sd_mountpoint)
                    wait_for_drive_removal(sd_mountpoint)
                    logger.info("Monitoring for new storage devices...")
                    transfer_in_progress = False
                    logger.debug("Transfer in progress set to False after transfer.")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Cleaning up and exiting.")
        LED2_PIN.off()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        logger.debug(f"Transfer in progress at error: {transfer_in_progress}")
        LED2_PIN.on()
    finally:
        logger.debug("Final cleanup.")
        LED1_PIN.off()
        LED2_PIN.off()
        LED3_PIN.off()
        CHECKSUM_LED_PIN.off()
        lcd1602.clear()
        lcd1602.set_backlight(False)
        if hasattr(lcd1602, 'cleanup'):
            lcd1602.cleanup()

if __name__ == "__main__":
    main()
