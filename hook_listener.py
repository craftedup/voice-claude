"""Hook-based listener for Claude Code integration.

Instead of monitoring PTY output directly, this watches for signal files
created by Claude Code hooks. The hooks fire when Claude finishes responding
(Stop), needs input (idle_prompt), or needs permission (permission_prompt).

This module can be used by both the integrated mode and daemon mode to react
to Claude Code events without PTY scraping.
"""

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


# Signal file paths (shared with hook shell scripts)
HOOKS_ACTIVE_FILE = Path("/tmp/voice-claude-hooks-active")
TTS_QUEUE_FILE = Path("/tmp/voice-claude-tts-queue")
TTS_READY_FILE = Path("/tmp/voice-claude-tts-ready")
STT_TRIGGER_FILE = Path("/tmp/voice-claude-stt-trigger")
PERMISSION_QUEUE_FILE = Path("/tmp/voice-claude-permission-queue")
PERMISSION_READY_FILE = Path("/tmp/voice-claude-permission-ready")


class HookEventType(Enum):
    """Types of events from Claude Code hooks."""

    RESPONSE_READY = "response_ready"  # Claude finished, text available for TTS
    INPUT_NEEDED = "input_needed"  # Claude is idle, waiting for user input
    PERMISSION_NEEDED = "permission_needed"  # Claude needs permission approval


@dataclass
class HookEvent:
    """An event received via Claude Code hooks."""

    event_type: HookEventType
    text: str  # Response text, permission details, or empty


class HookListener:
    """Watches for signal files created by Claude Code hooks.

    Polls /tmp signal files at a configurable interval and emits events
    when Claude Code reaches lifecycle points we care about.
    """

    def __init__(
        self,
        on_event: Callable[[HookEvent], None],
        poll_interval: float = 0.2,
    ):
        self.on_event = on_event
        self.poll_interval = poll_interval
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

    def activate(self) -> None:
        """Create the signal file that tells hooks to fire."""
        HOOKS_ACTIVE_FILE.touch()

    def deactivate(self) -> None:
        """Remove the signal file so hooks stop firing."""
        HOOKS_ACTIVE_FILE.unlink(missing_ok=True)
        self._cleanup_signals()

    async def start(self) -> None:
        """Start polling for hook signals."""
        self.activate()
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop polling and clean up."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self.deactivate()

    async def _poll_loop(self) -> None:
        """Main polling loop — check for signal files."""
        while self._running:
            try:
                # Check for TTS response ready
                if TTS_READY_FILE.exists():
                    text = ""
                    if TTS_QUEUE_FILE.exists():
                        text = TTS_QUEUE_FILE.read_text().strip()
                        TTS_QUEUE_FILE.unlink(missing_ok=True)
                    TTS_READY_FILE.unlink(missing_ok=True)

                    if text:
                        self.on_event(
                            HookEvent(
                                event_type=HookEventType.RESPONSE_READY,
                                text=text,
                            )
                        )

                # Check for STT trigger (Claude waiting for input)
                if STT_TRIGGER_FILE.exists():
                    STT_TRIGGER_FILE.unlink(missing_ok=True)
                    self.on_event(
                        HookEvent(
                            event_type=HookEventType.INPUT_NEEDED,
                            text="",
                        )
                    )

                # Check for permission request
                if PERMISSION_READY_FILE.exists():
                    text = ""
                    if PERMISSION_QUEUE_FILE.exists():
                        text = PERMISSION_QUEUE_FILE.read_text().strip()
                        PERMISSION_QUEUE_FILE.unlink(missing_ok=True)
                    PERMISSION_READY_FILE.unlink(missing_ok=True)

                    self.on_event(
                        HookEvent(
                            event_type=HookEventType.PERMISSION_NEEDED,
                            text=text,
                        )
                    )

            except Exception:
                pass  # Don't crash on transient file errors

            await asyncio.sleep(self.poll_interval)

    def _cleanup_signals(self) -> None:
        """Remove all signal files."""
        for f in [
            TTS_QUEUE_FILE,
            TTS_READY_FILE,
            STT_TRIGGER_FILE,
            PERMISSION_QUEUE_FILE,
            PERMISSION_READY_FILE,
        ]:
            f.unlink(missing_ok=True)
