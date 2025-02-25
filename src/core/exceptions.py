# core/exceptions.py

class TransferBoxError(Exception):
    """Base exception for all TransferBox errors"""
    pass

class ConfigError(TransferBoxError):
    """Configuration related errors"""
    pass

class StorageError(TransferBoxError):
    """Storage device related errors"""
    
    def __init__(self, message, path=None, device=None, *args):
        self.path = path
        self.device = device
        super().__init__(message, *args)

class FileTransferError(TransferBoxError):
    """File transfer related errors"""
    
    def __init__(self, message, source=None, destination=None, *args):
        self.source = source
        self.destination = destination
        super().__init__(message, *args)

class ChecksumError(FileTransferError):
    """Checksum verification errors"""
    
    def __init__(self, message, file_path=None, expected=None, actual=None, *args):
        self.file_path = file_path
        self.expected = expected
        self.actual = actual
        super().__init__(message, *args)

class HardwareError(TransferBoxError):
    """Hardware related errors (Raspberry Pi specific)"""
    pass

class StateError(TransferBoxError):
    """State transition related errors"""
    pass

class DisplayError(TransferBoxError):
    """Display related errors"""
    pass

class SoundError(TransferBoxError):
    """Sound related errors"""