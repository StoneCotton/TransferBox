#!/usr/bin/env python3

import struct
import smbus
import sys
import time
import lgpio

# Constants
GPIO_PORT = 26       # GPIO pin to signal UPS HAT to shutdown
I2C_ADDR = 0x36      # I2C address for battery fuel gauge
PLD_PIN = 6          # GPIO pin to detect AC power loss
BUZZER_PIN = 20      # GPIO pin connected to buzzer

# Open the gpiochip
try:
    h = lgpio.gpiochip_open(0)  # Open /dev/gpiochip0
except lgpio.error as e:
    print("Error opening gpiochip:", e)
    sys.exit(1)

# Claim GPIOs
try:
    lgpio.gpio_claim_output(h, GPIO_PORT, 0)  # GPIO_PORT as output, initial level 0
    lgpio.gpio_claim_input(h, PLD_PIN)        # PLD_PIN as input
    lgpio.gpio_claim_output(h, BUZZER_PIN, 0) # BUZZER_PIN as output, initial level 0
except lgpio.error as e:
    print("GPIO setup error:", e)
    lgpio.gpiochip_close(h)
    sys.exit(1)

# Setup I2C bus
bus = smbus.SMBus(1)  # 1 = /dev/i2c-1 (I2C bus 1)

def readVoltage(bus):
    address = I2C_ADDR
    try:
        read = bus.read_word_data(address, 2)
    except Exception as e:
        print("Error reading voltage:", e)
        return None
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    voltage = swapped * 1.25 /1000/16
    return voltage

def readCapacity(bus):
    address = I2C_ADDR
    try:
        read = bus.read_word_data(address, 4)
    except Exception as e:
        print("Error reading capacity:", e)
        return None
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    capacity = swapped / 256
    if capacity > 100:
        capacity = 100
    return capacity

def main():
    last_beep_time = 0  # Initialize last beep time to 0
    beep_interval = 30  # Beep once every 30 seconds

    try:
        while True:
            # Read battery voltage and capacity
            voltage = readVoltage(bus)
            capacity = readCapacity(bus)

            # Read AC power status
            ac_power = lgpio.gpio_read(h, PLD_PIN)  # 0 = AC power OK, 1 = AC power lost

            # Print AC power status
            if ac_power == 0:
                print("AC Power OK")
            else:
                print("AC Power Lost")

            # Print battery status
            if voltage is not None and capacity is not None:
                print("******************")
                print("Voltage: %5.2fV" % voltage)
                print("Battery: %5i%%" % capacity)

                if capacity == 100:
                    print("Battery FULL")
                if capacity < 20:
                    print("Battery Low")

                # Check if battery capacity is below 15%
                if capacity < 15:
                    current_time = time.time()
                    if current_time - last_beep_time >= beep_interval:
                        # Beep the buzzer once
                        print("Battery below 15%, beeping buzzer")
                        lgpio.gpio_write(h, BUZZER_PIN, 1)
                        time.sleep(0.1)
                        lgpio.gpio_write(h, BUZZER_PIN, 0)
                        # Update last beep time
                        last_beep_time = current_time

                # Check if battery voltage is below threshold
                if voltage < 3.00:
                    print("Battery LOW!!!")
                    print("Shutdown in 10 seconds")
                    # Ensure buzzer is off
                    lgpio.gpio_write(h, BUZZER_PIN, 0)
                    time.sleep(10)
                    # Signal UPS HAT to shutdown
                    lgpio.gpio_write(h, GPIO_PORT, 1)
                    time.sleep(3)
                    lgpio.gpio_write(h, GPIO_PORT, 0)
                    # Exit loop after initiating shutdown
                    break

            else:
                print("Could not read battery status")

            time.sleep(2)

    except KeyboardInterrupt:
        print("Exiting...")

    finally:
        # Cleanup GPIO
        lgpio.gpiochip_close(h)

if __name__ == '__main__':
    main()
