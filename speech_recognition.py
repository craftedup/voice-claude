"""Local speech recognition using faster-whisper.

Handles microphone recording with silence detection and local Whisper transcription.
"""

import asyncio
import numpy as np
import sounddevice as sd
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from faster_whisper import WhisperModel

from config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    SILENCE_THRESHOLD,
    SILENCE_DURATION,
    MAX_RECORDING_SECONDS,
    SAMPLE_RATE,
)


class SpeechRecognizer:
    """Local speech-to-text using faster-whisper."""

    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._recording = False

    def load_model(self) -> None:
        """Load the Whisper model. Call this once at startup."""
        print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
        self._model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("Whisper model loaded.")

    async def load_model_async(self) -> None:
        """Load the Whisper model asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self.load_model)

    def _record_audio(self) -> Optional[np.ndarray]:
        """Record audio from microphone until silence is detected.

        Returns numpy array of audio samples, or None if no speech detected.
        """
        self._recording = True
        audio_chunks = []
        silence_samples = 0
        speech_detected = False
        silence_samples_needed = int(SILENCE_DURATION * SAMPLE_RATE)
        min_recording_samples = int(SAMPLE_RATE * 1.0)  # At least 1 second
        max_samples = int(MAX_RECORDING_SECONDS * SAMPLE_RATE)
        total_samples = 0

        # Use a small chunk size for responsive silence detection
        chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks

        def audio_callback(indata, frames, time, status):
            nonlocal silence_samples, total_samples, speech_detected
            if status:
                print(f"Audio status: {status}")

            audio_chunks.append(indata.copy())
            total_samples += frames

            # Check for silence
            volume = np.sqrt(np.mean(indata ** 2))
            if volume < SILENCE_THRESHOLD:
                silence_samples += frames
            else:
                silence_samples = 0
                speech_detected = True  # We heard something!

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                blocksize=chunk_size,
                callback=audio_callback,
            ):
                # Wait for either silence or max duration
                while self._recording:
                    sd.sleep(50)  # Check every 50ms

                    # Only stop for silence if we've heard speech AND recorded enough
                    if (speech_detected and
                        silence_samples >= silence_samples_needed and
                        total_samples > min_recording_samples):
                        break

                    # Stop if we've hit max duration
                    if total_samples >= max_samples:
                        break

        except Exception as e:
            print(f"Recording error: {e}")
            return None
        finally:
            self._recording = False

        if not audio_chunks:
            return None

        # Concatenate all chunks
        audio = np.concatenate(audio_chunks, axis=0)

        # Trim trailing silence
        if silence_samples > 0 and silence_samples < len(audio):
            audio = audio[:-silence_samples]

        # Check if we got any meaningful audio
        if len(audio) < SAMPLE_RATE * 0.5:  # Less than 0.5 seconds
            return None

        return audio

    def _transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio array to text."""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Write to temp WAV file (faster-whisper needs a file)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            with wave.open(f.name, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(SAMPLE_RATE)
                # Convert float32 to int16
                audio_int16 = (audio * 32767).astype(np.int16)
                wav.writeframes(audio_int16.tobytes())

            # Transcribe
            segments, info = self._model.transcribe(
                f.name,
                language="en",
                vad_filter=True,  # Filter out non-speech
            )

            # Collect all segments
            text = " ".join(segment.text.strip() for segment in segments)
            return text.strip()

    def listen_and_transcribe_sync(self) -> Optional[str]:
        """Record from microphone and transcribe. Blocking call.

        Returns transcribed text, or None if no speech detected.
        """
        audio = self._record_audio()
        if audio is None:
            return None

        return self._transcribe(audio)

    async def listen_and_transcribe(self) -> Optional[str]:
        """Record from microphone and transcribe. Async version.

        Returns transcribed text, or None if no speech detected.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.listen_and_transcribe_sync
        )

    def stop_recording(self) -> None:
        """Stop any ongoing recording."""
        self._recording = False


# Convenience function for simple usage
_recognizer: Optional[SpeechRecognizer] = None


async def get_recognizer() -> SpeechRecognizer:
    """Get or create the global speech recognizer."""
    global _recognizer
    if _recognizer is None:
        _recognizer = SpeechRecognizer()
        await _recognizer.load_model_async()
    return _recognizer


async def listen_for_speech() -> Optional[str]:
    """Listen for speech and return transcribed text.

    Returns None if no speech was detected.
    """
    recognizer = await get_recognizer()
    return await recognizer.listen_and_transcribe()
