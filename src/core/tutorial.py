# src/core/tutorial.py

import logging
from .utils import get_platform

logger = logging.getLogger(__name__)


class TutorialManager:
    """Manages interactive tutorials for first-time users"""
    
    def __init__(self, display=None):
        self.display = display
        self.platform = get_platform()
        self._tutorial_shown = False
        
    def should_show_tutorial(self, config):
        """Check if tutorial should be shown"""
        return getattr(config, 'tutorial_mode', False) and not self._tutorial_shown
    
    def run_desktop_tutorial_flow(self):
        """Interactive tutorial for first-time users in desktop mode."""
        console = None
        try:
            from rich.console import Console
            console = Console()
        except ImportError:
            pass
            
        def print_msg(msg):
            if console:
                console.print(msg)
            else:
                print(msg)
                
        def get_valid_input(prompt, valid, max_attempts=3):
            attempts = 0
            while attempts < max_attempts:
                print_msg(prompt)
                resp = input().strip().lower()
                if resp in valid:
                    return resp
                print_msg("[red]Invalid input. Please choose a correct option.[/red]")
                attempts += 1
            print_msg("[yellow]Too many invalid attempts. Skipping this step.[/yellow]")
            return 'skip'
            
        # Step 1
        step1_prompt = ("[bold cyan]Make sure that your SD card is not plugged into the system. "
                       "If it is, safely eject the card.[/bold cyan]\n"
                       "Press Enter to continue or type 'skip' to skip tutorial...")
        resp = get_valid_input(step1_prompt, {'', 'skip'})
        if resp == 'skip':
            return
            
        # Step 2/2a loop
        while True:
            step2_prompt = ("[bold cyan]Have you located the directory that the media will be "
                           "transferred to?[/bold cyan]\n"
                           "([green]YES[/green] / [red]NO[/red] / SKIP)")
            resp = get_valid_input(step2_prompt, {'y', 'yes', 'n', 'no', 'skip'})
            if resp == 'skip':
                return
            if resp in {'y', 'yes'}:
                break
                
            # Step 2a - Platform-specific instructions
            self._show_platform_instructions(print_msg)
            
        print_msg("[bold green]Great! Proceeding to destination path entry...[/bold green]")
        self._tutorial_shown = True
    
    def _show_platform_instructions(self, print_msg):
        """Show platform-specific instructions for finding file paths"""
        if self.platform == 'darwin':
            print_msg("[yellow]Go to Finder, and find the destination that you want to transfer "
                     "your media. Once found, right click on the destination and press 'Option' "
                     "to then 'Copy as Pathname'.[/yellow]")
        elif self.platform == 'windows':
            print_msg("[yellow]Go to Explorer, and find the destination that you want to transfer "
                     "your media. Once found, highlight and copy the destination path from the "
                     "navigation pane.[/yellow]")
        else:
            print_msg("[yellow]Locate your destination directory using your file manager and "
                     "copy its path.[/yellow]")
    
    def run_webui_tutorial_flow(self):
        """Tutorial flow for web UI - handled by frontend"""
        # In web UI mode, tutorial is handled by the frontend
        # Just show a message that tutorial is available
        if self.display:
            self.display.show_status("Tutorial available in web interface")
        else:
            logger.info("Tutorial available in web interface")
        self._tutorial_shown = True


class DestinationPathManager:
    """Manages destination path validation and input handling"""
    
    def __init__(self, display):
        self.display = display
        self.tutorial_manager = TutorialManager(display)
        
    def get_destination_path(self, config):
        """Get and validate destination path from user, with robust input validation."""
        from .path_utils import is_plausible_user_path
        from .utils import validate_path
        from .path_utils import sanitize_path
        import platform as plt
        
        # Show tutorial if needed
        if self.tutorial_manager.should_show_tutorial(config):
            self.tutorial_manager.run_desktop_tutorial_flow()
        
        # Platform-specific example paths
        system = plt.system().lower()
        if system == 'darwin':
            example_path = '/Volumes/BM-PRODUCTION/01_Burden Media/#2025 Content/05_FPV Shoot'
        elif system == 'windows':
            example_path = r'K:\BM-PRODUCTION\01_Burden Media\2025 Content\05_FPV Shoot'
        elif system == 'linux':
            example_path = '/home/yourname/Media'
        else:
            example_path = '/absolute/path/to/destination'
            
        def get_valid_input(prompt, valid, max_attempts=3):
            attempts = 0
            while attempts < max_attempts:
                self.display.show_status(prompt)
                resp = input().strip().lower()
                if resp in valid:
                    return resp
                self.display.show_error("Invalid input. Please choose a correct option.")
                attempts += 1
            self.display.show_error("Too many invalid attempts.")
            return 'exit'
            
        max_attempts = 3
        attempts = 0
        
        while True:
            if attempts >= max_attempts:
                # Hybrid: ask user if they want to retry tutorial or exit
                prompt = "Too many invalid attempts. Would you like to retry the tutorial or exit? (retry/exit)"
                resp = get_valid_input(prompt, {'retry', 'exit'}, max_attempts=1)
                if resp == 'retry':
                    self.tutorial_manager.run_desktop_tutorial_flow()
                    attempts = 0
                    continue
                else:
                    self.display.show_error("Exiting destination entry.")
                    return None
                    
            self.display.show_status(f"Enter destination path (e.g., {example_path}):")
            raw_destination = input().strip()
            
            # Validate plausibility
            plausible, plausible_error = is_plausible_user_path(raw_destination)
            if not plausible:
                self.display.show_error(f"{plausible_error} Example: {example_path}")
                attempts += 1
                continue
                
            # Sanitize path
            try:
                sanitized_destination = sanitize_path(raw_destination)
            except Exception as e:
                logger.error(f"Error sanitizing path: {e}")
                self.display.show_error(f"Invalid path format. Example: {example_path}")
                attempts += 1
                continue
                
            # Validate path
            is_valid, error_msg = validate_path(
                sanitized_destination, 
                must_exist=False, 
                must_be_writable=True
            )
            if not is_valid:
                self.display.show_error(f"{error_msg} Example: {example_path}")
                attempts += 1
                continue
                
            return sanitized_destination 