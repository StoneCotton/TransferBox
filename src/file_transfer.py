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

def calculate_checksum(file_path, led_pin, blink_speed, retries=3, delay=5):
    """Calculate checksum with LED blinking as notification and retry logic."""
    for attempt in range(1, retries + 3):
        try:
            logger.info(f"Running calculate_checksum function for {file_path} (Attempt {attempt})")
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

def copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count, retries=3, delay=5):
    """Copy a file with retry logic and checksum verification."""
    try:
        for attempt in range(1, retries + 1):
            logger.info(f"Attempt {attempt} to copy {src_path} to {dst_path}")
            try:
                file_size = os.path.getsize(src_path)
            except FileNotFoundError:
                logger.error(f"Source file {src_path} not found.")
                break
            except Exception as e:
                logger.error(f"Unexpected error getting file size: {e}")
                break

            success, stderr = rsync_copy(src_path, dst_path, file_size, file_number, file_count, retries, delay)

            if success:
                for checksum_attempt in range(1, retries + 1):
                    try:
                        logger.info(f"Running calculate_checksum for source (Attempt {checksum_attempt})")
                        set_led_state(CHECKSUM_LED, False)
                        src_checksum = calculate_checksum(src_path, CHECKSUM_LED, blink_speed=0.1)
                        if not src_checksum:
                            logger.warning(f"Checksum calculation failed for source {src_path} on attempt {checksum_attempt}")
                            time.sleep(delay)
                            continue

                        logger.info(f"Running calculate_checksum for destination (Attempt {checksum_attempt})")
                        set_led_state(CHECKSUM_LED, False)
                        dst_checksum = calculate_checksum(dst_path, CHECKSUM_LED, blink_speed=0.05)
                        if not dst_checksum:
                            logger.warning(f"Checksum calculation failed for destination {dst_path} on attempt {checksum_attempt}")
                            time.sleep(delay)
                            continue

                        set_led_state(CHECKSUM_LED, True)
                        if src_checksum == dst_checksum:
                            logger.info(f"Successfully copied {src_path} to {dst_path} with matching checksums.")
                            return True
                        else:
                            logger.warning(f"Checksum mismatch for {src_path} on attempt {checksum_attempt}")
                            time.sleep(delay)
                    except Exception as e:
                        logger.error(f"Unexpected error during checksum calculation: {e}")
                        break
            else:
                logger.warning(f"Attempt {attempt} failed with error: {stderr}")

            time.sleep(delay)

        logger.error(f"Failed to copy {src_path} to {dst_path} after {retries} attempts")
        set_led_state(ERROR_LED, True)  # Turn on the error LED
        lcd1602.clear()
        lcd1602.write(0, 0, "ERROR IN TRANSIT")
        lcd1602.write(0, 1, f"{file_number}/{file_count}")
        return False

    except Exception as e:
        logger.error(f"An unexpected error occurred in copy_file_with_checksum_verification: {e}")
        set_led_state(ERROR_LED, True)
        lcd1602.clear()
        lcd1602.write(0, 0, "CRITICAL ERROR")
        lcd1602.write(0, 1, "Check Log")
        return False

def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file, stop_event, blink_thread):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []

    logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

    mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)

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

                    src_checksum = calculate_checksum(src_path, CHECKSUM_LED, blink_speed=0.1)
                    if src_checksum:
                        add_file_to_mhl(mhl_filename, tree, hashes, dst_path, src_checksum, os.path.getsize(src_path))

                file_number += 1
                overall_progress = (file_number / file_count) * 100
                set_led_bar_graph(overall_progress)

    if failures:
        logger.error("The following files failed to copy:")
        for failure in failures:
            logger.error(failure)
        set_led_state(ERROR_LED, True)
        return False
    else:
        logger.info("All files copied successfully.")
        set_led_state(SUCCESS_LED, True)  # Turn on success LED
        return True
