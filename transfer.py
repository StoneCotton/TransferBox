import os
import time
import subprocess
import xxhash
from datetime import datetime
import platform

# Determine the appropriate mount point for DUMP_DRIVE based on the operating system and username
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
    result = subprocess.run(['lsblk', '-o', 'MOUNTPOINT', '-nr'], stdout=subprocess.PIPE, text=True)
    mounted_drives = result.stdout.strip().split('\n')
    return [drive for drive in mounted_drives if drive]

def detect_new_drive(initial_drives):
    """Detect any new drive by comparing initial drives with the current state."""
    while True:
        time.sleep(2)  # Check every 2 seconds
        current_drives = get_mounted_drives_lsblk()
        print(f"Current mounted drives: {current_drives}")
        new_drives = set(current_drives) - set(initial_drives)
        if new_drives:
            for drive in new_drives:
                if f"/media/{username}" in drive or "/mnt" in drive:
                    print(f"New drive detected: {drive}")
                    return drive

def create_timestamped_dir(dump_drive_mountpoint, timestamp):
    """Create a directory with a timestamp in the dump drive mount point."""
    target_dir = os.path.join(dump_drive_mountpoint, timestamp)
    os.makedirs(target_dir, exist_ok=True)  # Create the directory if it doesn't exist
    return target_dir

def calculate_checksum(filepath):
    """Calculate and return the checksum of the file."""
    hash_obj = xxhash.xxh64()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def rsync_copy(source, destination):
    """Copy files using rsync with checksumming and logging."""
    try:
        result = subprocess.run(
            ['rsync', '-a', '--progress', '--checksum', source, destination],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print(result.stdout)  # Output the progress to the console
        return result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return None, str(e)

def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file):
    """Copy files from the SD card to the dump drive, logging transfer details."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []

    print(f"Starting to copy files from {sd_mountpoint} to {dump_drive_mountpoint}")

    with open(log_file, 'a') as log:
        for root, _, files in os.walk(sd_mountpoint):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, sd_mountpoint)
                dst_path = os.path.join(target_dir, rel_path)

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)  # Create destination directory if it doesn't exist

                if not os.path.exists(src_path):
                    print(f"Source file {src_path} not found. Skipping...")
                    failures.append(src_path)
                    continue

                print(f"Copying {src_path} to {dst_path}")
                stdout, stderr = rsync_copy(src_path, dst_path)
                if stderr:
                    failures.append(src_path)
                    log.write(f"Error copying {src_path} to {dst_path}: {stderr}\n")
                else:
                    src_checksum = calculate_checksum(src_path)
                    dst_checksum = calculate_checksum(dst_path)
                    log.write(f"Source: {src_path}, Checksum: {src_checksum}\n")
                    log.write(f"Destination: {dst_path}, Checksum: {dst_checksum}\n")
                    log.write(stdout)
                    log.flush()  # Ensure immediate write to file

    if failures:
        print("The following files failed to copy:")
        for failure in failures:
            print(failure)
    else:
        print("All files copied successfully.")

def unmount_drive(drive_mountpoint):
    """Unmount the drive specified by its mount point."""
    try:
        if platform.system() == 'Linux':
            subprocess.run(['umount', drive_mountpoint], check=True)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['diskutil', 'unmount', drive_mountpoint], check=True)
        elif platform.system() == 'Windows':
            subprocess.run(['mountvol', drive_mountpoint, '/d'], check=True)
        print(f"Unmounted {drive_mountpoint}")
    except subprocess.CalledProcessError as e:
        print(f"Error unmounting {drive_mountpoint}: {e}")

def wait_for_drive_removal(mountpoint):
    """Wait until the drive is removed."""
    while os.path.ismount(mountpoint):
        print(f"Waiting for {mountpoint} to be removed...")
        time.sleep(2)

def main():
    """Main function to monitor and copy files from new storage devices."""
    dump_drive_mountpoint = DUMP_DRIVE_MOUNTPOINT
    if not os.path.ismount(dump_drive_mountpoint):
        print(f"{DUMP_DRIVE_MOUNTPOINT} not found.")
        return

    while True:
        initial_drives = get_mounted_drives_lsblk()
        print("Initial mounted drives:", initial_drives)

        print("Waiting for SD card to be plugged in...")
        sd_mountpoint = detect_new_drive(initial_drives)
        print(f"SD card detected at {sd_mountpoint}.")
        print("Updated state of drives:", get_mounted_drives_lsblk())

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
        log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")
        copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file)

        unmount_drive(sd_mountpoint)
        wait_for_drive_removal(sd_mountpoint)
        print("Monitoring for new storage devices...")

if __name__ == "__main__":
    main()
