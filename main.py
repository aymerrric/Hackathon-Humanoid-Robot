"""Chat with the Ultra X2 humanoid robot via natural language + voice.

ARCHITECTURE: Runs on your laptop with your microphone. Controls robot via ROS 2 when available.

PRIMARY USAGE:
  $ poetry run python main.py

This runs the voice agent on your laptop:
  - Listens to your laptop's microphone
  - Local Whisper for speech-to-text (no cloud, offline)
  - Claude LLM for analysis
  - Connects to robot's ROS 2 services (if ROS 2 installed)
  - Robot executes commands

MODES:
  - Default (no ROS 2): uses laptop mic, LLM works, robot motion unavailable
  - With ROS 2: laptop mic + robot control via ROS 2
  - DRY_RUN: poetry run python main.py --dry-run
    → simulated robot, no hardware needed

Examples (speak these):
  "stand up and walk forward one meter"
  "raise your right arm halfway"
  "what's your battery level?"

Type 'quit' or 'exit' to leave the voice loop.
"""

from __future__ import annotations

import logging
import sys
import os
import argparse

from ultra_x2 import UltraX2Robot, load_settings
from ultra_x2.config import Settings
from ultra_x2.llm import RobotAgent, make_client, list_personalities
from ultra_x2.diagnostics import diagnose
from ultra_x2.speech import Transcriber, speak, Recorder
from ultra_x2.exceptions import SpeechError

logger = logging.getLogger(__name__)


def cli_confirm(description: str) -> bool:
    answer = input(f"  ⚠️  allow physical action {description}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # CLI: allow opting into dry-run mode. By default the app runs against
    # live hardware unless --dry-run is provided.
    parser = argparse.ArgumentParser(description="Ultra X2 interactive agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run in dry-run mode (simulate hardware).")
    parser.add_argument("--personality", type=str, choices=list_personalities(),
                        default=None,
                        help=f"Robot personality ({', '.join(list_personalities())}). Default: friendly")
    args = parser.parse_args()

    # If requested via CLI, force the DRY_RUN env var so load_settings() picks it up.
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    settings = load_settings()

    if settings.anthropic_api_key is None:
        print("Set ANTHROPIC_API_KEY (see .env.example).", file=sys.stderr)
        return 1

    # Run diagnostics: check API key, SSH connectivity (if not dry-run), etc.
    all_ok, diag_msg = diagnose(settings)
    print(diag_msg)
    if not all_ok:
        print("❌ Diagnostics failed. Cannot proceed.", file=sys.stderr)
        return 1

    banner = "DRY_RUN" if settings.dry_run else "LIVE HARDWARE"
    personality = args.personality or settings.personality
    print(f"Ultra X2 agent [{banner}] — model {settings.llm_model}, personality {personality}.")
    print(f"Available commands: 'quit' to exit, '/personality <name>' to switch personalities.\n")

    client = make_client(settings)
    with UltraX2Robot(settings) as robot:
        agent = RobotAgent(client, robot, settings, confirmer=cli_confirm, personality=args.personality)

        # If live hardware (not DRY_RUN), use the robot's microphone; otherwise, text input
        if settings.dry_run:
            return _run_text_loop(agent, list_personalities())
        else:
            return _run_voice_loop(agent, settings, list_personalities())


def _run_text_loop(agent: RobotAgent, personalities: list[str]) -> int:
    """Text-based chat loop (DRY_RUN or when not on robot)."""
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.lower() in {"quit", "exit", "stop"}:
            break
        if not user:
            continue

        # Handle personality command
        if user.startswith("/personality "):
            pers_name = user.split(" ", 1)[1].strip()
            if pers_name in personalities:
                agent.set_personality(pers_name)
                print(f"x2 > Personality switched to: {pers_name}\n")
            else:
                print(f"x2 > Unknown personality. Available: {', '.join(personalities)}\n")
            continue

        reply = agent.send(user)
        print(f"x2 > {reply}\n")
    return 0


def _run_voice_loop(agent: RobotAgent, settings: Settings, personalities: list[str]) -> int:
    """Voice-based loop using your laptop's microphone."""
    transcriber = Transcriber(
        model_size=settings.stt_model,
        language=settings.stt_language,
        compute_type=settings.stt_compute_type,
    )

    # Use laptop microphone for voice input
    print("\n🎤 Using your laptop's microphone for voice input.")
    print("   (Robot control via ROS 2 when available)")
    mic = Recorder()

    print("Say 'quit' / 'exit' / 'stop' to leave the loop.\n")

    while True:
        try:
            print("🎤 listening…")
            try:
                audio = mic.listen()
            except SpeechError as exc:
                logger.error("Microphone error: %s", exc)
                print(f"❌ {exc}\n")
                continue

            text = transcriber.transcribe(audio)
            if not text:
                print("…(didn't catch that)")
                continue
            print(f"you (heard)> {text}")

            # Handle personality command
            if text.startswith("/personality "):
                pers_name = text.split(" ", 1)[1].strip()
                if pers_name in personalities:
                    agent.set_personality(pers_name)
                    print(f"x2 > Personality switched to: {pers_name}\n")
                else:
                    print(f"x2 > Unknown personality. Available: {', '.join(personalities)}\n")
                continue

            reply = agent.send(text)
            print(f"x2 > {reply}\n")
            if settings.speak_replies:
                speak(reply)

            # "stop" halts motion but keeps listening
            if text.lower().strip(".!? ") == "stop":
                print("x2 > Stopping motion immediately.\n")
                agent.send("stop")  # Call the robot's stop tool
                continue  # Keep listening, don't exit

            # Check for exit phrases (exit the loop, not just stop motion)
            if text.lower().strip(".!? ") in {"quit", "exit", "stop listening", "bye", "goodbye"}:
                break
        except SpeechError as exc:
            logger.error("Speech error: %s", exc)
            print(f"❌ {exc}\n")
            continue
        except (EOFError, KeyboardInterrupt):
            print()
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
