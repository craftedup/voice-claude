"""Claude API interpreter for bidirectional speech/CLI translation."""

from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY, INTERPRETER_MODEL, MAX_CONTEXT_CHARS


class Interpreter:
    """Uses Claude API to interpret CLI output and user speech."""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=10.0,  # 10 second timeout
        )

    def output_to_speech(self, output: str, output_type: str) -> str:
        """Convert CLI output to conversational speech for TTS.

        Args:
            output: The raw CLI output text
            output_type: Type of output (permission, question, completion, error)

        Returns:
            Natural speech text to be spoken aloud
        """
        # Truncate if too long
        if len(output) > MAX_CONTEXT_CHARS:
            output = output[-MAX_CONTEXT_CHARS:]

        # Check if this contains numbered options
        has_options = self._detect_numbered_options(output)

        prompt = f"""You are helping a user interact with Claude Code (a CLI coding assistant) via voice.

Convert the following CLI output into brief, conversational speech. The user will hear this spoken aloud.

Rules:
- Be concise but clear
- Use natural conversational language
- For permission prompts, clearly state what permission is being requested
- For questions, rephrase as a clear question
- For completions, summarize what was done
- For errors, explain the issue simply
- Never include code syntax, file paths longer than a few words, or technical jargon
- Don't say "Claude" - just describe what's happening
{"- IMPORTANT: This output contains NUMBERED OPTIONS. Read out each option clearly with its number, like: 'Choose an option: one, do X; two, do Y; or three, something else.' The user will respond by saying the number." if has_options else ""}

Output type: {output_type}

CLI Output:
{output}

Conversational speech{" (include all numbered options)" if has_options else " (short and natural)"}:"""

        response = self.client.messages.create(
            model=INTERPRETER_MODEL,
            max_tokens=250 if has_options else 150,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    def _detect_numbered_options(self, output: str) -> bool:
        """Detect if output contains numbered options like '1. X  2. Y'."""
        import re
        # Look for patterns like "1." or "1)" followed by text
        # Need at least 2 numbered items to be a selection
        pattern = r'(?:^|\s)(\d+)[.\)]\s*\w+'
        matches = re.findall(pattern, output)
        if len(matches) >= 2:
            # Check if numbers are sequential (1, 2, 3...)
            numbers = [int(m) for m in matches]
            return 1 in numbers and 2 in numbers
        return False

    def speech_to_input(
        self, speech: str, context: str, awaiting_type: str
    ) -> Optional[str]:
        """Convert user speech to CLI input.

        Args:
            speech: The transcribed user speech
            context: Recent CLI output for context
            awaiting_type: What type of input is expected (permission, question, etc.)

        Returns:
            The CLI input to send, or None if unclear
        """
        # Quick handling for common number words (skip API call)
        quick_result = self._quick_number_match(speech)
        if quick_result is not None:
            return quick_result

        # Truncate context if too long
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[-MAX_CONTEXT_CHARS:]

        prompt = f"""You are helping a user interact with Claude Code (a CLI coding assistant) via voice.

The user spoke a response that needs to be converted to CLI input.

Context (recent CLI output):
{context}

Input type expected: {awaiting_type}

User said: "{speech}"

Convert this to the appropriate CLI input. Rules:
- For numbered options (1. X, 2. Y, etc.): respond with JUST the number
  - "one", "first", "option one", "the first one" → 1
  - "two", "second", "option two" → 2
  - "three", "third" → 3
  - "four", "fourth" → 4
  - "other", "something else", "custom" → the "Other" option number if present
- For yes/no prompts: respond with just "y" or "n"
- For questions: provide a clear, typed response
- For general input: convert to appropriate text
- Keep responses minimal and direct
- If the user's intent is unclear, respond with "?" to ask for clarification

Return ONLY the CLI input to send (no quotes, no explanation):"""

        response = self.client.messages.create(
            model=INTERPRETER_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text.strip()

        # Clean up common issues
        result = result.strip('"\'')

        return result if result else None

    def _quick_number_match(self, speech: str) -> Optional[str]:
        """Quick local matching for number selections without API call."""
        speech_lower = speech.lower().strip()

        # Direct number words
        number_words = {
            "one": "1", "1": "1", "first": "1", "option one": "1", "the first": "1", "the first one": "1",
            "two": "2", "2": "2", "second": "2", "option two": "2", "the second": "2", "the second one": "2",
            "three": "3", "3": "3", "third": "3", "option three": "3", "the third": "3", "the third one": "3",
            "four": "4", "4": "4", "fourth": "4", "option four": "4", "the fourth": "4", "the fourth one": "4",
            "five": "5", "5": "5", "fifth": "5", "option five": "5",
            "six": "6", "6": "6", "sixth": "6",
            "seven": "7", "7": "7", "seventh": "7",
            "eight": "8", "8": "8", "eighth": "8",
            "nine": "9", "9": "9", "ninth": "9",
        }

        # Yes/no quick matches
        yes_words = {"yes", "yeah", "yep", "sure", "okay", "ok", "affirmative", "correct", "y"}
        no_words = {"no", "nope", "nah", "negative", "n", "don't", "cancel"}

        if speech_lower in number_words:
            return number_words[speech_lower]

        if speech_lower in yes_words:
            return "y"

        if speech_lower in no_words:
            return "n"

        return None

    def should_speak(self, output: str, output_type: str) -> bool:
        """Determine if this output warrants speaking.

        Some outputs are transitional and don't need voice feedback.

        Args:
            output: The CLI output
            output_type: Type of output

        Returns:
            True if this should be spoken aloud
        """
        # Always speak permission prompts and questions
        if output_type in ["permission", "question"]:
            return True

        # Don't speak very short outputs
        if len(output.strip()) < 20:
            return False

        # Don't speak if it's just progress indicators
        progress_indicators = ["...", "Loading", "Reading", "Searching"]
        if any(ind in output for ind in progress_indicators):
            return False

        # Speak errors and completions
        if output_type in ["error", "completion"]:
            return True

        return False
