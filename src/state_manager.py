import time
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self):
        self.current_state = "standby"
        self.menu_active = False
        self.transfer_start_time = None
        self.total_transfer_time = 0

    def get_current_state(self):
        return self.current_state

    def set_current_state(self, state):
        if state in ["standby", "transfer", "utility"]:
            self.current_state = state
        else:
            raise ValueError("Invalid state. Must be 'standby', 'transfer', or 'utility'.")

    def is_standby(self):
        return self.current_state == "standby"

    def is_transfer(self):
        return self.current_state == "transfer"

    def is_utility(self):
        return self.current_state == "utility"

    def enter_standby(self):
        self.current_state = "standby"
        self.menu_active = False

    def format_time(self, seconds):
        """Convert seconds to HH:MM:SS format."""
        return str(timedelta(seconds=int(seconds)))

    def enter_transfer(self):
        if self.current_state == "standby":
            self.current_state = "transfer"
            self.transfer_start_time = time.time()
            logger.info("Entering transfer state")
        else:
            raise ValueError("Can only enter transfer state from standby state.")

    def exit_transfer(self):
        if self.current_state == "transfer":
            end_time = time.time()
            transfer_duration = end_time - self.transfer_start_time
            self.total_transfer_time += transfer_duration
            self.current_state = "standby"
            formatted_duration = self.format_time(transfer_duration)
            formatted_total = self.format_time(self.total_transfer_time)
            logger.info(f"Exiting transfer state. Duration: {formatted_duration}")
            logger.info(f"Total transfer time: {formatted_total}")
            self.transfer_start_time = None
        else:
            raise ValueError("Can only exit transfer state when in transfer state.")

    def get_current_transfer_time(self):
        if self.current_state == "transfer" and self.transfer_start_time is not None:
            current_duration = time.time() - self.transfer_start_time
            return self.format_time(current_duration)
        return "00:00:00"

    def get_total_transfer_time(self):
        return self.format_time(self.total_transfer_time)
    
    def enter_utility(self):
        if self.current_state == "standby":
            self.current_state = "utility"
            self.menu_active = True
        else:
            raise ValueError("Can only enter utility state from standby state.")

    def exit_utility(self):
        if self.current_state == "utility":
            self.current_state = "standby"
            self.menu_active = False
        else:
            raise ValueError("Can only exit utility state when in utility state.")

    def is_menu_active(self):
        return self.menu_active

    def set_menu_active(self, active):
        self.menu_active = active

    def get_current_transfer_time(self):
        if self.current_state == "transfer" and self.transfer_start_time is not None:
            return time.time() - self.transfer_start_time
        return 0

    def get_total_transfer_time(self):
        return self.total_transfer_time