#!/usr/bin/env python3
"""
TransferBox Launcher - Defaults to Web UI mode
"""
import sys
import os
from pathlib import Path

# Add the main application directory to the path
if getattr(sys, 'frozen', False):
    # Running from PyInstaller bundle
    app_dir = Path(sys.executable).parent
else:
    # Running from source
    app_dir = Path(__file__).parent

sys.path.insert(0, str(app_dir))

# Import and run the main application
try:
    from main import main, parse_arguments
    
    # Check if --webui is already in arguments
    if '--webui' not in sys.argv and '--benchmark' not in sys.argv:
        # Add --webui flag by default
        sys.argv.append('--webui')
        print("Starting TransferBox in Web UI mode...")
        print("To use terminal mode, run with: --webui=false or remove --webui")
    
    # Run the main application
    sys.exit(main())
    
except ImportError as e:
    print(f"Error importing main application: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error running application: {e}")
    sys.exit(1)
