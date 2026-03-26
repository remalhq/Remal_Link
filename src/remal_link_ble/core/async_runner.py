"""Background asyncio loop runner for BLE operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import threading
from typing import Any


class AsyncRunner:
    """Run asyncio coroutines on a dedicated background thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="RemalLinkAsyncRunner", daemon=True)
        self._thread.start()
        self._loop_ready.wait()

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        self._loop_ready.set()
        loop.run_forever()

        pending_tasks = asyncio.all_tasks(loop)
        for task in pending_tasks:
            task.cancel()

        if pending_tasks:
            loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))

        loop.close()

    def submit(
        self,
        coroutine: Awaitable[Any],
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Schedule a coroutine for background execution."""
        if self._loop is None:
            raise RuntimeError("Async loop is not running.")

        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)

        def _on_done(completed_future: Any) -> None:
            try:
                result = completed_future.result()
            except Exception as exc:
                if on_error is not None:
                    on_error(exc)
                return

            if on_result is not None:
                on_result(result)

        future.add_done_callback(_on_done)

    def stop(self) -> None:
        """Stop the background event loop and wait for thread shutdown."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        self._thread.join(timeout=2.0)
