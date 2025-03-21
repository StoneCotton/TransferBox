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
from .file_operations import FileOperations, CHUNK_SIZE, BUFFER_SIZE
from .progress_tracker import ProgressTracker
from .checksum import ChecksumCalculator

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
        
        # Create required objects for the benchmark
        progress_tracker = ProgressTracker(self.display)
        checksum_calculator = ChecksumCalculator(self.display)
        file_ops = FileOperations(self.display, self.storage)
        
        # Create a custom file operations class with the specified buffer size
        class CustomFileOperations(FileOperations):
            def copy_file_with_hash(self, src_path, dst_path, hash_obj=None, progress_callback=None):
                # Ensure parent directory exists
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Get file size for progress updates
                file_size = src_path.stat().st_size
                
                # Copy the file with custom buffer size
                with open(src_path, 'rb') as src:
                    with open(dst_path, 'wb') as dst:
                        bytes_transferred = 0
                        
                        while True:
                            chunk = src.read(buffer_size)
                            if not chunk:
                                break
                                
                            dst.write(chunk)
                            if hash_obj:
                                hash_obj.update(chunk)
                            
                            bytes_transferred += len(chunk)
                            
                            # Update progress if callback provided
                            if progress_callback:
                                progress_callback(bytes_transferred, file_size)
                
                # Return checksum if hash_obj provided
                if hash_obj:
                    return True, hash_obj.hexdigest()
                return True, None
        
        # Use the custom file operations for benchmarking
        custom_file_ops = CustomFileOperations(self.display, self.storage)
        
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
            hash_obj = checksum_calculator.create_hash()
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
            
            # Initialize progress tracking
            progress_tracker.start_file(
                test_file, 1, 1, 
                result.file_size, result.file_size, 0
            )
            
            # Create a progress callback
            progress_callback = progress_tracker.create_progress_callback()
            
            # Perform the actual copy with custom file operations
            success, actual_checksum = custom_file_ops.copy_file_with_hash(
                test_file, dest_file, hash_obj, progress_callback
            )
            
            transfer_end = time.time()
            result.duration = transfer_end - transfer_start
            
            # Verify the transfer
            verify_start = time.time()
            verification_success = custom_file_ops.verify_checksum(dest_file, checksum, progress_callback)
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
            
            return result
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            result.success = False
            result.error = str(e)
            
            # Exit transfer state
            try:
                self.state_manager.exit_transfer()
            except Exception as exit_err:
                logger.error(f"Error exiting transfer state: {exit_err}")
            
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
            
            # Create test file for this size
            test_file = self.create_test_file(file_size)
            
            for buffer_size in self.benchmark_config.buffer_sizes:
                buffer_key = f"{buffer_size // (1024 * 1024)}MB"
                logger.info(f"Running benchmark with {buffer_key} buffer on {size_key} file")
                
                # Run multiple iterations
                iteration_results: List[BenchmarkResult] = []
                for i in range(self.benchmark_config.iterations):
                    logger.info(f"  Iteration {i+1}/{self.benchmark_config.iterations}")
                    result = self.run_single_benchmark(buffer_size, test_file)
                    iteration_results.append(result)
                    
                    if not result.success:
                        logger.warning(f"  Iteration {i+1} failed: {result.error}")
                    else:
                        logger.info(f"  Iteration {i+1} complete: {result.transfer_speed:.2f} MB/s")
                
                # Calculate average and save results
                if iteration_results:
                    avg_result = self._average_results(iteration_results)
                    results[size_key].append(avg_result)
                    
                    logger.info(f"Average transfer speed for {buffer_key} buffer on {size_key} file: "
                                f"{avg_result.transfer_speed:.2f} MB/s")
        
        # Save results to file
        self.save_results(results)
        
        # Generate plots if configured
        if self.benchmark_config.generate_plots:
            self.generate_plots(results)
        
        # Clean up if configured
        if self.benchmark_config.cleanup_after_run:
            self.cleanup()
        
        return results
    
    def _average_results(self, results: List[BenchmarkResult]) -> BenchmarkResult:
        """Calculate average benchmark result from multiple iterations"""
        if not results:
            return BenchmarkResult(0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, False, "No results")
        
        # Only use successful results for averaging
        successful_results = [r for r in results if r.success]
        if not successful_results:
            # If all failed, return the first result
            return results[0]
        
        # Use the first result as a template and update with averages
        avg_result = BenchmarkResult(
            buffer_size=results[0].buffer_size,
            file_size=results[0].file_size,
            transfer_speed=statistics.mean(r.transfer_speed for r in successful_results),
            duration=statistics.mean(r.duration for r in successful_results),
            checksum_duration=statistics.mean(r.checksum_duration for r in successful_results),
            verification_duration=statistics.mean(r.verification_duration for r in successful_results),
            total_duration=statistics.mean(r.total_duration for r in successful_results),
            success=True,
            error=None,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return avg_result
    
    def save_results(self, results: Dict[str, List[BenchmarkResult]]) -> None:
        """Save benchmark results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.benchmark_config.output_dir / f"benchmark_results_{timestamp}.json"
        
        # Convert results to serializable format
        serializable_results = {}
        for size_key, size_results in results.items():
            serializable_results[size_key] = [
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
                for r in size_results
            ]
        
        # Save to JSON file
        with open(result_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Benchmark results saved to {result_file}")
    
    def generate_plots(self, results: Dict[str, List[BenchmarkResult]]) -> None:
        """Generate benchmark result plots"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create figure for transfer speed
        plt.figure(figsize=(12, 8))
        
        for size_key, size_results in results.items():
            # Skip if no results
            if not size_results:
                continue
                
            # Extract data
            buffer_sizes = [r.buffer_size / (1024 * 1024) for r in size_results]  # Convert to MB
            transfer_speeds = [r.transfer_speed for r in size_results]
            
            # Plot transfer speed
            plt.plot(buffer_sizes, transfer_speeds, marker='o', label=f"File size: {size_key}")
        
        plt.title("Transfer Speed vs Buffer Size")
        plt.xlabel("Buffer Size (MB)")
        plt.ylabel("Transfer Speed (MB/s)")
        plt.xscale('log', base=2)
        plt.grid(True)
        plt.legend()
        
        # Save plot
        speed_plot_file = self.benchmark_config.output_dir / f"speed_plot_{timestamp}.png"
        plt.savefig(speed_plot_file)
        logger.info(f"Transfer speed plot saved to {speed_plot_file}")
        
        # Create figure for durations
        plt.figure(figsize=(12, 8))
        
        for size_key, size_results in results.items():
            # Skip if no results
            if not size_results:
                continue
                
            # Extract data for the largest file size
            buffer_sizes = [r.buffer_size / (1024 * 1024) for r in size_results]  # Convert to MB
            durations = [r.duration for r in size_results]
            checksum_durations = [r.checksum_duration for r in size_results]
            verification_durations = [r.verification_duration for r in size_results]
            
            # Plot durations
            plt.plot(buffer_sizes, durations, marker='o', label=f"Transfer Time ({size_key})")
            plt.plot(buffer_sizes, checksum_durations, marker='s', label=f"Checksum Time ({size_key})")
            plt.plot(buffer_sizes, verification_durations, marker='^', label=f"Verification Time ({size_key})")
        
        plt.title("Operation Durations vs Buffer Size")
        plt.xlabel("Buffer Size (MB)")
        plt.ylabel("Duration (seconds)")
        plt.xscale('log', base=2)
        plt.grid(True)
        plt.legend()
        
        # Save plot
        duration_plot_file = self.benchmark_config.output_dir / f"duration_plot_{timestamp}.png"
        plt.savefig(duration_plot_file)
        logger.info(f"Duration plot saved to {duration_plot_file}")
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        logger.info("Cleaning up temporary files")
        
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"Removed temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")


def run_benchmark_cli():
    """Run benchmarks from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TransferBox Benchmark Tool")
    parser.add_argument("--buffer-sizes", type=str, help="Comma-separated list of buffer sizes in MB")
    parser.add_argument("--file-sizes", type=str, help="Comma-separated list of file sizes in MB")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations per benchmark")
    parser.add_argument("--output-dir", type=str, default="benchmark_results", help="Output directory for results")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip cleanup of temporary files")
    parser.add_argument("--no-plots", action="store_true", help="Skip generating plots")
    
    args = parser.parse_args()
    
    # Configure benchmarks
    benchmark_config = BenchmarkConfig()
    
    if args.buffer_sizes:
        buffer_sizes = [int(size.strip()) * 1024 * 1024 for size in args.buffer_sizes.split(",")]
        benchmark_config.buffer_sizes = buffer_sizes
    
    if args.file_sizes:
        file_sizes = [int(size.strip()) * 1024 * 1024 for size in args.file_sizes.split(",")]
        benchmark_config.test_file_sizes = file_sizes
    
    if args.iterations:
        benchmark_config.iterations = args.iterations
    
    if args.output_dir:
        benchmark_config.output_dir = Path(args.output_dir)
    
    if args.no_cleanup:
        benchmark_config.cleanup_after_run = False
    
    if args.no_plots:
        benchmark_config.generate_plots = False
    
    # Initialize required components
    from .interfaces.dummy_display import DummyDisplay
    from .interfaces.local_storage import LocalStorage
    
    display = DummyDisplay()
    storage = LocalStorage()
    
    # Run benchmarks
    benchmark = TransferBenchmark(display, storage, benchmark_config=benchmark_config)
    results = benchmark.run_benchmarks()
    
    # Print results summary
    print("\nBenchmark Results Summary:")
    print("-------------------------")
    
    for size_key, size_results in results.items():
        print(f"\nFile size: {size_key}")
        print("-" * (10 + len(size_key)))
        
        if not size_results:
            print("  No results")
            continue
        
        for result in size_results:
            buffer_mb = result.buffer_size / (1024 * 1024)
            print(f"  Buffer size: {buffer_mb:.1f} MB")
            print(f"  Transfer speed: {result.transfer_speed:.2f} MB/s")
            print(f"  Duration: {result.duration:.2f} seconds")
            print("")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_benchmark_cli()) 