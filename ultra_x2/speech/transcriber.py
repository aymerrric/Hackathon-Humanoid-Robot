"""Speech-to-text via faster-whisper.

This is the single seam between the app and the Whisper backend. Keeping it
isolated means we can swap faster-whisper for the OpenAI API (or the robot's
on-board ASR) without touching the voice loop.

The model is loaded lazily on first use so importing this module stays cheap and
so a missing optional dependency surfaces as a clear SpeechError, not an
ImportError at startup.
"""

from __future__ import annotations

import logging
from typing import Any

from ultra_x2.exceptions import SpeechError

logger = logging.getLogger(__name__)
import os
# faster-whisper expects mono float32 PCM at 16 kHz.
SAMPLE_RATE = 16000


class Transcriber:
    def __init__(
        self,
        model_size: str = "base",
        language: str | None = None,
        compute_type: str = "int8",
    ) -> None:
        self._model_size = model_size
        self._language = language
        self._compute_type = compute_type
        self._model: Any = None  # loaded on first transcribe()

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechError(
                "faster-whisper is not installed. Install the voice extra: "
                "`poetry install --extras voice` (or `pip install faster-whisper`)."
            ) from exc
        logger.info(
            "Loading Whisper model %r (compute_type=%s)…",
            self._model_size, self._compute_type,
        )
        # CPU by default; CTranslate2 picks int8 for a small, fast footprint.
        self._model = WhisperModel(self._model_size, compute_type=self._compute_type)
        return self._model

    def transcribe(self, audio: Any) -> str:
        """Transcribe audio to text.

        `audio` may be a path to an audio file (str) or a mono float32 numpy
        array sampled at SAMPLE_RATE (what Recorder.listen returns).
        Returns the recognized text, stripped (empty string if nothing heard).
        """
        model = self._ensure_model()
        try:
            segments, _info = model.transcribe(audio, language=self._language)
            return " ".join(seg.text for seg in segments).strip()
        except Exception as exc:  # noqa: BLE001 — normalize backend errors
            raise SpeechError(f"Transcription failed: {exc}") from exc
