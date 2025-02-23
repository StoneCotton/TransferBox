# src/core/proxy_generator.py

import logging
import subprocess
import re
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime
from .interfaces.display import DisplayInterface
from .interfaces.types import TransferProgress, TransferStatus
from .config_manager import TransferConfig

logger = logging.getLogger(__name__)

class ProxyTask:
    def __init__(self, source_path: Path, destination_dir: Path, card_name: str):
        self.source_path = source_path
        self.destination_dir = destination_dir
        self.card_name = card_name

class ProxyGenerator:
    """Handles generation of video proxies using FFmpeg."""
    
    # List of supported video formats for proxy generation
    VIDEO_FORMATS = {'.mp4', '.mov', '.mxf', '.avi'}
    
    def __init__(self, config: TransferConfig, display: DisplayInterface):
        self.config = config
        self.display = display
        self.project_root = Path(__file__).parent.parent.parent
        
    def generate_proxies_for_tasks(self, tasks: List[ProxyTask], 
                                 progress_callback: Optional[Callable[[str, float, int, int], None]] = None) -> bool:
        """
        Generate proxies for a list of tasks sequentially.
        
        Args:
            tasks: List of proxy tasks to process
            progress_callback: Optional callback for progress updates
                             Args: (filename, progress %, current_file_num, total_files)
            
        Returns:
            bool: True if all proxies were generated successfully
        """
        total_tasks = len(tasks)
        success_count = 0
        failures = []

        logger.info(f"Starting proxy generation for {total_tasks} files")
        
        for i, task in enumerate(tasks, 1):
            try:
                logger.info(f"Generating proxy {i}/{total_tasks}: {task.source_path.name}")
                
                success = self.generate_proxy(
                    task.source_path,
                    task.destination_dir,
                    lambda progress: progress_callback(
                        task.source_path.name, 
                        progress, 
                        i, 
                        total_tasks
                    ) if progress_callback else None
                )
                
                if success:
                    success_count += 1
                else:
                    failures.append(task.source_path.name)
                    
            except Exception as e:
                logger.error(f"Error generating proxy for {task.source_path}: {e}")
                failures.append(task.source_path.name)
        
        # Log results
        if failures:
            logger.error(f"Failed to generate proxies for: {', '.join(failures)}")
        logger.info(f"Proxy generation complete. "
                   f"Success: {success_count}/{total_tasks}")
        
        return len(failures) == 0

    def generate_proxy(self, source_path: Path, destination_dir: Path,
                      progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """
        Generate a proxy video file using FFmpeg.
        
        Args:
            source_path: Path to source video file
            destination_dir: Base destination directory
            progress_callback: Optional callback for progress updates
            
        Returns:
            bool: True if proxy generation succeeded
        """
        try:
            # Skip unsupported formats
            if source_path.suffix.lower() not in self.VIDEO_FORMATS:
                logger.info(f"Skipping unsupported format: {source_path.suffix}")
                return False

            # Create proxy subfolder
            proxy_dir = destination_dir / self.config.proxy_subfolder
            proxy_dir.mkdir(parents=True, exist_ok=True)
            
            # Create output path with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = proxy_dir / f"{source_path.stem}_{timestamp}_proxy.mov"
            
            # Find watermark file
            watermark_path = self.project_root / "assets" / "adobe_proxy_logo.png"
            
            # Build FFmpeg command
            command = self._build_ffmpeg_command(source_path, output_path, watermark_path)
            logger.debug(f"FFmpeg command: {' '.join(command)}")
            
            # Run FFmpeg process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitor progress
            success = self._monitor_ffmpeg_progress(process, progress_callback)
            
            # Verify output
            if success and output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully generated proxy: {output_path}")
                return True
            else:
                logger.error("Proxy file was not created or is empty")
                return False
                
        except Exception as e:
            logger.error(f"Error generating proxy for {source_path}: {e}")
            return False

    def _build_ffmpeg_command(self, source_path: Path, output_path: Path, 
                            watermark_path: Path) -> List[str]:
        """Build FFmpeg command with appropriate settings."""
        command = [
            'ffmpeg',
            '-y',                     # Overwrite output files
            '-i', str(source_path),   # Input file
        ]
        
        # Add watermark if enabled and exists
        if self.config.include_proxy_watermark and watermark_path.exists():
            command.extend([
                '-i', str(watermark_path),
                '-filter_complex',
                '[0:v][1:v] overlay=W-w-10:H-h-10 [v]',
                '-map', '[v]',
                '-map', '0:a?',  # Copy audio if present
            ])
        else:
            command.extend([
                '-map', '0:v',
                '-map', '0:a?',
            ])
        
        # Add encoding settings
        command.extend([
            '-c:v', 'prores_ks',     # Use ProRes codec
            '-profile:v', '0',        # ProRes 422 Proxy profile
            '-s', '1024x540',         # Target resolution
            '-c:a', 'copy',           # Copy audio without re-encoding
            str(output_path)          # Output path
        ])
        
        return command

    def _monitor_ffmpeg_progress(self, process: subprocess.Popen,
                               progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """
        Monitor FFmpeg progress and update callback.
        
        Args:
            process: FFmpeg subprocess
            progress_callback: Optional callback for progress updates
            
        Returns:
            bool: True if process completed successfully
        """
        duration = None
        total_frames = None
        current_frame = 0
        
        while True:
            line = process.stderr.readline()
            
            if not line and process.poll() is not None:
                break
            
            # Extract duration on first pass
            if not duration and "Duration:" in line:
                duration_match = re.search(
                    r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})',
                    line
                )
                if duration_match:
                    h, m, s, ms = map(int, duration_match.groups())
                    duration = (h * 3600) + (m * 60) + s + (ms / 100)
                    
                    # Calculate total frames (assume 24fps if not found)
                    fps = 24
                    fps_match = re.search(r'(\d+(?:\.\d+)?)\s+fps', line)
                    if fps_match:
                        fps = float(fps_match.group(1))
                    total_frames = int(duration * fps)
            
            # Update progress based on frame count
            if "frame=" in line and total_frames:
                frame_match = re.search(r'frame=\s*(\d+)', line)
                if frame_match:
                    current_frame = int(frame_match.group(1))
                    if progress_callback and total_frames > 0:
                        progress = (current_frame / total_frames) * 100
                        progress_callback(progress)
            
            # Log any errors
            if "Error" in line or "failed" in line.lower():
                logger.error(f"FFmpeg error: {line.strip()}")
        
        return process.returncode == 0

    def is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for proxy generation."""
        return file_path.suffix.lower() in self.VIDEO_FORMATS