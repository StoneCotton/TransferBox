import time
import logging

logger = logging.getLogger(__name__)

class ButtonHandler:
    def __init__(self, back_button, ok_button, up_button, down_button, state_manager, menu_callback):
        self.back_button = back_button
        self.ok_button = ok_button
        self.up_button = up_button
        self.down_button = down_button
        self.state_manager = state_manager
        self.menu_callback = menu_callback
        self.last_ok_time = 0
        self.ok_press_count = 0

    def button_listener(self, main_stop_event):
        while not main_stop_event.is_set():
            if self.back_button.is_pressed:
                logger.debug("Back button is held down.")

                if self.ok_button.is_pressed:
                    logger.debug("OK button is pressed.")
                    current_time = time.time()

                    if current_time - self.last_ok_time <= 2:
                        self.ok_press_count += 1
                        logger.debug(f"OK button press count: {self.ok_press_count}")
                    else:
                        self.ok_press_count = 1  # Reset counter if more than 2 seconds passed
                        logger.debug("Resetting OK button press count due to timeout.")

                    self.last_ok_time = current_time

                    if self.ok_press_count >= 2:
                        if self.state_manager.is_standby():
                            logger.info("Menu activated.")
                            self.state_manager.enter_utility()
                            self.menu_callback()  # Call the menu callback function
                        else:
                            logger.info("Cannot enter utility mode: not in standby mode.")
                        self.ok_press_count = 0  # Reset count after activation attempt
                else:
                    logger.debug("OK button is not pressed after back button.")
            else:
                if self.ok_press_count > 0:
                    logger.debug("Back button released, resetting OK press count.")
                self.ok_press_count = 0

            time.sleep(0.1)  # Small delay to avoid overwhelming the logs