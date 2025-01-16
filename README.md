# TransferBox

A robust, platform-independent media file transfer utility designed for reliable data transfer from storage devices to a designated backup location. Originally designed for the Raspberry Pi but with support for macOS and Windows.

## Features

### Core Features
- **Cross-Platform Support**: Works on Raspberry Pi, macOS, and Windows
- **Automated File Transfer**: Automatically detects when storage devices are connected
- **Data Integrity**: Uses xxHash algorithm for fast and reliable checksum verification
- **Progress Monitoring**: Real-time transfer progress tracking
- **Comprehensive Logging**: Generates detailed logs and MHL (Media Hash List) files for each transfer session
- **Error Handling**: Robust error detection and reporting system

### Platform-Specific Features

#### Raspberry Pi
- **Hardware Interface**: 
  - 16x2 LCD Display (I2C interface)
  - LED status indicators with 74HC595 shift registers
  - Physical button controls
  - Power management with x728 UPS HAT support
- **Utility Menu**: Access system functions through hardware buttons
- **Visual Feedback**: LED progress bar and status indicators

#### Desktop (macOS/Windows)
- **Rich Console Interface**: Uses the Rich library for beautiful console output
- **Native Integration**: Platform-specific drive detection and handling
- **User Interface**: Interactive command-line interface

### Technical Features
- **Intelligent File Handling**:
  - Configurable file filtering based on extensions
  - Customizable directory organization
  - Timestamp-based file naming
  - Original metadata preservation
- **Flexible Configuration**:
  - YAML-based configuration system
  - Customizable file naming patterns
  - Adjustable directory structure
- **Extensible Architecture**:
  - Platform-agnostic core
  - Interface-based design for easy platform extension
  - Modular component system

## Requirements

### General Requirements
- Python 3.11.2+
- Required Python packages (installed via pip):
  - smbus==1.1.post2
  - xxhash==3.5.0
  - colorama==0.4.6
  - rich==13.9.4
  - pyyaml==6.0.2
  - pygame==2.6.1

### Platform-Specific Requirements

#### Raspberry Pi
- Raspberry Pi 4B (recommended)
- Raspberry Pi OS
- Hardware components:
  - 16x2 LCD Display (I2C)
  - 74HC595 Shift Registers (x2)
  - Push buttons for control
  - x728 UPS HAT (optional)

#### Windows
- Windows 10/11
- Python for Windows
- pywin32 package

#### macOS
- macOS 10.15+
- Python for macOS

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/TransferBox.git
cd TransferBox
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. For Raspberry Pi, additional setup may be required:
```bash
# Install I2C and GPIO dependencies
sudo apt-get update
sudo apt-get install -y python3-smbus i2c-tools
```

## Configuration

The application uses a YAML configuration file located at:
- `config.yml` in the current directory
- `~/.transferbox/config.yml` in the user's home directory
- `/etc/transferbox/config.yml` for system-wide configuration

Example configuration:
```yaml
# File handling
rename_with_timestamp: true
preserve_original_filename: true
filename_template: "{original}_{timestamp}"
timestamp_format: "%Y%m%d_%H%M%S"

# Media transfer settings
media_only_transfer: true
preserve_folder_structure: true
media_extensions: .mp4,.mov,.mxf,.avi,.braw,.r3d,.wav,.aif,.aiff,.jpg,.jpeg,.raw

# Directory structure
create_date_folders: true
date_folder_format: "%Y/%m/%d"
create_device_folders: false
device_folder_template: "{device_name}"
```

## Usage

### Raspberry Pi Mode

1. Connect the hardware components according to the pinout configuration.
2. Run the application:
```bash
python main.py
```

3. The system will boot into standby mode, waiting for a storage device.

4. Control using hardware buttons:
- Insert storage device to initiate transfer
- Use menu combination (BACK + double OK press) to access utilities
- Navigate menu with UP/DOWN buttons
- Select options with OK button
- Exit menu with BACK button

### Desktop Mode (macOS/Windows)

1. Run the application:
```bash
python main.py
```

2. Follow the prompts to:
- Set destination directory
- Insert source drive
- Monitor transfer progress

### Transfer Process

The transfer process follows these steps:

1. Device Detection
   - System detects when a storage device is connected
   - Validates device mounting and accessibility

2. File Transfer
   - Creates destination directory structure
   - Copies files with progress monitoring
   - Generates checksums during transfer

3. Verification
   - Verifies checksums for all transferred files
   - Generates MHL (Media Hash List) file
   - Creates detailed transfer log

4. Completion
   - Safely unmounts source device
   - Provides transfer summary
   - Returns to standby mode

## Error Handling

The system includes comprehensive error handling:
- Drive detection failures
- Transfer interruptions
- Checksum mismatches
- Hardware failures (Raspberry Pi)
- Permission issues
- Space constraints

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

[Add support information here]
