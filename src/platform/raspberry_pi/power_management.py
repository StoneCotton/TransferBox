# src/platform/raspberry_pi/power_management.py

import struct
import smbus
import time
import logging
from threading import Thread, Event
import lgpio
import subprocess
from pathlib import Path
from src.core.exceptions import HardwareError, TransferBoxError

logger = logging.getLogger(__name__)

class PowerManager:
    """Manages power-related functionality for Raspberry Pi with x728 UPS HAT"""
    
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

    def initialize_gpio(self) -> None:
        """Initialize GPIO resources"""
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
            raise HardwareError(
                f"Failed to initialize GPIO: {str(e)}",
                component="gpio",
                error_type="initialization",
                recovery_steps=[
                    "Check GPIO permissions",
                    "Verify hardware connections",
                    "Restart system if persistent"
                ]
            )

    def close_gpio(self) -> None:
        """Close GPIO resources"""
        if self.h is not None:
            try:
                lgpio.gpio_free(self.h, self.GPIO_PORT)
                lgpio.gpio_free(self.h, self.PLD_PIN)
                lgpio.gpio_free(self.h, self.BUZZER_PIN)
                lgpio.gpiochip_close(self.h)
            except lgpio.error as e:
                logger.warning(f"Error while closing GPIO: {e}")
                raise HardwareError(
                    f"Failed to close GPIO resources: {str(e)}",
                    component="gpio",
                    error_type="cleanup",
                    recovery_steps=[
                        "Check if resources are in use",
                        "Force cleanup if necessary",
                        "Restart system if persistent"
                    ]
                )
            finally:
                self.h = None

    def release_gpio_resources(self) -> None:
        """Release GPIO resources before shutdown"""
        logger.info("Releasing GPIO resources before shutdown")
        self.close_gpio()
        time.sleep(0.5)  # Small delay to ensure resources are released

    def read_voltage(self) -> float:
        """Read battery voltage"""
        try:
            read = self.bus.read_word_data(self.I2C_ADDR, 2)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            voltage = swapped * 1.25 / 1000 / 16
            return voltage
        except Exception as e:
            logger.error(f"Error reading voltage: {e}")
            raise HardwareError(
                f"Failed to read battery voltage: {str(e)}",
                component="battery",
                error_type="measurement",
                recovery_steps=[
                    "Check I2C connection",
                    "Verify battery is connected",
                    "Check UPS HAT hardware"
                ]
            )

    def read_capacity(self) -> float:
        """Read battery capacity percentage"""
        try:
            read = self.bus.read_word_data(self.I2C_ADDR, 4)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            capacity = swapped / 256
            return min(capacity, 100.0)
        except Exception as e:
            logger.error(f"Error reading capacity: {e}")
            raise HardwareError(
                f"Failed to read battery capacity: {str(e)}",
                component="battery",
                error_type="measurement",
                recovery_steps=[
                    "Check I2C connection",
                    "Verify battery is connected",
                    "Check UPS HAT hardware"
                ]
            )

    def check_ac_power(self) -> bool:
        """Check if AC power is connected"""
        if self.h is None:
            raise HardwareError(
                "GPIO chip handle is not valid",
                component="gpio",
                error_type="initialization",
                recovery_steps=[
                    "Reinitialize GPIO",
                    "Check hardware connections",
                    "Restart system if persistent"
                ]
            )
        return lgpio.gpio_read(self.h, self.PLD_PIN) == 0

    def beep_buzzer(self) -> None:
        """Activate buzzer for alert"""
        if self.h is None:
            raise HardwareError(
                "GPIO chip handle is not valid",
                component="buzzer",
                error_type="initialization",
                recovery_steps=[
                    "Reinitialize GPIO",
                    "Check buzzer connections",
                    "Verify buzzer hardware"
                ]
            )
        try:
            lgpio.gpio_write(self.h, self.BUZZER_PIN, 1)
            time.sleep(0.1)
            lgpio.gpio_write(self.h, self.BUZZER_PIN, 0)
        except lgpio.error as e:
            raise HardwareError(
                f"Failed to control buzzer: {str(e)}",
                component="buzzer",
                error_type="control",
                recovery_steps=[
                    "Check buzzer connections",
                    "Verify GPIO permissions",
                    "Test buzzer hardware"
                ]
            )

    def safe_shutdown(self) -> None:
        """Perform a safe system shutdown"""
        logger.warning("Initiating safe shutdown...")
        self.shutdown_event.set()
        self.release_gpio_resources()
        
        script_path = Path('/usr/local/bin/xSoft.sh')
        try:
            if script_path.exists():
                result = subprocess.run(
                    ['sudo', str(script_path), '0', '26'],
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"Shutdown command output: {result.stdout}")
            else:
                logger.error("Shutdown script not found")
                subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute shutdown command: {e}")
            logger.error(f"Command output: {e.output}")
            logger.error(f"Command stderr: {e.stderr}")
            raise HardwareError(
                f"System shutdown failed: {str(e)}",
                component="system",
                error_type="power",
                recovery_steps=[
                    "Check shutdown script permissions",
                    "Verify sudo access",
                    "Try manual shutdown"
                ]
            )

    def safe_reboot(self) -> None:
        """Perform a safe system reboot"""
        logger.warning("Initiating safe reboot...")
        self.stop_monitoring()
        
        if self.h is None:
            try:
                self.h = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_output(self.h, self.GPIO_PORT, 0)
            except lgpio.error as e:
                logger.error(f"Failed to re-initialize GPIO: {e}")
                raise HardwareError(
                    f"Failed to initialize GPIO for reboot: {str(e)}",
                    component="gpio",
                    error_type="initialization",
                    recovery_steps=[
                        "Check GPIO permissions",
                        "Verify hardware connections",
                        "Try manual reboot"
                    ]
                )
        
        try:
            lgpio.gpio_write(self.h, self.GPIO_PORT, 1)
            time.sleep(1.5)  # Press for 1.5 seconds
            lgpio.gpio_write(self.h, self.GPIO_PORT, 0)
        except lgpio.error as e:
            logger.error(f"Failed to perform GPIO operations: {e}")
            raise HardwareError(
                f"Failed to control GPIO for reboot: {str(e)}",
                component="gpio",
                error_type="control",
                recovery_steps=[
                    "Check GPIO permissions",
                    "Verify hardware connections",
                    "Try manual reboot"
                ]
            )
        finally:
            self.close_gpio()
        
        try:
            subprocess.run(['sudo', 'reboot'], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute reboot command: {e}")
            raise HardwareError(
                f"System reboot failed: {str(e)}",
                component="system",
                error_type="power",
                recovery_steps=[
                    "Check reboot permissions",
                    "Verify sudo access",
                    "Try manual reboot"
                ]
            )

    def monitor_power(self) -> None:
        """Monitor power status continuously"""
        last_beep_time = 0
        beep_interval = 30
        last_print_time = 0
        print_interval = 15

        while not self.stop_event.is_set() and not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                try:
                    voltage = self.read_voltage()
                    capacity = self.read_capacity()
                    ac_power = self.check_ac_power()
                except HardwareError as e:
                    logger.error(f"Failed to read power status: {e}")
                    if e.component == "battery" and e.error_type == "measurement":
                        # For battery measurement errors, we can continue monitoring with a delay
                        time.sleep(5)
                        continue
                    else:
                        # For other hardware errors, we should propagate them
                        raise

                if current_time - last_print_time >= print_interval:
                    status_message = f"Battery: {voltage:.2f}V, {capacity:.1f}%"
                    logger.info(status_message)
                    last_print_time = current_time
                
                if not ac_power:
                    logger.warning("AC power disconnected. Running on battery.")
                else:
                    logger.info("AC power connected.")
                
                if capacity < 15:
                    if current_time - last_beep_time >= beep_interval:
                        try:
                            logger.warning("Battery below 15%, beeping buzzer")
                            self.beep_buzzer()
                            last_beep_time = current_time
                        except HardwareError as e:
                            if e.component == "buzzer":
                                # Non-critical error, just log it
                                logger.error(f"Failed to beep buzzer: {e}")
                
                if voltage < 3.25:
                    logger.critical("Battery critically low!")
                    time.sleep(10)  # Give time for logs to be written
                    try:
                        self.safe_shutdown()
                    except HardwareError as e:
                        logger.critical(f"Failed to initiate safe shutdown: {e}")
                        # Try emergency shutdown as last resort
                        try:
                            subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=True)
                        except subprocess.CalledProcessError:
                            logger.critical("Emergency shutdown failed. System at risk!")
                    break
            
            except Exception as e:
                logger.error(f"Error in power monitoring loop: {e}")
                if isinstance(e, HardwareError):
                    # For hardware errors, we should stop monitoring
                    raise
                # For other unexpected errors, continue monitoring with a delay
                time.sleep(5)
            
            time.sleep(5)

    def start_monitoring(self) -> None:
        """Start power monitoring thread"""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.stop_event.clear()
            self.shutdown_event.clear()
            self.monitor_thread = Thread(target=self.monitor_power)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop power monitoring thread"""
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.close_gpio()

# Create singleton instance
power_manager = PowerManager()