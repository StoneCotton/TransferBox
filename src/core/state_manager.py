# src/core/state_manager.py

import time
import logging
from enum import Enum, auto
from datetime import timedelta
from typing import Optional
from pathlib import Path
from .interfaces.display import DisplayInterface
from .exceptions import StateError, DisplayError, TransferBoxError

logger = logging.getLogger(__name__)

class SystemState(Enum):
    """Enum representing possible system states"""
    STANDBY = auto()
    TRANSFER = auto()
    UTILITY = auto()  # Only used for Raspberry Pi

class StateTransitionError(StateError):
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
            
        Raises:
            DisplayError: If display interface initialization fails
        """
        try:
            self.display = display
            self.current_state = SystemState.STANDBY
            self.transfer_start_time: Optional[float] = None
            self.total_transfer_time: float = 0.0
            self.pending_unmount: Optional[Path] = None
            logger.info("State manager initialized in STANDBY state")
        except Exception as e:
            raise DisplayError(f"Failed to initialize display interface: {str(e)}", 
                             display_type="lcd",
                             error_type="initialization")
        
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
        
        Raises:
            DisplayError: If display update fails
        """
        try:
            prev_state = self.current_state
            self.current_state = SystemState.STANDBY
            
            # Only update display if we weren't already in standby
            if prev_state != SystemState.STANDBY:
                try:
                    self.display.show_status("Standby")
                    time.sleep(0.05)  # Small delay between lines
                    self.display.show_status("Input Card", line=1)
                except Exception as e:
                    raise DisplayError(f"Failed to update display in standby: {str(e)}", 
                                     display_type="lcd", 
                                     error_type="update")
                
            logger.info(f"Entering standby state from {prev_state}")
            
        except DisplayError:
            raise  # Re-raise display errors
        except Exception as e:
            logger.error(f"Error entering standby state: {e}")
            raise StateError(f"Failed to enter standby state: {str(e)}", 
                           current_state=prev_state, 
                           target_state=SystemState.STANDBY)
        
    def enter_transfer(self) -> None:
        """
        Enter transfer state.
        Only allowed from STANDBY state.
        
        Raises:
            StateError: If transition is not allowed
            DisplayError: If display update fails
        """
        prev_state = self.current_state
        try:
            logger.info(f"Transfer state requested while in {self.current_state}")
            
            if not self._can_enter_transfer():
                msg = f"Cannot enter transfer state from {self.current_state}"
                logger.warning(msg)
                raise StateError(msg, 
                               current_state=self.current_state,
                               target_state=SystemState.TRANSFER)
                
            self.current_state = SystemState.TRANSFER
            self.transfer_start_time = time.time()
            
            try:
                self.display.show_status("Transfer Mode")
            except Exception as e:
                raise DisplayError(f"Failed to update display for transfer mode: {str(e)}", 
                                 display_type="lcd",
                                 error_type="update")
                                 
            logger.info("Entering transfer state")
            
        except (StateError, DisplayError):
            raise  # Re-raise known errors
        except Exception as e:
            logger.error(f"Error entering transfer state: {e}")
            self.current_state = prev_state  # Restore previous state
            raise StateError(f"Failed to enter transfer state: {str(e)}", 
                           current_state=prev_state,
                           target_state=SystemState.TRANSFER)
        
    def exit_transfer(self, pending_unmount: Optional[Path] = None) -> None:
        """
        Exit transfer state and update timing information.
        
        Args:
            pending_unmount: Optional path to drive that still needs unmounting
            
        Raises:
            StateError: If not in transfer state
            DisplayError: If display update fails
        """
        try:
            if self.current_state != SystemState.TRANSFER:
                msg = "Attempting to exit transfer state when not in transfer state"
                logger.warning(msg)
                raise StateError(msg,
                               current_state=self.current_state,
                               target_state=SystemState.STANDBY)
                
            if self.transfer_start_time is not None:
                end_time = time.time()
                transfer_duration = end_time - self.transfer_start_time
                self.total_transfer_time += transfer_duration
                
                logger.info(f"Transfer duration: {self.format_time(transfer_duration)}")
                logger.info(f"Total transfer time: {self.format_time(self.total_transfer_time)}")
            
            # Store pending unmount if provided
            self.pending_unmount = pending_unmount
            
            # Return to standby state
            self.enter_standby()
            self.transfer_start_time = None
            
        except (StateError, DisplayError):
            raise  # Re-raise known errors
        except Exception as e:
            logger.error(f"Error exiting transfer state: {e}")
            raise StateError(f"Failed to exit transfer state: {str(e)}",
                           current_state=SystemState.TRANSFER,
                           target_state=SystemState.STANDBY)
        
    def enter_utility(self) -> bool:
        """
        Enter utility state.
        Only allowed from STANDBY state.
        
        Returns:
            bool: True if successfully entered utility state
            
        Raises:
            StateError: If transition is not allowed
        """
        prev_state = self.current_state
        try:
            logger.info(f"Attempting to enter utility state from current state: {self.current_state}")
            
            if not self._can_enter_utility():
                msg = "Cannot enter utility state from current state"
                logger.warning(msg)
                raise StateError(msg,
                               current_state=self.current_state,
                               target_state=SystemState.UTILITY)
                
            # Change state before updating display
            self.current_state = SystemState.UTILITY
            
            # Don't show status here - let the menu handler handle the display
            logger.info("Successfully entered utility state")
            return True
            
        except StateError:
            raise  # Re-raise state errors
        except Exception as e:
            logger.error(f"Failed to enter utility state: {e}")
            self.current_state = prev_state  # Restore previous state
            raise StateError(f"Failed to enter utility state: {str(e)}",
                           current_state=prev_state,
                           target_state=SystemState.UTILITY)

    def exit_utility(self) -> bool:
        """
        Exit utility state.
        Only valid when in UTILITY state.
        Always returns to STANDBY state.
        
        Returns:
            bool: True if successfully exited utility state
            
        Raises:
            StateError: If not in utility state
            DisplayError: If display update fails
        """
        prev_state = self.current_state
        try:
            logger.info(f"Attempting to exit utility state from current state: {self.current_state}")
            
            if self.current_state != SystemState.UTILITY:
                msg = "Not in utility state, cannot exit"
                logger.warning(msg)
                raise StateError(msg,
                               current_state=self.current_state,
                               target_state=SystemState.STANDBY)
                
            # First change state
            self.current_state = SystemState.STANDBY
            
            try:
                # Then update display with both lines
                self.display.show_status("Standby")
                time.sleep(0.05)  # Small delay between lines
                self.display.show_status("Input Card", line=1)
            except Exception as e:
                raise DisplayError(f"Failed to update display while exiting utility: {str(e)}",
                                 display_type="lcd",
                                 error_type="update")
            
            logger.info("Successfully exited utility state")
            return True
            
        except (StateError, DisplayError):
            raise  # Re-raise known errors
        except Exception as e:
            logger.error(f"Failed to exit utility state: {e}")
            self.current_state = prev_state  # Restore previous state
            raise StateError(f"Failed to exit utility state: {str(e)}",
                           current_state=prev_state,
                           target_state=SystemState.STANDBY)

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