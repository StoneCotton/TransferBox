from src.logger_setup import setup_logging
from src.drive_detection import get_mounted_drives_lsblk, detect_new_drive, wait_for_drive_removal
from src.mhl_handler import initialize_mhl_file, add_file_to_mhl
from src.file_transfer import copy_sd_to_dump, create_timestamped_dir, rsync_dry_run, rsync_copy, copy_file_with_checksum_verification
from src.lcd_display import setup_lcd, update_lcd_progress, shorten_filename, lcd1602
from src.led_control import setup_leds, blink_led, LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN, set_led_bar_graph
from src.system_utils import get_dump_drive_mountpoint, unmount_drive
import os
import time
from datetime import datetime
from threading import Thread, Event

logger = setup_logging()
DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()

def main():
    setup_leds()
    setup_lcd()
    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Missing")

    while not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
        time.sleep(2)

    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Detected")
    lcd1602.write(0, 1, "Load Media")

    LED3_PIN.off()  # Equivalent to GPIO.LOW

    try:
        while True:
            initial_drives = get_mounted_drives_lsblk()
            logger.debug(f"Initial mounted drives: {initial_drives}")

            logger.info("Waiting for SD card to be plugged in...")
            sd_mountpoint = detect_new_drive(initial_drives)
            if sd_mountpoint:
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
                        LED3_PIN.on()  # Equivalent to GPIO.HIGH
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
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Cleaning up and exiting.")
        LED2_PIN.off()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        LED2_PIN.on()  # Equivalent to GPIO.HIGH
    finally:
        # No need to call GPIO.cleanup() as gpiozero handles this internally
        lcd1602.clear()
        lcd1602.set_backlight(False)
        if hasattr(lcd1602, 'cleanup'):
            lcd1602.cleanup()

if __name__ == "__main__":
    main()
