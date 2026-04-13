"""Qt controller that binds GUI actions to BLE operations."""

from __future__ import annotations

import threading
from concurrent.futures import Future

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from remal_link_ble.ble.client import BleUartClient
from remal_link_ble.config.uuids import DEFAULT_UART_UUIDS, UartUuids
from remal_link_ble.core.async_runner import AsyncRunner
from remal_link_ble.core.models import DiscoveredDevice
from remal_link_ble.ui.main_window import MainWindow


class BleTerminalController(QObject):
    """Coordinate UI events, BLE client operations, and status updates."""

    _devices_ready = Signal(object)
    _status_changed = Signal(str)
    _connected_changed = Signal(bool)
    _busy_changed = Signal(bool)
    _rx_received = Signal(str)
    _tx_sent = Signal(str)
    _system_message = Signal(str)
    _error_message = Signal(str)
    _auto_scan_schedule_requested = Signal(int)
    _auto_scan_stop_requested = Signal()
    _auto_reconnect_schedule_requested = Signal(int)
    _auto_reconnect_stop_requested = Signal()

    def __init__(self, window: MainWindow, uuids: UartUuids = DEFAULT_UART_UUIDS) -> None:
        super().__init__(parent=window)

        self._window = window
        self._runner = AsyncRunner()
        self._client = BleUartClient(uuids=uuids)
        self._expected_disconnect = False
        self._is_busy = False
        self._is_connecting = False
        self._is_scanning = False
        self._is_auto_reconnect_attempt = False
        self._auto_reconnect_enabled = self._window.auto_reconnect_enabled()
        self._last_connected_address: str | None = None
        self._pending_connect_address: str | None = None
        self._active_scan_future: Future[object] | None = None

        self._auto_scan_interval_ms = 2000
        self._auto_scan_retry_ms = 3500
        self._auto_scan_timeout_seconds = 4.0
        self._auto_scan_timer = QTimer(self)
        self._auto_scan_timer.setSingleShot(True)
        self._auto_scan_timer.timeout.connect(self._on_auto_scan_timer_timeout)

        self._auto_reconnect_timer = QTimer(self)
        self._auto_reconnect_timer.setSingleShot(True)
        self._auto_reconnect_timer.timeout.connect(self._on_auto_reconnect_timer_timeout)
        self._auto_reconnect_initial_delay_ms = 350
        self._auto_reconnect_retry_ms = 1200
        self._auto_reconnect_blocked_retry_ms = 400

        self._client.set_receive_callback(self._on_receive_callback)
        self._client.set_disconnected_callback(self._on_disconnected_callback)

        self._window.scan_requested.connect(self.on_scan_requested)
        self._window.connect_requested.connect(self.on_connect_requested)
        self._window.disconnect_requested.connect(self.on_disconnect_requested)
        self._window.send_requested.connect(self.on_send_requested)
        self._window.auto_reconnect_changed.connect(self.on_auto_reconnect_changed)

        self._devices_ready.connect(self._window.set_devices)
        self._status_changed.connect(self._window.set_status)
        self._connected_changed.connect(self._window.set_connected_state)
        self._busy_changed.connect(self._window.set_busy)
        self._rx_received.connect(self._window.append_rx)
        self._tx_sent.connect(self._window.append_tx)
        self._system_message.connect(self._window.append_system)
        self._error_message.connect(self._window.show_error)
        self._auto_scan_schedule_requested.connect(self._schedule_auto_scan_on_ui)
        self._auto_scan_stop_requested.connect(self._stop_auto_scan_on_ui)
        self._auto_reconnect_schedule_requested.connect(self._schedule_auto_reconnect_on_ui)
        self._auto_reconnect_stop_requested.connect(self._stop_auto_reconnect_on_ui)

        self._status_changed.emit("Status: Ready. Auto-scan is active while disconnected.")
        self._connected_changed.emit(False)
        self._schedule_auto_scan(delay_ms=250)

    @Slot()
    def on_scan_requested(self) -> None:
        """Handle GUI request to scan for BLE devices."""
        was_auto_reconnect_attempt = self._is_auto_reconnect_attempt
        self._is_auto_reconnect_attempt = False
        self._stop_auto_reconnect()
        self._stop_auto_scan()

        if self._is_connecting:
            if was_auto_reconnect_attempt:
                self._status_changed.emit("Status: Auto-reconnect canceled. Current attempt is finishing...")
                self._system_message.emit("Auto-reconnect canceled by user.")
            else:
                self._status_changed.emit("Status: Connection attempt already in progress.")
            return

        if self._is_scanning:
            self._status_changed.emit("Status: Scan already running...")
            return

        self._request_scan(is_manual=True)

    @Slot()
    def _on_auto_scan_timer_timeout(self) -> None:
        self._request_scan(is_manual=False)

    @Slot()
    def _on_auto_reconnect_timer_timeout(self) -> None:
        self._request_auto_reconnect()

    def _request_scan(self, is_manual: bool) -> None:
        if self._client.is_connected or self._is_connecting or self._is_busy or self._is_scanning:
            return

        self._is_scanning = True

        if is_manual:
            self._set_busy(True)
            self._status_changed.emit("Status: Scanning for BLE devices...")
        else:
            self._status_changed.emit("Status: Auto-scanning for BLE devices...")

        self._active_scan_future = self._runner.submit(
            self._client.scan_devices(timeout_seconds=self._auto_scan_timeout_seconds),
            on_result=lambda devices: self._handle_scan_result(devices, is_manual),
            on_error=lambda error: self._handle_scan_error(error, is_manual),
            on_cancel=lambda: self._handle_scan_canceled(is_manual),
        )

    @Slot(str)
    def on_connect_requested(self, address: str) -> None:
        """Handle GUI request to connect to a selected BLE device."""
        was_auto_reconnect_attempt = self._is_auto_reconnect_attempt
        self._is_auto_reconnect_attempt = False
        self._stop_auto_reconnect()
        self._stop_auto_scan()

        if self._is_connecting:
            if was_auto_reconnect_attempt:
                self._status_changed.emit("Status: Auto-reconnect canceled. Current attempt is finishing...")
                self._system_message.emit("Auto-reconnect canceled by user.")
            else:
                self._status_changed.emit("Status: Connection attempt already in progress.")
            return

        if self._is_scanning:
            self._pending_connect_address = address
            self._status_changed.emit("Status: Stopping auto-scan and connecting...")
            scan_canceled = self._runner.cancel(self._active_scan_future)
            if not scan_canceled:
                self._status_changed.emit("Status: Finishing scan, then connecting...")
            return

        self._begin_connect(address)

    @Slot()
    def on_disconnect_requested(self) -> None:
        """Handle GUI request to disconnect from current device."""
        self._is_auto_reconnect_attempt = False
        self._stop_auto_reconnect()
        self._stop_auto_scan()
        self._set_busy(True)
        self._status_changed.emit("Status: Disconnecting...")
        self._expected_disconnect = True

        self._runner.submit(
            self._client.disconnect(),
            on_result=lambda _result: self._handle_disconnect_result(
                "Disconnected by user.", allow_auto_reconnect=False
            ),
            on_error=self._handle_operation_error,
        )

    @Slot(str, str)
    def on_send_requested(self, text: str, line_ending: str) -> None:
        """Handle outgoing terminal messages from the GUI."""
        if not self._client.is_connected:
            self._status_changed.emit("Status: No device is connected.")
            self._system_message.emit("Error: No device is connected.")
            return

        payload = text + line_ending

        self._runner.submit(
            self._client.send_text(payload),
            on_result=lambda _result: self._tx_sent.emit(text),
            on_error=self._handle_operation_error,
        )

    @Slot(bool)
    def on_auto_reconnect_changed(self, is_enabled: bool) -> None:
        """Handle user toggling auto reconnect option."""
        self._auto_reconnect_enabled = is_enabled
        if not is_enabled:
            if self._is_auto_reconnect_attempt:
                self._status_changed.emit("Status: Auto-reconnect canceled by user.")
                self._system_message.emit("Auto-reconnect canceled by user.")
            self._is_auto_reconnect_attempt = False
            self._stop_auto_reconnect()
            return

        if self._client.is_connected and self._last_connected_address is not None:
            self._system_message.emit(f"Auto reconnect armed for {self._last_connected_address}.")

    def shutdown(self) -> None:
        """Disconnect BLE safely and stop background async runner."""
        completion_event = threading.Event()
        self._expected_disconnect = True
        self._is_connecting = False
        self._is_auto_reconnect_attempt = False
        self._stop_auto_reconnect()
        self._stop_auto_scan()

        def _mark_complete(_result: object | None = None) -> None:
            completion_event.set()

        self._runner.submit(
            self._client.disconnect(),
            on_result=_mark_complete,
            on_error=lambda _error: completion_event.set(),
        )

        completion_event.wait(timeout=2.0)
        self._runner.stop()

    def _request_auto_reconnect(self) -> None:
        if (
            not self._auto_reconnect_enabled
            or self._last_connected_address is None
            or self._client.is_connected
        ):
            return

        if self._is_connecting or self._is_busy or self._is_scanning:
            self._schedule_auto_reconnect(delay_ms=self._auto_reconnect_blocked_retry_ms)
            return

        self._stop_auto_scan()
        self._is_auto_reconnect_attempt = True
        self._begin_connect(
            self._last_connected_address,
            status_prefix="Status: Auto-reconnecting to ",
            set_busy=False,
        )

    def _set_busy(self, is_busy: bool) -> None:
        self._is_busy = is_busy
        self._busy_changed.emit(is_busy)

    def _schedule_auto_scan(self, delay_ms: int) -> None:
        self._auto_scan_schedule_requested.emit(max(0, delay_ms))

    @Slot(int)
    def _schedule_auto_scan_on_ui(self, delay_ms: int) -> None:
        if self._client.is_connected or self._is_connecting:
            return

        self._auto_scan_timer.start(delay_ms)

    def _stop_auto_scan(self) -> None:
        self._auto_scan_stop_requested.emit()

    @Slot()
    def _stop_auto_scan_on_ui(self) -> None:
        self._auto_scan_timer.stop()

    def _schedule_auto_reconnect(self, delay_ms: int) -> None:
        self._auto_reconnect_schedule_requested.emit(max(0, delay_ms))

    @Slot(int)
    def _schedule_auto_reconnect_on_ui(self, delay_ms: int) -> None:
        if not self._auto_reconnect_enabled or self._client.is_connected:
            return

        self._auto_reconnect_timer.start(delay_ms)

    def _stop_auto_reconnect(self) -> None:
        self._auto_reconnect_stop_requested.emit()

    @Slot()
    def _stop_auto_reconnect_on_ui(self) -> None:
        self._auto_reconnect_timer.stop()

    def _handle_scan_result(self, devices: list[DiscoveredDevice], is_manual: bool) -> None:
        self._active_scan_future = None
        self._is_scanning = False
        self._devices_ready.emit(devices)
        if is_manual:
            self._set_busy(False)

        if is_manual:
            if devices:
                self._status_changed.emit(f"Status: Scan complete. Found {len(devices)} device(s).")
            else:
                self._status_changed.emit("Status: Scan complete. No BLE devices found.")
        else:
            if devices:
                self._status_changed.emit(f"Status: Auto-scan found {len(devices)} device(s).")
            else:
                self._status_changed.emit("Status: Auto-scan running...")

        if (
            not is_manual
            and self._pending_connect_address is not None
            and not self._client.is_connected
            and not self._is_connecting
        ):
            pending_address = self._pending_connect_address
            self._pending_connect_address = None
            self._begin_connect(pending_address)
            return

        self._schedule_auto_scan(delay_ms=self._auto_scan_interval_ms)

    def _handle_scan_error(self, error: Exception, is_manual: bool) -> None:
        self._active_scan_future = None
        self._is_scanning = False
        if is_manual:
            self._set_busy(False)

        error_text = str(error).strip() or error.__class__.__name__

        if is_manual:
            self._status_changed.emit(f"Status: Error - {error_text}")
            self._system_message.emit(f"Error: {error_text}")
            self._error_message.emit(error_text)
        else:
            self._status_changed.emit("Status: Auto-scan error. Retrying soon...")
            self._system_message.emit(f"Auto-scan error: {error_text}")

        if (
            not is_manual
            and self._pending_connect_address is not None
            and not self._client.is_connected
            and not self._is_connecting
        ):
            pending_address = self._pending_connect_address
            self._pending_connect_address = None
            self._begin_connect(pending_address)
            return

        self._schedule_auto_scan(delay_ms=self._auto_scan_retry_ms)

    def _handle_scan_canceled(self, is_manual: bool) -> None:
        self._active_scan_future = None
        self._is_scanning = False
        if is_manual:
            self._set_busy(False)

        if (
            self._pending_connect_address is not None
            and not self._client.is_connected
            and not self._is_connecting
        ):
            pending_address = self._pending_connect_address
            self._pending_connect_address = None
            self._begin_connect(pending_address)
            return

        if self._client.is_connected or self._is_connecting:
            return

        if is_manual:
            self._status_changed.emit("Status: Scan canceled.")
            self._schedule_auto_scan(delay_ms=self._auto_scan_retry_ms)
            return

        self._status_changed.emit("Status: Auto-scan paused.")
        self._schedule_auto_scan(delay_ms=self._auto_scan_interval_ms)

    def _handle_connect_result(self, address: str) -> None:
        self._stop_auto_reconnect()
        self._stop_auto_scan()
        self._expected_disconnect = False
        self._is_connecting = False
        self._is_auto_reconnect_attempt = False
        self._last_connected_address = address
        self._set_busy(False)
        self._connected_changed.emit(True)
        self._status_changed.emit(f"Status: Connected to {address}.")
        self._system_message.emit(f"Connected to {address}.")

    def _handle_disconnect_result(self, reason: str, allow_auto_reconnect: bool = True) -> None:
        self._expected_disconnect = False
        self._is_connecting = False
        self._is_auto_reconnect_attempt = False
        self._set_busy(False)
        self._connected_changed.emit(False)
        self._status_changed.emit(f"Status: {reason}")
        self._system_message.emit(reason)

        if (
            allow_auto_reconnect
            and self._auto_reconnect_enabled
            and self._last_connected_address is not None
        ):
            self._status_changed.emit(
                f"Status: Disconnected. Auto-reconnect to {self._last_connected_address} scheduled..."
            )
            self._schedule_auto_reconnect(delay_ms=self._auto_reconnect_initial_delay_ms)
            return

        self._schedule_auto_scan(delay_ms=300)

    def _handle_operation_error(self, error: Exception) -> None:
        was_auto_reconnect_attempt = self._is_auto_reconnect_attempt
        self._is_connecting = False
        self._is_auto_reconnect_attempt = False
        self._expected_disconnect = False
        self._set_busy(False)

        error_text = str(error).strip() or error.__class__.__name__
        self._connected_changed.emit(self._client.is_connected)

        if was_auto_reconnect_attempt:
            self._status_changed.emit("Status: Auto-reconnect failed. Retrying...")
            self._system_message.emit(f"Auto-reconnect error: {error_text}")
            if not self._client.is_connected and self._auto_reconnect_enabled:
                self._schedule_auto_reconnect(delay_ms=self._auto_reconnect_retry_ms)
            return

        self._status_changed.emit(f"Status: Error - {error_text}")
        self._system_message.emit(f"Error: {error_text}")
        self._error_message.emit(error_text)

        if not self._client.is_connected:
            self._schedule_auto_scan(delay_ms=self._auto_scan_retry_ms)

    def _begin_connect(
        self,
        address: str,
        status_prefix: str = "Status: Connecting to ",
        set_busy: bool = True,
    ) -> None:
        self._pending_connect_address = None
        self._is_connecting = True
        if set_busy:
            self._set_busy(True)
        self._status_changed.emit(f"{status_prefix}{address}...")

        self._runner.submit(
            self._client.connect(address),
            on_result=lambda _result: self._handle_connect_result(address),
            on_error=self._handle_operation_error,
        )

    def _on_receive_callback(self, payload: str) -> None:
        self._rx_received.emit(payload)

    def _on_disconnected_callback(self) -> None:
        if self._expected_disconnect:
            return

        self._handle_disconnect_result("Disconnected.")
