"""Speech layer: capture audio, turn it into text, speak replies back."""

from ultra_x2.speech.recorder import Recorder
from ultra_x2.speech.speaker import speak
from ultra_x2.speech.transcriber import SAMPLE_RATE, Transcriber

__all__ = ["Recorder", "Transcriber", "speak", "SAMPLE_RATE"]
