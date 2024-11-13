# src/platform/raspberry_pi/menu.py

import time
import logging
import os
import subprocess
import shutil
from threading import Lock
from pathlib import Path

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface
from .led_control import setup_leds, set_led_state, LEDControl
from .power_management import power_manager

logger = logging.getLogger(__name__)

class MenuManager:
    """Manages the utility menu system for Raspberry Pi"""
    
    def __init__(self, display: DisplayInterface, storage: StorageInterface):
        self.display = display
        self.storage = storage
        self.option_lock = Lock()
        self.menu_active = False
        self.current_menu_index = 0
        self.processing_option = False
        self.menu_options = [
            "List Drives", "Format Drive", "Unmount Drives", "Test LEDs", 
            "Test Screen", "Shutdown", "Reboot", "Available Space", 
            "Version Info", "Update Firmware", "Reset to Factory"
        ]

    def display_menu(self):
        """Display the current menu option"""
        self.processing_option = False
        self.display.clear()
        self.display.show_status("UTIL MENU")
        self.display.show_status(self.menu_options[self.current_menu_index], line=1)

    def navigate_up(self):
        """Navigate to previous menu option"""
        if self.processing_option:
            return
        logger.debug("Up button pressed in menu")
        self.current_menu_index = (self.current_menu_index - 1) % len(self.menu_options)
        self.display_menu()

    def navigate_down(self):
        """Navigate to next menu option"""
        if self.processing_option:
            return
        logger.debug("Down button pressed in menu")
        self.current_menu_index = (self.current_menu_index + 1) % len(self.menu_options)
        self.display_menu()

    def select_option(self, ok_button, back_button, up_button, down_button, on_complete, clear_handlers, assign_handlers):
        """Handle menu option selection"""
        if not self.option_lock.acquire(blocking=False):
            return

        try:
            if self.processing_option:
                return

            self.processing_option = True
            selected_option = self.menu_options[self.current_menu_index]
            logger.info(f"Selected option: {selected_option}")
            
            self.display.clear()
            self.display.show_status(selected_option)
            self.display.show_status("Running...", line=1)

            option_methods = {
                "List Drives": self._list_drives,
                "Format Drive": self._format_drive,
                "Test LEDs": self._test_leds,
                "Test Screen": self._test_screen,
                "Shutdown": self._shutdown_system,
                "Reboot": self._reboot_system,
                "Version Info": self._version_number,
                "Available Space": self._check_available_space
            }

            if selected_option in option_methods:
                option_methods[selected_option](ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)

            while ok_button.is_pressed:
                time.sleep(0.1)

        finally:
            self.processing_option = False
            self.option_lock.release()
            on_complete()

    def _list_drives(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Display list of mounted drives"""
        drives = self.storage.get_available_drives()
        for drive in drives:
            self.display.clear()
            self.display.show_status("Mounted Drives:")
            self.display.show_status(drive.name, line=1)
            time.sleep(2)

def _format_drive(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
    """Format the dump drive"""
    dump_drive = self.storage.get_dump_drive()
    if not dump_drive:
        self.display.show_status("DUMP_DRIVE not")
        self.display.show_status("found", line=1)
        logger.error("DUMP_DRIVE mountpoint not found")
        time.sleep(2)
        return

    if not dump_drive.is_mount():
        self.display.show_status("DUMP_DRIVE not")
        self.display.show_status("mounted", line=1)
        logger.error(f"DUMP_DRIVE not mounted at {dump_drive}")
        time.sleep(2)
        return

    self.display.show_status("Hold OK for 3s")
    self.display.show_status("to format drive", line=1)

    start_time = time.time()
    while ok_button.is_pressed:
        if time.time() - start_time >= 3:
            break
        time.sleep(0.1)

    if time.time() - start_time < 3:
        self.display.show_status("Format cancelled")
        time.sleep(2)
        return

    self.display.show_status("Formatting...")
    self.display.show_status("Please wait...", line=1)

    try:
        # Use findmnt to get the device name
        findmnt_output = subprocess.check_output(
            ['findmnt', '-n', '-o', 'SOURCE', str(dump_drive)], 
            text=True
        ).strip()
        logger.info(f"findmnt output: {findmnt_output}")

        if not findmnt_output:
            raise ValueError(f"Couldn't find device for {dump_drive} using findmnt")

        device = findmnt_output
        logger.info(f"Found device {device} for {dump_drive}")

        # Unmount the drive before formatting
        subprocess.run(['sudo', 'umount', str(dump_drive)], check=True)
        logger.info(f"Unmounted {dump_drive}")

        # Double-check if the device still exists after unmounting
        blkid_output = subprocess.check_output(['sudo', 'blkid', '-o', 'device'], text=True)
        logger.info(f"blkid output: {blkid_output}")
        if device not in blkid_output:
            raise ValueError(f"Device {device} not found after unmounting")

        # Format the drive as NTFS
        subprocess.run(['sudo', 'ntfslabel', '--force', device, 'DUMP_DRIVE'], check=True)
        subprocess.run(['sudo', 'mkfs.ntfs', '-f', '-L', 'DUMP_DRIVE', device], check=True)
        logger.info(f"Formatted {device} as NTFS")
        
        # Reload system services
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

        # Create the mount point if it doesn't exist
        dump_drive.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created mount point: {dump_drive}")

        # Mount the newly formatted drive
        current_label = subprocess.check_output(
            ['sudo', 'blkid', '-s', 'LABEL', '-o', 'value', device], 
            text=True
        ).strip()
        
        if current_label != 'DUMP_DRIVE':
            subprocess.run(['sudo', 'ntfslabel', device, 'DUMP_DRIVE'], check=True)
            
        subprocess.run(['sudo', 'mount', '-t', 'ntfs', device, str(dump_drive)], check=True)
        logger.info(f"Mounted {device} to {dump_drive}")

        # Verify that the drive is mounted
        if dump_drive.is_mount():
            self.display.show_status("Format complete")
            self.display.show_status("DUMP_DRIVE ready", line=1)
            logger.info("DUMP_DRIVE formatted and mounted successfully")
        else:
            raise RuntimeError(f"Failed to mount {device} to {dump_drive}")

        # Change ownership of the mount point to the current user
        current_user = os.environ.get('SUDO_USER', os.environ.get('USER'))
        subprocess.run(
            ['sudo', 'chown', f'{current_user}:{current_user}', str(dump_drive)], 
            check=True
        )
        logger.info(f"Changed ownership of {dump_drive} to {current_user}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Error formatting or mounting DUMP_DRIVE: {e}")
        self.display.show_status("Format failed")
        self.display.show_status("Check logs", line=1)
    except ValueError as e:
        logger.error(f"Error finding DUMP_DRIVE: {e}")
        self.display.show_status("Error: Drive not")
        self.display.show_status("found", line=1)
    except RuntimeError as e:
        logger.error(str(e))
        self.display.show_status("Mount failed")
        self.display.show_status("Check logs", line=1)
    except Exception as e:
        logger.error(f"Unexpected error during formatting: {e}", exc_info=True)
        self.display.show_status("Unexpected error")
        self.display.show_status("Check logs", line=1)

    time.sleep(3)

    def _test_screen(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Test LCD screen functionality"""
        self.display.show_status("Testing Screen")
        time.sleep(2)
        self.display.clear()
        time.sleep(2)

        # Test upper case alphabet on both lines
        for i in range(1, 27):  # 26 letters in the alphabet
            self.display.clear()
            if i <= 16:
                self.display.show_status("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:i])
            else:
                self.display.show_status("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:16])
                self.display.show_status("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[16:i], line=1)
            time.sleep(0.1)

        time.sleep(2)
        self.display.clear()
        time.sleep(2)

        # Test lower case alphabet on both lines
        for i in range(1, 27):
            self.display.clear()
            if i <= 16:
                self.display.show_status("abcdefghijklmnopqrstuvwxyz"[:i])
            else:
                self.display.show_status("abcdefghijklmnopqrstuvwxyz"[:16])
                self.display.show_status("abcdefghijklmnopqrstuvwxyz"[16:i], line=1)
            time.sleep(0.1)

        time.sleep(2)
        self.display.clear()
        time.sleep(2)

        # Test digits and special characters on both lines
        for i in range(1, 21):  # 10 digits plus 10 special characters
            self.display.clear()
            if i <= 10:
                self.display.show_status("0123456789"[:i])
            else:
                self.display.show_status("0123456789")
                self.display.show_status(".,:;!?/()@#$%^&*"[0:i-10], line=1)
            time.sleep(0.1)

        time.sleep(2)
        self.display.clear()
        time.sleep(2)

        # Test special character pattern on both lines
        for i in range(1, 33):  # 32 '#' characters
            self.display.clear()
            if i <= 16:
                self.display.show_status("#" * i)
            else:
                self.display.show_status("#" * 16)
                self.display.show_status("#" * (i-16), line=1)
            time.sleep(0.1)

        time.sleep(2)
        self.display.clear()
        self.display.show_status("Screen Test Done")
        time.sleep(2)

    def _shutdown_system(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Initiate system shutdown"""
        logger.info("Shutting down system")
        self.display.show_status("Shutting Down...")
        self.display.show_status("Wait 60 Seconds.", line=1)
        time.sleep(5)
        power_manager.safe_shutdown()

    def _reboot_system(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Initiate system reboot"""
        logger.info("Rebooting system")
        self.display.show_status("Rebooting...")
        self.display.show_status("Wait 60 Seconds.", line=1)
        time.sleep(5)
        power_manager.safe_reboot()

    def _version_number(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Display version information"""
        logger.info("Version Number: v0.0.1")
        self.display.show_status("Version Number:")
        self.display.show_status("v0.0.1 240820", line=1)
        time.sleep(5)

    def _check_available_space(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        """Check and display available space"""
        dump_drive = self.storage.get_dump_drive()
        if not dump_drive:
            self.display.show_error("Drive not found")
            return

        try:
            drive_info = self.storage.get_drive_info(dump_drive)
            free_space = drive_info['free']
            
            # Convert to appropriate unit
            if free_space < 999 * 1024 * 1024:  # Less than 999 MB
                free_space = free_space / (1024 * 1024)
                unit = "MB"
            elif free_space < 999 * 1024 * 1024 * 1024:  # Less than 999 GB
                free_space = free_space / (1024 * 1024 * 1024)
                unit = "GB"
            else:  # 1 TB or more
                free_space = free_space / (1024 * 1024 * 1024 * 1024)
                unit = "TB"
            
            free_space = round(free_space, 2)
            self.display.show_status("Available Space:")
            self.display.show_status(f"{free_space} {unit}", line=1)
            
        except Exception as e:
            logger.error(f"Error checking space: {e}")
            self.display.show_error("Error checking space")
    
