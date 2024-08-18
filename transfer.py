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
import RPi.GPIO as GPIO
from threading import Thread, Event
from src.LCD1602 import CharLCD1602
import xml.etree.ElementTree as ET
import socket

# # Setup for LCD
# lcd1602 = CharLCD1602()
# lcd1602.init_lcd(addr=0x3f, bl=1)
# lcd1602.set_backlight(True)

# # Setup for LED Bar Graph
# LED_BAR_PINS = [5, 6, 13, 19, 26, 20, 21, 16, 12, 18]
# GPIO.setmode(GPIO.BCM)
# for pin in LED_BAR_PINS:
#     GPIO.setup(pin, GPIO.OUT)
#     GPIO.output(pin, GPIO.LOW)

# LED1_PIN = 17  # Activity LED
# LED2_PIN = 27  # Error LED
# LED3_PIN = 22  # All Good LED
# CHECKSUM_LED_PIN = 23  # New Checksum LED

# for pin in [LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN]:
#     GPIO.setup(pin, GPIO.OUT)
#     GPIO.output(pin, GPIO.LOW)

# def setup_logging():
#     logger = logging.getLogger()
#     logger.setLevel(logging.DEBUG)

#     file_handler = logging.FileHandler('script_log.log')
#     file_handler.setLevel(logging.DEBUG)

#     console_handler = logging.StreamHandler()
#     console_handler.setLevel(logging.INFO)  # Set console handler to INFO level

#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#     file_handler.setFormatter(formatter)
#     console_handler.setFormatter(formatter)

#     logger.addHandler(file_handler)
#     logger.addHandler(console_handler)
#     return logger

# logger = setup_logging()

# def get_dump_drive_mountpoint():
#     username = os.getenv("USER")
#     if platform.system() == 'Linux':
#         print("Running Linux mountpoint.")
#         return f'/media/{username}/DUMP_DRIVE'
#     elif platform.system() == 'Darwin':  # macOS
#         return '/Volumes/DUMP_DRIVE'
#     elif platform.system() == 'Windows':
#         return 'D:\\DUMP_DRIVE'
#     else:
#         raise NotImplementedError("This script only supports Linux, macOS, and Windows.")

# DUMP_DRIVE_MOUNTPOINT = get_dump_drive_mountpoint()

# def get_mounted_drives_lsblk():
#     """Get a list of currently mounted drives using lsblk command."""
#     try:
#         result = subprocess.run(['lsblk', '-o', 'MOUNTPOINT', '-nr'], stdout=subprocess.PIPE, text=True, check=True)
#         return [drive for drive in result.stdout.strip().split('\n') if drive]
#     except subprocess.CalledProcessError as e:
#         logger.error(f"Error running lsblk: {e}")
#         return []

# def initialize_mhl_file(directory_name, target_dir):
#     mhl_filename = os.path.join(target_dir, f"{directory_name}.mhl")
#     root = ET.Element("hashlist", version="2.0", xmlns="urn:ASC:MHL:v2.0")

#     # Creator Info
#     creator_info = ET.SubElement(root, "creatorinfo")
#     creation_date = ET.SubElement(creator_info, "creationdate")
#     creation_date.text = datetime.now().isoformat()
#     hostname = ET.SubElement(creator_info, "hostname")
#     hostname.text = socket.gethostname()
#     tool = ET.SubElement(creator_info, "TransferBox", version="0.1.0")
#     tool.text = "TransferBox"

#     # Process Info
#     process_info = ET.SubElement(root, "processinfo")
#     process = ET.SubElement(process_info, "process")
#     process.text = "in-place"
#     roothash = ET.SubElement(process_info, "roothash")
#     content = ET.SubElement(roothash, "content")
#     structure = ET.SubElement(roothash, "structure")
    
#     # Add initial ignore patterns
#     ignore = ET.SubElement(process_info, "ignore")
#     for pattern in [".DS_Store", "ascmhl", "ascmhl/"]:
#         ignore_pattern = ET.SubElement(ignore, "pattern")
#         ignore_pattern.text = pattern

#     # Create the hashes element
#     hashes = ET.SubElement(root, "hashes")

#     # Write the initial MHL file
#     tree = ET.ElementTree(root)
#     tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
    
#     return mhl_filename, tree, hashes


# def add_file_to_mhl(mhl_filename, tree, hashes, file_path, checksum, file_size):
#     hash_element = ET.SubElement(hashes, "hash")
    
#     # File path, size, and last modification date
#     path = ET.SubElement(hash_element, "path", size=str(file_size))
#     path.text = os.path.relpath(file_path)
#     last_modification_date = ET.SubElement(path, "lastmodificationdate")
#     last_modification_date.text = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
    
#     # File checksum
#     xxh64 = ET.SubElement(hash_element, "xxh64", action="original")
#     xxh64.text = checksum
#     xxh64.set("hashdate", datetime.now().isoformat())
    
#     # Write the updated MHL file
#     tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)


# def detect_new_drive(initial_drives):
#     """Detect any new drive by comparing initial drives with the current state."""
#     while True:
#         time.sleep(2)  # Increased interval to 2 seconds
#         current_drives = get_mounted_drives_lsblk()
#         logger.debug(f"Current mounted drives: {current_drives}")
#         new_drives = set(current_drives) - set(initial_drives)
#         for drive in new_drives:
#             if f"/media/{os.getenv('USER')}" in drive or "/mnt" in drive:
#                 logger.info(f"New drive detected: {drive}")
#                 return drive

# def create_timestamped_dir(dump_drive_mountpoint, timestamp):
#     """Create a directory with a timestamp in the dump drive mount point."""
#     target_dir = os.path.join(dump_drive_mountpoint, timestamp)
#     print("Creating target directory:", target_dir)
#     os.makedirs(target_dir, exist_ok=True)
#     return target_dir

# def rsync_dry_run(source, destination):
#     """Perform a dry run of rsync to get file count and total size."""
#     try:
#         print("Running rsync dry run...")
#         process = subprocess.run(
#             ['rsync', '-a', '--dry-run', '--stats', source, destination],
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             check=True
#         )
#         output = process.stdout
#         file_count_pattern = re.compile(r'Number of regular files transferred: (\d+)')
#         total_size_pattern = re.compile(r'Total transferred file size: ([\d,]+)')

#         file_count = int(file_count_pattern.search(output).group(1))
#         total_size = int(total_size_pattern.search(output).group(1).replace(',', ''))
#         return file_count, total_size
#     except (subprocess.CalledProcessError, AttributeError) as e:
#         logger.error(f"Error during rsync dry run: {e}")
#         return 0, 0

# def has_enough_space(dump_drive_mountpoint, required_size):
#     """Check if there is enough space on the dump drive."""
#     print("Checking available space on dump drive...")
#     _, _, free = shutil.disk_usage(dump_drive_mountpoint)
#     return free >= required_size

# def calculate_checksum(file_path, led_pin, blink_speed, retries=3, delay=5):
#     """Calculate checksum with LED blinking as notification and retry logic."""
#     for attempt in range(1, retries + 1):
#         try:
#             print(f"Running calculate_checksum function for {file_path} (Attempt {attempt})")
#             hash_obj = xxhash.xxh64()
#             blink_event = Event()
#             blink_thread = Thread(target=blink_led, args=(led_pin, blink_event, blink_speed))
#             blink_thread.start()
#             try:
#                 with open(file_path, 'rb') as f:
#                     while chunk := f.read(32 * 1024 * 1024):  # Increase chunk size to 32MB
#                         hash_obj.update(chunk)
#             except (FileNotFoundError, PermissionError) as e:
#                 logger.error(f"Error calculating checksum for {file_path}: {e}")
#                 blink_event.set()
#                 blink_thread.join()
#                 time.sleep(delay)
#                 continue
#             finally:
#                 blink_event.set()
#                 blink_thread.join()
#             return hash_obj.hexdigest()
#         except Exception as e:
#             logger.error(f"Unexpected error calculating checksum for {file_path} on attempt {attempt}: {e}")
#             time.sleep(delay)
#     return None

# def rsync_copy(source, destination, file_size, file_number, file_count, retries=3, delay=5):
#     """Copy files using rsync with progress reporting and retry logic."""
#     for attempt in range(1, retries + 1):
#         try:
#             print(f"Running rsync copy (Attempt {attempt})...")
#             process = subprocess.Popen(
#                 ['rsync', '-a', '--info=progress2', source, destination],
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 text=True
#             )
#             transferred = 0
#             last_percent = 0
#             overall_progress = 0
#             while True:
#                 output = process.stdout.readline()
#                 if output == '' and process.poll() is not None:
#                     break
#                 if output:
#                     sys.stdout.write(output)
#                     sys.stdout.flush()
#                     match = re.search(r'(\d+)%', output)
#                     if match:
#                         percent = int(match.group(1))
#                         if percent - last_percent >= 10:
#                             last_percent = update_lcd_progress(file_number, file_count, percent, last_percent)
#                     match = re.search(r'(\d+) bytes/sec', output)
#                     if match:
#                         bytes_transferred = int(match.group(1))
#                         transferred += bytes_transferred
#                         overall_progress = int((transferred / file_size) * 100)
#                         set_led_bar_graph(overall_progress)
#             stderr_output = process.stderr.read()
#             if stderr_output:
#                 logger.error(stderr_output.strip())
#             if process.returncode == 0:
#                 return True, stderr_output
#         except subprocess.CalledProcessError as e:
#             logger.error(f"Error during rsync: {e}")
#         logger.warning(f"Attempt {attempt} failed, retrying after {delay} seconds...")
#         time.sleep(delay)
#     return False, stderr_output

# def update_lcd_progress(file_number, file_count, progress, last_progress=0):
#     """Update the LCD display with the file queue counter and progress bar."""
#     if abs(progress - last_progress) >= 10:  # Update only if progress changes by 10% or more
#         logger.debug("Updating LCD progress...")
#         lcd_progress = int(progress / 10)
#         progress_bar = '#' * lcd_progress + ' ' * (10 - lcd_progress)
#         lcd1602.write(0, 1, f"{file_number}/{file_count} {progress_bar}")
#         return progress
#     return last_progress

# def copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count, retries=3, delay=5):
#     """Copy a file with retry logic and checksum verification."""
#     try:
#         for attempt in range(1, retries + 1):
#             logger.info(f"Attempt {attempt} to copy {src_path} to {dst_path}")
#             try:
#                 file_size = os.path.getsize(src_path)
#             except FileNotFoundError:
#                 logger.error(f"Source file {src_path} not found.")
#                 break
#             except Exception as e:
#                 logger.error(f"Unexpected error getting file size: {e}")
#                 break

#             success, stderr = rsync_copy(src_path, dst_path, file_size, file_number, file_count, retries, delay)

#             if success:
#                 for checksum_attempt in range(1, retries + 1):
#                     try:
#                         logger.info(f"Running calculate_checksum for source (Attempt {checksum_attempt})")
#                         GPIO.output(LED1_PIN, GPIO.LOW)
#                         src_checksum = calculate_checksum(src_path, CHECKSUM_LED_PIN, blink_speed=0.1)
#                         if not src_checksum:
#                             logger.warning(f"Checksum calculation failed for source {src_path} on attempt {checksum_attempt}")
#                             time.sleep(delay)
#                             continue

#                         logger.info(f"Running calculate_checksum for destination (Attempt {checksum_attempt})")
#                         GPIO.output(LED1_PIN, GPIO.LOW)
#                         dst_checksum = calculate_checksum(dst_path, CHECKSUM_LED_PIN, blink_speed=0.05)
#                         if not dst_checksum:
#                             logger.warning(f"Checksum calculation failed for destination {dst_path} on attempt {checksum_attempt}")
#                             time.sleep(delay)
#                             continue

#                         GPIO.output(LED1_PIN, GPIO.HIGH)
#                         if src_checksum == dst_checksum:
#                             logger.info(f"Successfully copied {src_path} to {dst_path} with matching checksums.")
#                             return True
#                         else:
#                             logger.warning(f"Checksum mismatch for {src_path} on attempt {checksum_attempt}")
#                             time.sleep(delay)
#                     except Exception as e:
#                         logger.error(f"Unexpected error during checksum calculation: {e}")
#                         break
#             else:
#                 logger.warning(f"Attempt {attempt} failed with error: {stderr}")

#             time.sleep(delay)

#         # After retries are exhausted, activate error LED
#         logger.error(f"Failed to copy {src_path} to {dst_path} after {retries} attempts")
#         GPIO.output(LED2_PIN, GPIO.HIGH)  # Make sure to activate the correct error LED pin
#         lcd1602.clear()
#         lcd1602.write(0, 0, "ERROR IN TRANSIT")
#         lcd1602.write(0, 1, f"{file_number}/{file_count}")
#         return False

#     except Exception as e:
#         # General exception handling to catch anything unexpected
#         logger.error(f"An unexpected error occurred in copy_file_with_checksum_verification: {e}")
#         GPIO.output(LED2_PIN, GPIO.HIGH)
#         lcd1602.clear()
#         lcd1602.write(0, 0, "CRITICAL ERROR")
#         lcd1602.write(0, 1, "Check Log")
#         return False

# def shorten_filename(filename, max_length=16):
#     """Shorten the filename to fit within the max length for the LCD display."""
#     if len(filename) <= max_length:
#         return filename
#     part_length = (max_length - 3) // 2
#     return filename[:part_length] + "..." + filename[-part_length:]


# def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file, stop_event, blink_thread):
#     """Copy files from the SD card to the dump drive, logging transfer details."""
#     print("Running copy_sd_to_dump")
#     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#     target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
#     failures = []

#     logger.info(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

#     # Initialize the MHL file
#     mhl_filename, tree, hashes = initialize_mhl_file(timestamp, target_dir)

#     file_count, total_size = rsync_dry_run(sd_mountpoint, target_dir)
#     logger.info(f"Number of files to transfer: {file_count}, Total size: {total_size} bytes")

#     if not has_enough_space(dump_drive_mountpoint, total_size):
#         logger.error(f"Not enough space on {dump_drive_mountpoint}. Required: {total_size} bytes")
        
#         # Stop LED1 blinking
#         stop_event.set()
#         blink_thread.join()

#         # Blink LED2 and update LCD display
#         lcd1602.clear()
#         lcd1602.write(0, 0, "ERROR: No Space")
#         lcd1602.write(0, 1, "Remove Drives")
        
#         blink_event = Event()
#         blink_thread_error = Thread(target=blink_led, args=(LED2_PIN, blink_event, 0.5))
#         blink_thread_error.start()

#         # Unmount the drive
#         unmount_drive(dump_drive_mountpoint)
#         unmount_drive(sd_mountpoint)

#         # Wait for drive removal
#         wait_for_drive_removal(dump_drive_mountpoint)
        
#         # # Stop the blinking LED2 and keep the error state
#         # blink_event.set()
#         # blink_thread_error.join()
        
#         # Keep the system in this state until restarted
#         while True:
#             time.sleep(1)

#     file_number = 1
#     overall_progress = 0

#     with open(log_file, 'a') as log:
#         for root, _, files in os.walk(sd_mountpoint):
#             for file in files:
#                 src_path = os.path.join(root, file)
#                 rel_path = os.path.relpath(src_path, sd_mountpoint)
#                 dst_path = os.path.join(target_dir, rel_path)

#                 os.makedirs(os.path.dirname(dst_path), exist_ok=True)

#                 if not os.path.exists(src_path):
#                     logger.warning(f"Source file {src_path} not found. Skipping...")
#                     failures.append(src_path)
#                     continue

#                 short_file = shorten_filename(file, 16)
#                 lcd1602.clear()
#                 lcd1602.write(0, 0, short_file)
#                 lcd1602.write(0, 1, f"{file_number}/{file_count}")

#                 progress = (file_number / file_count) * 100
#                 set_led_bar_graph(overall_progress)  # Set overall progress on LED
#                 overall_progress = update_lcd_progress(file_number, file_count, 0)  # Initialize progress bar

#                 logger.info(f"Copying {src_path} to {dst_path}")
#                 if not copy_file_with_checksum_verification(src_path, dst_path, file_number, file_count):
#                     failures.append(src_path)
#                     log.write(f"Failed to copy {src_path} to {dst_path} after multiple attempts\n")
#                 else:
#                     log.write(f"Source: {src_path} copied successfully to Destination: {dst_path}\n")
#                     log.flush()

#                     # Add file to MHL
#                     src_checksum = calculate_checksum(src_path, CHECKSUM_LED_PIN, blink_speed=0.1)
#                     if src_checksum:
#                         add_file_to_mhl(mhl_filename, tree, hashes, dst_path, src_checksum, os.path.getsize(src_path))

#                 file_number += 1
#                 overall_progress = (file_number / file_count) * 100
#                 set_led_bar_graph(overall_progress)  # Update overall progress on LED

#     if failures:
#         logger.error("The following files failed to copy:")
#         for failure in failures:
#             logger.error(failure)
#         GPIO.output(LED2_PIN, GPIO.HIGH)
#         return False
#     else:
#         logger.info("All files copied successfully.")
#         return True
    
# def unmount_drive(drive_mountpoint):
#     """Unmount the drive specified by its mount point."""
#     try:
#         print("Unmounting drive...")
#         if platform.system() == 'Linux':
#             subprocess.run(['umount', drive_mountpoint], check=True)
#         elif platform.system() == 'Darwin':  # macOS
#             subprocess.run(['diskutil', 'unmount', drive_mountpoint], check=True)
#         elif platform.system() == 'Windows':
#             subprocess.run(['mountvol', drive_mountpoint, '/d'], check=True)
#         logger.info(f"Unmounted {drive_mountpoint}")
#     except subprocess.CalledProcessError as e:
#         logger.error(f"Error unmounting {drive_mountpoint}: {e}")
#         GPIO.output(LED2_PIN, GPIO.HIGH)

# def wait_for_drive_removal(mountpoint):
#     """Wait until the drive is removed."""
#     while os.path.ismount(mountpoint):
#         logger.debug(f"Waiting for {mountpoint} to be removed...")
#         time.sleep(5)  # Increased interval to 5 seconds

# def blink_led(led_pin, stop_event, blink_speed=0.3):
#     """Blink an LED until the stop_event is set."""
#     while not stop_event.is_set():
#         GPIO.output(led_pin, GPIO.HIGH)
#         time.sleep(blink_speed)
#         GPIO.output(led_pin, GPIO.LOW)
#         time.sleep(blink_speed)

# def set_led_bar_graph(progress):
#     """Set the LED bar graph based on the overall progress value."""
#     num_leds_on = int((progress / 100.0) * len(LED_BAR_PINS))
#     for i, pin in enumerate(LED_BAR_PINS):
#         GPIO.output(pin, GPIO.HIGH if i < num_leds_on else GPIO.LOW)

# def main():
#     """Main function to monitor and copy files from new storage devices."""
#     lcd1602.clear()
#     lcd1602.write(0, 0, "Storage Missing")

#     while not os.path.ismount(DUMP_DRIVE_MOUNTPOINT):
#         time.sleep(2)

#     lcd1602.clear()
#     lcd1602.write(0, 0, "Storage Detected")
#     lcd1602.write(0, 1, "Load Media")

#     GPIO.output(LED3_PIN, GPIO.LOW)

#     try:
#         while True:
#             initial_drives = get_mounted_drives_lsblk()
#             logger.debug(f"Initial mounted drives: {initial_drives}")

#             logger.info("Waiting for SD card to be plugged in...")
#             sd_mountpoint = detect_new_drive(initial_drives)
#             if sd_mountpoint:
#                 logger.info(f"SD card detected at {sd_mountpoint}.")
#                 logger.debug(f"Updated state of drives: {get_mounted_drives_lsblk()}")

#                 GPIO.output(LED3_PIN, GPIO.LOW)
#                 GPIO.output(LED2_PIN, GPIO.LOW)

#                 timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#                 target_dir = create_timestamped_dir(DUMP_DRIVE_MOUNTPOINT, timestamp)
#                 log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")

#                 stop_event = Event()
#                 blink_thread = Thread(target=blink_led, args=(LED1_PIN, stop_event))
#                 blink_thread.start()

#                 try:
#                     success = copy_sd_to_dump(sd_mountpoint, DUMP_DRIVE_MOUNTPOINT, log_file, stop_event, blink_thread)
#                     if success:
#                         GPIO.output(LED3_PIN, GPIO.HIGH)
#                         GPIO.output(LED1_PIN, GPIO.LOW)
#                         GPIO.output(CHECKSUM_LED_PIN, GPIO.LOW)
#                         lcd1602.clear()
#                         lcd1602.write(0, 0, "Transfer Done")
#                         lcd1602.write(0, 1, "Load New Media")
#                 finally:
#                     stop_event.set()
#                     blink_thread.join()

#                 unmount_drive(sd_mountpoint)
#                 wait_for_drive_removal(sd_mountpoint)
#                 logger.info("Monitoring for new storage devices...")
#     except KeyboardInterrupt:
#         logger.info("KeyboardInterrupt received. Cleaning up and exiting.")
#         GPIO.output(LED2_PIN, GPIO.LOW)
#     except Exception as e:
#         logger.error(f"An unexpected error occurred: {e}")
#         GPIO.output(LED2_PIN, GPIO.HIGH)
#     finally:
#         GPIO.cleanup()
#         lcd1602.clear()
#         lcd1602.set_backlight(False)
#         # Check if the lcd1602 object has a cleanup method before calling it
#         if hasattr(lcd1602, 'cleanup'):
#             lcd1602.cleanup()

# if __name__ == "__main__":
#     main()
