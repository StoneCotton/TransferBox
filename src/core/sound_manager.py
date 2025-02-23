# src/core/sound_manager.py

import pygame
import logging
from pathlib import Path
from typing import Optional, Dict
from .config_manager import TransferConfig

logger = logging.getLogger(__name__)

class SoundManager:
    """Manages sound effects for TransferBox"""
    
    def __init__(self, config: TransferConfig):
        """
        Initialize sound manager with configuration.
        
        Args:
            config: TransferConfig object containing sound settings
        """
        self.config = config
        self._initialized = False
        self._sounds: Dict[str, Optional[pygame.mixer.Sound]] = {
            'success': None,
            'error': None
        }
        
        # Only initialize if sounds are enabled
        if self.config.enable_sounds:
            self._initialize_pygame()
            self._load_sounds()
    
    def _initialize_pygame(self) -> None:
        """Initialize pygame mixer for sound playback"""
        try:
            pygame.mixer.init()
            self._initialized = True
            logger.info("Sound system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize sound system: {e}")
            self._initialized = False
    
    def _load_sounds(self) -> None:
        """Load sound files into memory"""
        if not self._initialized:
            return
            
        try:
            # Get the absolute path to the sounds directory
            # Assuming sounds are in a 'sounds' directory relative to the application root
            app_root = Path(__file__).parent.parent.parent
            
            # Load success sound
            success_path = app_root / self.config.success_sound_path
            if success_path.exists():
                self._sounds['success'] = pygame.mixer.Sound(str(success_path))
                logger.info(f"Loaded success sound from {success_path}")
            else:
                logger.warning(f"Success sound file not found at {success_path}")
            
            # Load error sound
            error_path = app_root / self.config.error_sound_path
            if error_path.exists():
                self._sounds['error'] = pygame.mixer.Sound(str(error_path))
                logger.info(f"Loaded error sound from {error_path}")
            else:
                logger.warning(f"Error sound file not found at {error_path}")
            
            # Set volume for all sounds
            volume = max(0, min(1.0, self.config.sound_volume / 100))
            for sound in self._sounds.values():
                if sound:
                    sound.set_volume(volume)
            
        except Exception as e:
            logger.error(f"Error loading sound files: {e}")
            self._sounds = {'success': None, 'error': None}
    
    def play_success(self) -> None:
        """Play success sound if enabled"""
        if not self.config.enable_sounds or not self._initialized:
            return
            
        try:
            if self._sounds['success']:
                self._sounds['success'].play()
                logger.debug("Playing success sound")
        except Exception as e:
            logger.error(f"Error playing success sound: {e}")
    
    def play_error(self) -> None:
        """Play error sound if enabled"""
        if not self.config.enable_sounds or not self._initialized:
            return
            
        try:
            if self._sounds['error']:
                self._sounds['error'].play()
                logger.debug("Playing error sound")
        except Exception as e:
            logger.error(f"Error playing error sound: {e}")
    
    def cleanup(self) -> None:
        """Clean up pygame mixer resources"""
        if self._initialized:
            try:
                pygame.mixer.quit()
                self._initialized = False
                logger.info("Sound system cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up sound system: {e}")