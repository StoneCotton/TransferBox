from time import sleep
from threading import Event
from src.pi74HC595 import pi74HC595

# Initialize the shift register with appropriate GPIO pins
shift_register = pi74HC595(DS=7, ST=26, SH=19, daisy_chain=2)

# Constants for shift register outputs (QA, QB, QC, etc.)
PROGRESS_LED = 0  # QA of the first shift register
CHECKSUM_LED = 1  # QB of the first shift register
SUCCESS_LED = 2   # QC of the first shift register
ERROR_LED = 3     # QD of the first shift register

# LED bar graph mapping
BAR_GRAPH_LEDS = list(range(4, 8)) + list(range(8, 14))  # QE-H (first reg) + QA-F (second reg)

def setup_leds():
    """Clear all the shift register outputs (turn off all LEDs)."""
    shift_register.clear()

def set_led_state(led_index, state):
    """
    Set the state of a specific LED.
    :param led_index: Index of the LED in the shift register (0 for QA, 1 for QB, etc.)
    :param state: True to turn on the LED, False to turn it off.
    """
    current_state = shift_register.get_values()
    current_state[led_index] = 1 if state else 0
    shift_register.set_by_list(current_state)

def blink_led(led_index, stop_event, blink_speed=0.3):
    """
    Blink a specific LED by toggling its state.
    :param led_index: Index of the LED in the shift register.
    :param stop_event: Event to stop the blinking.
    :param blink_speed: Speed of the blinking.
    """
    while not stop_event.is_set():
        set_led_state(led_index, True)
        sleep(blink_speed)
        set_led_state(led_index, False)
        sleep(blink_speed)

def set_led_bar_graph(progress):
    """
    Light up the bar graph based on the progress percentage.
    :param progress: Progress as a percentage (0 to 100).
    """
    num_leds_on = int((progress / 100.0) * len(BAR_GRAPH_LEDS))
    current_state = shift_register.get_values()
    
    # Turn on LEDs according to the progress
    for i in range(len(BAR_GRAPH_LEDS)):
        current_state[BAR_GRAPH_LEDS[i]] = 1 if i < num_leds_on else 0
    
    shift_register.set_by_list(current_state)
