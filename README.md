# Voice Claude

Hands-free voice interface for Claude Code. Speak your requests, hear the responses — no keyboard needed.

Uses [Wispr Flow](https://wispr.com) for speech-to-text and [ElevenLabs](https://elevenlabs.io) for text-to-speech, wired together through Claude Code's hook system.

## How It Works

1. Claude Code starts in a PTY (you see the normal terminal UI)
2. When Claude is ready for input, a beep plays and Wispr Flow activates automatically
3. You speak — Wispr Flow transcribes and types your words into the prompt
4. After you stop speaking, the input is auto-submitted
5. When Claude finishes responding, the Stop hook captures the response text
6. ElevenLabs speaks the response back to you
7. Loop back to step 2

## Prerequisites

- **macOS** (uses CoreGraphics for key simulation)
- **[Claude Code](https://claude.ai/claude-code)** installed and authenticated (`claude` CLI)
- **[Wispr Flow](https://wispr.com)** installed, running, with Option key as the push-to-talk hotkey
- **[ElevenLabs](https://elevenlabs.io) API key** for text-to-speech
- **Python 3.10+**
- **Accessibility permission** granted to your terminal app (System Settings > Privacy & Security > Accessibility)

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url> voice-claude
cd voice-claude
python3 -m venv venv
source venv/bin/activate
pip install anthropic elevenlabs sounddevice numpy pyobjc-framework-Quartz
```

### 2. Set environment variables

```bash
export ELEVEN_API_KEY="your-elevenlabs-api-key"
# Optional: customize the voice
export ELEVEN_VOICE_ID="EXAVITQu4vr4xnSDxMaL"  # Default: Sarah
```

### 3. Configure Wispr Flow

Open Wispr Flow settings and set the activation hotkey to **Option** (push-to-talk mode). This is key code 58, which Voice Claude simulates via CoreGraphics events.

### 4. Configure Claude Code hooks

Add the following to `~/.claude/settings.json` (merge with any existing hooks):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/voice-claude/hooks/on-stop.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/voice-claude` with the actual path where you cloned the repo.

The `on-stop.sh` hook fires when Claude finishes responding. It extracts the assistant's message from the hook JSON and writes it to a temp file that Voice Claude reads and speaks.

### 5. Make hook scripts executable

```bash
chmod +x hooks/on-stop.sh hooks/on-idle.sh hooks/on-permission.sh
```

### 6. Grant Accessibility permission

Your terminal app (Terminal, iTerm2, etc.) must have Accessibility permission for CGEvent key simulation to work. Go to:

**System Settings > Privacy & Security > Accessibility** and add your terminal app.

## Running

```bash
./run.sh
```

Or manually:

```bash
source venv/bin/activate
python main.py
```

You'll hear "Ready" when everything is loaded. A beep means it's listening.

## Configuration

Edit `config.py` or set environment variables:

| Setting | Default | Description |
|---------|---------|-------------|
| `STT_MODE` | `wisprflow` | Speech-to-text mode (`wisprflow` or `whisper`) |
| `ELEVEN_API_KEY` | - | ElevenLabs API key (required) |
| `ELEVEN_VOICE_ID` | `EXAVITQu4vr4xnSDxMaL` | ElevenLabs voice (Sarah) |
| `WISPRFLOW_MAX_LISTEN_SECONDS` | `10` | How long to hold Option key per utterance |
| `WISPRFLOW_TYPING_TIMEOUT` | `0.75` | Seconds of no typing before auto-submit |

## Troubleshooting

**Wispr Flow doesn't activate**: Check that your terminal has Accessibility permission and that Wispr Flow's hotkey is set to Option.

**No speech output**: Verify your `ELEVEN_API_KEY` is valid. Check that the Stop hook is configured in `~/.claude/settings.json` and the hook script path is correct.

**Garbled terminal display**: This can happen when Wispr Flow types while Claude Code refreshes its UI. The display suppression should handle most of this, but occasional visual glitches are cosmetic only.

**Listening triggers while Claude is working**: The system waits for Claude's Stop hook before re-listening. If this happens, check that `on-stop.sh` is executable and the hook is correctly configured.
