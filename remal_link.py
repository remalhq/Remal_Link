#!/usr/bin/env python3
"""Launcher script for the Remal Link BLE terminal GUI."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

try:
    from remal_link_ble.app import main
except ModuleNotFoundError as exc:
    missing_module = exc.name or "unknown"
    print(f"Missing Python dependency: {missing_module}")
    print("Install requirements with: pip install -r requirements.txt")
    raise SystemExit(1) from exc


if __name__ == "__main__":
    raise SystemExit(main())
