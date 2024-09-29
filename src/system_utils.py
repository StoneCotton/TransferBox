import os
import platform
import subprocess
import logging
import shutil
from src.led_control import setup_leds, set_led_state, LEDControl

logger = logging.getLogger(__name__)

def get_dump_drive_mountpoint():
    username = os.getenv("USER")
    if platform.system() == 'Linux':
        possible_mountpoints = [f'/media/{username}/DUMP_DRIVE', f'/media/{username}/DUMP_DRIVE1']
        for mountpoint in possible_mountpoints:
            if os.path.ismount(mountpoint):
                return mountpoint
        
        # If not found in the expected locations, search all mounted drives
        try:
            mount_output = subprocess.check_output(['mount'], text=True)
            for line in mount_output.split('\n'):
                if 'DUMP_DRIVE' in line:
                    return line.split()[2]  # The mount point is typically the third item
        except subprocess.CalledProcessError:
            pass
        
        return None  # Return None if no matching mountpoint is found
    else:
        raise NotImplementedError("This script only supports Linux.")

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
        set_led_state(LEDControl.ERROR_LED, True)  # Turn on the error LED if unmounting fails

def has_enough_space(dump_drive_mountpoint, required_size):
    """Check if there is enough space on the dump drive."""
    print("Checking available space on dump drive...")
    _, _, free = shutil.disk_usage(dump_drive_mountpoint)
    return free >= required_size
