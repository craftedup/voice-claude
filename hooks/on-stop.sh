#!/bin/bash
# Hook: Speak Claude's response via TTS when it finishes responding.
# Receives JSON on stdin with last_assistant_message.
# Only activates when the voice-claude daemon signals it should.

VOICE_CLAUDE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SIGNAL_FILE="/tmp/voice-claude-hooks-active"

# Only run if voice-claude daemon has activated hooks
if [ ! -f "$SIGNAL_FILE" ]; then
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)

# Extract the assistant message from JSON
MESSAGE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
msg = data.get('last_assistant_message', '')
if msg:
    # Truncate very long messages for TTS
    if len(msg) > 2000:
        msg = msg[:2000] + '... message truncated.'
    print(msg)
" 2>/dev/null)

if [ -z "$MESSAGE" ]; then
    exit 0
fi

# Write message to a file for the voice-claude daemon to pick up and speak
echo "$MESSAGE" > /tmp/voice-claude-tts-queue

# Signal the daemon that there's something to speak
touch /tmp/voice-claude-tts-ready
