# src/core/logger_setup.py

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import sys
import os
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(
    log_dir: Optional[Path] = None,
    log_level: int = logging.DEBUG,
    log_format: str = '%(message)s',  # Simplified format for Rich
    console_level: Optional[int] = None
) -> logging.Logger:
    """Setup logging configuration with Rich integration."""
    try:
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.handlers.clear()
        
        # Create logs directory in project root
        if log_dir is None:
            project_dir = Path(__file__).parent.parent  # Go up two levels from core/
            log_dir = project_dir / 'logs'
        
        # Create logs directory if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'transferbox_{timestamp}.log'
        
        # File handler keeps detailed format
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Create Rich handler for console output
        console = Console()
        rich_handler = RichHandler(
            console=console,
            show_time=False,  # Rich will add its own timestamps
            show_path=False,  # Don't show file paths in console
            enable_link_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            level=console_level if console_level is not None else log_level
        )
        rich_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(rich_handler)
        
        # Log initial setup information
        logger.info(f"Log file created at: {log_file}")
        logger.info(f"Logging level: {logging.getLevelName(log_level)}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")
        
        return logger
        
    except Exception as e:
        print(f"Failed to set up logging: {e}", file=sys.stderr)
        raise