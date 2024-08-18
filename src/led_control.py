from gpiozero import LED, LEDBoard
from time import sleep
from threading import Event

# Original variable names
LED1_PIN = LED(17)
LED2_PIN = LED(27)
LED3_PIN = LED(22)
CHECKSUM_LED_PIN = LED(23)

# Create an LEDBoard object for the LED bar graph
LED_BAR_PINS = LEDBoard(*[5, 6, 13, 19, 26, 20, 21, 16, 12, 18], pwm=True)

def setup_leds():
    # No need for manual setup; `gpiozero` handles this
    LED1_PIN.off()
    LED2_PIN.off()
    LED3_PIN.off()
    CHECKSUM_LED_PIN.off()
    LED_BAR_PINS.off()

def blink_led(led_pin, stop_event, blink_speed=0.3):
    while not stop_event.is_set():
        led_pin.on()
        sleep(blink_speed)
        led_pin.off()
        sleep(blink_speed)

def set_led_bar_graph(progress):
    num_leds_on = int((progress / 100.0) * len(LED_BAR_PINS))
    for i in range(len(LED_BAR_PINS)):
        if i < num_leds_on:
            LED_BAR_PINS[i].on()
        else:
            LED_BAR_PINS[i].off()
