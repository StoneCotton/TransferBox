import time
from threading import Event, Thread
import logging
from src.pi74HC595 import pi74HC595

logger = logging.getLogger(__name__)

class LEDControl:
    # Constants for the LED positions on the shift register
    PROGRESS_LED = 0
    CHECKSUM_LED = 1
    SUCCESS_LED = 2
    ERROR_LED = 3
    BAR_GRAPH_LEDS = list(range(4, 8)) + list(range(8, 14))  # Positions of the bar graph LEDs

    def __init__(self, ds_pin=7, st_pin=13, sh_pin=19, daisy_chain=2):
        self.shift_register = pi74HC595(DS=ds_pin, ST=st_pin, SH=sh_pin, daisy_chain=daisy_chain)
        self.led_state = [0] * 16  # 16 bits for 2 daisy-chained shift registers

    def setup_leds(self):
        """Clear all the LEDs by turning off all shift register outputs."""
        self.led_state = [0] * 16  # Reset all LEDs to off
        self.shift_register.set_by_list(self.led_state)
        logger.info("LEDs setup completed")

    def set_led_state(self, led_index, state):
        """
        Set a specific LED state in the shift register without affecting others.
        :param led_index: The index of the LED in the shift register (0-based).
        :param state: True for ON, False for OFF.
        """
        self.led_state[led_index] = 1 if state else 0  # Update the specific LED's state
        self.shift_register.set_by_list(self.led_state)
        logger.debug(f"LED {led_index} set to {'ON' if state else 'OFF'}")

    def blink_led(self, led_index, stop_event, blink_speed=0.5):
        """
        Blink a specific LED on the shift register without affecting others.
        :param led_index: The index of the LED in the shift register.
        :param stop_event: Threading event to stop blinking.
        :param blink_speed: Speed of the blinking (in seconds).
        """
        original_state = self.led_state[led_index]  # Preserve the original state of the LED

        while not stop_event.is_set():
            self.set_led_state(led_index, True)  # Turn the LED on
            time.sleep(blink_speed)
            self.set_led_state(led_index, False)  # Turn the LED off
            time.sleep(blink_speed)

        # Restore the original state of the LED when blinking stops
        self.set_led_state(led_index, original_state)

    def set_led_bar_graph(self, progress):
        """
        Light up the bar graph based on transfer progress.
        :param progress: Progress as a percentage (0-100).
        """
        num_leds = len(self.BAR_GRAPH_LEDS)
        num_leds_on = int((progress / 100.0) * num_leds)
        
        logger.debug(f"Setting bar graph LEDs. Progress: {progress}%, LEDs on: {num_leds_on}")

        # Turn on LEDs according to the progress, and ensure others remain off
        for i in range(num_leds):
            self.led_state[self.BAR_GRAPH_LEDS[i]] = 1 if i < num_leds_on else 0

        self.shift_register.set_by_list(self.led_state)

    def cleanup(self):
        """Turn off all LEDs and clean up resources."""
        self.led_state = [0] * 16
        self.shift_register.set_by_list(self.led_state)
        self.shift_register.cleanup()
        logger.info("LED cleanup completed")

# Create a single instance of LEDControl to be used throughout the application
led_control = LEDControl()

# Utility functions that use the led_control instance
def setup_leds():
    led_control.setup_leds()

def set_led_state(led_index, state):
    led_control.set_led_state(led_index, state)

def blink_led(led_index, stop_event, blink_speed=0.5):
    led_control.blink_led(led_index, stop_event, blink_speed)

def set_led_bar_graph(progress):
    led_control.set_led_bar_graph(progress)

def cleanup_leds():
    led_control.cleanup()