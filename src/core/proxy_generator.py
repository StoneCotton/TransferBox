# src/core/proxy_generator.py

import logging
import subprocess
from pathlib import Path
from typing import Optional
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
            
            # Create output path with _proxy suffix
            output_path = proxy_dir / f"{source_path.stem}_proxy{source_path.suffix}"
            
            # Update progress display
            if progress:
                progress.status = TransferStatus.COPYING
                progress.current_file = f"Creating proxy: {source_path.name}"
                self.display.show_progress(progress)
            
            # Build FFmpeg command
            command = [
                'ffmpeg',
                '-y',  # Overwrite output files
                '-i', str(source_path),  # Input file
            ]
            
            # Add watermark if enabled
            if self.config.include_proxy_watermark:
                watermark_path = Path(self.config.proxy_watermark_path)
                if watermark_path.exists():
                    command.extend([
                        '-i', str(watermark_path),
                        '-filter_complex', 
                        '[0:v][1:v] overlay=150:main_h-overlay_h-150 [v]',
                        '-map', '[v]',
                    ])
                else:
                    logger.warning(f"Watermark file not found: {watermark_path}")
                    command.extend(['-map', '0:v'])
            else:
                command.extend(['-map', '0:v'])
            
            # Add audio and data stream mapping
            command.extend([
                '-map', '0:a?',  # Copy audio if present
                '-map', '0:d?',  # Copy data streams if present
                '-c:v', 'prores_ks',
                '-profile:v', '0',
                '-s', '1024x540',
                '-c:a', 'copy',
                '-c:d', 'copy',
                str(output_path)
            ])
            
            # Run FFmpeg
            logger.info(f"Generating proxy for {source_path}")
            logger.debug(f"FFmpeg command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Successfully generated proxy: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error generating proxy: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error generating proxy: {e}")
            return False