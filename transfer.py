import os
import time
import subprocess
import xxhash
from datetime import datetime
import platform
import logging
import sys
import shutil
import re
import RPi.GPIO as GPIO
from threading import Thread, Event
from LCD1602 import CharLCD1602
import board
import busio

# Setup for LCD
lcd1602 = CharLCD1602()
lcd1602.init_lcd(addr=0x3f, bl=1)  # Initialize the LCD with the correct address
lcd1602.set_backlight(True)  # Ensure the backlight is on

# Setup for LED Bar Graph
LED_BAR_PINS = [5, 6, 13, 19, 26, 20, 21, 16, 12, 18]
GPIO.setmode(GPIO.BCM)
for pin in LED_BAR_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

LED1_PIN = 17  # Activity LED
LED2_PIN = 27  # Error LED
LED3_PIN = 22  # All Good LED

GPIO.setup(LED1_PIN, GPIO.OUT)
GPIO.setup(LED2_PIN, GPIO.OUT)
GPIO.setup(LED3_PIN, GPIO.OUT)

GPIO.output(LED1_PIN, GPIO.LOW)
GPIO.output(LED2_PIN, GPIO.LOW)
GPIO.output(LED3_PIN, GPIO.LOW)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('script_log.log')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

username = os.getenv("USER")
if platform.system() == 'Linux':
    DUMP_DRIVE_MOUNTPOINT = f'/media/{username}/DUMP_DRIVE'
elif platform.system() == 'Darwin':  # macOS
    DUMP_DRIVE_MOUNTPOINT = '/Volumes/DUMP_DRIVE'
elif platform.system() == 'Windows':
    DUMP_DRIVE_MOUNTPOINT = 'D:\\DUMP_DRIVE'
else:
    raise NotImplementedError("This script only supports Linux, macOS, and Windows.")

def get_mounted_drives_lsblk():
    """Get a list of currently mounted drives using lsblk command."""
    try:
        result = subprocess.run(['lsblk', '-o', 'MOUNTPOINT', '-nr'], stdout=subprocess.PIPE, text=True, check=True)
        mounted_drives = result.stdout.strip().split('\n')
        return [drive for drive in mounted_drives if drive]
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running lsblk: {e}")
        return []

def detect_new_drive(initial_drives):
    """Detect any new drive by comparing initial drives with the current state."""
    while True:
        time.sleep(2)  # Check every 2 seconds
        current_drives = get_mounted_drives_lsblk()
        logger.debug(f"Current mounted drives: {current_drives}")
        new_drives = set(current_drives) - set(initial_drives)
        if new_drives:
            for drive in new_drives:
                if f"/media/{username}" in drive or "/mnt" in drive:
                    logger.info(f"New drive detected: {drive}")
                    return drive

def create_timestamped_dir(dump_drive_mountpoint, timestamp):
    """Create a directory with a timestamp in the dump drive mount point."""
    target_dir = os.path.join(dump_drive_mountpoint, timestamp)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)  # Create the directory if it doesn't exist
    return target_dir

def calculate_checksum(filepath):
    """Calculate and return the checksum of the file."""
    hash_obj = xxhash.xxh64()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return None
    except PermissionError:
        logger.error(f"Permission denied: {filepath}")
        return None

def rsync_dry_run(source, destination):
    """Perform a dry run of rsync to get file count and total size."""
    try:
        process = subprocess.run(
            ['rsync', '-a', '--dry-run', '--stats', source, destination],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        output = process.stdout
        file_count = 0
        total_size = 0
        file_count_pattern = re.compile(r'Number of files: (\d+)')
        total_size_pattern = re.compile(r'Total file size: ([\d,]+)')

        for line in output.split('\n'):
            file_count_match = file_count_pattern.search(line)
            total_size_match = total_size_pattern.search(line)

            if file_count_match:
                file_count = int(file_count_match.group(1))
            if total_size_match:
                total_size = int(total_size_match.group(1).replace(',', ''))
        
        return file_count, total_size
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during rsync dry run: {e}")
        return 0, 0

def has_enough_space(dump_drive_mountpoint, required_size):
    """Check if there is enough space on the dump drive."""
    total, used, free = shutil.disk_usage(dump_drive_mountpoint)
    return free >= required_size

def rsync_copy(source, destination):
    """Copy files using rsync with progress reporting."""
    try:
        process = subprocess.Popen(
            ['rsync', '-a', '--info=progress2', source, destination],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()
        stderr_output = process.stderr.read()
        if stderr_output:
            logger.error(stderr_output.strip())
        return process.returncode == 0, stderr_output
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during rsync: {e}")
        return False, str(e)

def copy_file_with_retry(src_path, dst_path, retries=3, delay=5):
    """Copy a file with retry logic."""
    for attempt in range(1, retries + 1):
        logger.info(f"Attempt {attempt} to copy {src_path} to {dst_path}")
        success, stderr = rsync_copy(src_path, dst_path)
        if not success:
            logger.warning(f"Attempt {attempt} failed with error: {stderr}")
            time.sleep(delay)
        else:
            src_checksum = calculate_checksum_with_led(src_path, 0.05)
            dst_checksum = calculate_checksum_with_led(dst_path, 0.05)
            if src_checksum and dst_checksum and src_checksum == dst_checksum:
                logger.info(f"Successfully copied {src_path} to {dst_path} with matching checksums.")
                return True
            else:
                logger.warning(f"Checksum mismatch for {src_path} on attempt {attempt}")
                time.sleep(delay)
    return False

def shorten_filename(filename, max_length=16):
    """Shorten the filename to fit within the max length for the LCD display."""
    if len(filename) <= max_length:
        return filename
    part_length = (max_length - 3) // 2
    return filename[:part_length] + "..." + filename[-part_length:]

def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file):
    """Copy files from the SD card to the dump drive, logging transfer details."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []

    logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

    file_count, total_size = rsync_dry_run(sd_mountpoint, target_dir)
    logger.info(f"Number of files to transfer: {file_count}, Total size: {total_size} bytes")

    if not has_enough_space(dump_drive_mountpoint, total_size):
        logger.error(f"Not enough space on {dump_drive_mountpoint}. Required: {total_size} bytes")
        return False

    file_number = 1

    with open(log_file, 'a') as log:
        for root, _, files in os.walk(sd_mountpoint):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, sd_mountpoint)
                dst_path = os.path.join(target_dir, rel_path)

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)  # Create destination directory if it doesn't exist

                if not os.path.exists(src_path):
                    logger.warning(f"Source file {src_path} not found. Skipping...")
                    failures.append(src_path)
                    continue

                # Update LCD with shortened file name and position in queue
                short_file = shorten_filename(file, 16)
                lcd1602.clear()
                lcd1602.write(0, 0, short_file)
                lcd1602.write(0, 1, f"{file_number}/{file_count}")
                lcd1602.set_backlight(True)  # Ensure the backlight is on

                # Update LED Bar Graph with progress
                progress = (file_number / file_count) * 100
                set_led_bar_graph(progress)

                logger.info(f"Copying {src_path} to {dst_path}")
                if not copy_file_with_retry(src_path, dst_path):
                    failures.append(src_path)
                    log.write(f"Failed to copy {src_path} to {dst_path} after multiple attempts\n")
                else:
                    src_checksum = calculate_checksum_with_led(src_path, 0.05)
                    dst_checksum = calculate_checksum_with_led(dst_path, 0.05)
                    log.write(f"Source: {src_path}, Checksum: {src_checksum}\n")
                    log.write(f"Destination: {dst_path}, Checksum: {dst_checksum}\n")
                    log.flush()  # Ensure immediate write to file

                file_number += 1

    if failures:
        logger.error("The following files failed to copy:")
        for failure in failures:
            logger.error(failure)
        GPIO.output(LED2_PIN, GPIO.HIGH)  # Turn on Error LED if there were failures
        return False
    else:
        logger.info("All files copied successfully.")
        return True

def unmount_drive(drive_mountpoint):
    """Unmount the drive specified by its mount point."""
    try:
        if platform.system() == 'Linux':
            subprocess.run(['umount', drive_mountpoint], check=True)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['diskutil', 'unmount', drive_mountpoint], check=True)
        elif platform.system() == 'Windows':
            subprocess.run(['mountvol', drive_mountpoint, '/d'], check=True)
        logger.info(f"Unmounted {drive_mountpoint}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error unmounting {drive_mountpoint}: {e}")
        GPIO.output(LED2_PIN, GPIO.HIGH)  # Turn on Error LED if unmounting fails

def wait_for_drive_removal(mountpoint):
    """Wait until the drive is removed."""
    while os.path.ismount(mountpoint):
        logger.debug(f"Waiting for {mountpoint} to be removed...")
        time.sleep(2)

def blink_led(led_pin, stop_event, blink_speed=0.3):
    """Blink an LED until the stop_event is set."""
    while not stop_event.is_set():
        GPIO.output(led_pin, GPIO.HIGH)
        time.sleep(blink_speed)
        GPIO.output(led_pin, GPIO.LOW)
        time.sleep(blink_speed)

def calculate_checksum_with_led(filepath, blink_speed):
    """Calculate checksum while blinking LED at specified speed."""
    hash_obj = xxhash.xxh64()
    stop_event = Event()
    blink_thread = Thread(target=blink_led, args=(LED1_PIN, stop_event, blink_speed))
    blink_thread.start()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    finally:
        stop_event.set()
        blink_thread.join()

def set_led_bar_graph(progress):
    """
    Set the LED bar graph based on the progress value.
    :param progress: A value between 0 and 100 indicating the percentage of progress.
    """
    num_leds_on = int((progress / 100.0) * len(LED_BAR_PINS))
    
    for i in range(len(LED_BAR_PINS)):
        if i < num_leds_on:
            GPIO.output(LED_BAR_PINS[i], GPIO.HIGH)
        else:
            GPIO.output(LED_BAR_PINS[i], GPIO.LOW)

def main():
    """Main function to monitor and copy files from new storage devices."""
    dump_drive_mountpoint = DUMP_DRIVE_MOUNTPOINT
    if not os.path.ismount(dump_drive_mountpoint):
        logger.error(f"{DUMP_DRIVE_MOUNTPOINT} not found.")
        return

    GPIO.output(LED3_PIN, GPIO.LOW)  # Ensure LED3 is off initially

    while True:
        initial_drives = get_mounted_drives_lsblk()
        logger.debug(f"Initial mounted drives: {initial_drives}")

        logger.info("Waiting for SD card to be plugged in...")
        sd_mountpoint = detect_new_drive(initial_drives)
        if sd_mountpoint:
            logger.info(f"SD card detected at {sd_mountpoint}.")
            logger.debug(f"Updated state of drives: {get_mounted_drives_lsblk()}")

            GPIO.output(LED3_PIN, GPIO.LOW)  # Turn off All Good LED when a new transfer starts
            GPIO.output(LED2_PIN, GPIO.LOW)  # Turn off Error LED when a new transfer starts

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
            log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")

            stop_event = Event()
            blink_thread = Thread(target=blink_led, args=(LED1_PIN, stop_event))
            blink_thread.start()

            try:
                success = copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file)
                if success:
                    GPIO.output(LED3_PIN, GPIO.HIGH)  # Turn on All Good LED after successful transfer
            finally:
                stop_event.set()
                blink_thread.join()

            unmount_drive(sd_mountpoint)
            wait_for_drive_removal(sd_mountpoint)
            logger.info("Monitoring for new storage devices...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        GPIO.output(LED2_PIN, GPIO.HIGH)  # Turn on Error LED in case of any unexpected error
    finally:
        GPIO.cleanup()
        lcd1602.clear()
        lcd1602.set_backlight(False)  # Turn off backlight
