"""UUID configuration for Nordic UART Service based devices."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UartUuids:
    """Container for BLE UART service and characteristic UUIDs."""

    service_uuid: str
    tx_characteristic_uuid: str
    rx_characteristic_uuid: str


DEFAULT_UART_UUIDS = UartUuids(
    service_uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA9E",
    tx_characteristic_uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA9E",
    rx_characteristic_uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA9E",
)
