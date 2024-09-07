import time
import RPi.GPIO as gpio
from threading import Event, Thread
import logging

logger = logging.getLogger(__name__)

# Initialize the shift register class
from src.pi74HC595 import pi74HC595

# Set up the shift register (with your pin configuration)
shift_register = pi74HC595(DS=7, ST=26, SH=19, daisy_chain=2)

# Constants for the LED positions on the shift register
PROGRESS_LED = 0
CHECKSUM_LED = 1
SUCCESS_LED = 2
ERROR_LED = 3

# LED bar graph pins (QE-H of first reg and QA-F of second reg)
BAR_GRAPH_LEDS = list(range(4, 8)) + list(range(8, 14))  # Positions of the bar graph LEDs

# Store the current state of all the LEDs (initialize to off)
led_state = [0] * 16  # 16 bits for 2 daisy-chained shift registers

def setup_leds():
    """Clear all the LEDs by turning off all shift register outputs."""
    global led_state
    led_state = [0] * 16  # Reset all LEDs to off
    shift_register.set_by_list(led_state)  # Use the instance of shift_register to clear all LEDs

def set_led_state(led_index, state):
    """
    Set a specific LED state in the shift register without affecting others.
    :param led_index: The index of the LED in the shift register (0-based).
    :param state: True for ON, False for OFF.
    """
    global led_state
    led_state[led_index] = 1 if state else 0  # Update the specific LED's state
    shift_register.set_by_list(led_state)  # Update the shift register with the new state

def blink_led(led_index, stop_event, blink_speed=0.5):
    """
    Blink a specific LED on the shift register without affecting others.
    :param led_index: The index of the LED in the shift register.
    :param stop_event: Threading event to stop blinking.
    :param blink_speed: Speed of the blinking (in seconds).
    """
    global led_state
    original_state = led_state[led_index]  # Preserve the original state of the LED

    while not stop_event.is_set():
        set_led_state(led_index, True)  # Turn the LED on
        time.sleep(blink_speed)
        set_led_state(led_index, False)  # Turn the LED off
        time.sleep(blink_speed)

    # Restore the original state of the LED when blinking stops
    set_led_state(led_index, original_state)

def set_led_bar_graph(progress):
    """
    Light up the bar graph based on transfer progress.
    :param progress: Progress as a percentage (0-100).
    """
    global led_state
    num_leds_on = int((progress / 100.0) * len(BAR_GRAPH_LEDS))
    
    logger.debug(f"Setting bar graph LEDs. Progress: {progress}%, LEDs on: {num_leds_on}")

    # Turn on LEDs according to the progress, and ensure others remain off
    for i in range(len(BAR_GRAPH_LEDS)):
        led_state[BAR_GRAPH_LEDS[i]] = 1 if i < num_leds_on else 0

    shift_register.set_by_list(led_state)  # Update the shift register with the bar graph state
