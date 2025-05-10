import pytest
from src.core.state_manager import StateManager, SystemState, StateError, StateTransitionError
from src.core.exceptions import DisplayError
import time

class TestStateManager:
    """Test suite for StateManager class."""

    def test_initial_state(self, mock_display_interface):
        """Test that StateManager initializes in STANDBY state."""
        manager = StateManager(mock_display_interface)
        assert manager.get_current_state() == SystemState.STANDBY
        assert manager.is_standby()
        assert not manager.is_transfer()
        assert not manager.is_utility()

    def test_enter_transfer_from_standby(self, mock_display_interface):
        """Test entering transfer state from standby."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        assert manager.is_transfer()
        assert manager.transfer_start_time is not None

    def test_enter_transfer_from_transfer(self, mock_display_interface):
        """Test that entering transfer from transfer state raises error."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        with pytest.raises(StateError) as exc_info:
            manager.enter_transfer()
        assert "Cannot enter transfer state" in str(exc_info.value)

    def test_exit_transfer(self, mock_display_interface):
        """Test exiting transfer state."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        time.sleep(0.1)  # Ensure some time passes
        manager.exit_transfer()
        assert manager.is_standby()
        assert manager.transfer_start_time is None
        assert manager.total_transfer_time > 0

    def test_enter_utility_from_standby(self, mock_display_interface):
        """Test entering utility state from standby."""
        manager = StateManager(mock_display_interface)
        assert manager.enter_utility()
        assert manager.is_utility()

    def test_enter_utility_from_transfer(self, mock_display_interface):
        """Test that entering utility from transfer state raises error."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        with pytest.raises(StateError) as exc_info:
            manager.enter_utility()
        assert "Cannot enter utility state" in str(exc_info.value)

    def test_exit_utility(self, mock_display_interface):
        """Test exiting utility state."""
        manager = StateManager(mock_display_interface)
        manager.enter_utility()
        assert manager.exit_utility()
        assert manager.is_standby()

    def test_exit_utility_from_transfer(self, mock_display_interface):
        """Test that exiting utility from transfer state raises error."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        with pytest.raises(StateError) as exc_info:
            manager.exit_utility()
        assert "Not in utility state" in str(exc_info.value)

    def test_transfer_timing(self, mock_display_interface):
        """Test transfer timing functionality."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        time.sleep(0.1)
        current_time = manager.get_current_transfer_time()
        assert current_time > 0
        manager.exit_transfer()
        total_time = manager.get_total_transfer_time()
        assert total_time > 0
        assert total_time >= current_time

    def test_format_time(self, mock_display_interface):
        """Test time formatting functionality."""
        manager = StateManager(mock_display_interface)
        # Test various time durations
        assert manager.format_time(0) == "0:00:00"
        assert manager.format_time(61) == "0:01:01"
        assert manager.format_time(3661) == "1:01:01"

    def test_display_error_handling(self, mock_display_interface):
        """Test handling of display errors."""
        mock_display_interface.show_status.side_effect = Exception("Display error")
        manager = StateManager(mock_display_interface)
        with pytest.raises(DisplayError) as exc_info:
            manager.enter_transfer()
        assert "Failed to update display" in str(exc_info.value)

    def test_pending_unmount(self, mock_display_interface):
        """Test handling of pending unmount path."""
        manager = StateManager(mock_display_interface)
        manager.enter_transfer()
        test_path = "/test/path"
        manager.exit_transfer(pending_unmount=test_path)
        assert manager.pending_unmount == test_path 