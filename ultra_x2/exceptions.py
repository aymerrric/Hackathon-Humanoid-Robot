"""Typed errors for the Ultra X2 wrapper.

Catch these instead of letting raw vendor-SDK exceptions leak into application
code — it keeps callers decoupled from the vendor's error types.
"""


class RobotError(Exception):
    """Base class for all robot errors."""


class RobotConnectionError(RobotError):
    """Raised when the robot cannot be reached or the session drops."""


class UnsafeActionError(RobotError):
    """Raised when a requested action fails a safety precondition.

    Examples: a joint angle outside its limit, walking while not standing,
    or a command issued before the robot is connected.
    """


class SpeechError(RobotError):
    """Raised when audio capture or speech-to-text fails.

    Examples: no microphone available, an optional dependency (faster-whisper /
    sounddevice) not installed, or a transcription backend error.
    """
