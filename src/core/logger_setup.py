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
    """Setup logging configuration."""
    try:
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.handlers.clear()
        
        formatter = logging.Formatter(log_format)
        
        if log_dir is None:
            log_dir = Path.cwd()
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'transferbox_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Create a custom console handler that can be enabled/disabled
        class TransferConsoleHandler(logging.StreamHandler):
            def __init__(self):
                super().__init__(sys.stdout)
                self.transfer_mode = False
                
            def emit(self, record):
                if not self.transfer_mode:
                    super().emit(record)
        
        console_handler = TransferConsoleHandler()
        console_handler.setLevel(console_level if console_level is not None else log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Store handler reference for mode switching
        logger.console_handler = console_handler
        
        logger.info(f"Log file created at: {log_file}")
        logger.info(f"Logging level: {logging.getLevelName(log_level)}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        
        return logger
        
    except Exception as e:
        print(f"Failed to set up logging: {e}", file=sys.stderr)
        raise