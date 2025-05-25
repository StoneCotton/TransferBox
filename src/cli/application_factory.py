# src/cli/application_factory.py

import sys
import logging

logger = logging.getLogger(__name__)


def run_benchmark(args):
    """
    Run benchmark with specified arguments.
    
    Args:
        args: Parsed command line arguments containing benchmark parameters
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from src.core.benchmark import run_benchmark_cli
    except ImportError as e:
        logger.error(f"Benchmark module not available: {e}")
        print("Error: Benchmark functionality not available")
        return 1
    
    # Prepare sys.argv for benchmark CLI
    original_argv = sys.argv.copy()
    try:
        sys.argv = [sys.argv[0]]
        if args.buffer_sizes:
            sys.argv.extend(["--buffer-sizes", args.buffer_sizes])
        if args.file_sizes:
            sys.argv.extend(["--file-sizes", args.file_sizes])
        if args.iterations:
            sys.argv.extend(["--iterations", str(args.iterations)])
            
        return run_benchmark_cli()
    except Exception as e:
        logger.error(f"Benchmark execution failed: {e}")
        print(f"Error running benchmark: {e}")
        return 1
    finally:
        # Restore original sys.argv
        sys.argv = original_argv


def run_application(args):
    """
    Run the main application with given arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Import the factory from core
        from src.core.transfer_box_factory import create_transfer_box
        
        # Create the appropriate TransferBox instance
        app = create_transfer_box(use_webui=args.webui)
        
        # Run the application
        app.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt")
        return 0
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        print(f"Error: Missing required dependencies: {e}")
        return 1
    except Exception as e:
        logger.error(f"Application execution failed: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1


def validate_arguments(args):
    """
    Validate command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    # Validate benchmark-specific arguments
    if args.benchmark:
        if args.iterations and args.iterations < 1:
            return False, "Iterations must be a positive integer"
        
        if args.buffer_sizes:
            try:
                sizes = [int(x.strip()) for x in args.buffer_sizes.split(',')]
                if any(size <= 0 for size in sizes):
                    return False, "Buffer sizes must be positive integers"
            except ValueError:
                return False, "Buffer sizes must be comma-separated integers"
        
        if args.file_sizes:
            try:
                sizes = [int(x.strip()) for x in args.file_sizes.split(',')]
                if any(size <= 0 for size in sizes):
                    return False, "File sizes must be positive integers"
            except ValueError:
                return False, "File sizes must be comma-separated integers"
    
    return True, "" 