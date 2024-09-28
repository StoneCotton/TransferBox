from time import sleep
from src.lcd_display import lcd1602
from src.drive_detection import DriveDetection
from src.system_utils import unmount_drive, get_dump_drive_mountpoint
from src.led_control import setup_leds, set_led_state, PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED, BAR_GRAPH_LEDS
from src.power_management import power_manager
import logging
from threading import Lock
import os
import time
import subprocess
import shutil

logger = logging.getLogger(__name__)
drive_detector = DriveDetection()
# Global lock for preventing simultaneous access
option_lock = Lock()

# State variables for button handling
menu_active = False
current_menu_index = 0
processing_option = False  # Flag to prevent double handling

# Menu options
menu_options = ["List Drives", "Format Drive", "Unmount Drives", "Test LEDs", "Test Screen", "Shutdown", "Reboot", "Available Space", "Version Info", "Update Firmware", "Reset to Factory"]

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
        elif selected_option == "Available Space":
            check_available_space(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)
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
    drives = drive_detector.get_mounted_drives_lsblk()
    for drive in drives:
        # Get the last part of the path
        drive_name = os.path.basename(drive)
        lcd1602.clear()
        lcd1602.write(0, 0, "Mounted Drives:")
        lcd1602.write(0, 1, drive_name)
        time.sleep(2)  # Pause to display each drive for 2 seconds
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def format_drive(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    dump_drive_mountpoint = get_dump_drive_mountpoint()
    
    # Check if a valid mountpoint was found
    if dump_drive_mountpoint is None:
        lcd1602.clear()
        lcd1602.write(0, 0, "DUMP_DRIVE not")
        lcd1602.write(0, 1, "found")
        logger.error("DUMP_DRIVE mountpoint not found")
        time.sleep(2)
        return handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

    # Check if the drive is mounted
    if not os.path.ismount(dump_drive_mountpoint):
        lcd1602.clear()
        lcd1602.write(0, 0, "DUMP_DRIVE not")
        lcd1602.write(0, 1, "mounted")
        logger.error(f"DUMP_DRIVE not mounted at {dump_drive_mountpoint}")
        time.sleep(2)
        return handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

    lcd1602.clear()
    lcd1602.write(0, 0, "Hold OK for 3s")
    lcd1602.write(0, 1, "to format drive")

    start_time = time.time()
    while ok_button.is_pressed:
        if time.time() - start_time >= 3:
            break
        time.sleep(0.1)
   
    if time.time() - start_time < 3:
        lcd1602.clear()
        lcd1602.write(0, 0, "Format cancelled")
        time.sleep(2)
        return handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

    lcd1602.clear()
    lcd1602.write(0, 0, "Formatting...")
    lcd1602.write(0, 1, "Please wait...")

    try:
        # Use findmnt to get the device name
        findmnt_output = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', dump_drive_mountpoint], text=True).strip()
        logger.info(f"findmnt output: {findmnt_output}")

        if not findmnt_output:
            raise ValueError(f"Couldn't find device for {dump_drive_mountpoint} using findmnt")

        device = findmnt_output

        logger.info(f"Found device {device} for {dump_drive_mountpoint}")

        # Unmount the drive before formatting
        subprocess.run(['sudo', 'umount', dump_drive_mountpoint], check=True)
        logger.info(f"Unmounted {dump_drive_mountpoint}")

        # Double-check if the device still exists after unmounting
        blkid_output = subprocess.check_output(['sudo', 'blkid', '-o', 'device'], text=True)
        logger.info(f"blkid output: {blkid_output}")
        if device not in blkid_output:
            raise ValueError(f"Device {device} not found after unmounting")

        # Format the drive as NTFS
        subprocess.run(['sudo', 'ntfslabel', '--force', device, 'DUMP_DRIVE'], check=True)

        subprocess.run(['sudo', 'mkfs.ntfs', '-f', '-L', 'DUMP_DRIVE', device], check=True)
        logger.info(f"Formatted {device} as NTFS")
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

        # Create the mount point if it doesn't exist
        subprocess.run(['sudo', 'mkdir', '-p', dump_drive_mountpoint], check=True)
        logger.info(f"Created mount point: {dump_drive_mountpoint}")

        # Mount the newly formatted drive
        current_label = subprocess.check_output(['sudo', 'blkid', '-s', 'LABEL', '-o', 'value', device], text=True).strip()
        if current_label != 'DUMP_DRIVE':
            subprocess.run(['sudo', 'ntfslabel', device, 'DUMP_DRIVE'], check=True)
        subprocess.run(['sudo', 'mount', '-t', 'ntfs', device, dump_drive_mountpoint], check=True)
        logger.info(f"Mounted {device} to {dump_drive_mountpoint}")

        # Verify that the drive is mounted
        if os.path.ismount(dump_drive_mountpoint):
            lcd1602.clear()
            lcd1602.write(0, 0, "Format complete")
            lcd1602.write(0, 1, "DUMP_DRIVE ready")
            logger.info("DUMP_DRIVE formatted and mounted successfully")
        else:
            raise RuntimeError(f"Failed to mount {device} to {dump_drive_mountpoint}")

        # Optionally, change ownership of the mount point to the current user
        current_user = os.environ.get('SUDO_USER', os.environ.get('USER'))
        subprocess.run(['sudo', 'chown', f'{current_user}:{current_user}', dump_drive_mountpoint], check=True)
        logger.info(f"Changed ownership of {dump_drive_mountpoint} to {current_user}")

    except subprocess.CalledProcessError as e:
        lcd1602.clear()
        lcd1602.write(0, 0, "Format failed")
        lcd1602.write(0, 1, "Check logs")
        logger.error(f"Error formatting or mounting DUMP_DRIVE: {e}")
    except ValueError as e:
        lcd1602.clear()
        lcd1602.write(0, 0, "Error: Drive not")
        lcd1602.write(0, 1, "found")
        logger.error(f"Error finding DUMP_DRIVE: {e}")
    except RuntimeError as e:
        lcd1602.clear()
        lcd1602.write(0, 0, "Mount failed")
        lcd1602.write(0, 1, "Check logs")
        logger.error(str(e))
    except Exception as e:
        lcd1602.clear()
        lcd1602.write(0, 0, "Unexpected error")
        lcd1602.write(0, 1, "Check logs")
        logger.error(f"Unexpected error during formatting: {e}", exc_info=True)

    time.sleep(3)
    return handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

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
    power_manager.safe_shutdown()

def reboot_system(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    logger.info("Rebooting the system...")
    lcd1602.clear()
    lcd1602.write(0, 0, "Rebooting...")
    lcd1602.write(0, 1, "Wait 60 Seconds.")
    sleep(5)
    power_manager.safe_reboot()

def version_number(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    logger.info("Version Number: v0.0.1")
    lcd1602.clear()
    lcd1602.write(0, 0, "Version Number:")
    lcd1602.write(0, 1, "v0.0.1 240820")
    sleep(5)
    handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))

def check_available_space(ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    dump_drive_mountpoint = get_dump_drive_mountpoint()

    if not os.path.ismount(dump_drive_mountpoint):
        lcd1602.clear()
        lcd1602.write(0, 0, "DUMP_DRIVE not")
        lcd1602.write(0, 1, "connected")
        logger.warning("DUMP_DRIVE not connected when checking available space")
    else:
        try:
            total, used, free = shutil.disk_usage(dump_drive_mountpoint)
            
            # Convert to appropriate unit
            if free < 999 * 1024 * 1024:  # Less than 999 MB
                free_space = free / (1024 * 1024)
                unit = "MB"
            elif free < 999 * 1024 * 1024 * 1024:  # Less than 999 GB
                free_space = free / (1024 * 1024 * 1024)
                unit = "GB"
            else:  # 1 TB or more
                free_space = free / (1024 * 1024 * 1024 * 1024)
                unit = "TB"
            
            # Round to 2 decimal places
            free_space = round(free_space, 2)
            
            lcd1602.clear()
            lcd1602.write(0, 0, "Available Space:")
            lcd1602.write(0, 1, f"{free_space} {unit}")
            logger.info(f"Available space on DUMP_DRIVE: {free_space} {unit}")
        except Exception as e:
            lcd1602.clear()
            lcd1602.write(0, 0, "Error checking")
            lcd1602.write(0, 1, "available space")
            logger.error(f"Error checking available space: {e}")

    # Wait for OK button press to return to menu
    while not ok_button.is_pressed:
        pass
    
    return handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, handle_option_completion, clear_handlers, assign_handlers))