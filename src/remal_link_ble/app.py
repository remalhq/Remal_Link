"""Application bootstrap for the Remal Link BLE serial terminal."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from remal_link_ble.config.settings_store import SettingsStore
from remal_link_ble.config.uuids import DEFAULT_UART_UUIDS
from remal_link_ble.core.controller import BleTerminalController
from remal_link_ble.ui.main_window import MainWindow


def main() -> int:
    """Start the Remal Link GUI application."""
    app = QApplication(sys.argv)

    settings_store = SettingsStore.for_project_root()
    settings = settings_store.load()

    window = MainWindow(settings_store=settings_store, initial_settings=settings)
    controller = BleTerminalController(window=window, uuids=DEFAULT_UART_UUIDS)

    app.aboutToQuit.connect(controller.shutdown)
    window.show()

    return app.exec()
