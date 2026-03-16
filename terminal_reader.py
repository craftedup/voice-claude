"""Read content from the active terminal window using macOS accessibility."""

import subprocess
from typing import Optional


class TerminalReader:
    """Reads content from the active terminal window on macOS."""

    def read_active_terminal(self) -> Optional[str]:
        """Read the visible content of the active terminal.

        Returns:
            The terminal's visible text content, or None if not available.
        """
        # Try multiple methods
        content = self._read_via_applescript()
        if content:
            return content

        content = self._read_via_accessibility()
        if content:
            return content

        return None

    def _read_via_applescript(self) -> Optional[str]:
        """Read terminal content via AppleScript."""
        # Script to get content from Terminal.app
        terminal_script = """
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
        end tell

        if frontApp is "Terminal" then
            tell application "Terminal"
                if (count of windows) > 0 then
                    return contents of selected tab of front window
                end if
            end tell
        else if frontApp is "iTerm2" or frontApp is "iTerm" then
            tell application "iTerm"
                if (count of windows) > 0 then
                    tell current session of current window
                        return contents
                    end tell
                end if
            end tell
        end if

        return ""
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", terminal_script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"AppleScript error: {e}")

        return None

    def _read_via_accessibility(self) -> Optional[str]:
        """Read terminal content via macOS accessibility APIs.

        This requires accessibility permissions to be granted.
        """
        # AppleScript using accessibility
        accessibility_script = """
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set appName to name of frontApp

            -- Try to get the content from a text area
            try
                set textContent to value of text area 1 of scroll area 1 of window 1 of frontApp
                return textContent
            end try

            -- Try AXValue
            try
                set textContent to value of attribute "AXValue" of window 1 of frontApp
                return textContent
            end try
        end tell

        return ""
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", accessibility_script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        return None

    def get_active_app(self) -> Optional[str]:
        """Get the name of the currently active application."""
        script = """
        tell application "System Events"
            return name of first application process whose frontmost is true
        end tell
        """

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        return None

    def is_terminal_active(self) -> bool:
        """Check if a terminal application is currently active."""
        app = self.get_active_app()
        if app:
            terminal_apps = ["Terminal", "iTerm", "iTerm2", "Alacritty", "kitty", "Hyper", "Warp"]
            return any(t.lower() in app.lower() for t in terminal_apps)
        return False
