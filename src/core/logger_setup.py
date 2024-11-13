# src/core/logger_setup.py

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import sys
import os

def setup_logging(
    log_dir: Optional[Path] = None,
    log_level: int = logging.DEBUG,
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    console_level: Optional[int] = None
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        log_dir: Directory for log files. Defaults to current working directory
        log_level: Logging level for file handler
        log_format: Format string for log messages
        console_level: Console output level. If None, uses log_level
        
    Returns:
        Configured logger instance
    """
    try:
        # Get the root logger
        logger = logging.getLogger()
        logger.setLevel(log_level)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(log_format)
        
        # Use current working directory if log_dir not specified
        if log_dir is None:
            log_dir = Path.cwd()
            
        # Create log filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'transferbox_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Set up console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level if console_level is not None else log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Log initial setup information
        logger.info(f"Log file created at: {log_file}")
        logger.info(f"Logging level: {logging.getLevelName(log_level)}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        
        if os.environ.get('USER'):
            logger.info(f"User: {os.environ['USER']}")
            
        return logger
        
    except Exception as e:
        print(f"Failed to set up logging: {e}", file=sys.stderr)
        raise