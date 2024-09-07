import os
import time
import subprocess
import re
import logging
import xxhash
import sys
from datetime import datetime
from threading import Event, Thread
from src.mhl_handler import add_file_to_mhl, initialize_mhl_file
from src.lcd_display import update_lcd_progress, shorten_filename, lcd1602
from src.led_control import setup_leds, set_led_state, blink_led, PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED, set_led_bar_graph
from src.system_utils import has_enough_space, unmount_drive
from src.drive_detection import wait_for_drive_removal

logger = logging.getLogger(__name__)

def create_timestamped_dir(dump_drive_mountpoint, timestamp):
    target_dir = os.path.join(dump_drive_mountpoint, timestamp)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def rsync_dry_run(source, destination):
    try:
        process = subprocess.run(
            ['rsync', '-a', '--dry-run', '--stats', source, destination],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        output = process.stdout
        file_count_pattern = re.compile(r'Number of regular files transferred: (\d+)')
        total_size_pattern = re.compile(r'Total transferred file size: ([\d,]+)')

        file_count = int(file_count_pattern.search(output).group(1))
        total_size = int(total_size_pattern.search(output).group(1).replace(',', ''))
        return file_count, total_size
    except (subprocess.CalledProcessError, AttributeError) as e:
        logger.error(f"Error during rsync dry run: {e}")
        return 0, 0

def rsync_copy(source, destination, file_size, file_number, file_count, retries=3, delay=5):
    """Copy files using rsync with progress reporting and retry logic."""
    stop_blink_event = Event()
    blink_thread = Thread(target=blink_led, args=(PROGRESS_LED, stop_blink_event, 0.5))

    # Do NOT clear all LEDs before starting the transfer (removed setup_leds())
    # The progress bar LEDs should not be cleared

    blink_thread.start()  # Start blinking the progress LED

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Running rsync copy (Attempt {attempt})...")
            process = subprocess.Popen(
                ['rsync', '-a', '--info=progress2', source, destination],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            transferred = 0
            last_percent = 0
            overall_progress = 0  # Initialize overall progress

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    sys.stdout.write(output)
                    sys.stdout.flush()

                    # Match the progress percentage and update the LCD
                    match = re.search(r'(\d+)%', output)
                    if match:
                        percent = int(match.group(1))
                        if percent - last_percent >= 10:
                            last_percent = update_lcd_progress(file_number, file_count, percent, last_percent)

                    # Calculate the transfer progress for the LED bar graph
                    match = re.search(r'(\d+) bytes/sec', output)
                    if match:
                        bytes_transferred = int(match.group(1))
                        transferred += bytes_transferred
                        overall_progress = int((transferred / file_size) * 100)

                        # Update the bar graph based on the overall progress
                        set_led_bar_graph(overall_progress)  # Update the bar graph continuously

            stderr_output = process.stderr.read()
            if stderr_output:
                logger.error(stderr_output.strip())
            if process.returncode == 0:
                stop_blink_event.set()  # Stop blinking when done
                blink_thread.join()
                return True, stderr_output
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during rsync: {e}")
        logger.warning(f"Attempt {attempt} failed, retrying after {delay} seconds...")
        time.sleep(delay)

    stop_blink_event.set()  # Stop blinking in case of failure
    blink_thread.join()
    return False, stderr_output


def calculate_checksum(file_path, retries=3, delay=5):
    """Calculate checksum with LED blinking for checksum operation."""
    stop_blink_event = Event()
    blink_thread = Thread(target=blink_led, args=(CHECKSUM_LED, stop_blink_event, 0.2))
    blink_thread.start()  # Start blinking checksum LED

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Calculating checksum for {file_path} (Attempt {attempt})...")
            hash_obj = xxhash.xxh64()
            with open(file_path, 'rb') as f:
                while chunk := f.read(32 * 1024 * 1024):
                    hash_obj.update(chunk)
            stop_blink_event.set()  # Stop blinking when done
            blink_thread.join()
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum: {e}")
        time.sleep(delay)

    stop_blink_event.set()  # Stop blinking in case of failure
    blink_thread.join()
    return None

def copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count, retries=3, delay=5):
    """Copy a file with retry logic and checksum verification."""
    try:
        for attempt in range(1, retries + 1):
            logger.info(f"Attempt {attempt} to copy {src_path} to {dst_path}")
            try:
                file_size = os.path.getsize(src_path)
            except FileNotFoundError:
                logger.error(f"Source file {src_path} not found.")
                set_led_state(ERROR_LED, True)  # Turn on error LED
                return False
            except Exception as e:
                logger.error(f"Unexpected error getting file size: {e}")
                set_led_state(ERROR_LED, True)  # Turn on error LED
                return False

            success, stderr = rsync_copy(src_path, dst_path, file_size, file_number, file_count, retries, delay)

            if success:
                # Verify checksum
                src_checksum = calculate_checksum(src_path)
                dst_checksum = calculate_checksum(dst_path)

                if src_checksum == dst_checksum:
                    logger.info(f"File {src_path} copied and checksum verified.")
                    return True
                else:
                    logger.warning(f"Checksum mismatch for {src_path}")
                    set_led_state(ERROR_LED, True)  # Turn on error LED for mismatch
                    return False
            else:
                logger.warning(f"Attempt {attempt} failed with error: {stderr}")
                set_led_state(ERROR_LED, True)  # Turn on error LED

            time.sleep(delay)

        logger.error(f"Failed to copy {src_path} to {dst_path} after {retries} attempts")
        set_led_state(ERROR_LED, True)  # Turn on error LED
        return False

    except Exception as e:
        logger.error(f"An unexpected error occurred in copy_file_with_checksum_verification: {e}")
        set_led_state(ERROR_LED, True)  # Turn on error LED
        return False


def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file, stop_event, blink_thread):
    """Main function for copying files from the SD card to the dump drive."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []

    logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

    # Initialize MHL file
    mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)

    # Perform dry run to get file count and total size
    file_count, total_size = rsync_dry_run(sd_mountpoint, target_dir)
    logger.info(f"Number of files to transfer: {file_count}, Total size: {total_size} bytes")

    if not has_enough_space(dump_drive_mountpoint, total_size):
        logger.error(f"Not enough space on {dump_drive_mountpoint}. Required: {total_size} bytes")
        
        stop_event.set()
        blink_thread.join()

        lcd1602.clear()
        lcd1602.write(0, 0, "ERROR: No Space")
        lcd1602.write(0, 1, "Remove Drives")
        
        blink_event = Event()
        blink_thread_error = Thread(target=blink_led, args=(ERROR_LED, blink_event, 0.5))
        blink_thread_error.start()

        unmount_drive(dump_drive_mountpoint)
        unmount_drive(sd_mountpoint)

        wait_for_drive_removal(dump_drive_mountpoint)
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

                progress = (file_number / file_count) * 100
                set_led_bar_graph(overall_progress)
                overall_progress = update_lcd_progress(file_number, file_count, 0)

                logger.info(f"Copying {src_path} to {dst_path}")
                if not copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count):
                    failures.append(src_path)
                    log.write(f"Failed to copy {src_path} to {dst_path} after multiple attempts\n")
                else:
                    log.write(f"Source: {src_path} copied successfully to Destination: {dst_path}\n")
                    log.flush()

                    src_checksum = calculate_checksum(src_path)
                    if src_checksum:
                        add_file_to_mhl(mhl_filename, tree, hashes, dst_path, src_checksum, os.path.getsize(src_path))

                file_number += 1
                overall_progress = (file_number / file_count) * 100
                set_led_bar_graph(overall_progress)

    # After all files are transferred, handle the success or error
    if failures:
        logger.error("The following files failed to copy:")
        for failure in failures:
            logger.error(failure)
        set_led_state(ERROR_LED, True)
        return False
    else:
        logger.info("All files copied successfully.")
        set_led_state(SUCCESS_LED, True)  # Turn on success LED only after all files are transferred
        set_led_state(PROGRESS_LED, False)  # Turn off progress LED
        return True
