"""Anthropic client factory.

Kept separate so the client can be constructed once and injected, and so test
code can swap in a fake.
"""

from __future__ import annotations

import anthropic

from ultra_x2.config import Settings


def make_client(settings: Settings) -> anthropic.Anthropic:
    """Build an Anthropic client.

    With no api_key the SDK falls back to the ANTHROPIC_API_KEY env var or an
    `ant auth login` profile — but we pass it explicitly from settings so the
    source is unambiguous.
    """
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)
