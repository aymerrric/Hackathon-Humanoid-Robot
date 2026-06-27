"""Environment-driven settings for the robot and the LLM layer."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # LLM
    anthropic_api_key: str | None
    llm_model: str

    # Robot
    robot_host: str
    robot_port: int
    robot_api_key: str | None

    # Safety
    dry_run: bool
    require_confirmation: bool


def load_settings() -> Settings:
    """Load settings from the environment (and a local .env file if present)."""
    load_dotenv()
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "claude-opus-4-8"),
        robot_host=os.getenv("ULTRA_X2_HOST", "127.0.0.1"),
        robot_port=int(os.getenv("ULTRA_X2_PORT", "8080")),
        robot_api_key=os.getenv("ULTRA_X2_API_KEY"),
        dry_run=_as_bool(os.getenv("DRY_RUN"), default=True),
        require_confirmation=_as_bool(os.getenv("REQUIRE_CONFIRMATION"), default=True),
    )
