import sys
import types
import pytest
from unittest import mock
from pathlib import Path
import os
import signal
import platform

import main
from src.core.validation import ErrorMessages
from src.cli.application_factory import run_benchmark, run_application, validate_arguments
from src.cli.argument_parser import parse_arguments
from src.core.transfer_box_factory import create_transfer_box
from src.core.transfer_operation import TransferOperation
from src.core.transfer_box_base import BaseTransferBox
from src.core.transfer_box_desktop import DesktopTransferBox
from src.core.transfer_box_embedded import EmbeddedTransferBox

def test_parse_arguments_defaults(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    args = parse_arguments()
    assert not args.benchmark
    assert args.buffer_sizes is None
    assert args.file_sizes is None
    assert args.iterations == 3

def test_parse_arguments_benchmark(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--benchmark', '--buffer-sizes', '1,2', '--file-sizes', '10,20', '--iterations', '5'])
    args = parse_arguments()
    assert args.benchmark
    assert args.buffer_sizes == '1,2'
    assert args.file_sizes == '10,20'
    assert args.iterations == 5

def test_create_transfer_box_app_desktop(monkeypatch):
    from src.core.utils import get_platform
    monkeypatch.setattr('src.core.utils.get_platform', lambda: 'darwin')
    app = create_transfer_box()
    assert isinstance(app, DesktopTransferBox)

def test_create_transfer_box_app_embedded(monkeypatch):
    # Pass platform directly to avoid mocking issues
    app = create_transfer_box(platform='embedded')
    assert isinstance(app, EmbeddedTransferBox)

def test_run_benchmark(monkeypatch):
    called = {}
    def fake_run_benchmark_cli():
        called['ran'] = True
        return 42
    monkeypatch.setattr('src.core.benchmark.run_benchmark_cli', fake_run_benchmark_cli)
    args = types.SimpleNamespace(buffer_sizes='1', file_sizes='2', iterations=1)
    result = run_benchmark(args)
    assert called['ran']
    assert result == 42

def test_main_benchmark(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--benchmark'])
    
    # Mock the benchmark module to avoid import errors
    def fake_run_benchmark_cli():
        return 123
    
    # Mock the benchmark import to avoid missing interface imports
    monkeypatch.setattr('src.core.benchmark.run_benchmark_cli', fake_run_benchmark_cli)
    
    assert main.main() == 123

def test_main_normal(monkeypatch):
    fake_app = mock.Mock()
    fake_app.run.return_value = None
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    monkeypatch.setattr('src.core.transfer_box_factory.create_transfer_box', lambda **kwargs: fake_app)
    assert main.main() == 0

def test_main_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    def fake_create(**kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr('src.core.transfer_box_factory.create_transfer_box', fake_create)
    assert main.main() == 0

def test_main_exception(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    def fake_create(**kwargs):
        raise RuntimeError('fail')
    monkeypatch.setattr('src.core.transfer_box_factory.create_transfer_box', fake_create)
    monkeypatch.setattr(main.logger, 'error', lambda *a, **k: None)
    assert main.main() == 1

def test_transfer_operation_execute_transfer_success(monkeypatch):
    display = mock.Mock()
    storage = mock.Mock()
    file_transfer = mock.Mock()
    sound_manager = mock.Mock()
    file_transfer.copy_sd_to_dump.return_value = True
    storage.unmount_drive.return_value = True
    op = TransferOperation(display, storage, file_transfer, sound_manager)
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
    op = TransferOperation(display, storage, file_transfer, sound_manager)
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
    op = TransferOperation(display, storage, file_transfer, sound_manager)
    destination_path = Path('/tmp')
    error = op.execute_transfer(source_drive, destination_path)
    assert error is True
    display.show_error.assert_any_call(ErrorMessages.SOURCE_REMOVED)

def test_base_transfer_box_handle_shutdown(monkeypatch):
    box = BaseTransferBox()
    box.cleanup = mock.Mock()
    box.stop_event = mock.Mock()
    with pytest.raises(SystemExit):
        box.handle_shutdown(signal.SIGINT, None)
    box.stop_event.set.assert_called_once()
    box.cleanup.assert_called_once()

def test_desktop_transfer_box_get_destination_path_invalid(monkeypatch):
    box = DesktopTransferBox()
    box.display = mock.Mock()
    box.destination_path_manager = mock.Mock()
    box.destination_path_manager.get_destination_path.return_value = None
    result = box._get_destination_path()
    assert result is None

@pytest.mark.skip(reason="Tutorial flow is not implemented in desktop version")
def test_desktop_transfer_box_run_tutorial_flow_skip(monkeypatch):
    pass

@pytest.mark.skip(reason="Tutorial flow is not implemented in desktop version")
def test_desktop_transfer_box_run_tutorial_flow_yes(monkeypatch):
    pass

@pytest.mark.skip(reason="Tutorial flow is not implemented in desktop version")
def test_desktop_transfer_box_run_tutorial_flow_no(monkeypatch):
    pass

def skip_if_not_pi():
    if platform.system().lower() not in ('linux',) or 'raspberry' not in platform.uname().machine.lower():
        pytest.skip("Embedded mode tests are only relevant on Raspberry Pi.")

@pytest.mark.skipif(platform.system().lower() != 'linux' or 'raspberry' not in platform.uname().machine.lower(), reason="Embedded mode only runs on Raspberry Pi.")
def test_embedded_transfer_box_setup_raspberry_pi_import_error(monkeypatch):
    skip_if_not_pi()
    box = EmbeddedTransferBox()
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
    box = EmbeddedTransferBox()
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
    box = EmbeddedTransferBox()
    box.pi_initializer = mock.Mock()
    box.sound_manager = mock.Mock()
    box.display = mock.Mock()
    BaseTransferBox.cleanup = mock.Mock()
    box.cleanup()
    box.pi_initializer.cleanup.assert_called_once()

# Error handling in BaseTransferBox.cleanup

def test_base_transfer_box_cleanup_error(monkeypatch):
    box = BaseTransferBox()
    box.sound_manager = mock.Mock()
    box.display = mock.Mock()
    box.sound_manager.cleanup.side_effect = Exception('fail')
    box.cleanup()  # Should log error and not raise

# Error handling in BaseTransferBox.setup

def test_base_transfer_box_setup(monkeypatch):
    box = BaseTransferBox()
    box.display = mock.Mock()
    box.sound_manager = mock.Mock()
    box.display.clear = mock.Mock()
    box.display.show_status = mock.Mock()
    box.setup()
    box.display.clear.assert_called_once()
    box.display.show_status.assert_called_with('Completed: Setup') 