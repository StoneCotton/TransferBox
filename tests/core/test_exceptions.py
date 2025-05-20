import pytest
from src.core.exceptions import (
    TransferBoxError, ConfigError, StorageError, FileTransferError,
    ChecksumError, HardwareError, StateError, DisplayError, SoundError
)

# --- TransferBoxError ---
def test_transferboxerror_basic():
    e = TransferBoxError("msg", recoverable=False, recovery_steps=["step1"])
    assert str(e) == "msg"
    assert not e.recoverable
    assert e.recovery_steps == ["step1"]
    assert isinstance(e, Exception)

# --- ConfigError ---
def test_configerror_defaults():
    e = ConfigError("bad config", config_key="foo", invalid_value=123, expected_type=int)
    assert e.config_key == "foo"
    assert e.invalid_value == 123
    assert e.expected_type == int
    assert "Validate the 'foo' setting" in e.recovery_steps
    assert isinstance(e, TransferBoxError)

def test_configerror_custom_steps():
    e = ConfigError("bad", recovery_steps=["custom"])
    assert e.recovery_steps == ["custom"]

# --- StorageError ---
@pytest.mark.parametrize("msg,etype,expected_step", [
    ("permission denied", None, "permissions"),
    ("no space left", None, "space"),
    ("mount failed", None, "mount"),
    ("unknown error", None, "device"),
    ("explicit", "mount", "remounting"),
])
def test_storageerror_types(msg, etype, expected_step):
    e = StorageError(msg, path="/dev/sda", device="disk1", error_type=etype)
    assert e.path == "/dev/sda"
    assert e.device == "disk1"
    assert isinstance(e, TransferBoxError)
    # Check recovery steps contain a keyword for the error type
    assert any(expected_step in s for s in e.recovery_steps)

# --- FileTransferError ---
@pytest.mark.parametrize("msg,etype,expected_step", [
    ("permission denied", None, "permissions"),
    ("network error", None, "network"),
    ("interrupted", None, "restart"),
    ("unknown", None, "source"),
    ("explicit", "network", "network"),
])
def test_filetransfererror_types(msg, etype, expected_step):
    e = FileTransferError(msg, source="src", destination="dst", error_type=etype)
    assert e.source == "src"
    assert e.destination == "dst"
    assert isinstance(e, TransferBoxError)
    # Check recovery steps contain a keyword for the error type (case-insensitive substring)
    assert any(expected_step.lower() in s.lower() for s in e.recovery_steps)

# --- ChecksumError ---
def test_checksumerror_attrs():
    e = ChecksumError("bad sum", file_path="f", expected="a", actual="b")
    assert e.file_path == "f"
    assert e.expected == "a"
    assert e.actual == "b"
    assert "integrity" in " ".join(e.recovery_steps)
    assert isinstance(e, FileTransferError)

# --- HardwareError ---
@pytest.mark.parametrize("component,expected_step", [
    ("display", "display"),
    ("button", "button"),
    ("led", "LED"),
    ("other", "hardware"),
])
def test_hardwareerror_components(component, expected_step):
    e = HardwareError("fail", component=component)
    assert e.component == component
    assert any(expected_step.lower() in s.lower() for s in e.recovery_steps)
    assert isinstance(e, TransferBoxError)

# --- StateError ---
def test_stateerror_attrs():
    e = StateError("bad state", current_state="A", target_state="B")
    assert e.current_state == "A"
    assert e.target_state == "B"
    assert "standby" in " ".join(e.recovery_steps)
    assert isinstance(e, TransferBoxError)

# --- DisplayError & SoundError ---
def test_displayerror_attrs():
    e = DisplayError("fail", display_type="oled", error_type="hw")
    assert e.display_type == "oled"
    assert e.error_type == "hw"
    assert "display" in " ".join(e.recovery_steps)
    assert isinstance(e, TransferBoxError)

def test_sounderror_attrs():
    e = SoundError("fail", sound_type="beep", error_type="hw")
    assert e.sound_type == "beep"
    assert e.error_type == "hw"
    assert "audio" in " ".join(e.recovery_steps)
    assert isinstance(e, TransferBoxError) 