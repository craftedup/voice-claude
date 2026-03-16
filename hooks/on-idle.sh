#!/bin/bash
# Hook: Signal voice-claude that Claude is idle and waiting for input.
# This triggers the STT listener in the daemon.

SIGNAL_FILE="/tmp/voice-claude-hooks-active"

# Only run if voice-claude daemon has activated hooks
if [ ! -f "$SIGNAL_FILE" ]; then
    exit 0
fi

# Signal the daemon to start listening for voice input
touch /tmp/voice-claude-stt-trigger
