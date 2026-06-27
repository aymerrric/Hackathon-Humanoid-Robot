"""Voice entry point: talk to the Ultra X2 with your computer's microphone.

Pipeline:
    mic → Whisper (speech-to-text) → RobotAgent (LLM + tools) → spoken reply

The LLM analysis + command execution + answer all live in RobotAgent already;
this module only adds the speech front-end. Runs in DRY_RUN by default, so no
hardware is needed to try it.

    poetry run ultra-x2-voice                 # live microphone loop
    poetry run ultra-x2-voice path/to/clip.wav  # transcribe one file and exit

Say "quit" / "exit" / "stop listening" to leave the loop, or press Ctrl+C.
"""

from __future__ import annotations

import logging
import sys

from ultra_x2 import UltraX2Robot, load_settings
from ultra_x2.exceptions import SpeechError
from ultra_x2.llm import RobotAgent, make_client
from ultra_x2.speech import Recorder, Transcriber, speak

logger = logging.getLogger(__name__)

EXIT_PHRASES = {"quit", "exit", "stop listening", "goodbye", "bye"}


def cli_confirm(description: str) -> bool:
    answer = input(f"  ⚠️  allow physical action {description}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()

    if settings.anthropic_api_key is None:
        print("Set ANTHROPIC_API_KEY (see .env.example).", file=sys.stderr)
        return 1

    transcriber = Transcriber(
        model_size=settings.stt_model,
        language=settings.stt_language,
        compute_type=settings.stt_compute_type,
    )

    # Optional one-shot file mode: `ultra-x2-voice clip.wav`
    wav_path = sys.argv[1] if len(sys.argv) > 1 else None

    client = make_client(settings)
    with UltraX2Robot(settings) as robot:
        agent = RobotAgent(client, robot, settings, confirmer=cli_confirm)

        if wav_path is not None:
            return _run_once(transcriber, agent, settings, wav_path)

        return _run_loop(transcriber, agent, settings)


def _handle(transcriber, agent, settings, audio_or_path) -> str | None:
    """Transcribe, run the agent, speak the reply. Returns the heard text."""
    text = transcriber.transcribe(audio_or_path)
    if not text:
        print("…(didn't catch that)")
        return None
    print(f"you (heard)> {text}")

    reply = agent.send(text)
    print(f"x2 > {reply}\n")
    if settings.speak_replies:
        speak(reply)
    return text


def _run_once(transcriber, agent, settings, wav_path: str) -> int:
    try:
        _handle(transcriber, agent, settings, wav_path)
    except SpeechError as exc:
        print(f"Speech error : {exc}", file=sys.stderr)
        return 1
    return 0


def _run_loop(transcriber, agent, settings) -> int:
    banner = "DRY_RUN" if settings.dry_run else "LIVE HARDWARE"
    print(
        f"Ultra X2 voice [{banner}] — Whisper '{settings.stt_model}', "
        f"model {settings.llm_model}.\nSay 'quit' to exit.\n"
    )
    recorder = Recorder()
    while True:
        try:
            print("🎤 listening… (speak, then pause)")
            audio = recorder.listen()
            text = _handle(transcriber, agent, settings, audio)
        except SpeechError as exc:
            print(f"Speech error: {exc}", file=sys.stderr)
            continue
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text and text.lower().strip(".!? ") in EXIT_PHRASES:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
