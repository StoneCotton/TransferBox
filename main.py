# main.py

import sys
import logging

from src.core.config_manager import ConfigManager
from src.core.logger_setup import setup_logging
from src.cli.argument_parser import parse_arguments
from src.cli.application_factory import run_benchmark, run_application, validate_arguments

# Initialize configuration first
config_manager = ConfigManager()
config = config_manager.load_config()

# Now initialize logging with config settings
logger = setup_logging(
    log_level=getattr(logging, config.log_level),  # Convert string level to logging constant
    log_format='%(message)s',
    log_file_rotation=config.log_file_rotation,
    log_file_max_size=config.log_file_max_size
)

def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Validate arguments
    is_valid, error_message = validate_arguments(args)
    if not is_valid:
        print(f"Error: {error_message}")
        return 1
    
    # Route to appropriate handler
    if args.benchmark:
        return run_benchmark(args)
    
    return run_application(args)

if __name__ == "__main__":
    sys.exit(main())