import RPi.GPIO as GPIO
import time
from threading import Event

LED_BAR_PINS = [5, 6, 13, 19, 26, 20, 21, 16, 12, 18]
LED1_PIN = 17
LED2_PIN = 27
LED3_PIN = 22
CHECKSUM_LED_PIN = 23

def setup_leds():
    GPIO.setmode(GPIO.BCM)
    for pin in LED_BAR_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    for pin in [LED1_PIN, LED2_PIN, LED3_PIN, CHECKSUM_LED_PIN]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def blink_led(led_pin, stop_event, blink_speed=0.3):
    while not stop_event.is_set():
        GPIO.output(led_pin, GPIO.HIGH)
        time.sleep(blink_speed)
        GPIO.output(led_pin, GPIO.LOW)
        time.sleep(blink_speed)

def set_led_bar_graph(progress):
    num_leds_on = int((progress / 100.0) * len(LED_BAR_PINS))
    for i, pin in enumerate(LED_BAR_PINS):
        GPIO.output(pin, GPIO.HIGH if i < num_leds_on else GPIO.LOW)
