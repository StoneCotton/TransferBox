import sys
import types
import pytest
from unittest import mock
from pathlib import Path

import main

def test_parse_arguments_defaults(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    args = main.parse_arguments()
    assert not args.benchmark
    assert args.buffer_sizes is None
    assert args.file_sizes is None
    assert args.iterations == 3

def test_parse_arguments_benchmark(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--benchmark', '--buffer-sizes', '1,2', '--file-sizes', '10,20', '--iterations', '5'])
    args = main.parse_arguments()
    assert args.benchmark
    assert args.buffer_sizes == '1,2'
    assert args.file_sizes == '10,20'
    assert args.iterations == 5

def test_create_transfer_box_app_desktop(monkeypatch):
    monkeypatch.setattr(main, 'get_platform', lambda: 'darwin')
    app = main.create_transfer_box_app()
    from main import DesktopTransferBox
    assert isinstance(app, DesktopTransferBox)

def test_create_transfer_box_app_embedded(monkeypatch):
    monkeypatch.setattr(main, 'get_platform', lambda: 'raspberry_pi')
    app = main.create_transfer_box_app()
    from main import EmbeddedTransferBox
    assert isinstance(app, EmbeddedTransferBox)

def test_run_benchmark(monkeypatch):
    called = {}
    def fake_run_benchmark_cli():
        called['ran'] = True
        return 42
    monkeypatch.setattr('src.core.benchmark.run_benchmark_cli', fake_run_benchmark_cli)
    args = types.SimpleNamespace(buffer_sizes='1', file_sizes='2', iterations=1)
    result = main.run_benchmark(args)
    assert called['ran']
    assert result == 42

def test_main_benchmark(monkeypatch):
    monkeypatch.setattr(main, 'parse_arguments', lambda: types.SimpleNamespace(benchmark=True, buffer_sizes=None, file_sizes=None, iterations=3))
    monkeypatch.setattr(main, 'run_benchmark', lambda args: 123)
    assert main.main() == 123

def test_main_normal(monkeypatch):
    fake_app = mock.Mock()
    fake_app.run.return_value = None
    monkeypatch.setattr(main, 'parse_arguments', lambda: types.SimpleNamespace(benchmark=False))
    monkeypatch.setattr(main, 'create_transfer_box_app', lambda: fake_app)
    assert main.main() == 0

def test_main_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(main, 'parse_arguments', lambda: types.SimpleNamespace(benchmark=False))
    def fake_create():
        raise KeyboardInterrupt()
    monkeypatch.setattr(main, 'create_transfer_box_app', fake_create)
    assert main.main() == 0

def test_main_exception(monkeypatch):
    monkeypatch.setattr(main, 'parse_arguments', lambda: types.SimpleNamespace(benchmark=False))
    def fake_create():
        raise RuntimeError('fail')
    monkeypatch.setattr(main, 'create_transfer_box_app', fake_create)
    monkeypatch.setattr(main.logger, 'exception', lambda *a, **k: None)
    assert main.main() == 1 