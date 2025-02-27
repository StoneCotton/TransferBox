# tests/core/test_config_error.py
"""
Tests for the ConfigError exception class in the exceptions module.

This test module verifies that the ConfigError properly:
1. Extends the TransferBoxError base class
2. Stores appropriate error metadata
3. Provides recovery steps for various error conditions
"""
import pytest
from pathlib import Path
from typing import List, Dict, Any, Optional, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

# Import the modules to test
from src.core.exceptions import ConfigError, TransferBoxError


class TestConfigError:
    """Tests for the ConfigError exception class."""

    def test_inheritance(self) -> None:
        """Test that ConfigError inherits from TransferBoxError."""
        error = ConfigError("Test error message")
        assert isinstance(error, TransferBoxError)
        assert isinstance(error, Exception)

    def test_basic_properties(self) -> None:
        """Test that ConfigError correctly stores basic properties."""
        error_message = "Invalid configuration value"
        error = ConfigError(error_message)
        
        assert str(error) == error_message
        assert error.recoverable is True  # ConfigErrors are recoverable by default
        assert isinstance(error.recovery_steps, list)
        assert len(error.recovery_steps) > 0  # Should have default recovery steps

    def test_with_config_key(self) -> None:
        """Test ConfigError with specified config key."""
        error = ConfigError(
            "Invalid date format",
            config_key="date_folder_format",
            invalid_value="%Y/%m/%q",
            expected_type="valid strftime format"
        )
        
        assert error.config_key == "date_folder_format"
        assert error.invalid_value == "%Y/%m/%q"
        assert error.expected_type == "valid strftime format"
        assert isinstance(error.recovery_steps, list)
        assert any("date_folder_format" in step for step in error.recovery_steps)

    def test_error_formatting(self) -> None:
        """Test that ConfigError formats the error message appropriately."""
        # Create error with various attributes
        error = ConfigError(
            "Value cannot be parsed as boolean",
            config_key="rename_with_timestamp",
            invalid_value="not_a_boolean",
            expected_type="boolean"
        )
        
        error_str = str(error)
        assert "Value cannot be parsed as boolean" in error_str
        
        # Full message should be just what was passed in
        assert error_str == "Value cannot be parsed as boolean"

    def test_custom_recovery_steps(self) -> None:
        """Test ConfigError with custom recovery steps."""
        custom_steps = [
            "Check YAML syntax",
            "Verify config key names",
            "Try regenerating default config"
        ]
        
        error = ConfigError(
            "Invalid YAML syntax",
            recovery_steps=custom_steps
        )
        
        assert error.recovery_steps == custom_steps
        assert len(error.recovery_steps) == 3
        assert error.recovery_steps[0] == "Check YAML syntax"

    def test_recovery_steps_for_missing_key(self) -> None:
        """Test that default recovery steps are appropriate for missing config keys."""
        error = ConfigError(
            "Configuration not loaded. Call load_config() first."
        )
        
        # Should include general validation steps
        assert any("configuration file" in step.lower() for step in error.recovery_steps)

    def test_string_representation(self) -> None:
        """Test string representation of ConfigError."""
        error = ConfigError(
            "Invalid media extensions format",
            config_key="media_extensions",
            invalid_value=123
        )
        
        # The string representation should be the error message
        assert str(error) == "Invalid media extensions format"