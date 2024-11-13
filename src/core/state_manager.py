# src/core/state_manager.py

import time
import logging
from enum import Enum, auto
from datetime import timedelta
from typing import Optional
from .interfaces.display import DisplayInterface

logger = logging.getLogger(__name__)

class SystemState(Enum):
    """Enum representing possible system states"""
    STANDBY = auto()
    TRANSFER = auto()
    UTILITY = auto()  # Only used for Raspberry Pi

class StateManager:
    """
    Manages system state and timing across all platforms
    """
    
    def __init__(self, display: DisplayInterface):
        self.display = display
        self.current_state = SystemState.STANDBY
        self.transfer_start_time: Optional[float] = None
        self.total_transfer_time: float = 0.0
        
    def get_current_state(self) -> SystemState:
        """Get the current system state."""
        return self.current_state
        
    def is_standby(self) -> bool:
        """Check if system is in standby state."""
        return self.current_state == SystemState.STANDBY
        
    def is_transfer(self) -> bool:
        """Check if system is in transfer state."""
        return self.current_state == SystemState.TRANSFER
        
    def is_utility(self) -> bool:
        """Check if system is in utility state (Raspberry Pi only)."""
        return self.current_state == SystemState.UTILITY
        
    def enter_standby(self) -> None:
        """Enter standby state."""
        self.current_state = SystemState.STANDBY
        self.display.show_status("Standby Mode")
        logger.info("Entering standby state")
        
    def enter_transfer(self) -> None:
        """Enter transfer state."""
        # Always transition through standby state
        if self.current_state != SystemState.STANDBY:
            self.enter_standby()
            
        self.current_state = SystemState.TRANSFER
        self.transfer_start_time = time.time()
        self.display.show_status("Transfer Mode")
        logger.info("Entering transfer state")
        
    def exit_transfer(self) -> None:
        """Exit transfer state and update timing information."""
        if self.current_state != SystemState.TRANSFER:
            logger.warning("Attempting to exit transfer state when not in transfer state")
            return
            
        if self.transfer_start_time is not None:
            end_time = time.time()
            transfer_duration = end_time - self.transfer_start_time
            self.total_transfer_time += transfer_duration
            
            logger.info(f"Transfer duration: {self.format_time(transfer_duration)}")
            logger.info(f"Total transfer time: {self.format_time(self.total_transfer_time)}")
            
        # Return to standby state
        self.enter_standby()
        self.transfer_start_time = None
        
    def enter_utility(self) -> None:
        """
        Enter utility state (Raspberry Pi only).
        
        Raises:
            ValueError: If not in standby state
        """
        if self.current_state != SystemState.STANDBY:
            raise ValueError("Can only enter utility state from standby state")
            
        self.current_state = SystemState.UTILITY
        self.display.show_status("Utility Mode")
        logger.info("Entering utility state")
        
    def exit_utility(self) -> None:
        """Exit utility state (Raspberry Pi only)."""
        if self.current_state != SystemState.UTILITY:
            logger.warning("Attempting to exit utility state when not in utility state")
            return
            
        self.current_state = SystemState.STANDBY
        self.display.show_status("Exiting Utility Mode")
        logger.info("Exiting utility state")
        
    def get_current_transfer_time(self) -> float:
        """
        Get the duration of the current transfer.
        
        Returns:
            Duration in seconds, or 0 if not in transfer state
        """
        if self.is_transfer() and self.transfer_start_time is not None:
            return time.time() - self.transfer_start_time
        return 0.0
        
    def get_total_transfer_time(self) -> float:
        """
        Get the total time spent in transfer state.
        
        Returns:
            Total duration in seconds
        """
        return self.total_transfer_time
        
    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format time duration as string.
        
        Args:
            seconds: Time duration in seconds
            
        Returns:
            Formatted string in HH:MM:SS format
        """
        return str(timedelta(seconds=int(seconds)))