# src/platform/raspberry_pi/pi74HC595.py

import logging
from typing import List, Union
from gpiozero import OutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory

# Set gpiozero to use lgpio
Device.pin_factory = LGPIOFactory()

logger = logging.getLogger(__name__)

class pi74HC595:
    """Controls 74HC595 shift register(s) on Raspberry Pi using gpiozero and lgpio"""
    
    def __init__(
        self,
        DS: int = 11,  # Data pin
        ST: int = 13,  # Storage/latch pin
        SH: int = 15,  # Shift pin
        daisy_chain: int = 1
    ):
        """
        Initialize shift register control.
        
        Args:
            DS: Data pin (GPIO number)
            ST: Storage/latch pin (GPIO number)
            SH: Shift pin (GPIO number)
            daisy_chain: Number of daisy-chained shift registers
        """
        try:
            # Initialize GPIO pins using gpiozero
            self.data_pin = OutputDevice(DS)
            self.latch_pin = OutputDevice(ST)
            self.clock_pin = OutputDevice(SH)
            
            self.daisy_chain = max(1, daisy_chain)
            self.current = [0] * (8 * self.daisy_chain)
            
            # Initialize all pins to low
            self.data_pin.off()
            self.latch_pin.off()
            self.clock_pin.off()
            
            self.clear()
            logger.info(f"Initialized 74HC595 with {daisy_chain} registers")
            
        except Exception as e:
            logger.error(f"Failed to initialize 74HC595: {e}")
            self.cleanup()
            raise

    def _tick_clock(self) -> None:
        """Generate clock pulse"""
        self.clock_pin.on()
        self.clock_pin.off()

    def _latch_data(self) -> None:
        """Latch data to output"""
        self.latch_pin.on()
        self.latch_pin.off()

    def _write_bit(self, bit: int) -> None:
        """Write a single bit to the shift register"""
        self.data_pin.value = bool(bit)
        self._tick_clock()

    def set_by_list(self, values: List[Union[int, bool]]) -> None:
        """
        Set outputs using a list of values.
        
        Args:
            values: List of binary values (0/1 or True/False)
        """
        try:
            # Ensure correct length and convert to binary values
            binary_values = []
            for val in values[::-1]:  # Reverse to maintain correct output order
                if isinstance(val, bool):
                    binary_values.append(1 if val else 0)
                elif val in (0, 1):
                    binary_values.append(val)
                else:
                    raise ValueError("Values must be 0, 1, or boolean")
            
            # Pad or truncate to match register size
            target_length = 8 * self.daisy_chain
            binary_values = binary_values[:target_length]
            binary_values.extend([0] * (target_length - len(binary_values)))
            
            # Write data
            for bit in binary_values:
                self._write_bit(bit)
            
            self._latch_data()
            self.current = binary_values[::-1]  # Store in original order
            
        except Exception as e:
            logger.error(f"Error setting values: {e}")
            raise

    def clear(self) -> None:
        """Clear all outputs to zero"""
        try:
            self.set_by_list([0] * 8 * self.daisy_chain)
        except Exception as e:
            logger.error(f"Error clearing registers: {e}")

    def cleanup(self) -> None:
        """Clean up GPIO resources"""
        try:
            self.clear()
            self.data_pin.close()
            self.latch_pin.close()
            self.clock_pin.close()
            logger.info("74HC595 cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")