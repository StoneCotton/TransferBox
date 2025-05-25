"""
Factory for creating appropriate TransferBox instances based on platform and mode.
Separates creation logic from main application logic.
"""
import logging
from typing import Optional
from .utils import get_platform
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


def create_transfer_box(platform: Optional[str] = None, use_webui: bool = False, 
                       config_manager: Optional[ConfigManager] = None):
    """
    Pure factory function to create the appropriate TransferBox instance.
    
    Args:
        platform: Target platform (auto-detected if None)
        use_webui: Whether to use web UI interface
        config_manager: Optional config manager instance
        
    Returns:
        Appropriate TransferBox instance based on platform and mode
        
    Raises:
        ImportError: If required dependencies are not available
        ValueError: If invalid platform specified
    """
    if platform is None:
        platform = get_platform()
    
    # Validate platform
    valid_platforms = ["darwin", "windows", "linux", "embedded"]
    if platform not in valid_platforms:
        raise ValueError(f"Invalid platform '{platform}'. Must be one of: {valid_platforms}")
    
    # Handle WebUI requests
    if use_webui:
        if platform in ["darwin", "windows"]:
            try:
                from .transfer_box_webui import WebUITransferBox
                return WebUITransferBox(config_manager)
            except ImportError as e:
                logger.error(f"Web UI dependencies not available: {e}")
                logger.warning("Falling back to desktop UI")
                # Fall through to desktop creation
            except Exception as e:
                logger.error(f"Failed to create WebUI TransferBox: {e}")
                raise
        else:
            logger.warning("Web UI not supported on embedded platforms, falling back to terminal UI")
            # Fall through to embedded creation
    
    # Handle Desktop platforms
    if platform in ["darwin", "windows", "linux"]:
        try:
            from .transfer_box_desktop import DesktopTransferBox
            return DesktopTransferBox(config_manager)
        except ImportError as e:
            logger.error(f"Desktop TransferBox dependencies not available: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create Desktop TransferBox: {e}")
            raise
    
    # Handle Embedded platforms
    try:
        from .transfer_box_embedded import EmbeddedTransferBox
        return EmbeddedTransferBox(config_manager)
    except ImportError as e:
        logger.error(f"Embedded TransferBox dependencies not available: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to create Embedded TransferBox: {e}")
        raise


def create_transfer_box_app(use_webui: bool = False, config_manager: Optional[ConfigManager] = None):
    """
    Convenience wrapper for backwards compatibility.
    
    Args:
        use_webui: Whether to use web UI interface
        config_manager: Optional config manager instance
        
    Returns:
        Appropriate TransferBox instance
    """
    return create_transfer_box(use_webui=use_webui, config_manager=config_manager) 