"""Floating input window for voice dictation using macOS native dialogs."""

import subprocess
from typing import Callable, Optional


class InputWindow:
    """A simple input dialog using macOS AppleScript."""

    def __init__(self, on_submit: Callable[[str], None]):
        self.on_submit = on_submit
        self._result: Optional[str] = None

    def show(self, prompt: str = "Speak your response:") -> None:
        """Show the input dialog."""
        # Use AppleScript for a native macOS dialog
        script = f'''
        tell application "System Events"
            activate
            display dialog "{prompt}" default answer "" with title "Voice Claude" buttons {{"Cancel", "Send"}} default button "Send"
            set dialogResult to result
            return text returned of dialogResult
        end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0 and result.stdout.strip():
                self._result = result.stdout.strip()
                self.on_submit(self._result)
            else:
                # User cancelled or error
                self._result = None

        except subprocess.TimeoutExpired:
            self._result = None
        except Exception as e:
            print(f"Dialog error: {e}")
            self._result = None


class NotificationInput:
    """Alternative: Use terminal-notifier with input."""

    def __init__(self, on_submit: Callable[[str], None]):
        self.on_submit = on_submit

    def show(self, prompt: str = "Speak your response:") -> None:
        """Show notification and wait for input via stdin."""
        # Show a notification
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{prompt}" with title "Voice Claude"',
            ],
            capture_output=True,
        )

        # This would need to be called from a terminal context
        try:
            user_input = input(f"\n{prompt}\n🎤 > ")
            if user_input.strip():
                self.on_submit(user_input.strip())
        except (KeyboardInterrupt, EOFError):
            pass
