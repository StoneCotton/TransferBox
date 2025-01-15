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
from .led_control import LEDControl, led_manager
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

    def exit_menu(self) -> None:
        """Exit the utility menu"""
        with self.option_lock:
            logger.info("Exiting utility menu")
            self.display.clear()
            self.display.show_status("Exiting Menu")
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