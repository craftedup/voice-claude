"""Output monitor for detecting when Claude Code needs input."""

import asyncio
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import pyte

from config import MIN_OUTPUT_LENGTH, OUTPUT_DEBOUNCE_SECONDS


class OutputType(Enum):
    """Types of output that might need voice response."""

    PERMISSION_PROMPT = "permission"  # y/n permission prompts
    QUESTION = "question"  # Claude asking a question
    COMPLETION = "completion"  # Task completed, showing results
    ERROR = "error"  # Error message
    WAITING = "waiting"  # Idle/waiting for input
    ONGOING = "ongoing"  # Still outputting, not ready


@dataclass
class OutputEvent:
    """An output event detected by the monitor."""

    output_type: OutputType
    text: str
    raw_output: str
    needs_response: bool


class OutputMonitor:
    """Monitors PTY output and detects when voice interaction is needed."""

    # Patterns that indicate Claude is waiting for input
    PERMISSION_PATTERNS = [
        r"Allow\?.*\[y/n\]",
        r"\[Y/n\]",
        r"\[y/N\]",
        r"Do you want to proceed\?",
        r"Continue\?",
        r"Approve\?",
    ]

    QUESTION_PATTERNS = [
        r"\?\s*$",  # Ends with question mark
        r"What would you like",
        r"How should I",
        r"Which.*\?",
        r"Where.*\?",
    ]

    ERROR_PATTERNS = [
        r"Error:",
        r"error:",
        r"Failed:",
        r"failed:",
        r"Exception:",
    ]

    # Patterns indicating Claude is still working
    WORKING_PATTERNS = [
        r"Reading file",
        r"Searching",
        r"Writing",
        r"Running",
        r"\.{3}$",  # Ends with ...
    ]

    def __init__(self, on_event: Callable[[OutputEvent], None]):
        self.on_event = on_event
        self._buffer = ""
        self._raw_buffer = b""
        self._last_output_time = 0.0
        self._debounce_task: Optional[asyncio.Task] = None
        self._screen = pyte.Screen(80, 24)
        self._stream = pyte.Stream(self._screen)

    def feed(self, data: bytes) -> None:
        """Feed raw PTY output to the monitor."""
        self._raw_buffer += data

        # Decode and add to text buffer
        try:
            text = data.decode("utf-8", errors="replace")
            self._buffer += text
        except Exception:
            pass

        # Feed to terminal emulator for clean text extraction
        try:
            self._stream.feed(data.decode("utf-8", errors="replace"))
        except Exception:
            pass

        # Cancel existing debounce and start new one
        if self._debounce_task:
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounced_analyze())

    async def _debounced_analyze(self) -> None:
        """Wait for output to settle, then analyze."""
        await asyncio.sleep(OUTPUT_DEBOUNCE_SECONDS)
        self._analyze_buffer()

    def _get_screen_text(self) -> str:
        """Get clean text from the terminal emulator screen."""
        lines = []
        for line in self._screen.display:
            stripped = line.rstrip()
            if stripped:
                lines.append(stripped)
        return "\n".join(lines)

    def _analyze_buffer(self) -> None:
        """Analyze the buffer and emit events if needed."""
        if len(self._buffer) < MIN_OUTPUT_LENGTH:
            return

        # Get clean screen text
        screen_text = self._get_screen_text()
        raw_text = self._buffer

        # Determine output type
        output_type = self._classify_output(screen_text, raw_text)
        # Need voice input for prompts, questions, and when Claude is waiting at the input prompt
        needs_response = output_type in [OutputType.PERMISSION_PROMPT, OutputType.QUESTION, OutputType.WAITING]

        # Create and emit event
        event = OutputEvent(
            output_type=output_type,
            text=screen_text,
            raw_output=raw_text,
            needs_response=needs_response,
        )

        self.on_event(event)

        # Clear buffers after emitting
        self._buffer = ""
        self._raw_buffer = b""

    def _classify_output(self, screen_text: str, raw_text: str) -> OutputType:
        """Classify the type of output."""
        combined = screen_text + " " + raw_text
        lines = screen_text.strip().split('\n')
        last_line = lines[-1].strip() if lines else ""

        # Check for permission prompts first (highest priority)
        for pattern in self.PERMISSION_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return OutputType.PERMISSION_PROMPT

        # Check if Claude is at an input prompt (waiting for user)
        # This is high priority - if we see the ❯ prompt, we need input
        if '❯' in last_line:
            return OutputType.WAITING

        # Check for errors
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, combined):
                return OutputType.ERROR

        # Check if still working
        for pattern in self.WORKING_PATTERNS:
            if re.search(pattern, combined):
                return OutputType.ONGOING

        # Check for questions
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, combined):
                return OutputType.QUESTION

        # Default to completion if substantial output
        if len(screen_text) > 50:
            return OutputType.COMPLETION

        return OutputType.ONGOING

    def clear(self) -> None:
        """Clear the monitor buffers."""
        self._buffer = ""
        self._raw_buffer = b""
        self._screen.reset()

    def resize(self, cols: int, rows: int) -> None:
        """Resize the internal terminal emulator."""
        self._screen.resize(rows, cols)
