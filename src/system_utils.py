import os
import platform
import subprocess
import logging
import shutil
from src.led_control import setup_leds, blink_led, LED2_PIN

logger = logging.getLogger(__name__)

def get_dump_drive_mountpoint():
    username = os.getenv("USER")
    if platform.system() == 'Linux':
        return f'/media/{username}/DUMP_DRIVE'
    elif platform.system() == 'Darwin':  # macOS
        return '/Volumes/DUMP_DRIVE'
    elif platform.system() == 'Windows':
        return 'D:\\DUMP_DRIVE'
    else:
        raise NotImplementedError("This script only supports Linux, macOS, and Windows.")

def unmount_drive(drive_mountpoint):
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
        LED2_PIN.on()  # Turn on the error LED if unmounting fails

def has_enough_space(dump_drive_mountpoint, required_size):
    """Check if there is enough space on the dump drive."""
    print("Checking available space on dump drive...")
    _, _, free = shutil.disk_usage(dump_drive_mountpoint)
    return free >= required_size
