"""Eleven Labs text-to-speech integration with streaming support."""

import asyncio
import numpy as np
import subprocess
import tempfile
import threading
from queue import Empty, Queue
from typing import Optional

import sounddevice as sd
from elevenlabs import ElevenLabs

from config import ELEVEN_API_KEY, ELEVEN_MODEL_ID, ELEVEN_VOICE_ID

# Streaming audio settings
STREAMING_SAMPLE_RATE = 24000  # ElevenLabs pcm_24000 format
STREAMING_CHANNELS = 1


class TTSEngine:
    """Text-to-speech engine using Eleven Labs with streaming support."""

    def __init__(self, use_streaming: bool = True):
        self.client = ElevenLabs(api_key=ELEVEN_API_KEY)
        self._queue: Queue[Optional[str]] = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._use_streaming = use_streaming
        self._stop_playback = False

    def start(self) -> None:
        """Start the TTS worker thread."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop the TTS worker thread."""
        self._running = False
        self._stop_playback = True
        self._queue.put(None)  # Signal to stop
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def speak(self, text: str) -> None:
        """Queue text to be spoken."""
        if text and self._running:
            self._queue.put(text)

    def _worker(self) -> None:
        """Worker thread that processes TTS queue."""
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break
                self._speak_sync(text)
            except Empty:
                continue
            except Exception as e:
                print(f"TTS error: {e}")

    def _speak_sync(self, text: str) -> None:
        """Synchronously generate and play speech."""
        self._stop_playback = False

        if self._use_streaming:
            try:
                self._speak_streaming(text)
                return
            except Exception as e:
                print(f"Streaming TTS failed, falling back: {e}")

        # Fallback to non-streaming
        self._speak_buffered(text)

    def _speak_streaming(self, text: str) -> None:
        """Stream speech with large prebuffer to avoid crackling."""
        import time

        audio_generator = self.client.text_to_speech.convert(
            voice_id=ELEVEN_VOICE_ID,
            text=text,
            model_id=ELEVEN_MODEL_ID,
            output_format="pcm_24000",
        )

        # Collect all audio first, then play with sd.play
        # This is the most reliable approach - ElevenLabs turbo_v2_5 is fast enough
        # that the download completes quickly, and sd.play never has buffer issues
        pcm_data = b""
        for chunk in audio_generator:
            if self._stop_playback:
                return
            pcm_data += chunk

        if not pcm_data:
            return

        audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio_array, samplerate=STREAMING_SAMPLE_RATE)
        sd.wait()

    def _speak_buffered(self, text: str) -> None:
        """Non-streaming fallback - buffer all audio then play."""
        try:
            audio_generator = self.client.text_to_speech.convert(
                voice_id=ELEVEN_VOICE_ID,
                text=text,
                model_id=ELEVEN_MODEL_ID,
            )
            audio_data = b"".join(audio_generator)
            self._play_audio(audio_data)
        except Exception as e:
            print(f"TTS generation error: {e}")

    def _play_audio(self, audio_data: bytes) -> None:
        """Play audio data through system speakers."""
        # Write to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            # Try afplay (macOS) first, then aplay (Linux)
            try:
                subprocess.run(
                    ["afplay", temp_path],
                    check=True,
                    capture_output=True,
                )
            except FileNotFoundError:
                # Try aplay for Linux
                subprocess.run(
                    ["aplay", temp_path],
                    check=True,
                    capture_output=True,
                )
        except subprocess.CalledProcessError as e:
            print(f"Audio playback error: {e}")
        except FileNotFoundError:
            print("No audio player found (tried afplay and aplay)")
        finally:
            # Clean up temp file
            import os

            try:
                os.unlink(temp_path)
            except OSError:
                pass

    def clear_queue(self) -> None:
        """Clear any pending speech."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

    def interrupt(self) -> None:
        """Stop current playback immediately."""
        self._stop_playback = True
        self.clear_queue()


class AsyncTTSEngine:
    """Async wrapper around TTSEngine for use with asyncio."""

    def __init__(self, use_streaming: bool = True):
        self._engine = TTSEngine(use_streaming=use_streaming)

    async def start(self) -> None:
        """Start the TTS engine."""
        self._engine.start()

    async def stop(self) -> None:
        """Stop the TTS engine."""
        self._engine.stop()

    async def speak(self, text: str) -> None:
        """Queue text to be spoken (non-blocking)."""
        self._engine.speak(text)

    async def speak_and_wait(self, text: str) -> None:
        """Speak text and wait for completion."""
        # Run in thread pool to not block
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._engine._speak_sync, text)

    def clear_queue(self) -> None:
        """Clear pending speech."""
        self._engine.clear_queue()

    def interrupt(self) -> None:
        """Stop current playback immediately."""
        self._engine.interrupt()

    async def beep(self) -> None:
        """Play a quick system beep to indicate listening."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._play_beep_sync)

    def _play_beep_sync(self) -> None:
        """Play system beep synchronously."""
        try:
            # Use macOS system sound for quick feedback
            subprocess.run(
                ["afplay", "/System/Library/Sounds/Tink.aiff"],
                capture_output=True,
                timeout=1,
            )
        except Exception:
            # Fallback: terminal bell
            print("\a", end="", flush=True)
