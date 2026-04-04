"""BLE UART client built on bleak."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from bleak import BleakClient, BleakScanner

from remal_link_ble.config.uuids import DEFAULT_UART_UUIDS, UartUuids
from remal_link_ble.core.models import DiscoveredDevice

MAX_WRITE_CHUNK_BYTES = 180
BLE_CONNECT_TIMEOUT_SECONDS = 8.0


class BleUartClient:
    """Bluetooth LE UART client with scan/connect/send helpers."""

    def __init__(self, uuids: UartUuids = DEFAULT_UART_UUIDS) -> None:
        self._uuids = uuids
        self._client: BleakClient | None = None

        self._write_characteristic_uuid = uuids.tx_characteristic_uuid
        self._notify_characteristic_uuid = uuids.rx_characteristic_uuid
        self._write_requires_response = False

        self._receive_callback: Callable[[str], None] | None = None
        self._disconnected_callback: Callable[[], None] | None = None

    @property
    def is_connected(self) -> bool:
        """Return the active BLE connection state."""
        return self._client is not None and self._client.is_connected

    def set_receive_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked when UTF-8 text is received."""
        self._receive_callback = callback

    def set_disconnected_callback(self, callback: Callable[[], None]) -> None:
        """Register callback invoked when connection drops."""
        self._disconnected_callback = callback

    async def scan_devices(self, timeout_seconds: float = 5.0) -> list[DiscoveredDevice]:
        """Scan and return nearby BLE devices sorted by name and address."""
        discovered = await BleakScanner.discover(timeout=timeout_seconds)

        devices: list[DiscoveredDevice] = []
        for device in discovered:
            display_name = device.name or "Unknown"
            rssi = getattr(device, "rssi", None)
            devices.append(DiscoveredDevice(name=display_name, address=device.address, rssi=rssi))

        devices.sort(key=lambda item: (item.name.lower(), item.address.lower()))
        return devices

    async def connect(self, address: str) -> None:
        """Connect to a BLE device and subscribe for incoming UART notifications."""
        await self.disconnect()

        client = BleakClient(address, disconnected_callback=self._handle_disconnected)
        try:
            await asyncio.wait_for(client.connect(), timeout=BLE_CONNECT_TIMEOUT_SECONDS)
        except TimeoutError as error:
            try:
                await client.disconnect()
            except Exception:
                pass
            raise RuntimeError(
                f"BLE connect timed out after {BLE_CONNECT_TIMEOUT_SECONDS:.1f}s"
            ) from error

        self._client = client

        write_uuid, notify_uuid, requires_response = self._resolve_channels(client)
        self._write_characteristic_uuid = write_uuid
        self._notify_characteristic_uuid = notify_uuid
        self._write_requires_response = requires_response

        try:
            await client.start_notify(self._notify_characteristic_uuid, self._handle_notification)
        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Disconnect from the active BLE device if connected."""
        client = self._client
        if client is None:
            return

        try:
            if client.is_connected:
                try:
                    await client.stop_notify(self._notify_characteristic_uuid)
                except Exception:
                    pass

                await client.disconnect()
        finally:
            self._client = None

    async def send_text(self, text: str) -> None:
        """Transmit text over BLE UART using chunked writes."""
        if not self.is_connected or self._client is None:
            raise RuntimeError("No BLE device is connected.")

        payload = text.encode("utf-8")
        if not payload:
            return

        for start_idx in range(0, len(payload), MAX_WRITE_CHUNK_BYTES):
            chunk = payload[start_idx : start_idx + MAX_WRITE_CHUNK_BYTES]
            await self._client.write_gatt_char(
                self._write_characteristic_uuid,
                chunk,
                response=self._write_requires_response,
            )

    def _resolve_channels(self, client: BleakClient) -> tuple[str, str, bool]:
        """Pick write/notify characteristics using available GATT properties."""
        services = client.services
        if services is None:
            return (
                self._uuids.tx_characteristic_uuid,
                self._uuids.rx_characteristic_uuid,
                False,
            )

        property_map: dict[str, set[str]] = {}
        for service in services:
            for characteristic in service.characteristics:
                uuid_lower = characteristic.uuid.lower()
                if uuid_lower not in {
                    self._uuids.tx_characteristic_uuid.lower(),
                    self._uuids.rx_characteristic_uuid.lower(),
                }:
                    continue

                property_map[uuid_lower] = {prop.lower() for prop in characteristic.properties}

        ordered_candidates = [
            self._uuids.tx_characteristic_uuid,
            self._uuids.rx_characteristic_uuid,
        ]

        notify_uuid = self._uuids.rx_characteristic_uuid
        for candidate in ordered_candidates:
            properties = property_map.get(candidate.lower())
            if properties is not None and "notify" in properties:
                notify_uuid = candidate
                break

        write_uuid = self._uuids.tx_characteristic_uuid
        write_requires_response = False

        for candidate in ordered_candidates:
            properties = property_map.get(candidate.lower())
            if properties is not None and "write-without-response" in properties:
                write_uuid = candidate
                write_requires_response = False
                break
        else:
            for candidate in ordered_candidates:
                properties = property_map.get(candidate.lower())
                if properties is not None and "write" in properties:
                    write_uuid = candidate
                    write_requires_response = True
                    break

        return write_uuid, notify_uuid, write_requires_response

    def _handle_notification(self, _sender: Any, payload: bytearray) -> None:
        """Decode notification payload and forward to the receive callback."""
        if self._receive_callback is None:
            return

        decoded_text = bytes(payload).decode("utf-8", errors="replace")
        self._receive_callback(decoded_text)

    def _handle_disconnected(self, _client: BleakClient) -> None:
        """Internal bleak disconnected callback."""
        self._client = None

        if self._disconnected_callback is not None:
            self._disconnected_callback()
