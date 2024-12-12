# src/core/proxy_generator.py

import logging
import subprocess
import re
from pathlib import Path
from typing import Optional, List
from .interfaces.display import DisplayInterface
from .interfaces.types import TransferProgress, TransferStatus
from .config_manager import TransferConfig

logger = logging.getLogger(__name__)

class ProxyGenerator:
    """Handles generation of video proxies using FFmpeg"""
    
    # List of video formats we'll generate proxies for
    VIDEO_FORMATS = {'.mp4', '.mov', '.mxf', '.avi', '.braw', '.r3d'}
    
    def __init__(self, config: TransferConfig, display: DisplayInterface):
        self.config = config
        self.display = display
        
    def should_generate_proxy(self, file_path: Path) -> bool:
        """
        Determine if we should generate a proxy for this file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            True if we should generate a proxy, False otherwise
        """
        return (
            self.config.generate_proxies and
            file_path.suffix.lower() in self.VIDEO_FORMATS
        )
    
    def generate_proxy(
        self,
        source_path: Path,
        destination_dir: Path,
        progress: Optional[TransferProgress] = None
    ) -> bool:
        """
        Generate a proxy video file using FFmpeg.
        
        This function creates a lower-resolution proxy version of the source video,
        with optional watermarking. It handles multiple video formats and provides
        detailed progress tracking during the conversion process.
        
        Args:
            source_path: Path to source video file
            destination_dir: Base destination directory
            progress: Optional progress tracking object
            
        Returns:
            True if proxy generation succeeded, False otherwise
        """
        try:
            # Create proxy subfolder
            proxy_dir = destination_dir / self.config.proxy_subfolder
            proxy_dir.mkdir(parents=True, exist_ok=True)
            
            # Always use .mov extension for ProRes output
            output_path = proxy_dir / f"{source_path.stem}_proxy.mov"
            
            # Update progress display
            if progress:
                progress.status = TransferStatus.GENERATING_PROXY
                progress.current_file = f"Creating proxy: {source_path.name}"
                self.display.show_progress(progress)
            
            # Find project root to locate watermark
            project_root = Path(__file__).parent.parent.parent
            watermark_path = project_root / "assets" / "adobe_proxy_logo.png"
            
            # Build FFmpeg command based on source format
            command = [
                'ffmpeg',
                '-y',  # Overwrite output files
                '-i', str(source_path),  # Input file
            ]
            
            # Skip unsupported formats
            if source_path.suffix.lower() == '.braw':
                logger.warning(f"Skipping proxy generation for BRAW file: {source_path.name}")
                return False
            
            # Add watermark if enabled and file exists
            if self.config.include_proxy_watermark and watermark_path.exists():
                command.extend([
                    '-i', str(watermark_path),
                    '-filter_complex',
                    '[0:v][1:v] overlay=W-w-10:H-h-10 [v]',  # Position in bottom right with 10px padding
                    '-map', '[v]',
                    '-map', '0:a?',  # Copy audio if present
                ])
            else:
                if self.config.include_proxy_watermark:
                    logger.warning(f"Watermark file not found at {watermark_path}")
                command.extend([
                    '-map', '0:v',
                    '-map', '0:a?',
                ])
            
            # Add encoding settings
            command.extend([
                '-c:v', 'prores_ks',
                '-profile:v', '0',  # ProRes 422 Proxy profile
                '-s', '1024x540',   # Target resolution
                '-c:a', 'copy',     # Copy audio without re-encoding
            ])
            
            # Add output path
            command.append(str(output_path))
            
            # Log the complete command for debugging
            logger.debug(f"FFmpeg command: {' '.join(command)}")
            
            # Create process with pipe to capture output
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Initialize variables for progress tracking
            duration_match = None
            total_frames = None
            current_frame = 0
            
            # Process FFmpeg output for progress tracking
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                    
                # Extract video duration on first pass
                if not duration_match and "Duration:" in line:
                    duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
                    if duration_match:
                        hours, minutes, seconds, ms = map(int, duration_match.groups())
                        total_duration = (hours * 3600) + (minutes * 60) + seconds + (ms / 100)
                        # Estimate total frames based on framerate (assuming 24fps if not found)
                        fps_match = re.search(r'(\d+\.?\d*) fps', line)
                        fps = float(fps_match.group(1)) if fps_match else 24
                        total_frames = int(total_duration * fps)
                
                # Update progress based on frame count
                frame_match = re.search(r'frame=\s*(\d+)', line)
                if frame_match and total_frames and progress:
                    current_frame = int(frame_match.group(1))
                    proxy_progress = (current_frame / total_frames) * 100
                    
                    # Update progress display
                    progress.proxy_progress = proxy_progress
                    progress.proxy_total_frames = total_frames
                    progress.proxy_current_frame = current_frame
                    self.display.show_progress(progress)
                
                # Log any error messages
                if "Error" in line or "failed" in line.lower():
                    logger.error(f"FFmpeg error: {line.strip()}")
            
            # Check process return code
            if process.returncode != 0:
                logger.error(f"FFmpeg process failed with return code {process.returncode}")
                return False
            
            # Verify the output file exists and has size > 0
            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.error("Proxy file was not created or is empty")
                return False
                
            logger.info(f"Successfully generated proxy: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating proxy: {e}")
            return False
        
    def _get_output_extension(self, source_path: Path) -> str:
        """Determine appropriate output extension for proxy."""
        # Always use .mov for ProRes
        return ".mov"

    def _get_codec_settings(self, source_path: Path) -> List[str]:
        """Get format-specific FFmpeg settings."""
        if source_path.suffix.lower() == '.braw':
            # Skip BRAW files for now
            logger.info("Skipping proxy generation for BRAW file - codec not supported")
            return None
            
        return [
            '-c:v', 'prores_ks',
            '-profile:v', '0',
            '-s', '1024x540',
            '-c:a', 'copy',
            '-c:d', 'copy'
        ]