"""Shared data models used by the BLE terminal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """BLE device metadata displayed in the GUI."""

    name: str
    address: str
    rssi: int | None = None

    def display_label(self) -> str:
        """Build a human-readable label for the device dropdown."""
        if self.rssi is None:
            return f"{self.name} ({self.address})"

        return f"{self.name} ({self.address}) RSSI {self.rssi} dBm"
