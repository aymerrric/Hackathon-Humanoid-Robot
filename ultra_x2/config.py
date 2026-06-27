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
    robot_user: str
    robot_password: str | None
    robot_ssh_port: int
    robot_ssh_timeout_s: int

    # Safety
    dry_run: bool
    require_confirmation: bool

    # Speech (voice input + spoken replies)
    stt_model: str  # faster-whisper model size: tiny|base|small|medium|large-v3
    stt_language: str | None  # ISO code e.g. "en"/"fr"; None = auto-detect
    stt_compute_type: str  # faster-whisper compute type: int8|int8_float16|float16|float32
    speak_replies: bool  # speak the agent's answer out loud (macOS `say` locally)

    # Agent personality
    personality: str  # robot speaking style: professional|friendly|curious|energetic|minimalist


def load_settings() -> Settings:
    """Load settings from the environment (and a local .env file if present)."""
    load_dotenv()
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "claude-opus-4-8"),
        robot_host=os.getenv("ULTRA_X2_HOST", "127.0.0.1"),
        robot_port=int(os.getenv("ULTRA_X2_PORT", "8080")),
        robot_api_key=os.getenv("ULTRA_X2_API_KEY"),
        robot_user=os.getenv("ULTRA_X2_USER", "agi"),
        robot_password=os.getenv("ULTRA_X2_PASSWORD", "1"),
        robot_ssh_port=int(os.getenv("ULTRA_X2_SSH_PORT", "22")),
        robot_ssh_timeout_s=int(os.getenv("ULTRA_X2_SSH_TIMEOUT_S", "8")),
        # Default to live hardware unless explicitly enabled via env/CLI.
        dry_run=_as_bool(os.getenv("DRY_RUN"), default=False),
        require_confirmation=_as_bool(os.getenv("REQUIRE_CONFIRMATION"), default=True),
        stt_model=os.getenv("STT_MODEL", "base"),
        stt_language=os.getenv("STT_LANGUAGE") or None,
        stt_compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
        speak_replies=_as_bool(os.getenv("SPEAK_REPLIES"), default=True),
        personality=os.getenv("ROBOT_PERSONALITY", "friendly"),
    )
