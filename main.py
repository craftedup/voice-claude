#!/usr/bin/env python3
"""Voice interface for Claude Code.

Uses ❯ prompt detection for knowing when to listen (this works).
Uses Claude Code Stop hook for clean response text (no terminal scraping).
"""

import asyncio
import os
import signal
import sys
import time
import tty
import termios
from pathlib import Path
from typing import Optional

from config import ELEVEN_API_KEY, STT_MODE, WISPRFLOW_TYPING_TIMEOUT
from pty_wrapper import PTYWrapper
from tts import AsyncTTSEngine

# Signal files shared with hooks
HOOKS_ACTIVE_FILE = Path("/tmp/voice-claude-hooks-active")
TTS_QUEUE_FILE = Path("/tmp/voice-claude-tts-queue")
TTS_READY_FILE = Path("/tmp/voice-claude-tts-ready")


class VoiceClaude:
    def __init__(self):
        self.pty: Optional[PTYWrapper] = None
        self.tts: Optional[AsyncTTSEngine] = None
        self._running = False
        self._stt_mode = STT_MODE
        self._prompt_ready = False

        # WisprFlow state
        self._suppress_output = False
        self._wisprflow_waiting = False
        self._wisprflow_last_char_time: float = 0
        self._wisprflow_char_count: int = 0

    async def start(self) -> None:
        print("Starting Voice Claude...")

        if not ELEVEN_API_KEY:
            print("Error: ELEVEN_API_KEY not set")
            sys.exit(1)

        self.tts = AsyncTTSEngine()
        await self.tts.start()

        if self._stt_mode == "wisprflow":
            from wisprflow_stt import WisprFlowSTT
            self.wisprflow = WisprFlowSTT()
            print("STT mode: WisprFlow (hands-free via CGEvent)")
        else:
            from speech_recognition import SpeechRecognizer
            self.speech = SpeechRecognizer()
            print("Loading speech model...")
            await self.speech.load_model_async()
            print("Speech model loaded.")

        # Activate hooks and clean stale signals
        for f in [TTS_QUEUE_FILE, TTS_READY_FILE]:
            f.unlink(missing_ok=True)
        HOOKS_ACTIVE_FILE.touch()

        self.pty = PTYWrapper(
            on_output=self._on_pty_output,
            on_exit=self._on_pty_exit,
        )

        print("Starting Claude Code...")
        self.pty.start()
        self._running = True

        await self.tts.speak_and_wait("Ready")
        await self._run()

    async def _run(self) -> None:
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            pty_task = asyncio.create_task(self.pty.read_loop())
            stdin_task = asyncio.create_task(self._forward_stdin())
            voice_task = asyncio.create_task(self._main_voice_loop())

            await pty_task
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        await self._shutdown()

    async def _forward_stdin(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running and self.pty.is_running:
            try:
                data = await loop.run_in_executor(
                    None, lambda: os.read(sys.stdin.fileno(), 1024)
                )
                if data:
                    self.pty.write(data)
                    if self._wisprflow_waiting:
                        self._wisprflow_last_char_time = time.monotonic()
                        self._wisprflow_char_count += len(data)
            except:
                break

    async def _main_voice_loop(self) -> None:
        """Wait for Claude to finish, speak response, listen, repeat."""
        # Wait for initial startup prompt
        await asyncio.sleep(3)
        first_run = True

        while self._running and self.pty.is_running:
            if first_run:
                # First time: just wait for ❯ prompt, no Stop hook yet
                while self._running and self.pty.is_running:
                    if self._prompt_ready:
                        self._prompt_ready = False
                        break
                    await asyncio.sleep(0.2)
                first_run = False
            else:
                # After first input: wait for Stop hook (Claude finished responding)
                await self._wait_and_speak_response()

            # Beep and listen
            await asyncio.sleep(0.3)
            await self.tts.beep()

            if self._stt_mode == "wisprflow":
                # Hold Option for WisprFlow to record, then release
                self._suppress_output = True
                await self.wisprflow.trigger()

                # WisprFlow is now transcribing — wait for it to type
                self._wisprflow_waiting = True
                self._wisprflow_char_count = 0
                self._wisprflow_last_char_time = 0
                self._suppress_output = False

                # Wait for typing to start then stop
                timeout_start = time.monotonic()
                while self._running and self.pty.is_running:
                    await asyncio.sleep(0.1)
                    if self._wisprflow_char_count > 0 and self._wisprflow_last_char_time > 0:
                        elapsed = time.monotonic() - self._wisprflow_last_char_time
                        if elapsed >= WISPRFLOW_TYPING_TIMEOUT:
                            break
                    if time.monotonic() - timeout_start > 8:
                        break

                self._wisprflow_waiting = False

                if self._wisprflow_char_count > 0:
                    self._prompt_ready = False
                    await asyncio.sleep(0.05)
                    self.pty.write(b"\r")
                    await asyncio.sleep(1)
            else:
                text = await self.speech.listen_and_transcribe()
                if text:
                    self._prompt_ready = False
                    self.pty.write(text.encode())
                    await asyncio.sleep(0.05)
                    self.pty.write(b"\r")
                    await asyncio.sleep(1)

    async def _wait_and_speak_response(self) -> bool:
        """Wait for the Stop hook to fire, then speak the response.

        Returns True if a response was spoken.
        """
        # Poll until Stop hook writes the ready file
        while self._running and self.pty.is_running:
            if TTS_READY_FILE.exists():
                break
            await asyncio.sleep(0.2)

        if not self._running:
            return False

        text = ""
        try:
            await asyncio.sleep(0.1)  # Let hook finish writing
            if TTS_QUEUE_FILE.exists():
                text = TTS_QUEUE_FILE.read_text().strip()
                TTS_QUEUE_FILE.unlink(missing_ok=True)
            TTS_READY_FILE.unlink(missing_ok=True)
        except Exception:
            return False

        if not text:
            return False

        if len(text) > 500:
            text = text[:500]

        try:
            await self.tts.speak_and_wait(text)
            return True
        except Exception as e:
            print(f"\r\n[TTS ERROR: {e}]\r\n", end="", flush=True)
            return False

    def _on_pty_output(self, data: bytes) -> None:
        if not self._suppress_output:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        try:
            text = data.decode("utf-8", errors="replace")
            if '❯' in text:
                self._prompt_ready = True
        except:
            pass

    def _on_pty_exit(self, status: int) -> None:
        print(f"\nClaude Code exited with status {status}")
        self._running = False

    async def _shutdown(self) -> None:
        print("\nShutting down...")
        HOOKS_ACTIVE_FILE.unlink(missing_ok=True)
        for f in [TTS_QUEUE_FILE, TTS_READY_FILE]:
            f.unlink(missing_ok=True)
        if hasattr(self, 'wisprflow') and self.wisprflow:
            self.wisprflow.stop()
        if self.tts:
            await self.tts.stop()
        if self.pty:
            self.pty.stop()


def setup_signal_handlers(vc: VoiceClaude) -> None:
    def handler(sig, frame):
        vc._running = False
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


async def main() -> None:
    vc = VoiceClaude()
    setup_signal_handlers(vc)
    await vc.start()


if __name__ == "__main__":
    asyncio.run(main())
