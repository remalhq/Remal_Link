"""Main window for the Remal Link BLE serial terminal."""

from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from remal_link_ble.config.settings_store import AppSettings, SettingsStore
from remal_link_ble.core.models import DiscoveredDevice

LINE_ENDING_CHOICES: tuple[tuple[str, str], ...] = (
    ("None", ""),
    ("\\n", "\n"),
    ("\\r", "\r"),
    ("\\r\\n", "\r\n"),
)

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[([0-9;]*)m")
ANSI_BASIC_FG_COLORS: dict[int, str] = {
    30: "#000000",
    31: "#aa0000",
    32: "#00aa00",
    33: "#aa5500",
    34: "#0000aa",
    35: "#aa00aa",
    36: "#00aaaa",
    37: "#aaaaaa",
    90: "#555555",
    91: "#ff5555",
    92: "#55ff55",
    93: "#ffff55",
    94: "#5555ff",
    95: "#ff55ff",
    96: "#55ffff",
    97: "#ffffff",
}

ANSI_BASE_16_COLORS: tuple[str, ...] = (
    "#000000",
    "#800000",
    "#008000",
    "#808000",
    "#000080",
    "#800080",
    "#008080",
    "#c0c0c0",
    "#808080",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#0000ff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
)

MAX_TERMINAL_SCROLLBACK_LINES = 4000
MAX_SYSTEM_LOG_ENTRIES = 1500
DEFAULT_WINDOW_TITLE = "Remal Link BLE Terminal"
ABOUT_VERSION = "v1.2"
ABOUT_AUTHOR_NAME = "Khalid Mansoor AlAwadhi"
ABOUT_AUTHOR_EMAIL = "khalid@remal.io"
ABOUT_WEBSITE_URL = "https://www.remal.io"
ABOUT_WEBSITE_LABEL = "www.remal.io"


class PreferencesDialog(QDialog):
    """Dialog for UI behavior preferences."""

    def __init__(self, timestamps_enabled: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Preferences")
        self.setModal(True)

        self._timestamps_checkbox = QCheckBox("Enable timestamps")
        self._timestamps_checkbox.setChecked(timestamps_enabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._timestamps_checkbox)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def timestamps_enabled(self) -> bool:
        """Return selected timestamp preference."""
        return self._timestamps_checkbox.isChecked()


class SystemLogDialog(QDialog):
    """Dialog that displays timestamped system log entries."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("System Log")
        self.resize(760, 320)
        self.setModal(False)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        controls_layout = QHBoxLayout()
        controls_layout.addStretch(1)
        controls_layout.addWidget(close_button)

        layout = QVBoxLayout()
        layout.addWidget(self._log_view, stretch=1)
        layout.addLayout(controls_layout)
        self.setLayout(layout)

    def set_entries(self, entries: list[str]) -> None:
        """Refresh the visible system log entries."""
        if entries:
            self._log_view.setPlainText("\n".join(entries))
        else:
            self._log_view.setPlainText("No system messages yet.")

        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)


class AboutDialog(QDialog):
    """Dialog that displays brief app metadata and project links."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("About Remal Link")
        self.setModal(True)

        summary_label = QLabel(
            "Remal Link is a lightweight BLE UART terminal for Remal ESP32-based boards."
        )
        summary_label.setWordWrap(True)

        details_label = QLabel(
            "<b>Version:</b> {version}<br>"
            "<b>Author:</b> {author}<br>"
            "<b>Email:</b> <a href=\"mailto:{email}\">{email}</a><br>"
            "<b>Website:</b> <a href=\"{website}\">{website_label}</a>".format(
                version=ABOUT_VERSION,
                author=ABOUT_AUTHOR_NAME,
                email=ABOUT_AUTHOR_EMAIL,
                website=ABOUT_WEBSITE_URL,
                website_label=ABOUT_WEBSITE_LABEL,
            )
        )
        details_label.setOpenExternalLinks(True)
        details_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(summary_label)
        layout.addWidget(details_label)
        layout.addWidget(buttons)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    """Primary GUI window for BLE scan/connect/send/receive operations."""

    scan_requested = Signal()
    connect_requested = Signal(str)
    disconnect_requested = Signal()
    send_requested = Signal(str, str)
    auto_reconnect_changed = Signal(bool)

    def __init__(self, settings_store: SettingsStore, initial_settings: AppSettings) -> None:
        super().__init__()

        self.setWindowTitle(DEFAULT_WINDOW_TITLE)
        self.resize(880, 560)

        self._settings_store = settings_store
        self._is_connected = False
        self._is_busy = False
        self._timestamps_enabled = initial_settings.timestamps_enabled
        self._system_log_entries: list[str] = []
        self._system_log_dialog: SystemLogDialog | None = None
        self._all_devices: list[DiscoveredDevice] = []

        self._device_combo = QComboBox()
        self._device_filter_input = QLineEdit()
        self._device_filter_input.setPlaceholderText("Filter by device name")
        self._device_filter_input.setClearButtonEnabled(True)
        self._device_filter_input.setText(initial_settings.device_name_filter)
        self._scan_button = QPushButton("Scan")
        self._connect_button = QPushButton("Connect")
        self._disconnect_button = QPushButton("Disconnect")
        self._auto_reconnect_checkbox = QCheckBox("Auto reconnect")

        self._terminal_log = QTextEdit()
        self._terminal_log.setReadOnly(True)
        self._terminal_log.document().setMaximumBlockCount(MAX_TERMINAL_SCROLLBACK_LINES)

        self._message_input = QLineEdit()
        self._message_input.setPlaceholderText("Type text to send over BLE UART")
        self._line_ending_combo = QComboBox()
        for label, value in LINE_ENDING_CHOICES:
            self._line_ending_combo.addItem(label, value)
        self._line_ending_combo.setCurrentIndex(self._line_ending_index_for_value(initial_settings.line_ending))
        self._send_button = QPushButton("Send")
        self._clear_button = QPushButton("Clear")
        self._auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self._auto_scroll_checkbox.setChecked(initial_settings.auto_scroll_enabled)

        self._status_label = QLabel("Status: Idle")
        self._show_system_log_button = QPushButton("Show System Log")

        self._auto_reconnect_checkbox.setChecked(initial_settings.auto_reconnect_enabled)

        self._build_layout()
        self._build_menu()
        self._wire_events()
        self._apply_control_state()

    def _build_layout(self) -> None:
        top_controls_layout = QHBoxLayout()
        top_controls_layout.addWidget(self._scan_button)
        top_controls_layout.addWidget(QLabel("Name filter:"))
        top_controls_layout.addWidget(self._device_filter_input)
        top_controls_layout.addWidget(self._device_combo, stretch=1)
        top_controls_layout.addWidget(self._connect_button)
        top_controls_layout.addWidget(self._disconnect_button)
        top_controls_layout.addWidget(self._auto_reconnect_checkbox)

        send_layout = QHBoxLayout()
        send_layout.addWidget(self._message_input, stretch=1)
        send_layout.addWidget(QLabel("Line ending:"))
        send_layout.addWidget(self._line_ending_combo)
        send_layout.addWidget(self._send_button)
        send_layout.addWidget(self._clear_button)
        send_layout.addWidget(self._auto_scroll_checkbox)

        root_layout = QVBoxLayout()
        root_layout.addLayout(top_controls_layout)
        root_layout.addWidget(self._terminal_log, stretch=1)
        root_layout.addLayout(send_layout)

        status_layout = QHBoxLayout()
        status_layout.addWidget(self._status_label, stretch=1)
        status_layout.addWidget(self._show_system_log_button)
        root_layout.addLayout(status_layout)

        central_widget = QWidget()
        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("Menu")
        preferences_action = menu.addAction("Preferences")
        preferences_action.triggered.connect(lambda _checked=False: self._open_preferences())
        menu.addSeparator()
        about_action = menu.addAction("About")
        about_action.triggered.connect(lambda _checked=False: self._open_about())

    def _wire_events(self) -> None:
        self._scan_button.clicked.connect(lambda _checked=False: self.scan_requested.emit())
        self._connect_button.clicked.connect(lambda _checked=False: self._emit_connect_request())
        self._disconnect_button.clicked.connect(lambda _checked=False: self.disconnect_requested.emit())
        self._send_button.clicked.connect(lambda _checked=False: self._emit_send_request())
        self._clear_button.clicked.connect(lambda _checked=False: self._clear_terminal())
        self._show_system_log_button.clicked.connect(
            lambda _checked=False: self._open_system_log_dialog()
        )
        self._auto_reconnect_checkbox.toggled.connect(self._on_auto_reconnect_toggled)
        self._auto_scroll_checkbox.toggled.connect(lambda _checked: self._persist_settings())
        self._line_ending_combo.currentIndexChanged.connect(lambda _index: self._persist_settings())
        self._message_input.returnPressed.connect(self._emit_send_request)
        self._device_filter_input.textChanged.connect(self._on_device_filter_changed)
        self._device_combo.currentIndexChanged.connect(lambda _index: self._apply_control_state())

    def _on_auto_reconnect_toggled(self, checked: bool) -> None:
        self.auto_reconnect_changed.emit(bool(checked))
        self._persist_settings()

    def _on_device_filter_changed(self, _text: str) -> None:
        self._refresh_device_combo()
        self._persist_settings()

    def _emit_connect_request(self) -> None:
        current_address = self._device_combo.currentData()
        if current_address is None:
            self.set_status("Status: Select a device before connecting.")
            return

        self.connect_requested.emit(str(current_address))

    def _emit_send_request(self) -> None:
        raw_text = self._message_input.text()
        selected_line_ending = self._line_ending_combo.currentData()
        line_ending = str(selected_line_ending) if selected_line_ending is not None else ""

        if raw_text == "" and line_ending == "":
            return

        self.send_requested.emit(raw_text, line_ending)
        self._message_input.clear()

    def set_devices(self, devices: list[DiscoveredDevice]) -> None:
        """Refresh the BLE device dropdown."""
        self._all_devices = list(devices)
        self._refresh_device_combo()

    def set_status(self, status_text: str) -> None:
        """Update the status line."""
        self._status_label.setText(status_text)

    def set_connected_state(self, is_connected: bool) -> None:
        """Set current connection state and update control availability."""
        self._is_connected = is_connected
        self._apply_control_state()
        self._update_window_title()

    def set_busy(self, is_busy: bool) -> None:
        """Toggle busy state while asynchronous operations are running."""
        self._is_busy = is_busy
        self._apply_control_state()

    def append_rx(self, text: str) -> None:
        """Append incoming BLE payload to the terminal log."""
        self._append_log_line("", text)

    def append_tx(self, text: str) -> None:
        """Append outgoing BLE payload to the terminal log."""
        self._append_log_line("TX", text)

    def append_system(self, text: str) -> None:
        """Append internal system status to the system log viewer."""
        cleaned_text = text.strip()
        if cleaned_text.startswith("#System:"):
            cleaned_text = cleaned_text.removeprefix("#System:").strip()

        if cleaned_text == "":
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self._system_log_entries.append(f"[{timestamp}] {cleaned_text}")
        if len(self._system_log_entries) > MAX_SYSTEM_LOG_ENTRIES:
            self._system_log_entries = self._system_log_entries[-MAX_SYSTEM_LOG_ENTRIES:]
        self.set_status(cleaned_text)

        if self._system_log_dialog is not None:
            self._system_log_dialog.set_entries(self._system_log_entries)

    def show_error(self, text: str) -> None:
        """Display an error dialog for actionable failures."""
        QMessageBox.critical(self, "Remal Link Error", text)

    def _open_preferences(self) -> None:
        dialog = PreferencesDialog(timestamps_enabled=self._timestamps_enabled, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._timestamps_enabled = dialog.timestamps_enabled()
            self._persist_settings()

    def _open_about(self) -> None:
        dialog = AboutDialog(parent=self)
        dialog.exec()

    def _clear_terminal(self) -> None:
        self._terminal_log.clear()

    def _open_system_log_dialog(self) -> None:
        if self._system_log_dialog is None:
            self._system_log_dialog = SystemLogDialog(parent=self)

        self._system_log_dialog.set_entries(self._system_log_entries)
        self._system_log_dialog.show()
        self._system_log_dialog.raise_()
        self._system_log_dialog.activateWindow()

    def auto_reconnect_enabled(self) -> bool:
        """Return whether auto reconnect is enabled in the UI."""
        return self._auto_reconnect_checkbox.isChecked()

    def _line_ending_index_for_value(self, line_ending: str) -> int:
        for index, (_label, value) in enumerate(LINE_ENDING_CHOICES):
            if value == line_ending:
                return index

        return 1

    def _current_line_ending(self) -> str:
        selected_line_ending = self._line_ending_combo.currentData()
        if selected_line_ending is None:
            return "\n"

        return str(selected_line_ending)

    def _persist_settings(self) -> None:
        self._settings_store.save(
            AppSettings(
                timestamps_enabled=self._timestamps_enabled,
                auto_reconnect_enabled=self._auto_reconnect_checkbox.isChecked(),
                line_ending=self._current_line_ending(),
                auto_scroll_enabled=self._auto_scroll_checkbox.isChecked(),
                device_name_filter=self._device_filter_input.text(),
            )
        )

    def _apply_control_state(self) -> None:
        has_devices = self._device_combo.count() > 0 and self._device_combo.currentData() is not None

        self._scan_button.setEnabled(not self._is_busy)
        self._connect_button.setEnabled(not self._is_busy and not self._is_connected and has_devices)
        self._disconnect_button.setEnabled(not self._is_busy and self._is_connected)
        self._device_filter_input.setEnabled(not self._is_connected)
        self._device_combo.setEnabled(not self._is_connected and not self._is_busy)
        self._message_input.setEnabled(True)
        self._line_ending_combo.setEnabled(True)
        self._send_button.setEnabled(True)
        self._clear_button.setEnabled(True)

    def _update_window_title(self) -> None:
        if not self._is_connected:
            self.setWindowTitle(DEFAULT_WINDOW_TITLE)
            return

        connected_device_name = self._selected_device_name_for_title()
        if connected_device_name is None:
            self.setWindowTitle(DEFAULT_WINDOW_TITLE)
            return

        self.setWindowTitle(f"{DEFAULT_WINDOW_TITLE} - {connected_device_name}")

    def _selected_device_name_for_title(self) -> str | None:
        selected_address = self._device_combo.currentData()
        if selected_address is not None:
            selected_address_text = str(selected_address)
            for device in self._all_devices:
                if device.address == selected_address_text:
                    return device.name

        current_label = self._device_combo.currentText().strip()
        if current_label in {"", "No BLE devices found", "No matching devices"}:
            return None

        if " (" in current_label:
            return current_label.split(" (", 1)[0].strip()

        return current_label

    def _refresh_device_combo(self) -> None:
        selected_address = self._device_combo.currentData()
        name_filter = self._device_filter_input.text().strip().lower()

        if name_filter:
            filtered_devices = [
                device for device in self._all_devices if name_filter in device.name.lower()
            ]
        else:
            filtered_devices = list(self._all_devices)

        self._device_combo.blockSignals(True)
        self._device_combo.clear()

        for device in filtered_devices:
            self._device_combo.addItem(device.display_label(), device.address)

        if not filtered_devices:
            empty_label = "No matching devices" if self._all_devices else "No BLE devices found"
            self._device_combo.addItem(empty_label, None)

        if selected_address is not None:
            selected_index = self._device_combo.findData(selected_address)
            if selected_index >= 0:
                self._device_combo.setCurrentIndex(selected_index)

        self._device_combo.blockSignals(False)
        self._apply_control_state()

    def _append_log_line(self, prefix: str, text: str) -> None:
        line_prefix = self._build_line_prefix(prefix)
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = normalized.split("\n")
        has_non_empty_line = False

        for line in lines:
            if line == "":
                continue

            has_non_empty_line = True
            self._append_colored_line(line_prefix, line)

        if not has_non_empty_line:
            self._append_colored_line(line_prefix, "")

    def _build_line_prefix(self, prefix: str) -> str:
        if prefix:
            line_prefix = f"{prefix}: "
        else:
            line_prefix = ""

        if self._timestamps_enabled:
            timestamp = datetime.now().strftime("%H:%M:%S")
            return f"[{timestamp}] {line_prefix}"

        return line_prefix

    def _append_colored_line(self, line_prefix: str, message: str) -> None:
        scroll_bar = self._terminal_log.verticalScrollBar()
        previous_scroll_value = scroll_bar.value()

        cursor = self._terminal_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if not self._terminal_log.document().isEmpty():
            cursor.insertBlock()

        if line_prefix:
            cursor.insertText(line_prefix)

        for segment_text, color in self._parse_ansi_segments(message):
            if color is None:
                cursor.insertText(segment_text)
                continue

            color_format = QTextCharFormat()
            color_format.setForeground(color)
            cursor.insertText(segment_text, color_format)

        if self._auto_scroll_checkbox.isChecked():
            self._terminal_log.setTextCursor(cursor)
            self._terminal_log.ensureCursorVisible()
            return

        scroll_bar.setValue(min(previous_scroll_value, scroll_bar.maximum()))

    def _parse_ansi_segments(self, text: str) -> list[tuple[str, QColor | None]]:
        segments: list[tuple[str, QColor | None]] = []
        active_color: QColor | None = None
        last_index = 0

        for match in ANSI_ESCAPE_PATTERN.finditer(text):
            if match.start() > last_index:
                segments.append((text[last_index : match.start()], active_color))

            active_color = self._apply_ansi_codes(match.group(1), active_color)
            last_index = match.end()

        if last_index < len(text):
            segments.append((text[last_index:], active_color))

        return segments

    def _apply_ansi_codes(self, code_text: str, current_color: QColor | None) -> QColor | None:
        if code_text == "":
            return None

        codes = [int(code) if code else 0 for code in code_text.split(";")]
        next_color = current_color

        index = 0
        while index < len(codes):
            code = codes[index]

            if code == 0 or code == 39:
                next_color = None
            elif code in ANSI_BASIC_FG_COLORS:
                next_color = QColor(ANSI_BASIC_FG_COLORS[code])
            elif code == 38 and index + 1 < len(codes):
                mode = codes[index + 1]
                if mode == 5 and index + 2 < len(codes):
                    next_color = self._xterm_256_to_qcolor(codes[index + 2])
                    index += 2
                elif mode == 2 and index + 4 < len(codes):
                    red = max(0, min(255, codes[index + 2]))
                    green = max(0, min(255, codes[index + 3]))
                    blue = max(0, min(255, codes[index + 4]))
                    next_color = QColor(red, green, blue)
                    index += 4

            index += 1

        return next_color

    def _xterm_256_to_qcolor(self, code: int) -> QColor:
        clamped_code = max(0, min(255, code))

        if clamped_code < 16:
            return QColor(ANSI_BASE_16_COLORS[clamped_code])

        if clamped_code < 232:
            cube_code = clamped_code - 16
            red = cube_code // 36
            green = (cube_code // 6) % 6
            blue = cube_code % 6

            def _to_channel(value: int) -> int:
                return 0 if value == 0 else 55 + value * 40

            return QColor(_to_channel(red), _to_channel(green), _to_channel(blue))

        gray = 8 + (clamped_code - 232) * 10
        return QColor(gray, gray, gray)
