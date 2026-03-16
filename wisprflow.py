"""WisprFlow integration for auto-triggering dictation."""

import subprocess
import asyncio
from config import WISPRFLOW_HOTKEY


def _parse_hotkey(hotkey: str) -> list[str]:
    """Parse hotkey string into AppleScript key codes.

    Supported formats:
    - "option option" - double-tap Option
    - "fn fn" - double-tap Fn
    - "control option space" - Ctrl+Option+Space
    """
    key_map = {
        "option": "option down",
        "control": "control down",
        "command": "command down",
        "shift": "shift down",
        "fn": "fn down",  # Note: fn is tricky in AppleScript
        "space": "space",
    }
    return hotkey.lower().split()


def get_frontmost_app() -> str:
    """Get the name of the frontmost application."""
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        return frontApp
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return "Terminal"


def trigger_wisprflow_sync() -> bool:
    """Trigger WisprFlow activation (synchronous).

    Returns True if the trigger was attempted successfully.
    """
    hotkey = WISPRFLOW_HOTKEY.lower().strip()

    # Get the frontmost app so we can re-activate it
    frontmost = get_frontmost_app()

    # Handle different hotkey patterns
    parts = hotkey.split()

    if len(parts) == 1 and parts[0] == "option":
        # Hold option key for duration of speech (5 seconds default)
        # WisprFlow listens while key is held, transcribes on release
        script = f'''
        tell application "{frontmost}" to activate
        delay 0.1
        tell application "System Events"
            key down option
            delay 5
            key up option
        end tell
        '''
    elif len(parts) == 2 and parts[0] == parts[1]:
        # Double-tap pattern (e.g., "option option")
        key = parts[0]
        if key == "option":
            script = f'''
            tell application "{frontmost}" to activate
            delay 0.1
            tell application "System Events"
                key down option
                key up option
                delay 0.1
                key down option
                key up option
            end tell
            '''
        elif key == "fn":
            # fn key is harder to simulate, try keystroke approach
            script = f'''
            tell application "{frontmost}" to activate
            delay 0.1
            tell application "System Events"
                key code 63
                delay 0.1
                key code 63
            end tell
            '''
        else:
            return False
    elif hotkey == "control option space":
        script = f'''
        tell application "{frontmost}" to activate
        delay 0.1
        tell application "System Events"
            keystroke " " using {{control down, option down}}
        end tell
        '''
    else:
        # Generic single key combo
        return False

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=2,
        )
        return True
    except Exception as e:
        print(f"Failed to trigger WisprFlow: {e}")
        return False


async def trigger_wisprflow() -> bool:
    """Trigger WisprFlow activation (async)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, trigger_wisprflow_sync)


async def wait_and_trigger(delay: float = 0.3) -> bool:
    """Wait briefly then trigger WisprFlow.

    The delay allows the prompt to be displayed before triggering.
    """
    await asyncio.sleep(delay)
    return await trigger_wisprflow()
