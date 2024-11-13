# src/platform/raspberry_pi/menu_setup.py

import time
import logging
import subprocess
import os
from threading import Lock
from pathlib import Path
from typing import Optional, Callable
from gpiozero import Button

from src.core.interfaces.display import DisplayInterface
from src.core.interfaces.storage import StorageInterface
from .led_control import setup_leds, set_led_state, LEDControl, led_manager
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
        self.menu_options = [
            "List Drives",
            "Format Drive", 
            "Unmount Drives",
            "Test LEDs",
            "Test Screen",
            "Shutdown",
            "Reboot",
            "Available Space",
            "Version Info"
        ]

    def navigate_up(self) -> None:
        """Navigate to previous menu option"""
        with self.option_lock:
            logger.debug("Menu: Navigate up")
            self.current_menu_index = (self.current_menu_index - 1) % len(self.menu_options)
            self.display_current_option()

    def navigate_down(self) -> None:
        """Navigate down in menu"""
        with self.option_lock:
            logger.debug("Menu: Navigate down")
            self.current_menu_index = (self.current_menu_index + 1) % len(self.menu_options)
            self.display_current_option()

    def display_current_option(self) -> None:
        """Display the current menu option"""
        with self.option_lock:
            self.display.clear()
            # Force both lines to update
            self.display.show_status("UTIL MENU", line=0)
            time.sleep(0.1)  # Small delay between lines
            self.display.show_status(self.menu_options[self.current_menu_index], line=1)
            logger.info(f"Displayed menu option: {self.menu_options[self.current_menu_index]}")

    def select_option(self, ok_button: Button, back_button: Button,
                     up_button: Button, down_button: Button) -> None:
        """Execute the selected menu option"""
        with self.option_lock:
            selected_option = self.menu_options[self.current_menu_index]
            logger.info(f"Selected menu option: {selected_option}")
            
            # Execute the handler if it exists
            handler = getattr(self, f"_{selected_option.lower().replace(' ', '_')}", None)
            if handler:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error executing {selected_option}: {e}")
                    self.display.show_error("Option Failed")
                    time.sleep(2)
                finally:
                    self.display_current_option()

    def exit_menu(self) -> None:
        """Exit the utility menu"""
        with self.option_lock:
            logger.info("Exiting utility menu")
            self.display.clear()
            self.display.show_status("Exiting Menu")
            time.sleep(1)

    def _list_drives(self) -> None:
        """Display list of mounted drives"""
        self.display.clear()
        self.display.show_status("Mounted Drives:")
        
        drives = self.storage.get_available_drives()
        if not drives:
            self.display.show_status("No drives found", line=1)
            time.sleep(2)
            return
            
        for drive in drives:
            self.display.show_status(str(drive.name), line=1)
            time.sleep(2)

    def _format_drive(self) -> None:
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

        # Since we can't get the button states directly anymore, we'll use a timeout approach
        self.display.show_status("Hold OK for 3s")
        self.display.show_status("to format drive", line=1)
        time.sleep(3)  # Simple timeout instead of button monitoring

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

    def _test_screen(self) -> None:
        """Test LCD screen functionality"""
        self.display.clear()
        self.display.show_status("Screen Test")
        time.sleep(1)
        
        # Test patterns
        patterns = [
            "----------------",
            "################",
            "0123456789",
            "ABCDEFGHIJKLMNO",
            "abcdefghijklmno"
        ]
        
        for pattern in patterns:
            self.display.clear()
            self.display.show_status(pattern)
            self.display.show_status(pattern, line=1)
            time.sleep(1)
            
        self.display.clear()
        self.display.show_status("Screen Test Done")
        time.sleep(1)

    def _unmount_drives(self) -> None:
        """Safely unmount all removable drives"""
        self.display.clear()
        self.display.show_status("Unmounting...")
        
        drives = self.storage.get_available_drives()
        for drive in drives:
            try:
                if self.storage.unmount_drive(drive):
                    self.display.show_status(f"Unmounted {drive.name}", line=1)
                else:
                    self.display.show_status(f"Failed: {drive.name}", line=1)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error unmounting {drive}: {e}")
                
        time.sleep(2)

    def _test_leds(self) -> None:
        """Test all LED indicators"""
        self.display.clear()
        self.display.show_status("Testing LEDs")
        
        # Test individual LEDs
        for led in [LEDControl.PROGRESS_LED, LEDControl.CHECKSUM_LED,
                   LEDControl.SUCCESS_LED, LEDControl.ERROR_LED]:
            led_manager.all_leds_off_except(led)
            time.sleep(0.5)
        
        # Test progress bar
        for progress in range(0, 101, 10):
            led_manager.set_bar_graph(progress)
            time.sleep(0.2)
        
        # Reset all LEDs
        led_manager.all_leds_off_except(None)
        self.display.show_status("LED Test Done", line=1)
        time.sleep(1)

    def _shutdown_system(self) -> None:
        """Initiate system shutdown"""
        self.display.clear()
        self.display.show_status("Shutting Down...")
        self.display.show_status("Please Wait", line=1)
        time.sleep(2)
        power_manager.safe_shutdown()

    def _reboot_system(self) -> None:
        """Initiate system reboot"""
        self.display.clear()
        self.display.show_status("Rebooting...")
        self.display.show_status("Please Wait", line=1)
        time.sleep(2)
        power_manager.safe_reboot()

    def _version_info(self) -> None:
        """Display version information"""
        self.display.clear()
        self.display.show_status("TransferBox")
        self.display.show_status("v1.0.0", line=1)
        time.sleep(2)


    def _check_available_space(self) -> None:
        """Display available space on dump drive"""
        self.display.clear()
        self.display.show_status("Checking Space")
        
        dump_drive = self.storage.get_dump_drive()
        if not dump_drive:
            self.display.show_status("Drive not found", line=1)
            time.sleep(2)
            return
            
        try:
            info = self.storage.get_drive_info(dump_drive)
            free_gb = info['free'] / (1024**3)
            self.display.show_status(f"{free_gb:.1f}GB Free", line=1)
        except Exception as e:
            logger.error(f"Error checking space: {e}")
            self.display.show_status("Check Failed", line=1)
            
        time.sleep(2)