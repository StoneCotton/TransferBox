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
        if hasattr(self, '_initialized') and self._initialized:
            logger.debug("Pygame mixer already initialized")
            return
            
        try:
            # First attempt with default settings
            pygame.mixer.init()
            self._initialized = True
            logger.info("Sound system initialized successfully")
        except pygame.error as e:
            logger.warning(f"Standard pygame initialization failed: {e}")
            try:
                # Fallback with safer parameters (lower frequency, different buffer size)
                pygame.mixer.init(44100, -16, 2, 1024)
                self._initialized = True
                logger.info("Sound system initialized with fallback settings")
            except pygame.error as specific_err:
                logger.error(f"Failed to initialize pygame mixer with fallback: {specific_err}")
                self._initialized = False
                # No need to raise - sound is non-critical and we've set the flag
            except Exception as e:
                logger.error(f"Unexpected error during pygame fallback init: {e}")
                self._initialized = False
        except ImportError as e:
            logger.error(f"Pygame module not available: {e}")
            self._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize sound system: {e}")
            self._initialized = False
    
    def _load_sounds(self) -> None:
        """Load sound files into memory"""
        if not self._initialized:
            return
            
        # Store original sounds in case we need to restore on partial failure
        original_sounds = self._sounds.copy() if hasattr(self, '_sounds') else {}
        
        try:
            # Get the absolute path to the sounds directory
            try:
                app_root = Path(__file__).parent.parent.parent
            except (NameError, TypeError) as e:
                logger.error(f"Error resolving application root path: {e}")
                return
                
            # Initialize sounds dictionary if needed
            if not hasattr(self, '_sounds') or not isinstance(self._sounds, dict):
                self._sounds = {'success': None, 'error': None}
                
            # Load success sound
            try:
                success_sound_path = "sounds/success.mp3"  # Default path
                if hasattr(self.config, 'success_sound_path'):
                    success_sound_path = self.config.success_sound_path
                
                success_path = app_root / success_sound_path
                if success_path.exists():
                    try:
                        self._sounds['success'] = pygame.mixer.Sound(str(success_path))
                        logger.info(f"Loaded success sound from {success_path}")
                    except (pygame.error, IOError) as sound_err:
                        logger.error(f"Failed to load success sound: {sound_err}")
                        self._sounds['success'] = None
                else:
                    logger.warning(f"Success sound file not found at {success_path}")
                    self._sounds['success'] = None
            except Exception as success_err:
                logger.error(f"Error processing success sound: {success_err}")
                self._sounds['success'] = None
                
            # Load error sound
            try:
                error_sound_path = "sounds/error.mp3"  # Default path
                if hasattr(self.config, 'error_sound_path'):
                    error_sound_path = self.config.error_sound_path
                
                error_path = app_root / error_sound_path
                if error_path.exists():
                    try:
                        self._sounds['error'] = pygame.mixer.Sound(str(error_path))
                        logger.info(f"Loaded error sound from {error_path}")
                    except (pygame.error, IOError) as sound_err:
                        logger.error(f"Failed to load error sound: {sound_err}")
                        self._sounds['error'] = None
                else:
                    logger.warning(f"Error sound file not found at {error_path}")
                    self._sounds['error'] = None
            except Exception as error_err:
                logger.error(f"Error processing error sound: {error_err}")
                self._sounds['error'] = None
                
            # Set volume for all sounds
            try:
                sound_volume = 50  # Default volume
                if hasattr(self.config, 'sound_volume'):
                    sound_volume = self.config.sound_volume
                    
                volume = max(0, min(1.0, sound_volume / 100))
                for sound_key, sound in self._sounds.items():
                    if sound:
                        try:
                            sound.set_volume(volume)
                        except pygame.error as vol_err:
                            logger.warning(f"Failed to set volume for {sound_key} sound: {vol_err}")
            except Exception as vol_err:
                logger.error(f"Error setting sound volumes: {vol_err}")
                
        except Exception as e:
            logger.error(f"Error loading sound files: {e}")
            self._sounds = {'success': None, 'error': None}
    
    def _play_sound(self, sound_type: str) -> None:
        """
        Helper method to play a sound if enabled.
        
        Args:
            sound_type: Type of sound to play ('success' or 'error')
        """
        if not hasattr(self.config, 'enable_sounds') or not self.config.enable_sounds or not self._initialized:
            return
            
        try:
            if sound_type not in self._sounds:
                logger.warning(f"Unknown sound type: {sound_type}")
                return
                
            sound = self._sounds[sound_type]
            if sound is None:
                logger.debug(f"No {sound_type} sound available to play")
                return
                
            sound.play()
            logger.debug(f"Playing {sound_type} sound")
        except pygame.error as e:
            logger.error(f"Pygame error playing {sound_type} sound: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error playing {sound_type} sound: {e}")
            # Sound system might have been uninitialized
            self._initialized = False
        except Exception as e:
            logger.error(f"Error playing {sound_type} sound: {e}")

    def play_success(self) -> None:
        """Play success sound if enabled"""
        self._play_sound('success')
        
    def play_error(self) -> None:
        """Play error sound if enabled"""
        self._play_sound('error')
        
    def cleanup(self) -> None:
        """Clean up pygame mixer resources"""
        if not self._initialized:
            return
            
        try:
            # Stop any currently playing sounds
            try:
                pygame.mixer.stop()
            except pygame.error as e:
                logger.warning(f"Could not stop mixer: {e}")
                
            # Quit the mixer
            try:
                pygame.mixer.quit()
                self._initialized = False
                logger.info("Sound system cleaned up")
            except pygame.error as e:
                logger.error(f"Error quitting pygame mixer: {e}")
                self._initialized = False
        except Exception as e:
            logger.error(f"Error cleaning up sound system: {e}")
            self._initialized = False  # Consider it uninitialized regardless of error