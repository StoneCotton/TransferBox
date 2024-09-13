# TransferBox

## Overview

TransferBox is an autonomous media transfer utility designed for the Raspberry Pi 4B. It provides a reliable and efficient solution for transferring media files from SD cards to a designated storage drive, with built-in verification and logging capabilities.

## Features

- **Autonomous Operation**: Automatically detects when an SD card is inserted and initiates the transfer process.
- **File Integrity**: Uses xxHash algorithm for fast and reliable checksum verification.
- **Progress Tracking**: Real-time transfer progress displayed on an LCD screen and LED bar graph.
- **Comprehensive Logging**: Generates detailed logs and MHL (Media Hash List) files for each transfer session.
- **User Interface**: Simple button-based interface for initiating transfers and accessing utility functions.
- **Error Handling**: Robust error detection and reporting system.
- **Utility Menu**: Includes functions like drive formatting, LED testing, and system information display.

## Hardware Requirements

- Raspberry Pi 4B
- 16x2 LCD Display (I2C interface)
- 74HC595 Shift Register (x2, daisy-chained)
- LEDs for status indication
- Push buttons for user input
- SD card reader
- External storage drive (referred to as DUMP_DRIVE)

## Software Requirements

- Raspberry Pi OS
- Python 3.11.2+
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/TransferBox.git
   ```

2. Navigate to the project directory:
   ```
   cd TransferBox
   ```

3. Install required packages:
   ```
   pip install -r requirements.txt
   ```
## Usage

1. Power on your Raspberry Pi with TransferBox installed.

2. The system will boot into standby mode, waiting for an SD card to be inserted.

3. Insert an SD card containing media files.

4. TransferBox will automatically detect the card and begin the transfer process.

5. Monitor the progress on the LCD display and LED bar graph.

6. Once complete, the system will indicate success or failure and return to standby mode.

### Utility Menu

To access the utility menu:

1. In standby mode, press and hold the BACK button.
2. While holding BACK, quickly press the OK button twice.
3. Use UP and DOWN buttons to navigate the menu, and OK to select an option.

Available utility functions include:
- List connected drives
- Format DUMP_DRIVE
- Test LEDs and LCD
- Display system information
- Check available space
- Shutdown/Reboot system

## Project Structure

```
TransferBox/
│
├── src/
│   ├── __init__.py
│   ├── button_handler.py
│   ├── drive_detection.py
│   ├── file_transfer.py
│   ├── lcd_display.py
│   ├── led_control.py
│   ├── logger_setup.py
│   ├── menu_setup.py
│   ├── mhl_handler.py
│   ├── pi74HC595.py
│   ├── state_manager.py
│   └── system_utils.py
│
├── main.py
├── requirements.txt
├── README.md
```

## Troubleshooting

- **System won't boot**: Ensure all wiring is correct and secure.
- **Transfer fails**: Check SD card and DUMP_DRIVE connections. Verify available space on DUMP_DRIVE.
- **LEDs not working**: Confirm shift register connections and LED polarity.
- **LCD not displaying**: Check I2C connections and address configuration.

