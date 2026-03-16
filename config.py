"""Configuration for Voice Claude interface."""

import os
from dotenv import load_dotenv

load_dotenv()

# Claude Code command
CLAUDE_CODE_CMD = ["claude"]

# Eleven Labs settings
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY", "")
ELEVEN_VOICE_ID = os.environ.get("ELEVEN_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Default: Sarah
ELEVEN_MODEL_ID = "eleven_turbo_v2_5"

# STT mode: "whisper" (local faster-whisper) or "wisprflow" (WisprFlow app)
STT_MODE = os.environ.get("STT_MODE", "wisprflow")

# WisprFlow settings
WISPRFLOW_TYPING_TIMEOUT = 0.75  # Seconds of no typing before auto-submitting
WISPRFLOW_MAX_LISTEN_SECONDS = 10  # Seconds to hold Option key for WisprFlow

# Local Whisper settings (only used when STT_MODE=whisper)
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.5
MAX_RECORDING_SECONDS = 30
