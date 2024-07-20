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
            src_checksum = calculate_checksum(src_path)
            dst_checksum = calculate_checksum(dst_path)
            if src_checksum and dst_checksum and src_checksum == dst_checksum:
                logger.info(f"Successfully copied {src_path} to {dst_path} with matching checksums.")
                return True
            else:
                logger.warning(f"Checksum mismatch for {src_path} on attempt {attempt}")
                time.sleep(delay)
    return False

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
        return

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

                logger.info(f"Copying {src_path} to {dst_path}")
                if not copy_file_with_retry(src_path, dst_path):
                    failures.append(src_path)
                    log.write(f"Failed to copy {src_path} to {dst_path} after multiple attempts\n")
                else:
                    src_checksum = calculate_checksum(src_path)
                    dst_checksum = calculate_checksum(dst_path)
                    log.write(f"Source: {src_path}, Checksum: {src_checksum}\n")
                    log.write(f"Destination: {dst_path}, Checksum: {dst_checksum}\n")
                    log.flush()  # Ensure immediate write to file

    if failures:
        logger.error("The following files failed to copy:")
        for failure in failures:
            logger.error(failure)
    else:
        logger.info("All files copied successfully.")

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

def wait_for_drive_removal(mountpoint):
    """Wait until the drive is removed."""
    while os.path.ismount(mountpoint):
        logger.debug(f"Waiting for {mountpoint} to be removed...")
        time.sleep(2)

def main():
    """Main function to monitor and copy files from new storage devices."""
    dump_drive_mountpoint = DUMP_DRIVE_MOUNTPOINT
    if not os.path.ismount(dump_drive_mountpoint):
        logger.error(f"{DUMP_DRIVE_MOUNTPOINT} not found.")
        return

    while True:
        initial_drives = get_mounted_drives_lsblk()
        logger.debug(f"Initial mounted drives: {initial_drives}")

        logger.info("Waiting for SD card to be plugged in...")
        sd_mountpoint = detect_new_drive(initial_drives)
        if sd_mountpoint:
            logger.info(f"SD card detected at {sd_mountpoint}.")
            logger.debug(f"Updated state of drives: {get_mounted_drives_lsblk()}")

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
            log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")
            copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file)

            unmount_drive(sd_mountpoint)
            wait_for_drive_removal(sd_mountpoint)
            logger.info("Monitoring for new storage devices...")

if __name__ == "__main__":
    main()
