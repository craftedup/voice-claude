"""Optimized speech-to-text using faster-whisper with Silero VAD.

Uses Silero VAD for reliable speech endpoint detection (works with any
mic level including quiet AirPods), and keeps the Whisper model loaded
as a singleton for fast repeat calls.
"""

import asyncio
import numpy as np
import sounddevice as sd
import tempfile
import wave
import torch
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from faster_whisper import WhisperModel

from config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    SAMPLE_RATE,
    SILENCE_DURATION,
    MAX_RECORDING_SECONDS,
)


# Singleton model and VAD
_model: Optional[WhisperModel] = None
_vad_model = None
_vad_utils = None


def _load_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("Whisper model loaded.")
    return _model


def _load_vad():
    global _vad_model, _vad_utils
    if _vad_model is None:
        _vad_model, _vad_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            trust_repo=True,
        )
    return _vad_model, _vad_utils


class StreamingSpeechRecognizer:
    """Speech-to-text with Silero VAD endpoint detection."""

    def __init__(self):
        self._recording = False
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def listen_and_transcribe(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        loop = asyncio.get_running_loop()
        model = await loop.run_in_executor(self._executor, _load_model)
        await loop.run_in_executor(self._executor, _load_vad)

        self._recording = True
        audio = await loop.run_in_executor(self._executor, self._record_audio)

        if audio is None:
            return None

        text = await loop.run_in_executor(
            self._executor,
            lambda: self._transcribe(model, audio),
        )
        return text if text else None

    def _record_audio(self) -> Optional[np.ndarray]:
        """Record audio using Silero VAD for endpoint detection.

        Silero VAD is a neural network that detects speech vs non-speech
        regardless of absolute volume levels — works perfectly with quiet
        AirPods mics where RMS-based detection fails.
        """
        self._recording = True
        audio_chunks = []
        total_samples = 0
        max_samples = int(MAX_RECORDING_SECONDS * SAMPLE_RATE)

        # VAD state
        vad_model, _ = _load_vad()
        vad_model.reset_states()
        speech_detected = False
        silence_after_speech_samples = 0
        silence_needed = int(SILENCE_DURATION * SAMPLE_RATE)

        # Silero VAD needs 512 samples at 16kHz
        vad_chunk_size = 512
        vad_buffer = np.array([], dtype=np.float32)

        # sounddevice chunk size — 100ms
        sd_chunk_size = int(SAMPLE_RATE * 0.1)

        def audio_callback(indata, frames, time, status):
            nonlocal speech_detected, silence_after_speech_samples
            nonlocal total_samples, vad_buffer

            audio_chunks.append(indata.copy())
            total_samples += frames

            # Accumulate samples for VAD processing
            vad_buffer = np.append(vad_buffer, indata[:, 0])

            # Process all complete 512-sample chunks
            while len(vad_buffer) >= vad_chunk_size:
                chunk = vad_buffer[:vad_chunk_size]
                vad_buffer = vad_buffer[vad_chunk_size:]

                tensor = torch.from_numpy(chunk)
                speech_prob = vad_model(tensor, SAMPLE_RATE).item()

                if speech_prob > 0.15:
                    speech_detected = True
                    silence_after_speech_samples = 0
                elif speech_detected:
                    silence_after_speech_samples += vad_chunk_size

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                blocksize=sd_chunk_size,
                callback=audio_callback,
            ):
                while self._recording:
                    sd.sleep(50)

                    # Stop after silence following speech
                    if (speech_detected and
                        silence_after_speech_samples >= silence_needed):
                        break

                    if total_samples >= max_samples:
                        break

        except Exception as e:
            print(f"Recording error: {e}")
            return None
        finally:
            self._recording = False

        if not audio_chunks:
            return None

        audio = np.concatenate(audio_chunks, axis=0)

        # Trim trailing silence
        if speech_detected and silence_after_speech_samples > 0:
            trim = min(silence_after_speech_samples, len(audio) - SAMPLE_RATE)
            if trim > 0:
                audio = audio[:-trim]

        if len(audio) < SAMPLE_RATE * 0.3:
            return None

        return audio

    def _transcribe(self, model: WhisperModel, audio: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            with wave.open(f.name, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                audio_int16 = (audio * 32767).astype(np.int16)
                wav.writeframes(audio_int16.tobytes())

            segments, info = model.transcribe(
                f.name,
                language="en",
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments)
            return text.strip()

    def stop_recording(self) -> None:
        self._recording = False


_recognizer: Optional[StreamingSpeechRecognizer] = None


async def get_recognizer() -> StreamingSpeechRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = StreamingSpeechRecognizer()
    return _recognizer


async def listen_for_speech(
    on_partial: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    recognizer = await get_recognizer()
    return await recognizer.listen_and_transcribe(on_partial=on_partial)
