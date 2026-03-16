"""Input handler for capturing user input (including WisprFlow dictation)."""

import asyncio
import sys
from typing import Callable, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout


class InputHandler:
    """Handles user input from terminal, compatible with WisprFlow dictation."""

    def __init__(self, on_input: Callable[[str], None]):
        self.on_input = on_input
        self._session: Optional[PromptSession] = None
        self._running = False
        self._history = InMemoryHistory()

    async def start(self) -> None:
        """Start the input handler."""
        self._running = True
        self._session = PromptSession(history=self._history)

    async def stop(self) -> None:
        """Stop the input handler."""
        self._running = False

    async def prompt(self, message: str = "You: ") -> Optional[str]:
        """Display a prompt and wait for input.

        This works with WisprFlow - the dictation service types into
        the active text field, and Enter submits.

        Args:
            message: The prompt message to display

        Returns:
            The user's input, or None if cancelled
        """
        if not self._session:
            await self.start()

        try:
            with patch_stdout():
                result = await self._session.prompt_async(message)
                return result.strip() if result else None
        except KeyboardInterrupt:
            return None
        except EOFError:
            return None

    async def prompt_with_callback(self, message: str = "You: ") -> None:
        """Prompt for input and call the callback with the result."""
        result = await self.prompt(message)
        if result:
            self.on_input(result)


class SimpleInputHandler:
    """Simple synchronous input handler for basic terminal input."""

    def __init__(self):
        pass

    def get_input(self, prompt: str = "You: ") -> Optional[str]:
        """Get input from stdin."""
        try:
            result = input(prompt)
            return result.strip() if result else None
        except (KeyboardInterrupt, EOFError):
            return None


class AsyncInputReader:
    """Async wrapper for reading from stdin."""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        """Start the input reader."""
        self._running = True

    async def stop(self) -> None:
        """Stop the input reader."""
        self._running = False

    async def readline(self) -> Optional[str]:
        """Read a line from stdin asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            return line.strip() if line else None
        except Exception:
            return None
