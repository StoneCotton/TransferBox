import subprocess
import os
import time
import platform
import logging

logger = logging.getLogger(__name__)

class DriveDetection:
    def __init__(self):
        self.platform = platform.system()

    def get_mounted_drives_lsblk(self):
        try:
            result = subprocess.run(['lsblk', '-o', 'MOUNTPOINT', '-nr'], stdout=subprocess.PIPE, text=True, check=True)
            return [drive for drive in result.stdout.strip().split('\n') if drive]
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running lsblk: {e}")
            return []

    def detect_new_drive(self, initial_drives):
        while True:
            time.sleep(2)
            current_drives = self.get_mounted_drives_lsblk()
            logger.debug(f"Current mounted drives: {current_drives}")
            new_drives = set(current_drives) - set(initial_drives)
            for drive in new_drives:
                if f"/media/{os.getenv('USER')}" in drive or "/mnt" in drive:
                    logger.info(f"New drive detected: {drive}")
                    return drive

    def wait_for_drive_removal(self, mountpoint):
        while os.path.ismount(mountpoint):
            logger.debug(f"Waiting for {mountpoint} to be removed...")
            time.sleep(5)

    def is_linux(self):
        return self.platform == 'Linux'

    def is_windows(self):
        return self.platform == 'Windows'

    def is_macos(self):
        return self.platform == 'Darwin'