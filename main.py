from src.logger_setup import setup_logging
from src.drive_detection import get_mounted_drives_lsblk, detect_new_drive, wait_for_drive_removal
from src.mhl_handler import initialize_mhl_file, add_file_to_mhl
from src.file_transfer import copy_sd_to_dump, create_timestamped_dir, rsync_dry_run, rsync_copy, copy_file_with_checksum_verification
from src.lcd_display import setup_lcd, update_lcd_progress, shorten_filename, lcd1602
from src.led_control import setup_leds, set_led_state, blink_led, PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED, set_led_bar_graph
from src.system_utils import get_dump_drive_mountpoint, unmount_drive
from src.menu_setup import navigate_up, navigate_down, select_option, display_menu, handle_option_completion
import os
import time
from datetime import datetime
from threading import Thread, Event
from gpiozero import Button
from src.pi74HC595 import pi74HC595

logger = setup_logging()
DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()
shift_register = pi74HC595(DS=7, ST=26, SH=19, daisy_chain=2)

# GPIO pins for buttons
BACK_BUTTON_PIN = 10
UP_BUTTON_PIN = 9
DOWN_BUTTON_PIN = 11
OK_BUTTON_PIN = 8

# Initialize buttons
back_button = Button(BACK_BUTTON_PIN)
up_button = Button(UP_BUTTON_PIN)
down_button = Button(DOWN_BUTTON_PIN)
ok_button = Button(OK_BUTTON_PIN)

# Event to signal threads to stop
stop_event = Event()

def assign_menu_handlers():
    """Assign the correct handlers for when the menu is active."""
    logger.debug("Assigning menu handlers from main.py.")
    clear_button_handlers()  # Ensure previous handlers are cleared
    up_button.when_pressed = navigate_up
    down_button.when_pressed = navigate_down
    ok_button.when_pressed = lambda: select_option(ok_button, back_button, up_button, down_button, assign_menu_handlers, clear_button_handlers, assign_menu_handlers)
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

    while not stop_event.is_set():  # Use the stop_event to control thread termination
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

    button_thread = Thread(target=button_listener)
    button_thread.start()

    try:
        # Wait until the dump drive is mounted
        while not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
            time.sleep(2)

        lcd1602.clear()
        lcd1602.write(0, 0, "Storage Detected")
        lcd1602.write(0, 1, "Load Media")

        # This LED state resetting should only happen on program startup
        set_led_state(SUCCESS_LED, False)  # Initially turn off success LED
        set_led_state(ERROR_LED, False)    # Initially turn off error LED
        set_led_state(PROGRESS_LED, False) # Ensure progress LED is off

        while True:
            # Only reset LEDs when starting a new transfer
            if not transfer_in_progress and current_mode == "transfer":
                initial_drives = get_mounted_drives_lsblk()
                logger.info("Waiting for SD card to be plugged in...")

                # Detect new SD card
                sd_mountpoint = detect_new_drive(initial_drives)
                if sd_mountpoint:
                    transfer_in_progress = True
                    logger.info(f"SD card detected at {sd_mountpoint}")

                    # Now we reset LEDs because a new transfer is starting
                    set_led_state(SUCCESS_LED, False)  # Turn off previous success LED
                    set_led_state(ERROR_LED, False)    # Turn off previous error LED
                    set_led_bar_graph(0)               # Reset the progress bar

                    set_led_state(PROGRESS_LED, True)  # Turn on progress LED for new transfer

                    # Proceed with transfer
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    target_dir = create_timestamped_dir(DUMP_DRIVE_MOUNTPOINT, timestamp)
                    log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")

                    stop_event.clear()
                    blink_thread = Thread(target=blink_led, args=(PROGRESS_LED, stop_event))
                    blink_thread.start()

                    try:
                        success = copy_sd_to_dump(sd_mountpoint, DUMP_DRIVE_MOUNTPOINT, log_file, stop_event, blink_thread)
                        if success:
                            set_led_state(SUCCESS_LED, True)  # Turn on success LED after a successful transfer
                            set_led_state(PROGRESS_LED, False) # Turn off progress LED when done
                            lcd1602.clear()
                            lcd1602.write(0, 0, "Transfer Done")
                            lcd1602.write(0, 1, "Load New Media")
                        else:
                            set_led_state(PROGRESS_LED, False) # Ensure progress LED is off in case of failure
                    finally:
                        stop_event.set()
                        blink_thread.join()

                    # After the transfer, we either show SUCCESS_LED or ERROR_LED depending on the result
                    if success:
                        set_led_state(PROGRESS_LED, False) # Turn off progress LED when done
                        set_led_state(SUCCESS_LED, True)  # Keep the success LED on after successful transfer
                        set_led_state(ERROR_LED, False)    # Turn off the error LED if the transfer succeeded
                    else:
                        set_led_state(ERROR_LED, True)    # Keep the error LED on if the transfer failed
                        set_led_state(SUCCESS_LED, False)  # Turn off the success LED if the transfer failed
                        set_led_state(PROGRESS_LED, False)

                    # Unmount and wait for card removal
                    unmount_drive(sd_mountpoint)
                    wait_for_drive_removal(sd_mountpoint)

                    transfer_in_progress = False

    except KeyboardInterrupt:
        stop_event.set()
        button_thread.join()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        set_led_state(ERROR_LED, True)
    finally:
        # Cleanup and turn off all LEDs when the program exits
        set_led_state(PROGRESS_LED, False)
        set_led_state(CHECKSUM_LED, False)
        set_led_state(SUCCESS_LED, False)
        set_led_state(ERROR_LED, False)
        set_led_bar_graph(0)
        lcd1602.clear()
        lcd1602.set_backlight(False)
        shift_register.clear()
        shift_register.cleanup()
        logger.info("Exiting program.")



if __name__ == "__main__":
    main()