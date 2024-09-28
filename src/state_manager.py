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
        logger.info("Entering standby state")

    def enter_transfer(self):
        if self.current_state != "standby":
            raise ValueError("Can only enter transfer state from standby state.")
        self.current_state = "transfer"
        self.transfer_start_time = time.time()
        logger.info("Entering transfer state")

    def exit_transfer(self):
        if self.current_state != "transfer":
            logger.warning("Attempting to exit transfer state when not in transfer state.")
            return
        end_time = time.time()
        transfer_duration = end_time - self.transfer_start_time
        self.total_transfer_time += transfer_duration
        self.current_state = "standby"
        logger.info(f"Exiting transfer state. Duration: {self.format_time(transfer_duration)}")
        logger.info(f"Total transfer time: {self.format_time(self.total_transfer_time)}")
        self.transfer_start_time = None

    def get_current_transfer_time(self):
        if self.current_state == "transfer" and self.transfer_start_time is not None:
            current_duration = time.time() - self.transfer_start_time
            return self.format_time(current_duration)
        return "00:00:00"

    def get_total_transfer_time(self):
        return self.format_time(self.total_transfer_time)
    
    def enter_utility(self):
        if self.current_state != "standby":
            raise ValueError("Can only enter utility state from standby state.")
        self.current_state = "utility"
        logger.info("Entering utility state")

    def exit_utility(self):
        if self.current_state != "utility":
            logger.warning("Attempting to exit utility state when not in utility state.")
            return
        self.current_state = "standby"
        logger.info("Exiting utility state")

    @staticmethod
    def format_time(seconds):
        return str(timedelta(seconds=int(seconds)))

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