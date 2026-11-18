"""Helpers for tests that need GTK's main loop to run."""

import time
from collections.abc import Callable

from gi.repository import GLib


def process_pending_events() -> None:
    """Let GTK handle everything that is waiting, without blocking."""
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(may_block=False)


def wait_until(condition: Callable[[], bool], timeout: float = 10.0) -> None:
    """Run the main loop until the condition is true; fail if it takes longer than the timeout, in seconds."""
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Timed out waiting for the condition")
        context.iteration(may_block=False)
        time.sleep(0.005)
