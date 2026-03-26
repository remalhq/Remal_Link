# Remal Link

Remal Link is a desktop Bluetooth Low Energy serial terminal for ESP32 based boards using Nordic UART Service style UUIDs.

It gives you a GUI terminal for scan/connect/send/receive workflows, with reconnect support and long-session safety controls.

## Features
- BLE scan, connect, disconnect, and UART text send/receive
- Auto-scan while disconnected
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

## First Run Workflow
1. Wait for auto-scan to discover nearby BLE devices.
2. Select your ESP32 device from the dropdown.
3. Click `Connect`.
4. Type a message, choose a line ending, and click `Send`.
5. Use `Clear` to clear the terminal at any time.

## UI Notes
- `Auto reconnect`: retries the last connected device after unexpected disconnects.
- `Auto-scroll`: when enabled, terminal view follows new messages; when disabled, view position stays where you left it.
- `Menu -> Preferences`: enable/disable terminal timestamps.
- `Show System Log`: view timestamped internal status messages.

## BLE UUID Defaults
Default Nordic UART Service style UUIDs:
- Service: `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`
- TX characteristic: `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
- RX characteristic: `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`

UUID constants live in `src/remal_link_ble/config/uuids.py`.

## Project Structure
- `remal_link.py`: launcher entry point
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
