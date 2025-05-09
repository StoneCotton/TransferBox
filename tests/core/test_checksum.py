import pytest
import xxhash
from pathlib import Path
from src.core.checksum import ChecksumCalculator


def create_temp_file(tmp_path, content: bytes) -> Path:
    file_path = tmp_path / "testfile.bin"
    file_path.write_bytes(content)
    return file_path


def test_calculate_file_checksum_happy_path(tmp_path, mock_display_interface):
    content = b"TransferBox checksum test content."
    file_path = create_temp_file(tmp_path, content)
    expected_checksum = xxhash.xxh64(content).hexdigest()
    calc = ChecksumCalculator(mock_display_interface)
    result = calc.calculate_file_checksum(file_path)
    assert result == expected_checksum
    mock_display_interface.show_error.assert_not_called()


def test_verify_checksum_happy_path(tmp_path, mock_display_interface):
    content = b"Another test for checksum verification."
    file_path = create_temp_file(tmp_path, content)
    expected_checksum = xxhash.xxh64(content).hexdigest()
    calc = ChecksumCalculator(mock_display_interface)
    assert calc.verify_checksum(file_path, expected_checksum) is True
    assert calc.verify_checksum(file_path, "deadbeef") is False
    mock_display_interface.show_error.assert_not_called() 


def test_calculate_file_checksum_file_not_found(tmp_path, mock_display_interface):
    calc = ChecksumCalculator(mock_display_interface)
    missing_file = tmp_path / "does_not_exist.bin"
    result = calc.calculate_file_checksum(missing_file)
    assert result is None
    mock_display_interface.show_error.assert_called_once()


def test_verify_checksum_file_not_found(tmp_path, mock_display_interface):
    calc = ChecksumCalculator(mock_display_interface)
    missing_file = tmp_path / "does_not_exist.bin"
    assert calc.verify_checksum(missing_file, "abcd1234") is False
    mock_display_interface.show_error.assert_not_called()  # verify_checksum does not call show_error on file not found


def test_verify_checksum_no_expected_checksum(tmp_path, mock_display_interface):
    content = b"test"
    file_path = create_temp_file(tmp_path, content)
    calc = ChecksumCalculator(mock_display_interface)
    assert calc.verify_checksum(file_path, "") is False
    mock_display_interface.show_error.assert_not_called()


def test_calculate_file_checksum_progress_callback(tmp_path, mock_display_interface, mocker):
    content = b"progress callback test"
    file_path = create_temp_file(tmp_path, content)
    callback = mocker.Mock()
    calc = ChecksumCalculator(mock_display_interface)
    calc.calculate_file_checksum(file_path, progress_callback=callback)
    callback.assert_called()


def test_calculate_file_checksum_display_error_handling(tmp_path, mocker):
    content = b"display error test"
    file_path = create_temp_file(tmp_path, content)
    mock_display = mocker.Mock()
    mock_display.show_progress.side_effect = Exception("Display error")
    mock_display.show_error = mocker.Mock()
    calc = ChecksumCalculator(mock_display)
    result = calc.calculate_file_checksum(file_path)
    assert result == xxhash.xxh64(content).hexdigest()
    mock_display.show_error.assert_not_called() 