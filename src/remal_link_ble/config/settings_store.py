"""Persistent settings storage for Remal Link."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

SETTINGS_FILE_NAME = ".remal_link_settings.json"
VALID_LINE_ENDINGS = {"", "\n", "\r", "\r\n"}


@dataclass(slots=True)
class AppSettings:
    """User-configurable settings persisted between app launches."""

    timestamps_enabled: bool = True
    auto_reconnect_enabled: bool = False
    line_ending: str = "\n"
    auto_scroll_enabled: bool = True
    device_name_filter: str = ""


class SettingsStore:
    """Read/write app settings as JSON in the project root."""

    def __init__(self, settings_path: Path) -> None:
        self._settings_path = settings_path

    @classmethod
    def for_project_root(cls) -> "SettingsStore":
        project_root = Path(__file__).resolve().parents[3]
        return cls(settings_path=project_root / SETTINGS_FILE_NAME)

    def load(self) -> AppSettings:
        if not self._settings_path.exists():
            return AppSettings()

        try:
            raw_payload = self._settings_path.read_text(encoding="utf-8")
            parsed_payload: dict[str, Any] = json.loads(raw_payload)
        except (OSError, ValueError, TypeError):
            return AppSettings()

        line_ending = parsed_payload.get("line_ending", "\n")
        if not isinstance(line_ending, str) or line_ending not in VALID_LINE_ENDINGS:
            line_ending = "\n"

        device_name_filter = parsed_payload.get("device_name_filter", "")
        if not isinstance(device_name_filter, str):
            device_name_filter = ""

        return AppSettings(
            timestamps_enabled=bool(parsed_payload.get("timestamps_enabled", True)),
            auto_reconnect_enabled=bool(parsed_payload.get("auto_reconnect_enabled", False)),
            line_ending=line_ending,
            auto_scroll_enabled=bool(parsed_payload.get("auto_scroll_enabled", True)),
            device_name_filter=device_name_filter,
        )

    def save(self, settings: AppSettings) -> None:
        safe_line_ending = settings.line_ending if settings.line_ending in VALID_LINE_ENDINGS else "\n"

        payload = {
            "timestamps_enabled": settings.timestamps_enabled,
            "auto_reconnect_enabled": settings.auto_reconnect_enabled,
            "line_ending": safe_line_ending,
            "auto_scroll_enabled": settings.auto_scroll_enabled,
            "device_name_filter": settings.device_name_filter,
        }

        try:
            self._settings_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            return
