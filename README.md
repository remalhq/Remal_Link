# Remal Link

Remal Link is a desktop Bluetooth Low Energy serial terminal for Remal ESP32-based boards using Nordic UART Service style UUIDs.

It gives you a GUI terminal for scan/connect/send/receive workflows, with reconnect support and long-session safety controls.

## Features
- BLE scan, connect, disconnect, and UART text send/receive
- Auto-scan while disconnected
- Name filter for scanned device list
- Optional auto reconnect to the last connected device
- Line ending selector: `None`, `\n`, `\r`, `\r\n`
- ANSI foreground color rendering in terminal output
- System log panel with timestamps
- Auto-scroll toggle for terminal follow behavior
- Terminal scrollback cap to avoid unbounded memory growth
- Persistent UI settings between launches

## Requirements
- Python 3.10+
- BLE adapter enabled on your machine
- Dependencies from `requirements.txt`:
  - `PySide6>=6.8.0`
  - `bleak>=0.22.0`

## Quick Start
1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Launch:

```bash
python remal_link.py
```

## Desktop Shortcut (Linux)
This repository includes a launcher script and icon so you can create a desktop shortcut that opens the app by double-click.

- Launcher script: `remal_link_launcher.sh`
- Icon asset: `icon/Remal_Logo.svg`

Example `.desktop` entry:

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Remal Link
Comment=BLE Serial Terminal for Remal ESP32-based boards
Exec=/ABSOLUTE/PATH/TO/REPO/remal_link_launcher.sh
Path=/ABSOLUTE/PATH/TO/REPO
Icon=/ABSOLUTE/PATH/TO/REPO/icon/Remal_Logo.svg
Terminal=false
Categories=Utility;Development;
StartupNotify=true
```

After creating the desktop file, make it executable:

```bash
chmod +x ~/Desktop/Remal_Link.desktop
```

## First Run Workflow
1. Wait for auto-scan to discover nearby BLE devices.
2. Optional: use `Name filter` to narrow the device dropdown.
3. Select your Remal ESP32-based board from the dropdown.
4. Click `Connect`.
5. Type a message, choose a line ending, and click `Send`.
6. Use `Clear` to clear the terminal at any time.

## UI Notes
- `Name filter`: type part of a BLE device name to show matching scan results only.
- `Name filter` value is persisted between launches.
- Send input stays enabled during disconnect/reconnect; sending while disconnected logs `No device is connected`.
- `Auto reconnect`: retries the last connected device after unexpected disconnects.
- `Auto-scroll`: when enabled, terminal view follows new messages; when disabled, view position stays where you left it.
- `Menu -> Preferences`: enable/disable terminal timestamps.
- `Menu -> About`: shows brief app info, version, author email, and Remal website link.
- `Show System Log`: view timestamped internal status messages.

## BLE UUID Defaults
Default Nordic UART Service style UUIDs:
- Service: `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`
- TX characteristic: `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
- RX characteristic: `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`

UUID constants live in `src/remal_link_ble/config/uuids.py`.

## Project Structure
- `remal_link.py`: launcher entry point
- `remal_link_launcher.sh`: shell launcher used by desktop shortcut (prefers `.venv` Python)
- `icon/Remal_Logo.svg`: app/shortcut icon
- `src/remal_link_ble/app.py`: Qt app bootstrap
- `src/remal_link_ble/ui/main_window.py`: GUI and terminal rendering
- `src/remal_link_ble/core/controller.py`: UI/BLE orchestration
- `src/remal_link_ble/ble/client.py`: BLE transport (scan/connect/notify/write)
- `src/remal_link_ble/config/settings_store.py`: persistent settings
- `src/remal_link_ble/config/uuids.py`: UUID configuration

## Long-Session Safety
- Terminal scrollback is capped (oldest lines are dropped automatically).
- System log entry count is capped.
- `Clear` stays available even during reconnect/busy states.

## Changelog
### v1.1:
- Added name filter to auto-scan for easier device selection, saved between sessions.
- Added `Menu -> About` dialog with brief app info, version, author name/email, and website link (`www.remal.io`).
- Kept send controls enabled during reconnect/disconnect and added system error feedback when no device is connected.

### v1.0 - Hello, World!
- Initial release with core BLE UART terminal functionality, auto-scan, auto-reconnect, and line ending controls.
