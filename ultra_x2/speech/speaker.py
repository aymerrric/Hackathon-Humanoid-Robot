"""Spoken answer-back for local testing.

Uses the macOS `say` command if available — zero dependencies, good enough to
hear the agent reply. On the robot this is where you'd call the PlayTts service
instead (see agibot-x2-sdk-main/USAGE_GUIDE.md).
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def speak(text: str) -> None:
    """Say `text` out loud via macOS `say`; no-op (logged) if unavailable."""
    if not text:
        return
    say = shutil.which("say")
    if say is None:
        logger.debug("`say` not available; skipping spoken reply.")
        return
    try:
        subprocess.run([say, text], check=False)
    except Exception as exc:  # noqa: BLE001 — speaking is best-effort
        logger.warning("Failed to speak reply: %s", exc)
