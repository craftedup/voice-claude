#!/usr/bin/env python3
"""Quick test for speech recognition."""

import sys
sys.path.insert(0, '.')

from speech_recognition import SpeechRecognizer

def main():
    print("Loading Whisper model...")
    recognizer = SpeechRecognizer()
    recognizer.load_model()

    print("\n--- Speech Recognition Test ---")
    print("Speak now! (Recording will stop after 1.5s of silence)")
    print("Press Ctrl+C to exit\n")

    while True:
        try:
            print("Listening...")
            text = recognizer.listen_and_transcribe_sync()

            if text:
                print(f"You said: {text}\n")
            else:
                print("(No speech detected)\n")

        except KeyboardInterrupt:
            print("\nExiting.")
            break

if __name__ == "__main__":
    main()
