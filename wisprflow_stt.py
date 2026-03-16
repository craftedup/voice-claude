"""WisprFlow STT integration — hands-free voice input.

Uses CGEvent (CoreGraphics) to simulate real hardware key events.
Holds Option key for a fixed duration, then releases so WisprFlow
transcribes and types the result.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import Quartz

from config import WISPRFLOW_MAX_LISTEN_SECONDS

# macOS key code for Option (58)
OPTION_KEYCODE = 58


class WisprFlowSTT:
    """Hands-free WisprFlow integration using CGEvent."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _press_option(self) -> None:
        """Press (key down) Option using CGEvent."""
        event = Quartz.CGEventCreateKeyboardEvent(None, OPTION_KEYCODE, True)
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskAlternate)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _release_option(self) -> None:
        """Release (key up) Option using CGEvent."""
        event = Quartz.CGEventCreateKeyboardEvent(None, OPTION_KEYCODE, False)
        Quartz.CGEventSetFlags(event, 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def trigger_sync(self, hold_seconds: float = None) -> None:
        """Hold Option to activate WisprFlow, release after duration.

        WisprFlow handles its own audio — we just hold and release the key.
        """
        if hold_seconds is None:
            hold_seconds = WISPRFLOW_MAX_LISTEN_SECONDS

        self._press_option()
        time.sleep(hold_seconds)
        self._release_option()

    async def trigger(self, hold_seconds: float = None) -> None:
        """Async: hold Option for duration, then release."""
        if hold_seconds is None:
            hold_seconds = WISPRFLOW_MAX_LISTEN_SECONDS

        self._press_option()
        await asyncio.sleep(hold_seconds)
        self._release_option()

    def stop(self) -> None:
        """Make sure Option is released."""
        try:
            self._release_option()
        except Exception:
            pass
