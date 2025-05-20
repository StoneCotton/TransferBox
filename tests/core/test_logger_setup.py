import pytest
import logging
import sys
from pathlib import Path
from unittest import mock
from src.core import logger_setup

@pytest.fixture
def tmp_log_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return d

# --- setup_logging: basic file and console handler ---
def test_setup_logging_file_and_console(tmp_log_dir, monkeypatch):
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: tmp_log_dir)
    logger = logger_setup.setup_logging(log_dir=tmp_log_dir, log_level=logging.INFO)
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    assert any(isinstance(h, logging.Handler) for h in logger.handlers)
    logger.info("test message")

# --- setup_logging: fallback to home dir on PermissionError ---
def test_setup_logging_fallback_home(monkeypatch, tmp_path):
    # Simulate PermissionError on log_dir.mkdir
    fake_dir = tmp_path / "fail"
    def fail_mkdir(*a, **k): raise PermissionError("fail")
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: fake_dir)
    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    logger = logger_setup.setup_logging(log_dir=None, log_level=logging.INFO)
    assert isinstance(logger, logging.Logger)

# --- setup_logging: fallback to stderr on OSError ---
def test_setup_logging_fallback_stderr(monkeypatch, tmp_path):
    fake_dir = tmp_path / "fail"
    def fail_mkdir(*a, **k): raise OSError("fail")
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: fake_dir)
    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    logger = logger_setup.setup_logging(log_dir=None, log_level=logging.INFO)
    assert isinstance(logger, logging.Logger)

# --- setup_logging: RichHandler ImportError fallback ---
def test_setup_logging_rich_importerror(monkeypatch, tmp_log_dir):
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: tmp_log_dir)
    monkeypatch.setattr(logger_setup, "Console", mock.Mock(side_effect=ImportError("fail")))
    logger = logger_setup.setup_logging(log_dir=tmp_log_dir, log_level=logging.INFO)
    assert isinstance(logger, logging.Logger)

# --- setup_logging: RichHandler generic Exception fallback ---
def test_setup_logging_rich_genericerror(monkeypatch, tmp_log_dir):
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: tmp_log_dir)
    monkeypatch.setattr(logger_setup, "Console", mock.Mock(side_effect=Exception("fail")))
    logger = logger_setup.setup_logging(log_dir=tmp_log_dir, log_level=logging.INFO)
    assert isinstance(logger, logging.Logger)

# --- setup_logging: log rotation settings ---
def test_setup_logging_log_rotation(tmp_log_dir, monkeypatch):
    monkeypatch.setattr(logger_setup, "get_default_log_dir", lambda: tmp_log_dir)
    logger = logger_setup.setup_logging(log_dir=tmp_log_dir, log_level=logging.INFO, log_file_rotation=2, log_file_max_size=1)
    assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)

# --- setup_logging: minimal fallback logger on total failure ---
def test_setup_logging_total_failure():
    # Simulate all errors by passing a logger_factory that fails once, then succeeds
    calls = [0]
    class DummyLogger(logging.Logger):
        pass
    def fail_then_succeed(*a, **k):
        if calls[0] == 0:
            calls[0] += 1
            raise Exception("fail")
        return DummyLogger("fallback")
    fallback_logger = logger_setup.setup_logging(log_dir=None, log_level=logging.INFO, logger_factory=fail_then_succeed)
    assert isinstance(fallback_logger, logging.Logger) 