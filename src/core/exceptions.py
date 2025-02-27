# core/exceptions.py

class TransferBoxError(Exception):
    """Base exception for all TransferBox errors"""
    
    def __init__(self, message, recoverable=True, recovery_steps=None, *args):
        self.recoverable = recoverable
        self.recovery_steps = recovery_steps or []
        super().__init__(message, *args)

class ConfigError(TransferBoxError):
    """Configuration related errors"""
    
    def __init__(self, message, config_key=None, invalid_value=None, expected_type=None, *args):
        self.config_key = config_key
        self.invalid_value = invalid_value
        self.expected_type = expected_type
        recovery_steps = ["Check configuration file format", "Verify configuration values"]
        if config_key:
            recovery_steps.append(f"Validate the '{config_key}' setting")
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class StorageError(TransferBoxError):
    """Storage device related errors"""
    
    def __init__(self, message, path=None, device=None, *args, error_type=None):
        self.path = path
        self.device = device
        self.error_type = error_type
        recovery_steps = []
        
        # Infer error type from message if not provided
        if error_type is None:
            if "permission" in message.lower():
                error_type = "permission"
            elif "space" in message.lower():
                error_type = "space"
            elif any(word in message.lower() for word in ["mount", "volume", "drive"]):
                error_type = "mount"
        
        if error_type == "permission":
            recovery_steps = [
                "Check file/directory permissions",
                "Verify user has necessary access rights"
            ]
        elif error_type == "space":
            recovery_steps = [
                "Free up space on the device",
                "Verify sufficient storage capacity"
            ]
        elif error_type == "mount":
            recovery_steps = [
                "Check if device is properly connected",
                "Try remounting the device",
                "Verify device is not in use by another process"
            ]
        else:
            # Default recovery steps for unknown error types
            recovery_steps = [
                "Check device connection",
                "Verify device permissions",
                "Ensure device is properly mounted"
            ]
        
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class FileTransferError(TransferBoxError):
    """File transfer related errors"""
    
    def __init__(self, message, source=None, destination=None, *args, error_type=None):
        self.source = source
        self.destination = destination
        self.error_type = error_type
        recovery_steps = []
        
        # Infer error type from message if not provided
        if error_type is None:
            if any(word in message.lower() for word in ["permission", "access"]):
                error_type = "io"
            elif any(word in message.lower() for word in ["network", "connection"]):
                error_type = "network"
            elif "interrupt" in message.lower():
                error_type = "interrupted"
        
        if error_type == "io":
            recovery_steps = [
                "Check source and destination paths exist",
                "Verify read/write permissions",
                "Ensure sufficient disk space"
            ]
        elif error_type == "network":
            recovery_steps = [
                "Check network connection",
                "Verify network share is accessible",
                "Try reconnecting to the network"
            ]
        elif error_type == "interrupted":
            recovery_steps = [
                "Restart the transfer process",
                "Check for system resource constraints"
            ]
        else:
            # Default recovery steps for unknown error types
            recovery_steps = [
                "Verify source and destination paths",
                "Check file permissions",
                "Ensure sufficient space"
            ]
        
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class ChecksumError(FileTransferError):
    """Checksum verification errors"""
    
    def __init__(self, message, file_path=None, expected=None, actual=None, *args):
        self.file_path = file_path
        self.expected = expected
        self.actual = actual
        recovery_steps = [
            "Verify source file integrity",
            "Retry the transfer process",
            "Check for transfer medium errors"
        ]
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class HardwareError(TransferBoxError):
    """Hardware related errors (Raspberry Pi specific)"""
    
    def __init__(self, message, component=None, error_type=None, *args):
        self.component = component
        self.error_type = error_type
        recovery_steps = []
        
        if component == "display":
            recovery_steps = [
                "Check display connections",
                "Verify display power",
                "Restart the display service"
            ]
        elif component == "button":
            recovery_steps = [
                "Check button connections",
                "Verify GPIO configuration",
                "Test button hardware"
            ]
        elif component == "led":
            recovery_steps = [
                "Check LED connections",
                "Verify GPIO configuration",
                "Test LED functionality"
            ]
        else:
            # Default recovery steps for unknown components
            recovery_steps = [
                "Check hardware connections",
                "Verify power supply",
                "Test component functionality"
            ]
        
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class StateError(TransferBoxError):
    """State transition related errors"""
    
    def __init__(self, message, current_state=None, target_state=None, *args):
        self.current_state = current_state
        self.target_state = target_state
        recovery_steps = [
            "Return to standby state",
            "Check system status",
            "Verify state transition requirements"
        ]
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class DisplayError(TransferBoxError):
    """Display related errors"""
    
    def __init__(self, message, display_type=None, error_type=None, *args):
        self.display_type = display_type
        self.error_type = error_type
        recovery_steps = [
            "Check display hardware connection",
            "Verify display service status",
            "Restart display interface"
        ]
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)

class SoundError(TransferBoxError):
    """Sound related errors"""
    
    def __init__(self, message, sound_type=None, error_type=None, *args):
        self.sound_type = sound_type
        self.error_type = error_type
        recovery_steps = [
            "Check audio hardware connection",
            "Verify audio service status",
            "Test system sound"
        ]
        super().__init__(message, recoverable=True, recovery_steps=recovery_steps, *args)