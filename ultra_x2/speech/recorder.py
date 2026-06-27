"""Microphone capture with simple silence-based segmentation.

Records one utterance at a time from the default input device: it waits for
speech to start, then stops automatically after a short trailing silence — so
you just talk and it figures out when you're done.

This is the *local-testing* audio source. On the robot you'd replace this with a
subscriber to `/agent/process_audio_output`, which already does VAD on-device;
the rest of the voice loop stays identical because both yield the same float32
mono PCM that Transcriber.transcribe expects.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

from ultra_x2.exceptions import SpeechError
from ultra_x2.speech.transcriber import SAMPLE_RATE

logger = logging.getLogger(__name__)


class Recorder:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        silence_threshold: float = 0.015,  # RMS below this counts as silence
        silence_duration: float = 1.2,     # stop after this much trailing silence
        max_duration: float = 20.0,        # hard cap on one utterance
        block_duration: float = 0.05,      # audio callback granularity (s)
    ) -> None:
        self._sr = sample_rate
        self._threshold = silence_threshold
        self._silence_duration = silence_duration
        self._max_duration = max_duration
        self._block = int(sample_rate * block_duration)

    def listen(self) -> Any:
        """Block until one utterance is captured; return mono float32 PCM.

        Returns an empty array if nothing above the threshold was heard before
        the max duration elapsed.
        """
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechError(
                "sounddevice/numpy not installed. Install the voice extra: "
                "`poetry install --extras voice`."
            ) from exc

        q: "queue.Queue[Any]" = queue.Queue()

        def callback(indata, _frames, _time, status) -> None:
            if status:
                logger.debug("audio status: %s", status)
            q.put(indata.copy())

        block_dur = self._block / self._sr
        silence_blocks_needed = int(self._silence_duration / block_dur)
        max_blocks = int(self._max_duration / block_dur)

        frames: list[Any] = []
        speech_started = False
        silent_blocks = 0

        try:
            with sd.InputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                blocksize=self._block,
                callback=callback,
            ):
                for _ in range(max_blocks):
                    block = q.get()
                    rms = float(np.sqrt(np.mean(block**2)))

                    if rms >= self._threshold:
                        speech_started = True
                        silent_blocks = 0
                        frames.append(block)
                    elif speech_started:
                        silent_blocks += 1
                        frames.append(block)
                        if silent_blocks >= silence_blocks_needed:
                            break
                    # before speech starts, silent blocks are simply ignored
        except Exception as exc:  # noqa: BLE001 — normalize mic/device errors
            raise SpeechError(f"Microphone capture failed: {exc}") from exc

        if not frames:
            return np.zeros(0, dtype="float32")
        return np.concatenate(frames).flatten()
