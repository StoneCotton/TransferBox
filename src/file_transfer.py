import os
import time
import subprocess
import re
import logging
import xxhash
import sys
from datetime import datetime
from threading import Event, Thread
from contextlib import contextmanager

from src.mhl_handler import add_file_to_mhl, initialize_mhl_file
from src.lcd_display import update_lcd_progress, shorten_filename, lcd1602
from src.led_control import setup_leds, set_led_state, blink_led, PROGRESS_LED, CHECKSUM_LED, SUCCESS_LED, ERROR_LED, set_led_bar_graph
from src.system_utils import has_enough_space, unmount_drive
from src.drive_detection import DriveDetection

logger = logging.getLogger(__name__)

class FileTransfer:
    def __init__(self, state_manager):
        self.state_manager = state_manager

    @contextmanager
    def led_context(self, led, blink=False, blink_speed=0.5):
        stop_event = Event()
        if blink:
            blink_thread = Thread(target=blink_led, args=(led, stop_event, blink_speed))
            blink_thread.start()
        else:
            set_led_state(led, True)
        try:
            yield
        finally:
            if blink:
                stop_event.set()
                blink_thread.join()
            set_led_state(led, False)

    def create_timestamped_dir(self, dump_drive_mountpoint, timestamp):
        target_dir = os.path.join(dump_drive_mountpoint, timestamp)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def rsync_dry_run(self, source, destination):
        try:
            process = subprocess.run(
                ['rsync', '-a', '--dry-run', '--stats', source, destination],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            output = process.stdout
            file_count = int(re.search(r'Number of regular files transferred: (\d+)', output).group(1))
            total_size = int(re.search(r'Total transferred file size: ([\d,]+)', output).group(1).replace(',', ''))
            return file_count, total_size
        except (subprocess.CalledProcessError, AttributeError) as e:
            logger.error(f"Error during rsync dry run: {e}")
            return 0, 0

    def rsync_copy(self, source, destination, file_size, file_number, file_count):
        with self.led_context(PROGRESS_LED, blink=True, blink_speed=0.5):
            try:
                process = subprocess.Popen(
                    ['rsync', '-a', '--info=progress2', source, destination],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                transferred = 0
                last_percent = 0

                for line in process.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()

                    if match := re.search(r'(\d+)%', line):
                        percent = int(match.group(1))
                        if percent - last_percent >= 10:
                            last_percent = update_lcd_progress(file_number, file_count, percent, last_percent)

                    if match := re.search(r'(\d+) bytes/sec', line):
                        bytes_transferred = int(match.group(1))
                        transferred += bytes_transferred
                        overall_progress = int((transferred / file_size) * 100)
                        set_led_bar_graph(overall_progress)

                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, process.args)
                return True, process.stderr.read()
            except subprocess.CalledProcessError as e:
                logger.error(f"Error during rsync: {e}")
                return False, str(e)

    def calculate_checksum(self, file_path):
        with self.led_context(CHECKSUM_LED, blink=True, blink_speed=0.1):
            try:
                hash_obj = xxhash.xxh64()
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(32 * 1024 * 1024), b''):
                        hash_obj.update(chunk)
                checksum = hash_obj.hexdigest()
                logger.info(f"Checksum calculated for {file_path}: {checksum}")
                return checksum
            except Exception as e:
                logger.error(f"Error calculating checksum for {file_path}: {e}")
                return None

    def copy_file_with_verification(self, src_path, dst_path, file_number, file_count):
        try:
            file_size = os.path.getsize(src_path)
        except OSError as e:
            logger.error(f"Error getting file size for {src_path}: {e}")
            return False, None

        success, stderr = self.rsync_copy(src_path, dst_path, file_size, file_number, file_count)
        if not success:
            return False, None

        logger.info(f"Calculating checksum for source file: {src_path}")
        src_checksum = self.calculate_checksum(src_path)
        logger.info(f"Calculating checksum for destination file: {dst_path}")
        dst_checksum = self.calculate_checksum(dst_path)

        if src_checksum != dst_checksum:
            logger.warning(f"Checksum mismatch for {src_path}")
            logger.warning(f"Source checksum: {src_checksum}")
            logger.warning(f"Destination checksum: {dst_checksum}")
            set_led_state(ERROR_LED, True)
            return False, None

        logger.info(f"File {src_path} copied and verified successfully.")
        logger.info(f"Checksum: {src_checksum}")
        return True, src_checksum

    def copy_sd_to_dump(self, sd_mountpoint, dump_drive_mountpoint, log_file):
        logger.info("Starting copy_sd_to_dump method")
        
        if dump_drive_mountpoint is None:
            logger.error("DUMP_DRIVE not found, cannot proceed with copy")
            return False

        if not self.state_manager.is_standby():
            logger.error("Cannot start transfer: system is not in standby state")
            return False

        logger.info("System is in standby state, proceeding with transfer")

        try:
            logger.info("Attempting to enter transfer state")
            self.state_manager.enter_transfer()  # Start timing the transfer
        except ValueError as e:
            logger.error(f"Failed to enter transfer state: {e}")
            return False

        logger.info("Successfully entered transfer state")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_dir = self.create_timestamped_dir(dump_drive_mountpoint, timestamp)
        failures = []

        logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

        try:
            mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)

            file_count, total_size = self.rsync_dry_run(sd_mountpoint, target_dir)
            logger.info(f"Number of files to transfer: {file_count}, Total size: {total_size} bytes")

            if not has_enough_space(dump_drive_mountpoint, total_size):
                logger.error(f"Not enough space on {dump_drive_mountpoint}. Required: {total_size} bytes")
                lcd1602.clear()
                lcd1602.write(0, 0, "ERROR: No Space")
                lcd1602.write(0, 1, "Remove Drives")
                set_led_state(ERROR_LED, True)
                return False

            with open(log_file, 'a') as log:
                total_files = sum([len(files) for _, _, files in os.walk(sd_mountpoint)])
                file_number = 0
                for root, _, files in os.walk(sd_mountpoint):
                    for file in files:
                        file_number += 1
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
                        lcd1602.write(0, 1, f"{file_number}/{total_files}")

                        logger.info(f"Copying file {file_number}/{total_files}: {src_path}")
                        success, checksum = self.copy_file_with_verification(src_path, dst_path, file_number, total_files)
                        if success:
                            log.write(f"Source: {src_path} copied successfully to Destination: {dst_path}\n")
                            log.flush()
                            if checksum:
                                add_file_to_mhl(mhl_filename, tree, hashes, dst_path, checksum, os.path.getsize(dst_path))
                                logger.info(f"Added file to MHL: {dst_path}, Checksum: {checksum}")
                        else:
                            failures.append(src_path)
                            log.write(f"Failed to copy {src_path} to {dst_path}\n")
                            logger.error(f"Failed to copy {src_path} to {dst_path}")

                        overall_progress = int((file_number / total_files) * 100)
                        set_led_bar_graph(overall_progress)

        except Exception as e:
            logger.error(f"An error occurred during transfer: {e}")
            set_led_state(ERROR_LED, True)
            return False
        finally:
            logger.info("Exiting transfer state")
            self.state_manager.exit_transfer()  # Ensure we always exit transfer state

        if failures:
            logger.error("The following files failed to copy:")
            for failure in failures:
                logger.error(failure)
            set_led_state(ERROR_LED, True)
            return False
        else:
            logger.info("All files copied successfully.")
            set_led_state(SUCCESS_LED, True)
            return True