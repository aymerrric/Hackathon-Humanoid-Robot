"""Demo entry point: chat with the Ultra X2 in natural language.

Runs in DRY_RUN mode by default (no hardware required). Type instructions like:
    "stand up and walk forward one meter"
    "raise your right arm halfway"
    "what's your battery level?"
Type 'quit' to exit.
"""

from __future__ import annotations

import logging
import sys

from ultra_x2 import UltraX2Robot, load_settings
from ultra_x2.llm import RobotAgent, make_client


def cli_confirm(description: str) -> bool:
    answer = input(f"  ⚠️  allow physical action {description}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()

    if settings.anthropic_api_key is None:
        print("Set ANTHROPIC_API_KEY (see .env.example).", file=sys.stderr)
        return 1

    banner = "DRY_RUN" if settings.dry_run else "LIVE HARDWARE"
    print(f"Ultra X2 agent [{banner}] — model {settings.llm_model}. Type 'quit' to exit.\n")

    client = make_client(settings)
    with UltraX2Robot(settings) as robot:
        agent = RobotAgent(client, robot, settings, confirmer=cli_confirm)
        while True:
            try:
                user = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if user.lower() in {"quit", "exit"}:
                break
            if not user:
                continue
            reply = agent.send(user)
            print(f"x2 > {reply}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
