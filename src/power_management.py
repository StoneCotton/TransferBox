import struct
import smbus
import time
import logging
from threading import Thread, Event
import lgpio
import subprocess

logger = logging.getLogger(__name__)

class PowerManager:
    def __init__(self):
        self.GPIO_PORT = 26
        self.I2C_ADDR = 0x36
        self.PLD_PIN = 6
        self.BUZZER_PIN = 20
        self.bus = smbus.SMBus(1)
        self.h = None
        self.stop_event = Event()
        self.shutdown_event = Event()
        self.monitor_thread = None
        
        self.initialize_gpio()

    def initialize_gpio(self):
        try:
            if self.h is not None:
                self.close_gpio()
            self.h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self.h, self.GPIO_PORT, 0)
            lgpio.gpio_claim_input(self.h, self.PLD_PIN)
            lgpio.gpio_claim_output(self.h, self.BUZZER_PIN, 0)
        except lgpio.error as e:
            logger.error(f"GPIO setup error: {e}")
            self.close_gpio()
            raise

    def close_gpio(self):
        if self.h is not None:
            try:
                lgpio.gpio_free(self.h, self.GPIO_PORT)
                lgpio.gpio_free(self.h, self.PLD_PIN)
                lgpio.gpio_free(self.h, self.BUZZER_PIN)
                lgpio.gpiochip_close(self.h)
            except lgpio.error as e:
                logger.warning(f"Error while closing GPIO: {e}")
            finally:
                self.h = None

    def release_gpio_resources(self):
        logger.info("Releasing GPIO resources before shutdown")
        self.close_gpio()
        # Add a small delay to ensure resources are fully released
        time.sleep(0.5)

    def read_voltage(self):
        try:
            read = self.bus.read_word_data(self.I2C_ADDR, 2)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            voltage = swapped * 1.25 / 1000 / 16
            return voltage
        except Exception as e:
            logger.error(f"Error reading voltage: {e}")
            return None

    def read_capacity(self):
        try:
            read = self.bus.read_word_data(self.I2C_ADDR, 4)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            capacity = swapped / 256
            return min(capacity, 100)
        except Exception as e:
            logger.error(f"Error reading capacity: {e}")
            return None

    def check_ac_power(self):
        if self.h is None:
            logger.error("GPIO chip handle is not valid.")
            return False
        return lgpio.gpio_read(self.h, self.PLD_PIN) == 0

    def beep_buzzer(self):
        if self.h is None:
            logger.error("GPIO chip handle is not valid. Cannot beep buzzer.")
            return
        lgpio.gpio_write(self.h, self.BUZZER_PIN, 1)
        time.sleep(0.1)
        lgpio.gpio_write(self.h, self.BUZZER_PIN, 0)

    def safe_shutdown(self):
        """
        Perform a safe shutdown of the system using the x728 command.
        """
        logger.warning("Initiating safe shutdown...")
        self.shutdown_event.set()  # Signal the monitoring thread to stop
        self.release_gpio_resources()  # Release GPIO resources
        
        try:
            result = subprocess.run(['sudo', '/usr/local/bin/xSoft.sh', '0', '26'], 
                                    check=True, 
                                    capture_output=True, 
                                    text=True)
            logger.info(f"Shutdown command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute shutdown command: {e}")
            logger.error(f"Command output: {e.output}")
            logger.error(f"Command stderr: {e.stderr}")
        except FileNotFoundError:
            logger.error("Shutdown script not found. Make sure it's installed and the path is correct.")

    def safe_reboot(self):
        """
        Perform a safe reboot of the system by simulating a 1-2 second button press.
        """
        logger.warning("Initiating safe reboot...")
        self.stop_monitoring()
        
        if self.h is None:
            try:
                self.h = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_output(self.h, self.GPIO_PORT, 0)
            except lgpio.error as e:
                logger.error(f"Failed to re-initialize GPIO: {e}")
                return
        
        try:
            lgpio.gpio_write(self.h, self.GPIO_PORT, 1)
            time.sleep(1.5)  # Press for 1.5 seconds
            lgpio.gpio_write(self.h, self.GPIO_PORT, 0)
        except lgpio.error as e:
            logger.error(f"Failed to perform GPIO operations: {e}")
        finally:
            self.close_gpio()
        
        # Initiate system reboot
        try:
            subprocess.run(['sudo', 'reboot'], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute reboot command: {e}")

    def monitor_power(self):
        last_beep_time = 0
        beep_interval = 30
        last_print_time = 0
        print_interval = 15

        while not self.stop_event.is_set() and not self.shutdown_event.is_set():
            current_time = time.time()
            voltage = self.read_voltage()
            capacity = self.read_capacity()
            ac_power = self.check_ac_power()

            if voltage is not None and capacity is not None:
                # Print and log battery status every 15 seconds
                if current_time - last_print_time >= print_interval:
                    status_message = f"Battery: {voltage:.2f}V, {capacity:.1f}%"
                    print(status_message)
                    logger.info(status_message)
                    last_print_time = current_time
                
                if not ac_power:
                    logger.warning("AC power disconnected. Running on battery.")
                else:
                    logger.info("AC power connected.")
                
                if capacity < 15:
                    if current_time - last_beep_time >= beep_interval:
                        logger.warning("Battery below 15%, beeping buzzer")
                        self.beep_buzzer()
                        last_beep_time = current_time
                
                if voltage < 3.45:
                    logger.critical("Battery critically low!")
                    time.sleep(10)
                    self.safe_shutdown()
                    break
            
            time.sleep(5)  # Check every 5 seconds, but only print every 15 seconds

    def start_monitoring(self):
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_event.clear()
            self.shutdown_event.clear()
            self.monitor_thread = Thread(target=self.monitor_power)
            self.monitor_thread.start()

    def stop_monitoring(self):
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)  # Wait for up to 5 seconds
        self.close_gpio()

power_manager = PowerManager()