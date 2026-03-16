"""PTY wrapper for spawning and managing Claude Code process."""

import asyncio
import fcntl
import os
import pty
import signal
import struct
import termios
from typing import Callable, Optional

from config import CLAUDE_CODE_CMD


class PTYWrapper:
    """Manages a Claude Code process in a PTY."""

    def __init__(
        self,
        on_output: Callable[[bytes], None],
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        self.on_output = on_output
        self.on_exit = on_exit
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self._read_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        """Spawn Claude Code in a PTY."""
        # Create pseudo-terminal
        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:
            # Child process - change to working directory if specified
            cwd = os.environ.get("VOICE_CLAUDE_CWD")
            if cwd:
                os.chdir(cwd)
            # Exec Claude Code
            os.execvp(CLAUDE_CODE_CMD[0], CLAUDE_CODE_CMD)
        else:
            # Parent process
            self._running = True
            # Set non-blocking mode
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            # Set initial terminal size
            self._set_terminal_size(80, 24)

    def _set_terminal_size(self, cols: int, rows: int) -> None:
        """Set the PTY terminal size."""
        if self.master_fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    async def read_loop(self) -> None:
        """Continuously read output from PTY and dispatch to callback."""
        loop = asyncio.get_event_loop()

        while self._running and self.master_fd is not None:
            try:
                # Wait for data to be available
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop

                try:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        self.on_output(data)
                    else:
                        # EOF - process exited
                        self._running = False
                        break
                except BlockingIOError:
                    # No data available yet
                    continue
                except OSError as e:
                    if e.errno == 5:  # Input/output error - PTY closed
                        self._running = False
                        break
                    raise

            except Exception as e:
                print(f"PTY read error: {e}")
                self._running = False
                break

        # Clean up and notify
        self._cleanup()

    def write(self, data: bytes) -> None:
        """Write data to the PTY (send to Claude Code)."""
        if self.master_fd is not None and self._running:
            try:
                os.write(self.master_fd, data)
            except OSError as e:
                print(f"PTY write error: {e}")

    def write_line(self, text: str) -> None:
        """Write a line of text followed by Enter."""
        self.write(text.encode("utf-8") + b"\r")

    def send_control(self, char: str) -> None:
        """Send a control character (e.g., 'c' for Ctrl+C)."""
        ctrl_char = chr(ord(char.upper()) - ord("A") + 1)
        self.write(ctrl_char.encode("utf-8"))

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY terminal."""
        self._set_terminal_size(cols, rows)
        # Send SIGWINCH to notify the child process
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGWINCH)
            except ProcessLookupError:
                pass

    def _cleanup(self) -> None:
        """Clean up PTY resources."""
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        # Check exit status
        if self.pid is not None:
            try:
                _, status = os.waitpid(self.pid, os.WNOHANG)
                if self.on_exit:
                    self.on_exit(status)
            except ChildProcessError:
                pass

    def stop(self) -> None:
        """Stop the PTY and child process."""
        self._running = False
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self._cleanup()

    @property
    def is_running(self) -> bool:
        """Check if the PTY is still running."""
        return self._running
