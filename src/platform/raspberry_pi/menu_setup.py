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
from src.core.interfaces.storage_inter import StorageInterface
from src.core.exceptions import (
    TransferBoxError,
    HardwareError,
    DisplayError,
    StorageError,
    StateError
)
from .led_control import LEDControl, led_manager
from .power_management import power_manager

logger = logging.getLogger(__name__)

class MenuManager:
    """Manages the utility menu system for Raspberry Pi"""
    
    def __init__(self, display: DisplayInterface, storage: StorageInterface):
        try:
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
        except Exception as e:
            raise TransferBoxError(
                f"Failed to initialize menu manager: {str(e)}",
                recoverable=False
            )

    def navigate_up(self) -> None:
        """Navigate to previous menu option"""
        with self.option_lock:
            try:
                logger.debug("Menu: Navigate up")
                self.current_menu_index = (self.current_menu_index - 1) % len(self.menu_options)
                self.display_current_option()
            except Exception as e:
                raise StateError(
                    f"Failed to navigate menu up: {str(e)}",
                    current_state="menu",
                    target_state="menu"
                )

    def navigate_down(self) -> None:
        """Navigate down in menu"""
        with self.option_lock:
            try:
                logger.debug("Menu: Navigate down")
                self.current_menu_index = (self.current_menu_index + 1) % len(self.menu_options)
                self.display_current_option()
            except Exception as e:
                raise StateError(
                    f"Failed to navigate menu down: {str(e)}",
                    current_state="menu",
                    target_state="menu"
                )

    def display_current_option(self) -> None:
        """Display the current menu option"""
        with self.option_lock:
            try:
                self.display.clear()
                # Force both lines to update
                self.display.show_status("UTIL MENU", line=0)
                time.sleep(0.1)  # Small delay between lines
                self.display.show_status(self.menu_options[self.current_menu_index], line=1)
                logger.info(f"Displayed menu option: {self.menu_options[self.current_menu_index]}")
            except Exception as e:
                raise DisplayError(
                    f"Failed to display menu option: {str(e)}",
                    display_type="lcd",
                    error_type="write"
                )

    def exit_menu(self) -> None:
        """Exit the utility menu"""
        with self.option_lock:
            try:
                logger.info("Exiting utility menu")
                self.display.clear()
                self.display.show_status("Exiting Menu")
                time.sleep(1)
            except Exception as e:
                raise StateError(
                    f"Failed to exit menu: {str(e)}",
                    current_state="menu",
                    target_state="standby",
                    recovery_steps=["Return to standby mode", "Reset display"]
                )

    def _unmount_drives(self) -> None:
        """Safely unmount all removable drives"""
        try:
            self.display.clear()
            self.display.show_status("Unmounting...")
            
            drives = self.storage.get_available_drives()
            if not drives:
                self.display.show_status("No drives found", line=1)
                time.sleep(2)
                return
                
            for drive in drives:
                try:
                    if self.storage.unmount_drive(drive):
                        self.display.show_status(f"Unmounted {drive.name}", line=1)
                    else:
                        raise StorageError(
                            f"Failed to unmount {drive.name}",
                            device=drive.name,
                            error_type="mount"
                        )
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error unmounting {drive}: {e}")
                    raise StorageError(
                        f"Error unmounting drive {drive}: {str(e)}",
                        device=str(drive),
                        error_type="mount",
                        recovery_steps=[
                            "Check if drive is in use",
                            "Try manual unmount",
                            "Check drive permissions"
                        ]
                    )
        except DisplayError:
            raise
        except Exception as e:
            raise StorageError(
                f"Drive unmount operation failed: {str(e)}",
                error_type="mount",
                recovery_steps=[
                    "Check drive connections",
                    "Verify drive status",
                    "Try rebooting system"
                ]
            )
        finally:
            time.sleep(2)

    def _shutdown_system(self) -> None:
        """Initiate system shutdown"""
        try:
            self.display.clear()
            self.display.show_status("Shutting Down...")
            self.display.show_status("Please Wait", line=1)
            time.sleep(2)
            power_manager.safe_shutdown()
        except Exception as e:
            raise HardwareError(
                f"System shutdown failed: {str(e)}",
                component="system",
                error_type="power",
                recovery_steps=[
                    "Try manual shutdown",
                    "Check system processes",
                    "Force shutdown if necessary"
                ]
            )

    def _reboot_system(self) -> None:
        """Initiate system reboot"""
        try:
            self.display.clear()
            self.display.show_status("Rebooting...")
            self.display.show_status("Please Wait", line=1)
            time.sleep(2)
            power_manager.safe_reboot()
        except Exception as e:
            raise HardwareError(
                f"System reboot failed: {str(e)}",
                component="system",
                error_type="power",
                recovery_steps=[
                    "Try manual reboot",
                    "Check system processes",
                    "Force reboot if necessary"
                ]
            )

    def _version_info(self) -> None:
        """Display version information"""
        try:
            from src import __version__, __project_name__, __author__, __copyright__
            
            self.display.clear()
            self.display.show_status(__project_name__)
            self.display.show_status(f"v{__version__}", line=1)
            time.sleep(2)
            
            # Show additional info
            self.display.clear()
            self.display.show_status(f"By: {__author__}")
            self.display.show_status(__copyright__, line=1)
            time.sleep(2)
        except Exception as e:
            raise DisplayError(
                f"Failed to display version info: {str(e)}",
                display_type="lcd",
                error_type="write"
            )

    def _check_available_space(self) -> None:
        """Display available space on dump drive"""
        try:
            self.display.clear()
            self.display.show_status("Checking Space")
            
            dump_drive = self.storage.get_dump_drive()
            if not dump_drive:
                raise StorageError(
                    "Dump drive not found",
                    error_type="mount",
                    recovery_steps=[
                        "Check drive connection",
                        "Verify drive mounting",
                        "Check drive permissions"
                    ]
                )
                
            try:
                info = self.storage.get_drive_info(dump_drive)
                free_gb = info['free'] / (1024**3)
                self.display.show_status(f"{free_gb:.1f}GB Free", line=1)
            except Exception as e:
                raise StorageError(
                    f"Failed to get drive info: {str(e)}",
                    device=str(dump_drive),
                    error_type="space",
                    recovery_steps=[
                        "Check drive permissions",
                        "Verify drive is mounted",
                        "Check filesystem health"
                    ]
                )
        except (StorageError, DisplayError):
            raise
        except Exception as e:
            raise StorageError(
                f"Space check operation failed: {str(e)}",
                error_type="space",
                recovery_steps=[
                    "Check drive connection",
                    "Verify drive status",
                    "Try remounting drive"
                ]
            )
        finally:
            time.sleep(2)