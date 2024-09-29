import time
import logging
from threading import Lock
import os
import subprocess
import shutil

from src.lcd_display import lcd_display
from src.drive_detection import DriveDetection
from src.system_utils import unmount_drive, get_dump_drive_mountpoint
from src.led_control import setup_leds, set_led_state, LEDControl
from src.power_management import power_manager

logger = logging.getLogger(__name__)

class MenuManager:
    def __init__(self):
        self.drive_detector = DriveDetection()
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
        self.processing_option = False
        lcd_display.clear()
        lcd_display.write(0, 0, "UTIL MENU")
        lcd_display.write(0, 1, self.menu_options[self.current_menu_index])

    def navigate_up(self):
        if self.processing_option:
            return
        logger.debug("Up button pressed in menu.")
        self.current_menu_index = (self.current_menu_index - 1) % len(self.menu_options)
        self.display_menu()

    def navigate_down(self):
        if self.processing_option:
            return
        logger.debug("Down button pressed in menu.")
        self.current_menu_index = (self.current_menu_index + 1) % len(self.menu_options)
        self.display_menu()

    def select_option(self, ok_button, back_button, up_button, down_button, on_complete, clear_handlers, assign_handlers):
        if not self.option_lock.acquire(blocking=False):
            return

        try:
            if self.processing_option:
                return

            self.processing_option = True
            logger.info(f"OK button pressed, selecting option at index {self.current_menu_index}.")

            selected_option = self.menu_options[self.current_menu_index]
            logger.info(f"Selected option: {selected_option}")
            lcd_display.clear()
            lcd_display.write(0, 0, selected_option)
            lcd_display.write(0, 1, "Running...")

            option_methods = {
                "List Drives": self.list_drives,
                "Format Drive": self.format_drive,
                "Test LEDs": self.test_leds,
                "Test Screen": self.test_screen,
                "Shutdown": self.shutdown_system,
                "Reboot": self.reboot_system,
                "Version Info": self.version_number,
                "Available Space": self.check_available_space
            }

            if selected_option in option_methods:
                option_methods[selected_option](ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers)

            while ok_button.is_pressed:
                logger.debug("Waiting for OK button to be released after action")
                time.sleep(0.1)

            logger.info("OK button released, returning to menu.")
            time.sleep(0.5)

        finally:
            self.processing_option = False
            self.option_lock.release()
            on_complete()

    def handle_option_completion(self, on_complete):
        logger.info("Action completed, waiting for OK button press to confirm.")
        lcd_display.clear()
        on_complete()
        self.display_menu()

    def list_drives(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        drives = self.drive_detector.get_mounted_drives_lsblk()
        for drive in drives:
            drive_name = os.path.basename(drive)
            lcd_display.clear()
            lcd_display.write(0, 0, "Mounted Drives:")
            lcd_display.write(0, 1, drive_name)
            time.sleep(2)
        self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

    def format_drive(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        dump_drive_mountpoint = get_dump_drive_mountpoint()
    
        # Check if a valid mountpoint was found
        if dump_drive_mountpoint is None:
            lcd_display.clear()
            lcd_display.write(0, 0, "DUMP_DRIVE not")
            lcd_display.write(0, 1, "found")
            logger.error("DUMP_DRIVE mountpoint not found")
            time.sleep(2)
            return self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

        # Check if the drive is mounted
        if not os.path.ismount(dump_drive_mountpoint):
            lcd_display.clear()
            lcd_display.write(0, 0, "DUMP_DRIVE not")
            lcd_display.write(0, 1, "mounted")
            logger.error(f"DUMP_DRIVE not mounted at {dump_drive_mountpoint}")
            time.sleep(2)
            return self.handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

        lcd_display.clear()
        lcd_display.write(0, 0, "Hold OK for 3s")
        lcd_display.write(0, 1, "to format drive")

        start_time = time.time()
        while ok_button.is_pressed:
            if time.time() - start_time >= 3:
                break
            time.sleep(0.1)
    
        if time.time() - start_time < 3:
            lcd_display.clear()
            lcd_display.write(0, 0, "Format cancelled")
            time.sleep(2)
            return self.handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

        lcd_display.clear()
        lcd_display.write(0, 0, "Formatting...")
        lcd_display.write(0, 1, "Please wait...")

        try:
            # Use findmnt to get the device name
            findmnt_output = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', dump_drive_mountpoint], text=True).strip()
            logger.info(f"findmnt output: {findmnt_output}")

            if not findmnt_output:
                raise ValueError(f"Couldn't find device for {dump_drive_mountpoint} using findmnt")

            device = findmnt_output

            logger.info(f"Found device {device} for {dump_drive_mountpoint}")

            # Unmount the drive before formatting
            subprocess.run(['sudo', 'umount', dump_drive_mountpoint], check=True)
            logger.info(f"Unmounted {dump_drive_mountpoint}")

            # Double-check if the device still exists after unmounting
            blkid_output = subprocess.check_output(['sudo', 'blkid', '-o', 'device'], text=True)
            logger.info(f"blkid output: {blkid_output}")
            if device not in blkid_output:
                raise ValueError(f"Device {device} not found after unmounting")

            # Format the drive as NTFS
            subprocess.run(['sudo', 'ntfslabel', '--force', device, 'DUMP_DRIVE'], check=True)

            subprocess.run(['sudo', 'mkfs.ntfs', '-f', '-L', 'DUMP_DRIVE', device], check=True)
            logger.info(f"Formatted {device} as NTFS")
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)

            # Create the mount point if it doesn't exist
            subprocess.run(['sudo', 'mkdir', '-p', dump_drive_mountpoint], check=True)
            logger.info(f"Created mount point: {dump_drive_mountpoint}")

            # Mount the newly formatted drive
            current_label = subprocess.check_output(['sudo', 'blkid', '-s', 'LABEL', '-o', 'value', device], text=True).strip()
            if current_label != 'DUMP_DRIVE':
                subprocess.run(['sudo', 'ntfslabel', device, 'DUMP_DRIVE'], check=True)
            subprocess.run(['sudo', 'mount', '-t', 'ntfs', device, dump_drive_mountpoint], check=True)
            logger.info(f"Mounted {device} to {dump_drive_mountpoint}")

            # Verify that the drive is mounted
            if os.path.ismount(dump_drive_mountpoint):
                lcd_display.clear()
                lcd_display.write(0, 0, "Format complete")
                lcd_display.write(0, 1, "DUMP_DRIVE ready")
                logger.info("DUMP_DRIVE formatted and mounted successfully")
            else:
                raise RuntimeError(f"Failed to mount {device} to {dump_drive_mountpoint}")

            # Optionally, change ownership of the mount point to the current user
            current_user = os.environ.get('SUDO_USER', os.environ.get('USER'))
            subprocess.run(['sudo', 'chown', f'{current_user}:{current_user}', dump_drive_mountpoint], check=True)
            logger.info(f"Changed ownership of {dump_drive_mountpoint} to {current_user}")

        except subprocess.CalledProcessError as e:
            lcd_display.clear()
            lcd_display.write(0, 0, "Format failed")
            lcd_display.write(0, 1, "Check logs")
            logger.error(f"Error formatting or mounting DUMP_DRIVE: {e}")
        except ValueError as e:
            lcd_display.clear()
            lcd_display.write(0, 0, "Error: Drive not")
            lcd_display.write(0, 1, "found")
            logger.error(f"Error finding DUMP_DRIVE: {e}")
        except RuntimeError as e:
            lcd_display.clear()
            lcd_display.write(0, 0, "Mount failed")
            lcd_display.write(0, 1, "Check logs")
            logger.error(str(e))
        except Exception as e:
            lcd_display.clear()
            lcd_display.write(0, 0, "Unexpected error")
            lcd_display.write(0, 1, "Check logs")
            logger.error(f"Unexpected error during formatting: {e}", exc_info=True)

        time.sleep(3)
        return self.handle_option_completion(lambda: select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

    def test_leds(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
            lcd_display.write(0, 0, "Testing LEDs")
            setup_leds()
            
            leds = [LEDControl.PROGRESS_LED, LEDControl.CHECKSUM_LED, LEDControl.SUCCESS_LED, LEDControl.ERROR_LED] + LEDControl.BAR_GRAPH_LEDS
            
            for led in leds:
                set_led_state(led, True)
                time.sleep(0.5)
                set_led_state(led, False)

            lcd_display.clear()
            lcd_display.write(0, 0, "LED Test Done")
            time.sleep(2)
            self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

    def test_screen(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        lcd_display.write(0, 0, "Testing Screen")
        time.sleep(2)
        lcd_display.clear()
        time.sleep(2)

        # Test upper case alphabet on both lines
        for i in range(1, 27):  # 26 letters in the alphabet
            lcd_display.clear()
            if i <= 16:
                lcd_display.write(0, 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:i])
            else:
                lcd_display.write(0, 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:16])
                lcd_display.write(0, 1, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[16:i])
            time.sleep(0.1)  # Adding a small delay to see the changes

        time.sleep(2)
        lcd_display.clear()
        time.sleep(2)

        # Test lower case alphabet on both lines
        for i in range(1, 27):  # 26 letters in the alphabet
            lcd_display.clear()
            if i <= 16:
                lcd_display.write(0, 0, "abcdefghijklmnopqrstuvwxyz"[:i])
            else:
                lcd_display.write(0, 0, "abcdefghijklmnopqrstuvwxyz"[:16])
                lcd_display.write(0, 1, "abcdefghijklmnopqrstuvwxyz"[16:i])
            time.sleep(0.1)  # Adding a small delay to see the changes

        time.sleep(2)
        lcd_display.clear()
        time.sleep(2)

        # Test digits and special characters on both lines
        for i in range(1, 21):  # 10 digits plus 10 special characters
            lcd_display.clear()
            if i <= 10:
                lcd_display.write(0, 0, "0123456789"[:i])
            else:
                lcd_display.write(0, 0, "0123456789")
                lcd_display.write(0, 1, ".,:;!?/()@#$%^&*"[0:i-10])
            time.sleep(0.1)  # Adding a small delay to see the changes

        time.sleep(2)
        lcd_display.clear()
        time.sleep(2)

        # Test special character pattern on both lines
        for i in range(1, 33):  # 32 `#` characters
            lcd_display.clear()
            if i <= 16:
                lcd_display.write(0, 0, "################################"[:i])
            else:
                lcd_display.write(0, 0, "################################"[:16])
                lcd_display.write(0, 1, "################################"[16:i])
            time.sleep(0.1)  # Adding a small delay to see the changes

        time.sleep(2)
        lcd_display.clear()

        lcd_display.write(0, 0, "Screen Test Done")
        time.sleep(2)
        self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

    def shutdown_system(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        logger.info("Shutting down the system...")
        lcd_display.clear()
        lcd_display.write(0, 0, "Shutting Down...")
        lcd_display.write(0, 1, "Wait 60 Seconds.")
        time.sleep(5)
        power_manager.safe_shutdown()

    def reboot_system(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        logger.info("Rebooting the system...")
        lcd_display.clear()
        lcd_display.write(0, 0, "Rebooting...")
        lcd_display.write(0, 1, "Wait 60 Seconds.")
        time.sleep(5)
        power_manager.safe_reboot()

    def version_number(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
            logger.info("Version Number: v0.0.1")
            lcd_display.clear()
            lcd_display.write(0, 0, "Version Number:")
            lcd_display.write(0, 1, "v0.0.1 240820")
            time.sleep(5)
            self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))

    def check_available_space(self, ok_button, back_button, up_button, down_button, clear_handlers, assign_handlers):
        dump_drive_mountpoint = get_dump_drive_mountpoint()

        if not os.path.ismount(dump_drive_mountpoint):
            lcd_display.clear()
            lcd_display.write(0, 0, "DUMP_DRIVE not")
            lcd_display.write(0, 1, "connected")
            logger.warning("DUMP_DRIVE not connected when checking available space")
        else:
            try:
                total, used, free = shutil.disk_usage(dump_drive_mountpoint)
                
                # Convert to appropriate unit
                if free < 999 * 1024 * 1024:  # Less than 999 MB
                    free_space = free / (1024 * 1024)
                    unit = "MB"
                elif free < 999 * 1024 * 1024 * 1024:  # Less than 999 GB
                    free_space = free / (1024 * 1024 * 1024)
                    unit = "GB"
                else:  # 1 TB or more
                    free_space = free / (1024 * 1024 * 1024 * 1024)
                    unit = "TB"
                
                # Round to 2 decimal places
                free_space = round(free_space, 2)
                
                lcd_display.clear()
                lcd_display.write(0, 0, "Available Space:")
                lcd_display.write(0, 1, f"{free_space} {unit}")
                logger.info(f"Available space on DUMP_DRIVE: {free_space} {unit}")
            except Exception as e:
                lcd_display.clear()
                lcd_display.write(0, 0, "Error checking")
                lcd_display.write(0, 1, "available space")
                logger.error(f"Error checking available space: {e}")

        # Wait for OK button press to return to menu
        while not ok_button.is_pressed:
            pass
        
        return self.handle_option_completion(lambda: self.select_option(ok_button, back_button, up_button, down_button, self.handle_option_completion, clear_handlers, assign_handlers))
    
# Create a single instance of MenuManager to be used throughout the application
menu_manager = MenuManager()

# Utility functions that use the menu_manager instance
def display_menu():
    menu_manager.display_menu()

def navigate_up():
    menu_manager.navigate_up()

def navigate_down():
    menu_manager.navigate_down()

def select_option(ok_button, back_button, up_button, down_button, on_complete, clear_handlers, assign_handlers):
    menu_manager.select_option(ok_button, back_button, up_button, down_button, on_complete, clear_handlers, assign_handlers)