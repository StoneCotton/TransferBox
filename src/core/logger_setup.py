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
    logger = None
    file_handler = None
    
    try:
        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.handlers.clear()
        
        # Resolve log directory path
        try:
            if log_dir is None:
                try:
                    project_dir = Path(__file__).parent.parent  # Go up two levels from core/
                    log_dir = project_dir / 'logs'
                except (NameError, ValueError, AttributeError) as path_err:
                    print(f"Error resolving project directory: {path_err}", file=sys.stderr)
                    # Fallback to current directory if path resolution fails
                    log_dir = Path.cwd() / 'logs'
                    print(f"Using fallback log directory: {log_dir}", file=sys.stderr)
        except Exception as e:
            print(f"Error setting log directory: {e}", file=sys.stderr)
            # Last resort fallback
            log_dir = Path.cwd() / 'logs'
            
        # Create logs directory if it doesn't exist
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as perm_err:
            print(f"Permission denied creating log directory {log_dir}: {perm_err}", file=sys.stderr)
            # Try user's home directory as fallback
            log_dir = Path.home() / 'transferbox_logs'
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                print(f"Using fallback log directory in home folder: {log_dir}", file=sys.stderr)
            except Exception as home_err:
                print(f"Failed to create fallback log directory: {home_err}", file=sys.stderr)
                # Continue without file logging
                log_dir = None
        except OSError as os_err:
            print(f"OS error creating log directory {log_dir}: {os_err}", file=sys.stderr)
            log_dir = None
        
        # Create log file if directory is available
        if log_dir is not None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f'transferbox_{timestamp}.log'
            
            # Setup file handler with error handling
            try:
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(log_level)
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except PermissionError as perm_err:
                print(f"Permission denied creating log file {log_file}: {perm_err}", file=sys.stderr)
            except OSError as os_err:
                print(f"OS error creating log file {log_file}: {os_err}", file=sys.stderr)
        
        # Setup console handler with Rich if available
        try:
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
        except ImportError as imp_err:
            print(f"Rich library not available, using standard console handler: {imp_err}", file=sys.stderr)
            # Fallback to standard StreamHandler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(console_level if console_level is not None else log_level)
            console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(console_handler)
        except Exception as rich_err:
            print(f"Error setting up Rich handler: {rich_err}", file=sys.stderr)
            # Fallback to standard StreamHandler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(console_level if console_level is not None else log_level)
            console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(console_handler)
        
        # Log initial setup information if we have a working logger
        if logger.handlers:
            if file_handler is not None and file_handler in logger.handlers:
                logger.info(f"Log file created at: {log_file}")
            logger.info(f"Logging level: {logging.getLevelName(log_level)}")
            logger.info(f"Python version: {sys.version}")
            logger.info(f"Platform: {sys.platform}")
        
        return logger
        
    except Exception as e:
        print(f"Failed to set up logging: {e}", file=sys.stderr)
        # If we've partially set up logging, try to use it for the error
        if logger and logger.handlers:
            try:
                logger.critical(f"Critical error during logging setup: {e}", exc_info=True)
            except:
                pass  # Last resort, already printing to stderr
        
        # Create minimal fallback logger if everything else fails
        if logger is None:
            fallback_logger = logging.getLogger()
            fallback_logger.setLevel(logging.WARNING)
            
            if not fallback_logger.handlers:
                fallback_handler = logging.StreamHandler(sys.stderr)
                fallback_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
                fallback_logger.addHandler(fallback_handler)
            
            return fallback_logger
        
        raise