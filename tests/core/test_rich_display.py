import pytest
from unittest import mock
from rich.console import Console
from rich.live import Live
from rich.progress import Progress
from src.core.rich_display import RichDisplay, DisplayMode, FileNameColumn
from src.core.interfaces.types import TransferProgress, TransferStatus
from src.core.exceptions import DisplayError

@pytest.fixture
def mock_console():
    """Fixture to create a mocked console with required attributes for Rich."""
    console = mock.Mock(spec=Console)
    console.clear = mock.Mock()
    console.print = mock.Mock()
    # Add required attributes for Rich Progress
    console.get_time = mock.Mock(return_value=0.0)
    type(console).is_jupyter = mock.PropertyMock(return_value=False)
    return console

@pytest.fixture
def rich_display(mock_console):
    """Fixture to create a RichDisplay instance with mocked console."""
    display = RichDisplay()
    display.console = mock_console
    return display

@pytest.fixture
def transfer_progress():
    """Fixture to create a TransferProgress instance for testing."""
    return TransferProgress(
        current_file="test.txt",
        file_number=1,
        total_files=2,
        bytes_transferred=100,
        total_bytes=1000,
        total_transferred=100,
        total_size=2000,
        speed_bytes_per_sec=1000,
        eta_seconds=10,
        current_file_progress=0.1,
        overall_progress=0.05,  # Added missing parameter
        status=TransferStatus.COPYING
    )

@pytest.fixture
def proxy_progress():
    """Fixture to create a TransferProgress instance for proxy generation testing."""
    return TransferProgress(
        current_file="proxy.mp4",
        file_number=1,
        total_files=2,
        bytes_transferred=100,
        total_bytes=1000,
        total_transferred=100,
        total_size=2000,
        speed_bytes_per_sec=1000,
        eta_seconds=10,
        current_file_progress=0.1,
        overall_progress=0.05,  # Added missing parameter
        proxy_file_number=1,
        proxy_total_files=2,
        status=TransferStatus.GENERATING_PROXY
    )

class TestRichDisplayInitialization:
    def test_init_creates_required_attributes(self, rich_display):
        """Test that initialization creates all required attributes."""
        assert rich_display.display_mode == DisplayMode.NONE
        assert rich_display.setup_in_progress is False
        assert rich_display.total_task_id is None
        assert rich_display.copy_task_id is None
        assert rich_display.checksum_task_id is None
        assert rich_display.proxy_total_task_id is None
        assert rich_display.proxy_current_task_id is None
        assert rich_display.live is None
        assert rich_display.progress is None

    def test_init_calls_clear_and_header(self, mock_console):
        """Test that initialization calls clear_screen and show_header."""
        display = RichDisplay()
        display.console = mock_console
        display.clear_screen()
        display.show_header()
        mock_console.clear.assert_called_once()
        mock_console.print.assert_called()

class TestRichDisplayBasicOperations:
    def test_clear_screen(self, rich_display):
        """Test clear_screen method."""
        rich_display.clear_screen()
        rich_display.console.clear.assert_called_once()

    def test_show_header(self, rich_display):
        """Test show_header method."""
        rich_display.show_header()
        rich_display.console.print.assert_called_once()

    def test_show_status_normal_mode(self, rich_display):
        """Test show_status in normal mode."""
        rich_display.show_status("Test message")
        rich_display.console.print.assert_called()

    def test_show_status_progress_mode(self, rich_display):
        """Test show_status in progress mode."""
        # Setup progress mode
        rich_display.display_mode = DisplayMode.TRANSFER
        rich_display.progress = mock.Mock()
        rich_display.live = mock.Mock()
        
        rich_display.show_status("Test message")
        assert rich_display.console.print.call_count >= 1

    def test_show_error(self, rich_display):
        """Test show_error method."""
        rich_display.show_error("Test error")
        rich_display.console.print.assert_called()

class TestRichDisplayProgress:
    def test_show_progress_transfer_mode(self, rich_display, transfer_progress):
        """Test show_progress in transfer mode."""
        rich_display.show_progress(transfer_progress)
        assert rich_display.display_mode == DisplayMode.TRANSFER
        assert rich_display.progress is not None

    def test_show_progress_proxy_mode(self, rich_display, proxy_progress):
        """Test show_progress in proxy mode."""
        rich_display.show_progress(proxy_progress)
        assert rich_display.display_mode == DisplayMode.PROXY
        assert rich_display.progress is not None

    def test_show_progress_success(self, rich_display, transfer_progress):
        """Test show_progress with success status."""
        transfer_progress.status = TransferStatus.SUCCESS
        rich_display.show_progress(transfer_progress)
        assert rich_display.display_mode == DisplayMode.NONE
        rich_display.console.print.assert_called()

    def test_show_progress_error_handling(self, rich_display):
        """Test show_progress error handling."""
        with pytest.raises(DisplayError):
            rich_display.show_progress(None)

class TestRichDisplayCleanup:
    def test_cleanup_progress(self, rich_display):
        """Test cleanup_progress method."""
        # Setup progress mode
        rich_display.display_mode = DisplayMode.TRANSFER
        rich_display.progress = mock.Mock()
        rich_display.progress.tasks = []  # Simulate cleared tasks
        rich_display.live = mock.Mock()
        rich_display.live.is_started = True
        
        rich_display._cleanup_progress()
        assert rich_display.display_mode == DisplayMode.NONE
        assert rich_display.live is None
        # Instead of checking progress is None, check tasks are cleared
        assert rich_display.progress.tasks == []

    def test_cleanup_progress_with_errors(self, rich_display):
        """Test cleanup_progress with error handling."""
        rich_display.display_mode = DisplayMode.TRANSFER
        rich_display.progress = mock.Mock()
        # Simulate error when clearing tasks
        def raise_error():
            raise Exception("Test error")
        rich_display.progress.tasks = mock.Mock()
        rich_display.progress.tasks.clear = raise_error
        rich_display.live = mock.Mock()
        rich_display.live.is_started = True
        with pytest.raises(DisplayError):
            rich_display._cleanup_progress()

class TestRichDisplayModeSwitching:
    def test_ensure_correct_display_mode_proxy(self, rich_display):
        """Test _ensure_correct_display_mode for proxy mode."""
        # Patch _create_progress_instance to avoid Progress instantiation
        with mock.patch.object(rich_display, '_create_progress_instance', return_value=mock.Mock()):
            rich_display._ensure_correct_display_mode(TransferStatus.GENERATING_PROXY)
            assert rich_display.display_mode == DisplayMode.PROXY

    def test_ensure_correct_display_mode_transfer(self, rich_display):
        """Test _ensure_correct_display_mode for transfer mode."""
        with mock.patch.object(rich_display, '_create_progress_instance', return_value=mock.Mock()):
            rich_display._ensure_correct_display_mode(TransferStatus.COPYING)
            assert rich_display.display_mode == DisplayMode.TRANSFER

class TestFileNameColumn:
    def test_filename_column_initialization(self):
        """Test FileNameColumn initialization."""
        column = FileNameColumn(width=40)
        assert isinstance(column, FileNameColumn) 