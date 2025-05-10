import pytest
import pygame
from pathlib import Path
from src.core.sound_manager import SoundManager
from src.core.config_manager import TransferConfig

class TestSoundManager:
    """Test suite for SoundManager class"""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock TransferConfig object with sound settings"""
        config = TransferConfig()
        config.enable_sounds = True
        config.sound_volume = 50
        config.success_sound_path = "sounds/success.mp3"
        config.error_sound_path = "sounds/error.mp3"
        return config
    
    @pytest.fixture
    def sound_manager(self, mock_config):
        """Create a SoundManager instance with mock config"""
        manager = SoundManager(mock_config)
        yield manager
        manager.cleanup()
    
    def test_initialization(self, mock_config):
        """Test SoundManager initialization"""
        manager = SoundManager(mock_config)
        assert manager.config == mock_config
        assert hasattr(manager, '_initialized')
        assert isinstance(manager._sounds, dict)
        assert 'success' in manager._sounds
        assert 'error' in manager._sounds
        manager.cleanup()
    
    def test_initialization_with_sounds_disabled(self):
        """Test initialization when sounds are disabled"""
        config = TransferConfig()
        config.enable_sounds = False
        manager = SoundManager(config)
        assert not manager._initialized
        assert manager._sounds['success'] is None
        assert manager._sounds['error'] is None
        manager.cleanup()
    
    def test_sound_loading(self, sound_manager, tmp_path, mocker):
        """Test sound file loading"""
        # Create temporary sound files
        success_sound = tmp_path / "success.mp3"
        error_sound = tmp_path / "error.mp3"
        success_sound.touch()
        error_sound.touch()
        
        # Mock pygame.mixer.Sound using pytest-mock's mocker
        mock_sound = mocker.Mock()
        mocker.patch('pygame.mixer.Sound', return_value=mock_sound)
        
        # Update config paths
        sound_manager.config.success_sound_path = str(success_sound)
        sound_manager.config.error_sound_path = str(error_sound)
        
        # Reload sounds
        sound_manager._load_sounds()
        
        # Verify sounds were loaded
        assert sound_manager._sounds['success'] is not None
        assert sound_manager._sounds['error'] is not None
        assert sound_manager._sounds['success'] == mock_sound
        assert sound_manager._sounds['error'] == mock_sound
    
    def test_sound_volume_setting(self, sound_manager):
        """Test volume setting for loaded sounds"""
        # Set volume to 75%
        sound_manager.config.sound_volume = 75
        sound_manager._load_sounds()
        
        # Verify volume was set correctly
        for sound in sound_manager._sounds.values():
            if sound is not None:
                assert sound.get_volume() == 0.75
    
    def test_play_success(self, sound_manager, mocker):
        """Test playing success sound"""
        # Mock the _play_sound method
        mock_play = mocker.patch.object(sound_manager, '_play_sound')
        sound_manager.play_success()
        mock_play.assert_called_once_with('success')
    
    def test_play_error(self, sound_manager, mocker):
        """Test playing error sound"""
        # Mock the _play_sound method
        mock_play = mocker.patch.object(sound_manager, '_play_sound')
        sound_manager.play_error()
        mock_play.assert_called_once_with('error')
    
    def test_cleanup(self, sound_manager):
        """Test cleanup of sound resources"""
        sound_manager.cleanup()
        assert not sound_manager._initialized
    
    def test_play_sound_with_invalid_type(self, sound_manager, caplog):
        """Test playing sound with invalid type"""
        sound_manager._play_sound('invalid_type')
        assert "Unknown sound type: invalid_type" in caplog.text
    
    def test_play_sound_when_disabled(self, mock_config):
        """Test playing sound when sounds are disabled"""
        mock_config.enable_sounds = False
        manager = SoundManager(mock_config)
        # Should not raise any errors
        manager.play_success()
        manager.play_error()
        manager.cleanup()
    
    def test_initialization_failure_handling(self, mock_config, mocker):
        """Test handling of pygame initialization failures"""
        # Mock pygame.mixer.init to raise an error
        mocker.patch('pygame.mixer.init', side_effect=pygame.error("Test error"))
        
        # Should not raise exception
        manager = SoundManager(mock_config)
        assert not manager._initialized
        manager.cleanup() 