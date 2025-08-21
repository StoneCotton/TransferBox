# src/cli/argument_parser.py

import argparse
from src import __version__, __project_name__


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description=f"{__project_name__} v{__version__}")
    
    parser.add_argument(
        "--benchmark", 
        action="store_true", 
        help="Run transfer benchmark"
    )
    
    parser.add_argument(
        "--buffer-sizes", 
        type=str, 
        help="Comma-separated list of buffer sizes in MB for benchmark"
    )
    
    parser.add_argument(
        "--file-sizes", 
        type=str, 
        help="Comma-separated list of file sizes in MB for benchmark"
    )
    
    parser.add_argument(
        "--iterations", 
        type=int, 
        default=3, 
        help="Number of iterations per benchmark test"
    )
    
    parser.add_argument(
        "--webui", 
        action="store_true", 
        help="Start web UI instead of terminal interface"
    )
    
    return parser.parse_args() 