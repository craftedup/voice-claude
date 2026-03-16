"""Inject text into the active terminal window."""

import subprocess
import time
from typing import Optional


class TextInjector:
    """Injects text into the active terminal window on macOS."""

    def inject_text(self, text: str) -> bool:
        """Type text into the active application.

        Args:
            text: The text to type.

        Returns:
            True if successful, False otherwise.
        """
        # Escape special characters for AppleScript
        escaped_text = self._escape_for_applescript(text)

        script = f"""
        tell application "System Events"
            keystroke "{escaped_text}"
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"Text injection error: {e}")
            return False

    def inject_enter(self) -> bool:
        """Press the Enter key."""
        script = """
        tell application "System Events"
            keystroke return
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"Enter key injection error: {e}")
            return False

    def inject_key(self, key_code: int, modifiers: Optional[list] = None) -> bool:
        """Press a specific key with optional modifiers.

        Args:
            key_code: The macOS virtual key code.
            modifiers: List of modifiers like "command down", "shift down".

        Returns:
            True if successful, False otherwise.
        """
        modifier_str = ""
        if modifiers:
            modifier_str = " using {" + ", ".join(modifiers) + "}"

        script = f"""
        tell application "System Events"
            key code {key_code}{modifier_str}
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"Key injection error: {e}")
            return False

    def inject_control_c(self) -> bool:
        """Send Ctrl+C to the active application."""
        # Key code 8 is 'c', with control modifier
        script = """
        tell application "System Events"
            keystroke "c" using control down
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _escape_for_applescript(self, text: str) -> str:
        """Escape special characters for AppleScript string."""
        # Escape backslashes first, then quotes
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        return text

    def paste_text(self, text: str) -> bool:
        """Paste text using clipboard (alternative to keystroke).

        This is more reliable for longer text or special characters.

        Args:
            text: The text to paste.

        Returns:
            True if successful, False otherwise.
        """
        # Set clipboard content
        script = f"""
        set the clipboard to "{self._escape_for_applescript(text)}"
        tell application "System Events"
            keystroke "v" using command down
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"Paste error: {e}")
            return False
