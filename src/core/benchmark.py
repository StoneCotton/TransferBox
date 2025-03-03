import logging
import time
import statistics
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os
import shutil
import random
import xxhash
from dataclasses import dataclass, field

from .config_manager import ConfigManager, TransferConfig
from .interfaces.display import DisplayInterface
from .interfaces.storage_inter import StorageInterface
from .interfaces.types import TransferProgress, TransferStatus
from .file_transfer import FileTransfer
from .state_manager import StateManager

logger = logging.getLogger(__name__)

@dataclass
class BenchmarkResult:
    """Stores results from a single benchmark run"""
    buffer_size: int  # in bytes
    transfer_speed: float  # in MB/s
    file_size: int  # in bytes
    duration: float  # in seconds
    checksum_duration: float  # in seconds
    verification_duration: float  # in seconds
    total_duration: float  # in seconds
    success: bool = True
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs"""
    buffer_sizes: List[int] = field(default_factory=lambda: [
        1 * 1024 * 1024,      # 1MB
        4 * 1024 * 1024,      # 4MB
        8 * 1024 * 1024,      # 8MB
        16 * 1024 * 1024,     # 16MB
        32 * 1024 * 1024,     # 32MB
        64 * 1024 * 1024,     # 64MB
        128 * 1024 * 1024,    # 128MB
    ])
    test_file_sizes: List[int] = field(default_factory=lambda: [
        500 * 1024 * 1024,    # 500MB
        4096 * 1024 * 1024,   # 4GB
    ])
    iterations: int = 3
    cleanup_after_run: bool = True
    generate_plots: bool = True
    output_dir: Path = Path("benchmark_results")


class TransferBenchmark:
    """Benchmarks file transfer performance with different buffer sizes"""
    
    def __init__(
        self, 
        display: DisplayInterface,
        storage: StorageInterface,
        config: Optional[TransferConfig] = None,
        benchmark_config: Optional[BenchmarkConfig] = None
    ):
        """
        Initialize the benchmark system.
        
        Args:
            display: Display interface for showing progress
            storage: Storage interface for file operations
            config: Optional TransferBox configuration
            benchmark_config: Optional benchmark configuration
        """
        self.display = display
        self.storage = storage
        self.config = config or ConfigManager().load_config()
        self.benchmark_config = benchmark_config or BenchmarkConfig()
        
        # Create a state manager for the file transfer
        self.state_manager = StateManager(display)
        
        # Ensure output directory exists
        self.benchmark_config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare temp directories
        self.temp_dir = Path("/tmp/transferbox_benchmark") if os.name == "posix" else Path("C:/temp/transferbox_benchmark")
        self.source_dir = self.temp_dir / "source"
        self.dest_dir = self.temp_dir / "destination"
        
        # Create directories
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)
    
    def create_test_file(self, size_bytes: int) -> Path:
        """
        Create a test file of specified size with random data.
        
        Args:
            size_bytes: Size of the test file in bytes
            
        Returns:
            Path to the created test file
        """
        filename = f"test_file_{size_bytes // (1024 * 1024)}MB.bin"
        file_path = self.source_dir / filename
        
        # Check if file already exists with correct size
        if file_path.exists() and file_path.stat().st_size == size_bytes:
            logger.info(f"Using existing test file: {file_path}")
            return file_path
        
        # Create new file with random data
        logger.info(f"Creating test file: {file_path} ({size_bytes // (1024 * 1024)}MB)")
        
        # Use a buffer to write in chunks to avoid memory issues
        buffer_size = min(64 * 1024 * 1024, size_bytes)  # 64MB or file size if smaller
        remaining = size_bytes
        
        with open(file_path, 'wb') as f:
            while remaining > 0:
                chunk_size = min(buffer_size, remaining)
                f.write(os.urandom(chunk_size))
                remaining -= chunk_size
                
                # Show progress
                progress = (size_bytes - remaining) / size_bytes * 100
                logger.info(f"Creating test file: {progress:.1f}% complete")
        
        return file_path
    
    def run_single_benchmark(
        self, 
        buffer_size: int, 
        test_file: Path
    ) -> BenchmarkResult:
        """
        Run a single benchmark with specified buffer size and test file.
        
        Args:
            buffer_size: Buffer size to use for transfer in bytes
            test_file: Path to the test file
            
        Returns:
            BenchmarkResult with performance metrics
        """
        # Clear destination directory
        for item in self.dest_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        
        # Create a file transfer instance with custom buffer size
        file_transfer = FileTransfer(
            self.state_manager,
            self.display,
            self.storage,
            self.config
        )
        
        # Override the buffer size in the file copy method
        original_copy_method = file_transfer._perform_file_copy
        
        def patched_copy_method(self, src_path, dst_path, file_size, hash_obj, file_number, total_files, total_transferred):
            # Override buffer size in the file copy method
            chunk_size = buffer_size
            
            try:
                with open(src_path, 'rb') as src_file, open(dst_path, 'wb') as dst_file:
                    bytes_copied = 0
                    
                    while True:
                        chunk = src_file.read(chunk_size)
                        if not chunk:
                            break
                            
                        dst_file.write(chunk)
                        hash_obj.update(chunk)
                        
                        bytes_copied += len(chunk)
                        file_transfer._update_copy_progress(
                            bytes_copied, file_size, total_transferred + bytes_copied,
                            file_number, total_files
                        )
                
                return True
            except Exception as e:
                logger.error(f"Error during patched file copy: {e}")
                return False
        
        # Apply the monkey patch
        file_transfer._perform_file_copy = patched_copy_method.__get__(file_transfer, FileTransfer)
        
        # Prepare result object
        result = BenchmarkResult(
            buffer_size=buffer_size,
            file_size=test_file.stat().st_size,
            transfer_speed=0.0,
            duration=0.0,
            checksum_duration=0.0,
            verification_duration=0.0,
            total_duration=0.0
        )
        
        try:
            # Enter transfer state
            self.state_manager.enter_transfer()
            
            # Start timing
            start_time = time.time()
            checksum_start = start_time
            
            # Calculate source checksum
            hash_obj = xxhash.xxh64()
            with open(test_file, 'rb') as f:
                while True:
                    chunk = f.read(buffer_size)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
            
            checksum = hash_obj.hexdigest()
            checksum_end = time.time()
            result.checksum_duration = checksum_end - checksum_start
            
            # Perform the transfer
            dest_file = self.dest_dir / test_file.name
            transfer_start = time.time()
            
            # Create a progress object for display
            progress = TransferProgress(
                current_file=test_file.name,
                file_number=1,
                total_files=1,
                bytes_transferred=0,
                total_bytes=result.file_size,
                total_transferred=0,
                total_size=result.file_size,
                current_file_progress=0.0,
                overall_progress=0.0,
                status=TransferStatus.COPYING
            )
            
            # Display initial progress
            self.display.show_progress(progress)
            
            # Perform the actual copy
            success = file_transfer._perform_file_copy(
                test_file, dest_file, result.file_size, xxhash.xxh64(),
                1, 1, 0
            )
            
            transfer_end = time.time()
            result.duration = transfer_end - transfer_start
            
            # Verify the transfer
            verify_start = time.time()
            verification_success = file_transfer._verify_file_checksum(dest_file, checksum)
            verify_end = time.time()
            result.verification_duration = verify_end - verify_start
            
            # Calculate total duration and transfer speed
            result.total_duration = verify_end - start_time
            result.transfer_speed = (result.file_size / (1024 * 1024)) / result.duration  # MB/s
            
            # Check success
            result.success = success and verification_success
            if not result.success:
                result.error = "Transfer or verification failed"
            
            # Exit transfer state
            self.state_manager.exit_transfer()
            
            # Restore original method
            file_transfer._perform_file_copy = original_copy_method
            
            return result
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            result.success = False
            result.error = str(e)
            
            # Exit transfer state
            self.state_manager.exit_transfer()
            
            # Restore original method
            file_transfer._perform_file_copy = original_copy_method
            
            return result
    
    def run_benchmarks(self) -> Dict[str, List[BenchmarkResult]]:
        """
        Run benchmarks with all configured buffer sizes and file sizes.
        
        Returns:
            Dictionary mapping file sizes to lists of benchmark results
        """
        results: Dict[str, List[BenchmarkResult]] = {}
        
        for file_size in self.benchmark_config.test_file_sizes:
            size_key = f"{file_size // (1024 * 1024)}MB"
            results[size_key] = []
            
            # Create test file
            test_file = self.create_test_file(file_size)
            
            for buffer_size in self.benchmark_config.buffer_sizes:
                buffer_key = f"{buffer_size // (1024 * 1024)}MB"
                logger.info(f"Running benchmark with {buffer_key} buffer on {size_key} file")
                
                # Run multiple iterations
                iteration_results = []
                for i in range(self.benchmark_config.iterations):
                    logger.info(f"Iteration {i+1}/{self.benchmark_config.iterations}")
                    result = self.run_single_benchmark(buffer_size, test_file)
                    iteration_results.append(result)
                    
                    # Log result
                    if result.success:
                        logger.info(f"Transfer speed: {result.transfer_speed:.2f} MB/s")
                    else:
                        logger.error(f"Benchmark failed: {result.error}")
                
                # Calculate average result
                avg_result = BenchmarkResult(
                    buffer_size=buffer_size,
                    file_size=file_size,
                    transfer_speed=statistics.mean(r.transfer_speed for r in iteration_results if r.success),
                    duration=statistics.mean(r.duration for r in iteration_results if r.success),
                    checksum_duration=statistics.mean(r.checksum_duration for r in iteration_results if r.success),
                    verification_duration=statistics.mean(r.verification_duration for r in iteration_results if r.success),
                    total_duration=statistics.mean(r.total_duration for r in iteration_results if r.success),
                    success=all(r.success for r in iteration_results)
                )
                
                results[size_key].append(avg_result)
        
        # Save results
        self.save_results(results)
        
        # Generate plots if enabled
        if self.benchmark_config.generate_plots:
            self.generate_plots(results)
        
        # Clean up if configured
        if self.benchmark_config.cleanup_after_run:
            self.cleanup()
        
        return results
    
    def save_results(self, results: Dict[str, List[BenchmarkResult]]) -> None:
        """
        Save benchmark results to a JSON file.
        
        Args:
            results: Dictionary of benchmark results
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.benchmark_config.output_dir / f"benchmark_results_{timestamp}.json"
        
        # Convert results to serializable format
        serializable_results = {}
        for file_size, result_list in results.items():
            serializable_results[file_size] = [
                {
                    "buffer_size": r.buffer_size,
                    "buffer_size_mb": r.buffer_size / (1024 * 1024),
                    "file_size": r.file_size,
                    "file_size_mb": r.file_size / (1024 * 1024),
                    "transfer_speed": r.transfer_speed,
                    "duration": r.duration,
                    "checksum_duration": r.checksum_duration,
                    "verification_duration": r.verification_duration,
                    "total_duration": r.total_duration,
                    "success": r.success,
                    "error": r.error,
                    "timestamp": r.timestamp
                }
                for r in result_list
            ]
        
        # Save to file
        with open(result_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Benchmark results saved to {result_file}")
    
    def generate_plots(self, results: Dict[str, List[BenchmarkResult]]) -> None:
        """
        Generate plots from benchmark results.
        
        Args:
            results: Dictionary of benchmark results
        """
        try:
            import matplotlib.pyplot as plt
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create a plot for each file size
            for file_size, result_list in results.items():
                if not result_list:
                    continue
                
                # Sort results by buffer size
                result_list.sort(key=lambda r: r.buffer_size)
                
                # Extract data for plotting
                buffer_sizes = [r.buffer_size / (1024 * 1024) for r in result_list]  # Convert to MB
                transfer_speeds = [r.transfer_speed for r in result_list]
                
                # Create plot
                plt.figure(figsize=(10, 6))
                plt.plot(buffer_sizes, transfer_speeds, 'o-', linewidth=2)
                plt.xlabel('Buffer Size (MB)')
                plt.ylabel('Transfer Speed (MB/s)')
                plt.title(f'Transfer Speed vs Buffer Size for {file_size} File')
                plt.grid(True)
                
                # Add data labels
                for i, (x, y) in enumerate(zip(buffer_sizes, transfer_speeds)):
                    plt.annotate(f"{y:.1f} MB/s", (x, y), textcoords="offset points", 
                                xytext=(0, 10), ha='center')
                
                # Save plot
                plot_file = self.benchmark_config.output_dir / f"benchmark_plot_{file_size}_{timestamp}.png"
                plt.savefig(plot_file)
                plt.close()
                
                logger.info(f"Plot saved to {plot_file}")
            
            # Create a combined plot
            plt.figure(figsize=(12, 8))
            
            for file_size, result_list in results.items():
                if not result_list:
                    continue
                
                # Sort results by buffer size
                result_list.sort(key=lambda r: r.buffer_size)
                
                # Extract data for plotting
                buffer_sizes = [r.buffer_size / (1024 * 1024) for r in result_list]  # Convert to MB
                transfer_speeds = [r.transfer_speed for r in result_list]
                
                plt.plot(buffer_sizes, transfer_speeds, 'o-', linewidth=2, label=file_size)
            
            plt.xlabel('Buffer Size (MB)')
            plt.ylabel('Transfer Speed (MB/s)')
            plt.title('Transfer Speed vs Buffer Size for Different File Sizes')
            plt.grid(True)
            plt.legend()
            
            # Save combined plot
            combined_plot_file = self.benchmark_config.output_dir / f"benchmark_plot_combined_{timestamp}.png"
            plt.savefig(combined_plot_file)
            plt.close()
            
            logger.info(f"Combined plot saved to {combined_plot_file}")
            
        except ImportError:
            logger.warning("Matplotlib not available, skipping plot generation")
        except Exception as e:
            logger.error(f"Error generating plots: {e}")
    
    def cleanup(self) -> None:
        """Clean up temporary files and directories"""
        try:
            logger.info("Cleaning up benchmark files")
            
            # Remove temporary directory
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                
            logger.info("Cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def run_benchmark_cli():
    """Command-line interface for running benchmarks"""
    import argparse
    from src.core.logger_setup import setup_logging
    from src.core.platform_manager import PlatformManager
    
    # Setup logging
    logger = setup_logging()
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="TransferBox Benchmark Tool")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per test")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't clean up test files after benchmark")
    parser.add_argument("--no-plots", action="store_true", help="Don't generate plots")
    parser.add_argument("--output-dir", type=str, help="Output directory for results")
    
    args = parser.parse_args()
    
    # Create benchmark config
    benchmark_config = BenchmarkConfig()
    
    if args.buffer_sizes:
        buffer_sizes = [int(size) * 1024 * 1024 for size in args.buffer_sizes.split(",")]
        benchmark_config.buffer_sizes = buffer_sizes
    
    if args.file_sizes:
        file_sizes = [int(size) * 1024 * 1024 for size in args.file_sizes.split(",")]
        benchmark_config.test_file_sizes = file_sizes
    
    if args.iterations:
        benchmark_config.iterations = args.iterations
    
    if args.no_cleanup:
        benchmark_config.cleanup_after_run = False
    
    if args.no_plots:
        benchmark_config.generate_plots = False
    
    if args.output_dir:
        benchmark_config.output_dir = Path(args.output_dir)
    
    # Initialize platform components
    try:
        display = PlatformManager.create_display()
        storage = PlatformManager.create_storage()
        
        # Create and run benchmark
        benchmark = TransferBenchmark(
            display=display,
            storage=storage,
            benchmark_config=benchmark_config
        )
        
        results = benchmark.run_benchmarks()
        
        # Print summary
        print("\nBenchmark Summary:")
        for file_size, result_list in results.items():
            print(f"\nFile Size: {file_size}")
            print("-" * 80)
            print(f"{'Buffer Size (MB)':<15} {'Transfer Speed (MB/s)':<20} {'Duration (s)':<15} {'Total Time (s)':<15}")
            print("-" * 80)
            
            for result in sorted(result_list, key=lambda r: r.buffer_size):
                buffer_mb = result.buffer_size / (1024 * 1024)
                print(f"{buffer_mb:<15.1f} {result.transfer_speed:<20.2f} {result.duration:<15.2f} {result.total_duration:<15.2f}")
        
        # Find optimal buffer size
        optimal_results = {}
        for file_size, result_list in results.items():
            if result_list:
                optimal = max(result_list, key=lambda r: r.transfer_speed)
                optimal_results[file_size] = optimal
        
        print("\nOptimal Buffer Sizes:")
        for file_size, result in optimal_results.items():
            buffer_mb = result.buffer_size / (1024 * 1024)
            print(f"{file_size}: {buffer_mb:.1f}MB buffer - {result.transfer_speed:.2f} MB/s")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_benchmark_cli()) 