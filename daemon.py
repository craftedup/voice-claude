#!/usr/bin/env python3
"""Voice Claude Daemon - Global voice interface for any terminal."""

import subprocess
import sys
import threading
import time
from typing import Optional

from pynput import keyboard

from config import ANTHROPIC_API_KEY, ELEVEN_API_KEY
from input_window import InputWindow
from interpreter import Interpreter
from terminal_reader import TerminalReader
from text_injector import TextInjector
from tts import TTSEngine


class VoiceClaudeDaemon:
    """Background daemon for voice-enabled terminal interaction."""

    def __init__(self):
        self.interpreter = Interpreter()
        self.tts = TTSEngine()
        self.terminal_reader = TerminalReader()
        self.text_injector = TextInjector()

        self._running = False
        self._current_keys = set()
        self._listening = False
        self._last_terminal_content = ""
        self._pending_context = ""

    def start(self) -> None:
        """Start the daemon."""
        print("=" * 50)
        print("  Voice Claude Daemon")
        print("=" * 50)
        print()
        print("Hotkeys:")
        print("  Cmd+Shift+V  - Read terminal & speak summary")
        print("  Cmd+Shift+R  - Respond (opens input window)")
        print("  Ctrl+C       - Quit daemon")
        print()

        # Validate API keys
        if not ANTHROPIC_API_KEY:
            print("Error: ANTHROPIC_API_KEY not configured")
            sys.exit(1)
        if not ELEVEN_API_KEY:
            print("Error: ELEVEN_API_KEY not configured")
            sys.exit(1)

        # Start TTS engine
        self.tts.start()

        # Announce ready
        self.tts.speak("Voice daemon ready")
        print("[Ready] Listening for hotkeys...")

        self._running = True

        # Start keyboard listener
        with keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        ) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                pass

        self._shutdown()

    def _on_key_press(self, key) -> None:
        """Handle key press events."""
        self._current_keys.add(self._normalize_key(key))

        # Check for Cmd+Shift+V (read & speak)
        if self._check_hotkey("v"):
            self._activate_read_mode()

        # Check for Cmd+Shift+R (respond)
        if self._check_hotkey("r"):
            self._activate_respond_mode()

    def _on_key_release(self, key) -> None:
        """Handle key release events."""
        self._current_keys.discard(self._normalize_key(key))

    def _normalize_key(self, key):
        """Normalize key for comparison."""
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return key

    def _check_hotkey(self, char: str) -> bool:
        """Check if Cmd+Shift+<char> is pressed."""
        has_cmd = (
            keyboard.Key.cmd in self._current_keys
            or keyboard.Key.cmd_l in self._current_keys
            or keyboard.Key.cmd_r in self._current_keys
        )
        has_shift = (
            keyboard.Key.shift in self._current_keys
            or keyboard.Key.shift_l in self._current_keys
            or keyboard.Key.shift_r in self._current_keys
        )
        has_char = char in self._current_keys

        return has_cmd and has_shift and has_char

    def _activate_read_mode(self) -> None:
        """Read terminal and speak summary."""
        if self._listening:
            return

        self._listening = True
        threading.Thread(target=self._read_and_speak, daemon=True).start()

    def _read_and_speak(self) -> None:
        """Read terminal content and speak it."""
        try:
            print("\n[Reading terminal...]")

            # Small delay to let hotkey release
            time.sleep(0.2)

            terminal_content = self.terminal_reader.read_active_terminal()

            if not terminal_content:
                self.tts.speak("Couldn't read terminal content")
                return

            # Store for response context
            self._pending_context = terminal_content
            self._last_terminal_content = terminal_content

            # Summarize and speak
            summary = self.interpreter.output_to_speech(
                terminal_content[-3000:],
                "completion",
            )

            print(f"[Speaking] {summary}")
            self.tts._speak_sync(summary)
            print("[Done] Press Cmd+Shift+R to respond")

        except Exception as e:
            print(f"[Error] {e}")
        finally:
            self._listening = False

    def _activate_respond_mode(self) -> None:
        """Open input window for voice response."""
        if self._listening:
            return

        self._listening = True
        threading.Thread(target=self._show_input_window, daemon=True).start()

    def _show_input_window(self) -> None:
        """Show the floating input window."""
        try:
            print("\n[Opening input window...]")

            # Small delay to let hotkey release
            time.sleep(0.2)

            # Refresh terminal content if we don't have context
            if not self._pending_context:
                self._pending_context = (
                    self.terminal_reader.read_active_terminal() or ""
                )

            # Create and show window
            window = InputWindow(self._on_input_received)
            window.show("🎤 Speak your response (Enter to send, Esc to cancel):")

        except Exception as e:
            print(f"[Error] {e}")
        finally:
            self._listening = False

    def _on_input_received(self, text: str) -> None:
        """Handle input from the floating window."""
        if not text:
            print("[Cancelled]")
            return

        print(f"[Received] {text}")

        # Check for control commands
        if text.lower() in ["cancel", "nevermind", "never mind"]:
            print("[Cancelled]")
            return

        # Interpret speech to CLI input
        cli_input = self.interpreter.speech_to_input(
            text, self._pending_context[-2000:], "question"
        )

        if cli_input:
            print(f"[Injecting] {cli_input}")

            # Small delay before injecting
            time.sleep(0.3)

            # Inject into the terminal
            self.text_injector.inject_text(cli_input)
            time.sleep(0.1)
            self.text_injector.inject_enter()

            self.tts.speak("Sent")
        else:
            self.tts.speak("Didn't understand")

        # Clear context
        self._pending_context = ""

    def _shutdown(self) -> None:
        """Clean shutdown."""
        print("\n[Shutting down...]")
        self.tts.stop()


def main():
    """Main entry point."""
    daemon = VoiceClaudeDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
