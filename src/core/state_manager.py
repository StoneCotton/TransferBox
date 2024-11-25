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

class StateTransitionError(Exception):
    """Exception raised for invalid state transitions"""
    pass

class StateManager:
    """
    Manages system state and timing across all platforms with strict state transition rules:
    - STANDBY is the default state
    - UTILITY can only be entered from STANDBY
    - TRANSFER can only be entered from STANDBY
    - TRANSFER can only exit to STANDBY
    - UTILITY can only exit to STANDBY
    """
    
    def __init__(self, display: DisplayInterface):
        """
        Initialize state manager.
        
        Args:
            display: Display interface for showing status messages
        """
        self.display = display
        self.current_state = SystemState.STANDBY
        self.transfer_start_time: Optional[float] = None
        self.total_transfer_time: float = 0.0
        logger.info("State manager initialized in STANDBY state")
        
    def get_current_state(self) -> SystemState:
        """
        Get the current system state.
        
        Returns:
            Current SystemState enum value
        """
        return self.current_state
        
    def is_standby(self) -> bool:
        """
        Check if system is in standby state.
        
        Returns:
            True if in STANDBY state, False otherwise
        """
        return self.current_state == SystemState.STANDBY
        
    def is_transfer(self) -> bool:
        """
        Check if system is in transfer state.
        
        Returns:
            True if in TRANSFER state, False otherwise
        """
        return self.current_state == SystemState.TRANSFER
        
    def is_utility(self) -> bool:
        """
        Check if system is in utility state.
        
        Returns:
            True if in UTILITY state, False otherwise
        """
        is_util = self.current_state == SystemState.UTILITY
        logger.debug(f"Checking utility state: {is_util}")
        return is_util

    def _can_enter_utility(self) -> bool:
        """
        Check if system can enter utility state.
        Only allowed from STANDBY state.
        
        Returns:
            True if transition is allowed, False otherwise
        """
        return self.current_state == SystemState.STANDBY

    def _can_enter_transfer(self) -> bool:
        """
        Check if system can enter transfer state.
        Only allowed from STANDBY state.
        
        Returns:
            True if transition is allowed, False otherwise
        """
        return self.current_state == SystemState.STANDBY

    def enter_standby(self) -> None:
        """
        Enter standby state.
        Always allowed from any state.
        """
        try:
            prev_state = self.current_state
            self.current_state = SystemState.STANDBY
            
            # Only update display if we weren't already in standby
            if prev_state != SystemState.STANDBY:
                self.display.show_status("Standby")
                time.sleep(0.05)  # Small delay between lines
                self.display.show_status("Input Card", line=1)
                
            logger.info(f"Entering standby state from {prev_state}")
            
        except Exception as e:
            logger.error(f"Error entering standby state: {e}")
        
    def enter_transfer(self) -> None:
        """
        Enter transfer state.
        Only allowed from STANDBY state.
        
        Raises:
            StateTransitionError: If transition is not allowed
        """
        try:
            logger.info(f"Transfer state requested while in {self.current_state}")
            
            if not self._can_enter_transfer():
                msg = f"Cannot enter transfer state from {self.current_state}"
                logger.warning(msg)
                raise StateTransitionError(msg)
                
            self.current_state = SystemState.TRANSFER
            self.transfer_start_time = time.time()
            self.display.show_status("Transfer Mode")
            logger.info("Entering transfer state")
            
        except Exception as e:
            logger.error(f"Error entering transfer state: {e}")
            if not isinstance(e, StateTransitionError):
                self.enter_standby()  # Only fallback on non-state errors
        
    def exit_transfer(self) -> None:
        """
        Exit transfer state and update timing information.
        Only valid when in TRANSFER state.
        Always returns to STANDBY state.
        """
        try:
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
            
        except Exception as e:
            logger.error(f"Error exiting transfer state: {e}")
            self.enter_standby()  # Ensure we return to standby even on error
        
    def enter_utility(self) -> bool:
        """
        Enter utility state.
        Only allowed from STANDBY state.
        
        Returns:
            bool: True if successfully entered utility state, False otherwise
        """
        try:
            logger.info(f"Attempting to enter utility state from current state: {self.current_state}")
            
            if not self._can_enter_utility():
                logger.warning("Cannot enter utility state from current state")
                return False
                
            # Change state before updating display
            self.current_state = SystemState.UTILITY
            
            # Don't show status here - let the menu handler handle the display
            logger.info("Successfully entered utility state")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enter utility state: {e}")
            self.enter_standby()  # Fallback to standby on error
            return False

    def exit_utility(self) -> bool:
        """
        Exit utility state.
        Only valid when in UTILITY state.
        Always returns to STANDBY state.
        
        Returns:
            bool: True if successfully exited utility state, False otherwise
        """
        try:
            logger.info(f"Attempting to exit utility state from current state: {self.current_state}")
            
            if self.current_state != SystemState.UTILITY:
                logger.warning("Not in utility state, cannot exit")
                return False
                
            # First change state
            self.current_state = SystemState.STANDBY
            
            # Then update display with both lines
            self.display.show_status("Standby")
            time.sleep(0.05)  # Small delay between lines
            self.display.show_status("Input Card", line=1)
            
            logger.info("Successfully exited utility state")
            return True
            
        except Exception as e:
            logger.error(f"Failed to exit utility state: {e}")
            # Force standby state on error
            self.current_state = SystemState.STANDBY
            self.display.show_status("Standby")
            time.sleep(0.05)
            self.display.show_status("Input Card", line=1)
            return False

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