import os
import time
from datetime import datetime
from threading import Thread, Event

from gpiozero import Button
from src.pi74HC595 import pi74HC595

from src.logger_setup import setup_logging
from src.drive_detection import get_mounted_drives_lsblk, detect_new_drive, wait_for_drive_removal
from src.mhl_handler import initialize_mhl_file, add_file_to_mhl
from src.file_transfer import copy_sd_to_dump, create_timestamped_dir
from src.lcd_display import setup_lcd, lcd1602
from src.led_control import setup_leds, set_led_state, PROGRESS_LED, SUCCESS_LED, ERROR_LED, set_led_bar_graph, blink_led
from src.system_utils import get_dump_drive_mountpoint, unmount_drive
from src.menu_setup import navigate_up, navigate_down, select_option, display_menu
from src.button_handler import ButtonHandler
from src.state_manager import StateManager
from src.power_management import power_manager

logger = setup_logging()
DUMP_DRIVE_MOUNTPOINT = None  # Initialize to None

shift_register = pi74HC595(DS=7, ST=13, SH=19, daisy_chain=2)

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
main_stop_event = Event()

# Initialize StateManager
state_manager = StateManager()

def update_dump_drive_mountpoint():
    global DUMP_DRIVE_MOUNTPOINT
    DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()
    if DUMP_DRIVE_MOUNTPOINT is None:
        logger.warning("DUMP_DRIVE not found")
    else:
        logger.info(f"DUMP_DRIVE found at {DUMP_DRIVE_MOUNTPOINT}")

def assign_menu_handlers():
    logger.debug("Assigning menu handlers from main.py.")
    up_button.when_pressed = navigate_up
    down_button.when_pressed = navigate_down
    ok_button.when_pressed = lambda: select_option(ok_button, back_button, up_button, down_button, exit_menu_to_standby, clear_button_handlers, assign_menu_handlers)
    back_button.when_pressed = exit_menu_to_standby

def clear_button_handlers():
    logger.debug("Clearing button handlers to prevent unintended actions from main.py.")
    up_button.when_pressed = None
    down_button.when_pressed = None
    ok_button.when_pressed = None
    back_button.when_pressed = None

def exit_menu_to_standby():
    logger.info("Exiting utility menu, returning to standby mode from main.py.")
    state_manager.exit_utility()
    lcd1602.clear()
    lcd1602.write(0, 0, "Returning to")
    lcd1602.write(0, 1, "Standby Mode")
    time.sleep(1)
    clear_button_handlers()
    display_standby_mode_screen()

def display_standby_mode_screen():
    lcd1602.clear()
    update_dump_drive_mountpoint()
    if DUMP_DRIVE_MOUNTPOINT is None or not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
        lcd1602.write(0, 0, "Storage Missing")
    else:
        lcd1602.write(0, 0, "Storage Detected")
        lcd1602.write(0, 1, "Load Media")

def menu_callback():
    display_menu()
    assign_menu_handlers()

def main():
    setup_leds()
    setup_lcd()
    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Missing")

    button_handler = ButtonHandler(back_button, ok_button, up_button, down_button, state_manager, menu_callback)
    button_thread = Thread(target=button_handler.button_listener, args=(main_stop_event,))
    button_thread.start()

    # Start power monitoring
    power_manager.start_monitoring()

    try:
        while True:
            update_dump_drive_mountpoint()
            if DUMP_DRIVE_MOUNTPOINT is not None and os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
                break
            time.sleep(2)

        display_standby_mode_screen()

        # This LED state resetting should only happen on program startup
        set_led_state(SUCCESS_LED, False)  # Initially turn off success LED
        set_led_state(ERROR_LED, False)    # Initially turn off error LED
        set_led_state(PROGRESS_LED, False) # Ensure progress LED is off

        while not main_stop_event.is_set():
            update_dump_drive_mountpoint()  # Periodically update DUMP_DRIVE_MOUNTPOINT
            if DUMP_DRIVE_MOUNTPOINT is None:
                lcd1602.clear()
                lcd1602.write(0, 0, "Storage Missing")
                time.sleep(5)  # Wait a bit before checking again
                continue
            if state_manager.is_standby():
                initial_drives = get_mounted_drives_lsblk()
                logger.info("Waiting for SD card to be plugged in...")

                # Detect new SD card
                sd_mountpoint = detect_new_drive(initial_drives)
                if sd_mountpoint:
                    state_manager.enter_transfer()
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

                    try:
                        # Updated function call to match new signature
                        success = copy_sd_to_dump(sd_mountpoint, DUMP_DRIVE_MOUNTPOINT, log_file)
                        if success:
                            set_led_state(SUCCESS_LED, True)  # Turn on success LED after a successful transfer
                            set_led_state(PROGRESS_LED, False) # Turn off progress LED when done
                            lcd1602.clear()
                            lcd1602.write(0, 0, "Transfer Done")
                            lcd1602.write(0, 1, "Load New Media")
                        else:
                            set_led_state(PROGRESS_LED, False) # Ensure progress LED is off in case of failure
                    except Exception as e:
                        logger.error(f"An error occurred during transfer: {e}")
                        set_led_state(ERROR_LED, True)
                        set_led_state(PROGRESS_LED, False)

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

                    # Return to standby mode
                    state_manager.enter_standby()
                    display_standby_mode_screen()

            elif state_manager.is_utility():
                # If in utility mode, just wait
                time.sleep(0.1)
            else:
                # If in transfer mode, wait for it to complete
                time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting...")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        set_led_state(ERROR_LED, True)
    finally:
        # Signal all threads to stop
        main_stop_event.set()
        button_thread.join()

        # Stop power monitoring
        power_manager.stop_monitoring()

        # Cleanup and turn off all LEDs when the program exits
        set_led_state(PROGRESS_LED, False)
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