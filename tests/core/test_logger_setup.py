# tests/core/test_logger_setup.py
import pytest
import logging
import os
from pathlib import Path
from src.core.logger_setup import setup_logging

@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for log files"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir

def test_logger_initialization(temp_log_dir):
    """Test basic logger initialization"""
    logger = setup_logging(log_dir=temp_log_dir)
    
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2  # File handler and console handler
    
    # Verify handler types
    handlers = logger.handlers
    assert any(isinstance(h, logging.FileHandler) for h in handlers)
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)

def test_log_file_creation(temp_log_dir):
    """Test that log file is created with correct pattern"""
    logger = setup_logging(log_dir=temp_log_dir)
    
    # Check that exactly one log file was created
    log_files = list(temp_log_dir.glob("transferbox_*.log"))
    assert len(log_files) == 1
    
    # Verify log file name pattern
    log_file = log_files[0]
    assert log_file.name.startswith("transferbox_")
    assert log_file.name.endswith(".log")
    assert len(log_file.name) > len("transferbox_.log")  # Has timestamp

def test_log_file_content(temp_log_dir):
    """Test that logging actually writes to file"""
    logger = setup_logging(log_dir=temp_log_dir)
    
    test_message = "Test log message"
    logger.info(test_message)
    
    # Get the created log file
    log_file = next(temp_log_dir.glob("transferbox_*.log"))
    
    # Read the file content
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert test_message in content

def test_custom_log_level(temp_log_dir):
    """Test setting custom log level"""
    logger = setup_logging(log_dir=temp_log_dir, log_level=logging.WARNING)
    
    assert logger.level == logging.WARNING
    
    # Test that DEBUG messages don't get logged
    debug_message = "Debug message"
    logger.debug(debug_message)
    
    # Test that WARNING messages do get logged
    warning_message = "Warning message"
    logger.warning(warning_message)
    
    log_file = next(temp_log_dir.glob("transferbox_*.log"))
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert debug_message not in content
    assert warning_message in content

def test_console_handler_toggle(temp_log_dir):
    """Test enabling/disabling console output"""
    logger = setup_logging(log_dir=temp_log_dir)
    
    # Initially, transfer_mode should be False
    assert not logger.console_handler.transfer_mode
    
    # Enable transfer mode
    logger.console_handler.transfer_mode = True
    assert logger.console_handler.transfer_mode
    
    # Disable transfer mode
    logger.console_handler.transfer_mode = False
    assert not logger.console_handler.transfer_mode

def test_custom_log_format(temp_log_dir):
    """Test custom log format"""
    custom_format = '%(levelname)s - %(message)s'
    logger = setup_logging(log_dir=temp_log_dir, log_format=custom_format)
    
    test_message = "Test message"
    logger.info(test_message)
    
    log_file = next(temp_log_dir.glob("transferbox_*.log"))
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert f"INFO - {test_message}" in content

def test_multiple_logger_setup(temp_log_dir):
    """Test that multiple setup calls don't create duplicate handlers"""
    logger1 = setup_logging(log_dir=temp_log_dir)
    initial_handler_count = len(logger1.handlers)
    
    # Setup again
    logger2 = setup_logging(log_dir=temp_log_dir)
    
    assert len(logger2.handlers) == initial_handler_count
    assert logger1 is logger2  # Should return same logger instance

@pytest.mark.parametrize("log_level,message_level,should_log", [
    (logging.DEBUG, logging.DEBUG, True),      # DEBUG logs DEBUG
    (logging.INFO, logging.DEBUG, False),      # INFO doesn't log DEBUG
    (logging.WARNING, logging.DEBUG, False),   # WARNING doesn't log DEBUG
    (logging.ERROR, logging.DEBUG, False),     # ERROR doesn't log DEBUG
    (logging.CRITICAL, logging.DEBUG, False),  # CRITICAL doesn't log DEBUG
    (logging.INFO, logging.INFO, True),        # INFO logs INFO
    (logging.WARNING, logging.INFO, False),    # WARNING doesn't log INFO
    (logging.DEBUG, logging.INFO, True),       # DEBUG logs INFO
])
def test_log_levels(temp_log_dir, log_level, message_level, should_log):
    """Test different log levels"""
    logger = setup_logging(log_dir=temp_log_dir, log_level=log_level)

    test_message = f"Test message for level {logging.getLevelName(message_level)}"
    
    # Log the message at the appropriate level
    if message_level == logging.DEBUG:
        logger.debug(test_message)
    elif message_level == logging.INFO:
        logger.info(test_message)
    elif message_level == logging.WARNING:
        logger.warning(test_message)
    elif message_level == logging.ERROR:
        logger.error(test_message)
    elif message_level == logging.CRITICAL:
        logger.critical(test_message)

    # Give a small delay to ensure file writing is complete
    import time
    time.sleep(0.1)

def test_error_handling(tmp_path):
    """Test error handling when log directory creation fails"""
    # Create a file with the same name as our intended log directory
    bad_log_dir = tmp_path / "logs"
    bad_log_dir.touch()  # Create as file instead of directory
    
    with pytest.raises(Exception):
        setup_logging(log_dir=bad_log_dir)

def test_file_encoding(temp_log_dir):
    """Test that logs are written with UTF-8 encoding"""
    logger = setup_logging(log_dir=temp_log_dir)
    
    # Test with non-ASCII characters
    test_message = "Testing UTF-8 encoding: こんにちは 你好 안녕하세요"
    logger.info(test_message)
    
    log_file = next(temp_log_dir.glob("transferbox_*.log"))
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert test_message in content