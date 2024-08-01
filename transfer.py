import os
import time
import subprocess
import xxhash
from datetime import datetime
import platform
import logging
import shutil
import re
import sys
from threading import Thread, Event

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('script_log.log')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()
# Detect platform
os_name = platform.system()
is_raspberry_pi = os_name == 'Linux' and platform.machine().startswith('arm')

# Conditional imports
if is_raspberry_pi:
    import RPi.GPIO as GPIO
    from LCD1602 import CharLCD1602
else:
    # Mock GPIO and LCD classes for non-Raspberry Pi environments
    class MockGPIO:
        BCM = 'BCM'
        OUT = 'OUT'
        IN = 'IN'
        LOW = 0
        HIGH = 1

        @staticmethod
        def setmode(mode):
            logger.debug(f"Setting mode to {mode}")

        @staticmethod
        def setup(pin, mode):
            logger.debug(f"Setting up pin {pin} as {mode}")

        @staticmethod
        def output(pin, state):
            logger.debug(f"Setting pin {pin} to {'HIGH' if state else 'LOW'}")

        @staticmethod
        def input(pin):
            logger.debug(f"Reading pin {pin}")
            return MockGPIO.LOW

        @staticmethod
        def cleanup():
            logger.debug("Cleaning up GPIO")

    GPIO = MockGPIO()

    class MockLCD:
        def init_lcd(self, addr, bl):
            logger.debug(f"Initializing LCD at addr {addr} with backlight {bl}")

        def set_backlight(self, state):
            logger.debug(f"Setting LCD backlight to {state}")

        def clear(self):
            logger.debug("Clearing LCD display")

        def write(self, row, col, message):
            logger.debug(f"Writing to LCD at ({row}, {col}): {message}")

    lcd1602 = MockLCD()
    lcd1602.init_lcd(addr=0x3f, bl=1)
    lcd1602.set_backlight(True)

# Setup for LCD
if is_raspberry_pi:
    lcd1602 = CharLCD1602()
    lcd1602.init_lcd(addr=0x3f, bl=1)
    lcd1602.set_backlight(True)

# Setup for LED Bar Graph
LED_BAR_PINS = [5, 6, 13, 19, 26, 20, 21, 16, 12, 18]
GPIO.setmode(GPIO.BCM)
for pin in LED_BAR_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

LED1_PIN = 17  # Activity LED
LED2_PIN = 27  # Error LED
LED3_PIN = 22  # All Good LED
CHECKSUM_LED_PIN = 23  # New Checksum LED

for pin in [LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def get_dump_drive_mountpoint():
    username = os.getenv("USER")
    if os_name == 'Linux':
        print("Running Linux mountpoint.")
        return f'/media/{username}/DUMP_DRIVE'
    elif os_name == 'Darwin':  # macOS
        return '/Volumes/DUMP_DRIVE'
    else:
        raise NotImplementedError("This script only supports Linux and macOS.")

DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()

def get_mounted_drives():
    """Get a list of currently mounted drives using platform-specific commands."""
    try:
        if os_name == 'Linux':
            result = subprocess.run(['lsblk', '-o', 'MOUNTPOINT', '-nr'], stdout=subprocess.PIPE, text=True, check=True)
            drives = [drive for drive in result.stdout.strip().split('\n') if drive]
        elif os_name == 'Darwin':  # macOS
            result = subprocess.run(['mount'], stdout=subprocess.PIPE, text=True, check=True)
            drives = []
            for line in result.stdout.splitlines():
                if 'on /Volumes/' in line:
                    parts = line.split()
                    if len(parts) > 2:
                        mount_point = parts[2]
                        if mount_point.startswith('/Volumes/'):
                            drives.append(mount_point)
        else:
            raise NotImplementedError("This script only supports Linux and macOS.")
        
        return drives

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running platform-specific drive command: {e}")
        return []

def detect_new_drive(initial_drives):
    """Detect any new drive by comparing initial drives with the current state."""
    while True:
        time.sleep(2)  # Increased interval to 2 seconds
        current_drives = get_mounted_drives()
        logger.debug(f"Current mounted drives: {current_drives}")
        new_drives = set(current_drives) - set(initial_drives)
        for drive in new_drives:
            if (os_name == 'Linux' and f"/media/{os.getenv('USER')}" in drive) or \
               (os_name == 'Darwin' and drive.startswith('/Volumes/')):
                logger.info(f"New drive detected: {drive}")
                return drive

def create_timestamped_dir(dump_drive_mountpoint, timestamp):
    """Create a directory with a timestamp in the dump drive mount point."""
    target_dir = os.path.join(dump_drive_mountpoint, timestamp)
    print("Creating target directory:", target_dir)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def rsync_dry_run(source, destination):
    """Perform a dry run of rsync to get file count and total size."""
    try:
        print("Running rsync dry run...")
        process = subprocess.run(
            ['rsync', '-a', '--dry-run', '--stats', f"{source}/", f"{destination}/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        output = process.stdout
        logger.debug(f"rsync dry run output: {output}")

        # Adjust regex to match the actual output
        file_count_match = re.search(r'Number of files: (\d+)', output)
        total_size_match = re.search(r'Total file size: ([\d,]+) bytes', output)

        if file_count_match and total_size_match:
            file_count = int(file_count_match.group(1))
            total_size = int(total_size_match.group(1).replace(',', ''))
            return file_count, total_size
        else:
            logger.error("Unable to parse rsync output correctly.")
            return 0, 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during rsync dry run: {e}")
        logger.error(f"Stderr: {process.stderr}")
        return 0, 0

def has_enough_space(dump_drive_mountpoint, required_size):
    """Check if there is enough space on the dump drive."""
    print("Checking available space on dump drive...")
    _, _, free = shutil.disk_usage(dump_drive_mountpoint)
    return free >= required_size

def calculate_checksum(file_path, led_pin, blink_speed, retries=3, delay=5):
    """Calculate checksum with LED blinking as notification and retry logic."""
    for attempt in range(1, retries + 1):
        try:
            print(f"Running calculate_checksum function for {file_path} (Attempt {attempt})")
            hash_obj = xxhash.xxh64()
            blink_event = Event()
            blink_thread = Thread(target=blink_led, args=(led_pin, blink_event, blink_speed))
            blink_thread.start()
            try:
                with open(file_path, 'rb') as f:
                    while chunk := f.read(32 * 1024 * 1024):  # Increase chunk size to 32MB
                        hash_obj.update(chunk)
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"Error calculating checksum for {file_path}: {e}")
                blink_event.set()
                blink_thread.join()
                time.sleep(delay)
                continue
            finally:
                blink_event.set()
                blink_thread.join()
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Unexpected error calculating checksum for {file_path} on attempt {attempt}: {e}")
            time.sleep(delay)
    return None

def rsync_copy(source, destination, file_size, file_number, file_count, retries=3, delay=5):
    """Copy files using rsync with progress reporting and retry logic."""
    for attempt in range(1, retries + 1):
        try:
            print(f"Running rsync copy (Attempt {attempt})...")
            # We ensure the correct handling of file paths by using rsync appropriately
            process = subprocess.Popen(
                ['rsync', '-a', '--info=progress2', source, destination],  # No trailing slashes on files
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            transferred = 0
            last_percent = 0
            overall_progress = 0
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                    match = re.search(r'(\d+)%', output)
                    if match:
                        percent = int(match.group(1))
                        if percent - last_percent >= 10:
                            last_percent = update_lcd_progress(file_number, file_count, percent, last_percent)
                    match = re.search(r'(\d+) bytes/sec', output)
                    if match:
                        bytes_transferred = int(match.group(1))
                        transferred += bytes_transferred
                        overall_progress = int((transferred / file_size) * 100)
                        set_led_bar_graph(overall_progress)
            stderr_output = process.stderr.read()
            if stderr_output:
                logger.error(stderr_output.strip())
            if process.returncode == 0:
                return True, stderr_output
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during rsync: {e}")
        logger.warning(f"Attempt {attempt} failed, retrying after {delay} seconds...")
        time.sleep(delay)
    return False, stderr_output


def update_lcd_progress(file_number, file_count, progress, last_progress=0):
    """Update the LCD display with the file queue counter and progress bar."""
    if file_count > 0 and abs(progress - last_progress) >= 10:  # Update only if progress changes by 10% or more
        logger.debug("Updating LCD progress...")
        lcd_progress = int(progress / 10)
        progress_bar = '#' * lcd_progress + ' ' * (10 - lcd_progress)
        lcd1602.write(0, 1, f"{file_number}/{file_count} {progress_bar}")
        return progress
    return last_progress

def copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count, retries=3, delay=5):
    """Copy a file with retry logic and checksum verification."""
    for attempt in range(1, retries + 1):
        logger.info(f"Attempt {attempt} to copy {src_path} to {dst_path}")
        file_size = os.path.getsize(src_path)
        success, stderr = rsync_copy(src_path, dst_path, file_size, file_number, file_count, retries, delay)

        if success:
            for checksum_attempt in range(1, retries + 1):
                logger.debug(f"Running calculate_checksum for source (Attempt {checksum_attempt})")
                GPIO.output(LED1_PIN, GPIO.LOW)
                src_checksum = calculate_checksum(src_path, CHECKSUM_LED_PIN, blink_speed=0.1)
                if not src_checksum:
                    logger.warning(f"Checksum calculation failed for source {src_path} on attempt {checksum_attempt}")
                    time.sleep(delay)
                    continue

                logger.debug(f"Running calculate_checksum for destination (Attempt {checksum_attempt})")
                GPIO.output(LED1_PIN, GPIO.LOW)
                dst_checksum = calculate_checksum(dst_path, CHECKSUM_LED_PIN, blink_speed=0.05)
                if not dst_checksum:
                    logger.warning(f"Checksum calculation failed for destination {dst_path} on attempt {checksum_attempt}")
                    time.sleep(delay)
                    continue

                GPIO.output(LED1_PIN, GPIO.HIGH)
                if src_checksum == dst_checksum:
                    logger.info(f"Successfully copied {src_path} to {dst_path} with matching checksums.")
                    return True
                else:
                    logger.warning(f"Checksum mismatch for {src_path} on attempt {checksum_attempt}")
                    time.sleep(delay)
        else:
            logger.warning(f"Attempt {attempt} failed with error: {stderr}")

        time.sleep(delay)

    logger.error(f"Failed to copy {src_path} to {dst_path} after {retries} attempts")
    lcd1602.clear()
    lcd1602.write(0, 0, "ERROR IN TRANSIT")
    lcd1602.write(0, 1, f"{file_number}/{file_count}")
    return False

def shorten_filename(filename, max_length=16):
    """Shorten the filename to fit within the max length for the LCD display."""
    if len(filename) <= max_length:
        return filename
    part_length = (max_length - 3) // 2
    return filename[:part_length] + "..." + filename[-part_length:]

def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file, stop_event, blink_thread):
    """Copy files from the SD card to the dump drive, logging transfer details."""
    print("Running copy_sd_to_dump")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []

    logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

    file_count, total_size = rsync_dry_run(sd_mountpoint, target_dir)
    logger.info(f"Number of files to transfer: {file_count}, Total size: {total_size} bytes")

    if file_count == 0:
        logger.error("No files to transfer.")
        # Update LCD and GPIO to reflect no files error state
        lcd1602.clear()
        lcd1602.write(0, 0, "ERROR: No Files")
        lcd1602.write(0, 1, "Check Media")
        GPIO.output(LED2_PIN, GPIO.HIGH)
        return False

    if not has_enough_space(dump_drive_mountpoint, total_size):
        logger.error(f"Not enough space on {dump_drive_mountpoint}. Required: {total_size} bytes")
        
        # Stop LED1 blinking
        stop_event.set()
        blink_thread.join()

        # Blink LED2 and update LCD display
        lcd1602.clear()
        lcd1602.write(0, 0, "ERROR: No Space")
        lcd1602.write(0, 1, "Remove Drives")
        
        blink_event = Event()
        blink_thread_error = Thread(target=blink_led, args=(LED2_PIN, blink_event, 0.5))
        blink_thread_error.start()

        # Unmount the drive
        unmount_drive(dump_drive_mountpoint)
        unmount_drive(sd_mountpoint)

        # Wait for drive removal
        wait_for_drive_removal(dump_drive_mountpoint)

        # Keep the system in this state until restarted
        while True:
            time.sleep(1)

    file_number = 1
    overall_progress = 0

    with open(log_file, 'a') as log:
        for root, _, files in os.walk(sd_mountpoint):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, sd_mountpoint)
                dst_path = os.path.join(target_dir, rel_path)

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                if not os.path.exists(src_path):
                    logger.warning(f"Source file {src_path} not found. Skipping...")
                    failures.append(src_path)
                    continue

                short_file = shorten_filename(file, 16)
                lcd1602.clear()
                lcd1602.write(0, 0, short_file)
                lcd1602.write(0, 1, f"{file_number}/{file_count}")

                progress = (file_number / file_count) * 100 if file_count > 0 else 0
                set_led_bar_graph(overall_progress)  # Set overall progress on LED
                overall_progress = update_lcd_progress(file_number, file_count, 0)  # Initialize progress bar

                logger.info(f"Copying {src_path} to {dst_path}")
                if not copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count):
                    failures.append(src_path)
                    log.write(f"Failed to copy {src_path} to {dst_path} after multiple attempts\n")
                else:
                    log.write(f"Source: {src_path} copied successfully to Destination: {dst_path}\n")
                    log.flush()

                file_number += 1
                overall_progress = (file_number / file_count) * 100 if file_count > 0 else 0
                set_led_bar_graph(overall_progress)  # Update overall progress on LED

    if failures:
        logger.error("The following files failed to copy:")
        for failure in failures:
            logger.error(failure)
        GPIO.output(LED2_PIN, GPIO.HIGH)
        return False
    else:
        logger.info("All files copied successfully.")
        return True


def unmount_drive(drive_mountpoint):
    """Unmount the drive specified by its mount point."""
    try:
        print("Unmounting drive...")
        if os_name == 'Linux':
            subprocess.run(['umount', drive_mountpoint], check=True)
        elif os_name == 'Darwin':  # macOS
            subprocess.run(['diskutil', 'unmount', drive_mountpoint], check=True)
        elif os_name == 'Windows':
            subprocess.run(['mountvol', drive_mountpoint, '/d'], check=True)
        logger.info(f"Unmounted {drive_mountpoint}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error unmounting {drive_mountpoint}: {e}")
        GPIO.output(LED2_PIN, GPIO.HIGH)

def wait_for_drive_removal(mountpoint):
    """Wait until the drive is removed."""
    while os.path.ismount(mountpoint):
        logger.debug(f"Waiting for {mountpoint} to be removed...")
        time.sleep(5)  # Increased interval to 5 seconds

def blink_led(led_pin, stop_event, blink_speed=0.3):
    """Blink an LED until the stop_event is set."""
    while not stop_event.is_set():
        GPIO.output(led_pin, GPIO.HIGH)
        time.sleep(blink_speed)
        GPIO.output(led_pin, GPIO.LOW)
        time.sleep(blink_speed)

def set_led_bar_graph(progress):
    """Set the LED bar graph based on the overall progress value."""
    num_leds_on = int((progress / 100.0) * len(LED_BAR_PINS))
    for i, pin in enumerate(LED_BAR_PINS):
        GPIO.output(pin, GPIO.HIGH if i < num_leds_on else GPIO.LOW)

def main():
    """Main function to monitor and copy files from new storage devices."""
    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Missing")

    while not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
        time.sleep(2)

    lcd1602.clear()
    lcd1602.write(0, 0, "Storage Detected")
    lcd1602.write(0, 1, "Load Media")

    GPIO.output(LED3_PIN, GPIO.LOW)

    try:
        while True:
            initial_drives = get_mounted_drives()
            logger.debug(f"Initial mounted drives: {initial_drives}")

            logger.info("Waiting for SD card to be plugged in...")
            sd_mountpoint = detect_new_drive(initial_drives)
            if sd_mountpoint:
                logger.info(f"SD card detected at {sd_mountpoint}.")
                logger.debug(f"Updated state of drives: {get_mounted_drives()}")

                GPIO.output(LED3_PIN, GPIO.LOW)
                GPIO.output(LED2_PIN, GPIO.LOW)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                target_dir = create_timestamped_dir(DUMP_DRIVE_MOUNTPOINT, timestamp)
                log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")

                stop_event = Event()
                blink_thread = Thread(target=blink_led, args=(LED1_PIN, stop_event))
                blink_thread.start()

                try:
                    success = copy_sd_to_dump(sd_mountpoint, DUMP_DRIVE_MOUNTPOINT, log_file, stop_event, blink_thread)
                    if success:
                        GPIO.output(LED3_PIN, GPIO.HIGH)
                        GPIO.output(LED1_PIN, GPIO.LOW)
                        GPIO.output(CHECKSUM_LED_PIN, GPIO.LOW)
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
        GPIO.output(LED2_PIN, GPIO.LOW)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        GPIO.output(LED2_PIN, GPIO.HIGH)
    finally:
        GPIO.cleanup()
        lcd1602.clear()
        lcd1602.set_backlight(False)
        # Check if the lcd1602 object has a cleanup method before calling it
        if hasattr(lcd1602, 'cleanup'):
            lcd1602.cleanup()

if __name__ == "__main__":
    main()
