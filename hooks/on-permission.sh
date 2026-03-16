#!/bin/bash
# Hook: Signal voice-claude that Claude needs permission approval.

SIGNAL_FILE="/tmp/voice-claude-hooks-active"

# Only run if voice-claude daemon has activated hooks
if [ ! -f "$SIGNAL_FILE" ]; then
    exit 0
fi

# Read hook input from stdin
INPUT=$(cat)

# Write the permission request details for the daemon
echo "$INPUT" > /tmp/voice-claude-permission-queue
touch /tmp/voice-claude-permission-ready
