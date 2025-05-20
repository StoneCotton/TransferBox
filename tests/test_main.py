import sys
import types
import pytest
from unittest import mock
from pathlib import Path
import os
import signal
import platform

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

def test_transfer_operation_execute_transfer_success(monkeypatch):
    display = mock.Mock()
    storage = mock.Mock()
    file_transfer = mock.Mock()
    sound_manager = mock.Mock()
    file_transfer.copy_sd_to_dump.return_value = True
    storage.unmount_drive.return_value = True
    op = main.TransferOperation(display, storage, file_transfer, sound_manager)
    source_drive = mock.Mock()
    destination_path = Path('/tmp')
    error = op.execute_transfer(source_drive, destination_path)
    assert error is False
    display.show_status.assert_any_call("Transfer complete")
    storage.unmount_drive.assert_called_once()

def test_transfer_operation_execute_transfer_failure(monkeypatch):
    display = mock.Mock()
    storage = mock.Mock()
    file_transfer = mock.Mock()
    sound_manager = mock.Mock()
    file_transfer.copy_sd_to_dump.return_value = False
    file_transfer.no_files_found = False
    storage.unmount_drive.return_value = True
    source_drive = mock.Mock()
    source_drive.exists.return_value = True
    monkeypatch.setattr(os.path, 'ismount', lambda x: True)
    op = main.TransferOperation(display, storage, file_transfer, sound_manager)
    destination_path = Path('/tmp')
    error = op.execute_transfer(source_drive, destination_path)
    assert error is True
    display.show_error.assert_any_call("Transfer failed")

def test_transfer_operation_execute_transfer_exception(monkeypatch):
    display = mock.Mock()
    storage = mock.Mock()
    file_transfer = mock.Mock()
    sound_manager = mock.Mock()
    file_transfer.copy_sd_to_dump.side_effect = Exception("fail")
    source_drive = mock.Mock()
    source_drive.exists.return_value = False
    monkeypatch.setattr(os.path, 'ismount', lambda x: False)
    op = main.TransferOperation(display, storage, file_transfer, sound_manager)
    destination_path = Path('/tmp')
    error = op.execute_transfer(source_drive, destination_path)
    assert error is True
    display.show_error.assert_any_call("Source removed")

def test_base_transfer_box_handle_shutdown(monkeypatch):
    box = main.BaseTransferBox()
    box.cleanup = mock.Mock()
    box.stop_event = mock.Mock()
    with pytest.raises(SystemExit):
        box.handle_shutdown(signal.SIGINT, None)
    box.stop_event.set.assert_called_once()
    box.cleanup.assert_called_once()

def test_desktop_transfer_box_get_destination_path_invalid(monkeypatch):
    box = main.DesktopTransferBox()
    box.display = mock.Mock()
    # Provide many dummy values to cover all input() calls
    inputs = iter(['', 'yes'] + [''] * 10 + ['/valid/path'] * 10)
    monkeypatch.setattr('builtins.input', lambda: next(inputs))
    monkeypatch.setattr('src.core.path_utils.is_plausible_user_path', lambda x: (x == '/valid/path', 'bad' if x != '/valid/path' else ''))
    monkeypatch.setattr('src.core.path_utils.sanitize_path', lambda x: x)
    monkeypatch.setattr('src.core.utils.validate_path', lambda x, **k: (x == '/valid/path', 'bad' if x != '/valid/path' else ''))
    result = box._get_destination_path()
    assert result is None
    box.display.show_error.assert_any_call('Too many invalid attempts.')

def test_desktop_transfer_box_run_tutorial_flow_skip(monkeypatch):
    box = main.DesktopTransferBox()
    monkeypatch.setattr(main, 'get_platform', lambda: 'darwin')
    monkeypatch.setattr('builtins.input', lambda: 'skip')
    # Patch rich.console.Console
    monkeypatch.setattr('rich.console.Console', lambda: mock.Mock(print=lambda x: None))
    box._run_tutorial_flow()  # Should exit early

def test_desktop_transfer_box_run_tutorial_flow_yes(monkeypatch):
    box = main.DesktopTransferBox()
    monkeypatch.setattr(main, 'get_platform', lambda: 'darwin')
    # Simulate: Enter, yes
    inputs = iter(['', 'yes'])
    monkeypatch.setattr('builtins.input', lambda: next(inputs))
    monkeypatch.setattr('rich.console.Console', lambda: mock.Mock(print=lambda x: None))
    box._run_tutorial_flow()  # Should proceed to end

def test_desktop_transfer_box_run_tutorial_flow_no(monkeypatch):
    box = main.DesktopTransferBox()
    monkeypatch.setattr(main, 'get_platform', lambda: 'darwin')
    # Simulate: Enter, no, yes
    inputs = iter(['', 'no', 'yes'])
    monkeypatch.setattr('builtins.input', lambda: next(inputs))
    monkeypatch.setattr('rich.console.Console', lambda: mock.Mock(print=lambda x: None))
    box._run_tutorial_flow()  # Should loop then exit

def skip_if_not_pi():
    if platform.system().lower() not in ('linux',) or 'raspberry' not in platform.uname().machine.lower():
        pytest.skip("Embedded mode tests are only relevant on Raspberry Pi.")

@pytest.mark.skipif(platform.system().lower() != 'linux' or 'raspberry' not in platform.uname().machine.lower(), reason="Embedded mode only runs on Raspberry Pi.")
def test_embedded_transfer_box_setup_raspberry_pi_import_error(monkeypatch):
    skip_if_not_pi()
    box = main.EmbeddedTransferBox()
    box.display = mock.Mock()
    box.sound_manager = mock.Mock()
    def fail_import(*a, **k):
        raise ImportError('fail')
    monkeypatch.setattr('src.platform.raspberry_pi.initializer_pi.RaspberryPiInitializer', fail_import)
    with pytest.raises(ImportError):
        box._setup_raspberry_pi()

@pytest.mark.skipif(platform.system().lower() != 'linux' or 'raspberry' not in platform.uname().machine.lower(), reason="Embedded mode only runs on Raspberry Pi.")
def test_embedded_transfer_box_run_impl_invalid_config(monkeypatch):
    skip_if_not_pi()
    box = main.EmbeddedTransferBox()
    box.display = mock.Mock()
    box.sound_manager = mock.Mock()
    box.config = mock.Mock()
    box.config.transfer_destination = 'bad_path'
    monkeypatch.setattr('src.core.path_utils.sanitize_path', lambda x: (_ for _ in ()).throw(Exception('fail')))
    box.stop_event = mock.Mock()
    box.stop_event.is_set.return_value = True
    # Should handle error and continue
    box._run_impl()

@pytest.mark.skipif(platform.system().lower() != 'linux' or 'raspberry' not in platform.uname().machine.lower(), reason="Embedded mode only runs on Raspberry Pi.")
def test_embedded_transfer_box_cleanup(monkeypatch):
    skip_if_not_pi()
    box = main.EmbeddedTransferBox()
    box.pi_initializer = mock.Mock()
    box.sound_manager = mock.Mock()
    box.display = mock.Mock()
    main.BaseTransferBox.cleanup = mock.Mock()
    box.cleanup()
    box.pi_initializer.cleanup.assert_called_once()

# Error handling in BaseTransferBox.cleanup

def test_base_transfer_box_cleanup_error(monkeypatch):
    box = main.BaseTransferBox()
    box.sound_manager = mock.Mock()
    box.display = mock.Mock()
    box.sound_manager.cleanup.side_effect = Exception('fail')
    box.cleanup()  # Should log error and not raise

# Error handling in BaseTransferBox.setup

def test_base_transfer_box_setup(monkeypatch):
    box = main.BaseTransferBox()
    box.display = mock.Mock()
    box.sound_manager = mock.Mock()
    box.display.clear = mock.Mock()
    box.display.show_status = mock.Mock()
    box.setup()
    box.display.clear.assert_called_once()
    box.display.show_status.assert_called_with('Completed: Setup') 