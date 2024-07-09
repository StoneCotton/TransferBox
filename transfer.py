import os
import time
import subprocess
import psutil
import xxhash
from tqdm import tqdm
from datetime import datetime
import platform

# Determine the appropriate mount point for DUMP_DRIVE based on the operating system
if platform.system() == 'Linux':
    DUMP_DRIVE_MOUNTPOINT = '/media/DUMP_DRIVE'
elif platform.system() == 'Darwin':  # macOS
    DUMP_DRIVE_MOUNTPOINT = '/Volumes/DUMP_DRIVE'
elif platform.system() == 'Windows':
    DUMP_DRIVE_MOUNTPOINT = 'D:\\DUMP_DRIVE'
else:
    raise NotImplementedError("This script only supports Linux, macOS, and Windows.")

def list_all_drives():
    """List all drives based on the operating system."""
    if platform.system() == 'Linux':
        result = subprocess.run(['lsblk', '-o', 'NAME,MOUNTPOINT'], stdout=subprocess.PIPE, text=True)
    elif platform.system() == 'Darwin':  # macOS
        result = subprocess.run(['diskutil', 'list'], stdout=subprocess.PIPE, text=True)
    elif platform.system() == 'Windows':
        result = subprocess.run(['wmic', 'logicaldisk', 'get', 'name'], stdout=subprocess.PIPE, text=True)
    return result.stdout

def get_mounted_drives():
    """Get a list of currently mounted drives using psutil."""
    drives = psutil.disk_partitions()
    if platform.system() == 'Linux':
        mounted_drives = [drive.mountpoint for drive in drives if 'rw' in drive.opts and (drive.mountpoint.startswith('/media') or drive.mountpoint.startswith('/mnt'))]
    elif platform.system() == 'Darwin':  # macOS
        mounted_drives = [drive.mountpoint for drive in drives if 'rw' in drive.opts and 'local' in drive.opts]
    elif platform.system() == 'Windows':
        mounted_drives = [drive.mountpoint for drive in drives if 'rw' in drive.opts]
    return mounted_drives

def detect_new_drive(initial_drives):
    """Detect any new drive by comparing initial drives with the current state."""
    while True:
        time.sleep(5)  # Check every 5 seconds
        current_drives = get_mounted_drives()
        new_drives = set(current_drives) - set(initial_drives)
        if new_drives:
            for drive in new_drives:
                if (platform.system() == 'Linux' and ("/media" in drive or "/mnt" in drive)) or \
                   (platform.system() == 'Darwin' and "/Volumes" in drive) or \
                   (platform.system() == 'Windows' and drive.startswith('D:\\')):
                    return drive

def create_timestamped_dir(dump_drive_mountpoint, timestamp):
    """Create a directory with a timestamp in the dump drive mount point."""
    target_dir = os.path.join(dump_drive_mountpoint, timestamp)
    os.makedirs(target_dir, exist_ok=True)  # Create the directory if it doesn't exist
    return target_dir

def copy_with_checksum(source, destination, chunk_size=32*1024*1024, retries=3):
    """Copy a file with checksum verification and retry logic."""
    source_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(source, 'rb') as src, open(destination, 'wb') as dst:
            src_hash = xxhash.xxh64()
            dst_hash = xxhash.xxh64()

            file_size = os.path.getsize(source)
            with tqdm(total=file_size, unit='B', unit_scale=True, desc=os.path.basename(source)) as pbar:
                while chunk := src.read(chunk_size):
                    dst.write(chunk)
                    src_hash.update(chunk)
                    dst_hash.update(chunk)
                    pbar.update(len(chunk))

            if src_hash.hexdigest() != dst_hash.hexdigest():
                if retries > 0:
                    print(f"Checksum mismatch for {source}. Retrying...")
                    time.sleep(10)  # Wait for 10 seconds before retrying
                    return copy_with_checksum(source, destination, chunk_size, retries-1)
                else:
                    print(f"Failed to copy {source} after {retries} retries.")
                    return False, None, None, None, None

        source_checksum = src_hash.hexdigest()
        dest_checksum = dst_hash.hexdigest()
        dest_end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return True, source_checksum, source_start_time, dest_checksum, dest_end_time
    except IOError as e:
        if retries > 0:
            print(f"IOError while copying {source} to {destination}: {e}. Retrying...")
            time.sleep(10)  # Wait for 10 seconds before retrying
            return copy_with_checksum(source, destination, chunk_size, retries-1)
        else:
            print(f"Failed to copy {source} after {retries} retries due to IOError: {e}.")
            return False, None, None, None, None
    except Exception as e:
        print(f"Unexpected error while copying {source} to {destination}: {e}")
        return False, None, None, None, None

def copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file):
    """Copy files from the SD card to the dump drive, logging transfer details."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
    failures = []
    
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

                success, src_checksum, src_start_time, dst_checksum, dst_end_time = copy_with_checksum(src_path, dst_path)
                if not success:
                    failures.append(src_path)
                else:
                    # Log the transfer details
                    log.write(f"---\n")
                    log.write(f"Source Path: {src_path}\n")
                    log.write(f"Source Checksum: {src_checksum}\n")
                    log.write(f"Source Transfer Start: {src_start_time}\n")
                    log.write(f"Destination Path: {dst_path}\n")
                    log.write(f"Destination Checksum: {dst_checksum}\n")
                    log.write(f"Destination Transfer Finish: {dst_end_time}\n")
                    log.write(f"---\n")
                    log.flush()  # Flush to ensure immediate write to file
    
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

def main():
    """Main function to monitor and copy files from new storage devices."""
    dump_drive_mountpoint = DUMP_DRIVE_MOUNTPOINT
    if not os.path.ismount(dump_drive_mountpoint):
        print("DUMP_DRIVE not found.")
        return

    while True:
        initial_drives = get_mounted_drives()
        print("Initial mounted drives:", initial_drives)

        print("Waiting for SD card to be plugged in...")
        sd_mountpoint = detect_new_drive(initial_drives)
        print(f"SD card detected at {sd_mountpoint}.")
        print("Updated state of drives:\n", list_all_drives())

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_dir = create_timestamped_dir(dump_drive_mountpoint, timestamp)
        log_file = os.path.join(target_dir, f"transfer_log_{timestamp}.log")
        copy_sd_to_dump(sd_mountpoint, dump_drive_mountpoint, log_file)

        unmount_drive(sd_mountpoint)
        print("Monitoring for new storage devices...")

if __name__ == "__main__":
    main()
