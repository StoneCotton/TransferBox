# tests/core/test_state_manager.py
import pytest
import time
from pathlib import Path
from src.core.state_manager import (
    StateManager,
    SystemState,
    StateTransitionError
)

class MockDisplay:
    """Mock display for testing"""
    def __init__(self):
        self.messages = []
        self.current_status = None
        
    def show_status(self, message: str, line: int = 0):
        self.messages.append((message, line))
        self.current_status = message
        
    def clear(self):
        self.messages = []
        self.current_status = None

@pytest.fixture
def mock_display():
    return MockDisplay()

@pytest.fixture
def state_manager(mock_display):
    return StateManager(mock_display)

def assert_contains_message(self, expected_text):
    """Helper method to check if any message contains the expected text"""
    matching_messages = [msg for msg, _ in self.messages if expected_text in msg]
    return len(matching_messages) > 0

# Basic State Tests
def test_initial_state(state_manager):
    """Test initial state is STANDBY"""
    assert state_manager.get_current_state() == SystemState.STANDBY
    assert state_manager.is_standby()
    assert not state_manager.is_transfer()
    assert not state_manager.is_utility()

# State Transition Tests
def test_enter_standby(state_manager):
    """Test entering standby state"""
    # First enter transfer state
    state_manager.enter_transfer()
    assert state_manager.is_transfer()
    
    # Then enter standby
    state_manager.enter_standby()
    assert state_manager.is_standby()
    # Check that either Standby or Input Card is in messages
    assert any("Standby" in msg or "Input Card" in msg 
              for msg, _ in state_manager.display.messages), \
        f"Expected 'Standby' or 'Input Card' in messages: {state_manager.display.messages}"

def test_enter_transfer(state_manager):
    """Test entering transfer state"""
    state_manager.enter_transfer()
    assert state_manager.is_transfer()
    assert state_manager.transfer_start_time is not None
    assert "Transfer Mode" in state_manager.display.current_status

def test_enter_utility(state_manager):
    """Test entering utility state"""
    success = state_manager.enter_utility()
    assert success
    assert state_manager.is_utility()

def test_invalid_transfer_from_utility(state_manager):
    """Test cannot enter transfer from utility state"""
    state_manager.enter_utility()
    assert state_manager.is_utility()
    # Try to enter transfer - should fail but not raise exception
    success = not state_manager._can_enter_transfer()
    assert success
    assert state_manager.is_utility()  # Should remain in utility state

def test_invalid_utility_from_transfer(state_manager):
    """Test cannot enter utility from transfer state"""
    state_manager.enter_transfer()
    assert not state_manager.enter_utility()

# Transfer Timing Tests
def test_transfer_timing(state_manager):
    """Test transfer timing functionality"""
    state_manager.enter_transfer()
    time.sleep(0.1)  # Small delay
    
    # Get current transfer time
    current_time = state_manager.get_current_transfer_time()
    assert current_time > 0
    assert current_time < 1  # Should be less than 1 second
    
    # Exit transfer and check total time
    state_manager.exit_transfer()
    total_time = state_manager.get_total_transfer_time()
    assert total_time > 0
    assert total_time < 1

def test_multiple_transfers_timing(state_manager):
    """Test timing across multiple transfers"""
    # First transfer
    state_manager.enter_transfer()
    time.sleep(0.1)
    state_manager.exit_transfer()
    first_total = state_manager.get_total_transfer_time()
    
    # Second transfer
    state_manager.enter_transfer()
    time.sleep(0.1)
    state_manager.exit_transfer()
    second_total = state_manager.get_total_transfer_time()
    
    assert second_total > first_total

# Pending Unmount Tests
def test_exit_transfer_with_pending_unmount(state_manager):
    """Test exiting transfer with pending unmount"""
    state_manager.enter_transfer()
    pending_path = Path("/test/path")
    state_manager.exit_transfer(pending_unmount=pending_path)
    assert state_manager.pending_unmount == pending_path

# Display Integration Tests
def test_display_updates_on_state_changes(state_manager, mock_display):
    """Test display updates during state transitions"""
    # Enter transfer
    state_manager.enter_transfer()
    assert any("Transfer Mode" in msg for msg, _ in mock_display.messages)
    
    # Enter standby
    mock_display.clear()
    state_manager.enter_standby()
    assert any("Standby" in msg for msg, _ in mock_display.messages)
    assert any("Input Card" in msg for msg, _ in mock_display.messages)

# Utility Mode Tests
def test_utility_mode_transitions(state_manager):
    """Test utility mode enter/exit transitions"""
    # Enter utility
    assert state_manager.enter_utility()
    assert state_manager.is_utility()
    
    # Exit utility
    assert state_manager.exit_utility()
    assert state_manager.is_standby()

def test_utility_mode_display(state_manager, mock_display):
    """Test display updates in utility mode"""
    state_manager.enter_utility()
    assert state_manager.is_utility()
    
    state_manager.exit_utility()
    assert any("Standby" in msg for msg, _ in mock_display.messages)

# Time Formatting Tests
def test_time_formatting(state_manager):
    """Test time formatting functionality"""
    test_times = [
        (1, "0:00:01"),
        (60, "0:01:00"),
        (3600, "1:00:00"),
        (3661, "1:01:01")
    ]
    
    for seconds, expected in test_times:
        formatted = state_manager.format_time(seconds)
        assert formatted == expected

# Error Handling Tests
def test_error_handling_in_transfer(state_manager):
    """Test error handling during transfer state"""
    state_manager.enter_transfer()
    
    # Simulate error condition
    try:
        raise Exception("Test error")
    except:
        state_manager.enter_standby()  # Should handle error gracefully
    
    assert state_manager.is_standby()
    assert not state_manager.is_transfer()

# Edge Case Tests
@pytest.mark.parametrize("initial_state,action,expected_state", [
    (SystemState.STANDBY, "transfer", SystemState.TRANSFER),
    (SystemState.STANDBY, "utility", SystemState.UTILITY),
    (SystemState.TRANSFER, "standby", SystemState.STANDBY),
    (SystemState.UTILITY, "standby", SystemState.STANDBY),
])
def test_state_transitions_matrix(state_manager, initial_state, action, expected_state):
    """Test various state transitions"""
    # Set initial state
    if initial_state == SystemState.TRANSFER:
        state_manager.enter_transfer()
    elif initial_state == SystemState.UTILITY:
        state_manager.enter_utility()
    
    # Perform action
    if action == "transfer":
        try:
            state_manager.enter_transfer()
        except StateTransitionError:
            pass
    elif action == "utility":
        state_manager.enter_utility()
    elif action == "standby":
        state_manager.enter_standby()
    
    assert state_manager.get_current_state() == expected_state

def test_concurrent_state_changes(state_manager):
    """Test rapid state changes"""
    for _ in range(10):
        state_manager.enter_transfer()
        time.sleep(0.01)  # Small delay to accumulate time
        state_manager.exit_transfer()  # Use exit_transfer instead of enter_standby
    
    assert state_manager.is_standby()
    total_time = state_manager.get_total_transfer_time()
    assert total_time > 0, f"Expected positive total time, got {total_time}"