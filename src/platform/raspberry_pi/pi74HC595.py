# src/platform/raspberry_pi/pi74HC595.py

import logging
from typing import List, Union
import RPi.GPIO as gpio

logger = logging.getLogger(__name__)

class pi74HC595:
    """Controls 74HC595 shift register(s) on Raspberry Pi"""
    
    def __init__(
        self,
        DS: int = 11,
        ST: int = 13,
        SH: int = 15,
        daisy_chain: int = 1
    ):
        """
        Initialize shift register control.
        
        Args:
            DS: Data pin (GPIO number)
            ST: Storage/latch pin (GPIO number)
            SH: Shift pin (GPIO number)
            daisy_chain: Number of daisy-chained shift registers
            
        Raises:
            ValueError: If pin numbers are invalid
        """
        self.gpio = gpio
        self.gpio.setwarnings(False)
        
        # Set GPIO mode if not already set
        if not self.gpio.getmode():
            self.gpio.setmode(self.gpio.BCM)
        
        # Validate pins
        if not all(isinstance(pin, int) for pin in [DS, ST, SH]):
            raise ValueError("Pins must be integers")
            
        if not all(1 <= pin <= 40 for pin in [DS, ST, SH]):
            raise ValueError("Pin numbers must be between 1 and 40")
            
        if not isinstance(daisy_chain, int) or daisy_chain < 1:
            raise ValueError("daisy_chain must be a positive integer")

        self.data = DS       # DS pin
        self.parallel = ST   # ST_CP pin
        self.serial = SH     # SH_CP pin
        self.daisy_chain = daisy_chain
        self.current = [0] * (8 * self.daisy_chain)  # Current state
        
        self._setup_board()
        self.clear()

    def _setup_board(self) -> None:
        """Setup GPIO pins for shift register control"""
        try:
            for pin, initial in [
                (self.data, gpio.LOW),
                (self.parallel, gpio.LOW),
                (self.serial, gpio.LOW)
            ]:
                self.gpio.setup(pin, gpio.OUT)
                self.gpio.output(pin, initial)
                
        except Exception as e:
            logger.error(f"Failed to setup GPIO pins: {e}")
            raise

    def _output(self) -> None:
        """Trigger storage/latch (ST_CP)"""
        gpio.output(self.parallel, gpio.HIGH)
        gpio.output(self.parallel, gpio.LOW)

    def _tick(self) -> None:
        """Trigger shift register clock (SH_CP)"""
        gpio.output(self.serial, gpio.HIGH)
        gpio.output(self.serial, gpio.LOW)

    def _set_values(self, values: List[int]) -> None:
        """
        Set shift register values.
        
        Args:
            values: List of binary values (0 or 1)
        """
        try:
            for bit in values:
                self.current.append(bit)
                del self.current[0]
                gpio.output(self.data, gpio.HIGH if bit == 1 else gpio.LOW)
                self._tick()
            self._output()
            
        except Exception as e:
            logger.error(f"Failed to set values: {e}")
            raise

    def set_pin(self, pin_type: str, pin: int) -> None:
        """
        Set a specific pin configuration.
        
        Args:
            pin_type: Type of pin ('ds', 'sh', or 'st')
            pin: GPIO pin number
            
        Raises:
            ValueError: If pin number is invalid
        """
        if not isinstance(pin, int):
            raise ValueError("Pin must be an integer")
            
        if not 1 <= pin <= 40:
            raise ValueError("Pin must be between 1 and 40")
            
        pin_map = {
            'ds': 'data',
            'sh': 'serial',
            'st': 'parallel'
        }
        
        if pin_type.lower() in pin_map:
            setattr(self, pin_map[pin_type.lower()], pin)
        else:
            raise ValueError("Invalid pin type. Must be 'ds', 'sh', or 'st'")

    def set_daisy_chain(self, num: int) -> None:
        """
        Set number of daisy-chained shift registers.
        
        Args:
            num: Number of shift registers
            
        Raises:
            ValueError: If number is invalid
        """
        if not isinstance(num, int) or num < 1:
            raise ValueError("Number of shift registers must be a positive integer")
            
        self.daisy_chain = num
        self.current = [0] * (8 * self.daisy_chain)

    def set_by_list(self, values: List[Union[int, bool]]) -> None:
        """
        Set outputs using a list of values.
        
        Args:
            values: List of binary values (0/1 or True/False)
            
        Raises:
            ValueError: If values are invalid
        """
        if not isinstance(values, list):
            raise ValueError("Values must be provided as a list")

        # Reverse list to correct output order
        values = values[::-1]
        
        # Convert bools to ints
        processed_values = []
        for val in values:
            if isinstance(val, bool):
                processed_values.append(1 if val else 0)
            elif val in (0, 1):
                processed_values.append(val)
            else:
                raise ValueError("Values must be 0, 1, or boolean")
                
        self._set_values(processed_values)

    def set_by_int(self, value: int) -> None:
        """
        Set outputs using an integer value.
        
        Args:
            value: Integer to convert to binary
            
        Raises:
            ValueError: If value is invalid
        """
        if not isinstance(value, int):
            raise ValueError("Value must be an integer")
            
        if value < 0:
            raise ValueError("Value cannot be negative")
            
        self._set_values(list(map(int, bin(value)[2:])))

    def set_by_bool(self, value: bool) -> None:
        """
        Set output using a boolean value.
        
        Args:
            value: Boolean value to set
            
        Raises:
            ValueError: If value is not boolean
        """
        if not isinstance(value, bool):
            raise ValueError("Value must be boolean")
            
        self._set_values([1 if value else 0])

    def get_values(self) -> List[int]:
        """
        Get current shift register values.
        
        Returns:
            List of current output states
        """
        return self.current.copy()

    def clear(self) -> None:
        """Clear all outputs to zero"""
        self._set_values([0] * 8 * self.daisy_chain)

    def cleanup(self) -> None:
        """Clean up GPIO resources"""
        try:
            self.gpio.cleanup([self.data, self.parallel, self.serial])
            logger.debug("GPIO cleanup completed")
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")