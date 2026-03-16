#!/usr/bin/env python3
"""Test WisprFlow triggering in isolation."""

import subprocess
import time

def test_trigger(hotkey_type: str):
    """Test different WisprFlow trigger methods."""

    print(f"\nTesting: {hotkey_type}")
    print("WisprFlow should activate in 2 seconds...")
    time.sleep(2)

    if hotkey_type == "single_option":
        # Hold option key for 5 seconds while user speaks
        script = '''
        tell application "System Events"
            key down option
            delay 5
            key up option
        end tell
        '''
    elif hotkey_type == "double_option":
        script = '''
        tell application "System Events"
            key down option
            key up option
            delay 0.1
            key down option
            key up option
        end tell
        '''
    elif hotkey_type == "fn_fn":
        script = '''
        tell application "System Events"
            key code 63
            delay 0.1
            key code 63
        end tell
        '''
    elif hotkey_type == "globe":
        # Globe key (on newer Macs) - same as fn
        script = '''
        tell application "System Events"
            key code 63
        end tell
        '''
    else:
        print(f"Unknown hotkey type: {hotkey_type}")
        return False

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        print(f"AppleScript result: stdout='{result.stdout}', stderr='{result.stderr}', returncode={result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    print("WisprFlow Trigger Test")
    print("=" * 40)
    print("\nMake sure a text field is focused (like this terminal).")
    print("WisprFlow should activate and start listening.\n")

    print("Which hotkey does your WisprFlow use?")
    print("1. Single Option key tap")
    print("2. Double Option key tap")
    print("3. Double Fn key tap")
    print("4. Globe key (single tap)")
    print("5. Manual test - I'll press my WisprFlow hotkey myself")

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        test_trigger("single_option")
    elif choice == "2":
        test_trigger("double_option")
    elif choice == "3":
        test_trigger("fn_fn")
    elif choice == "4":
        test_trigger("globe")
    elif choice == "5":
        print("\nOK, press your WisprFlow hotkey now and speak.")
        print("Type what WisprFlow transcribed (or 'nothing' if it didn't work):")
        result = input("> ")
        if result.lower() == "nothing":
            print("WisprFlow didn't activate. Check your WisprFlow settings.")
        else:
            print(f"Great! WisprFlow typed: '{result}'")
            print("Now we know your manual activation works.")
    else:
        print("Invalid choice")
