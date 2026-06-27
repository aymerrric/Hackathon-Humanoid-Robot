"""Robot microphone source via ROS 2 /aima/hal/audio/capture topic.

Subscribes to the raw HAL audio stream, which is published by the robot's
audio hardware abstraction layer at 16 kHz, 16-bit, multichannel PCM.

Takes the first microphone channel, accumulates frames until silence is detected
(like LocalRecorder), then returns complete float32 utterance.
"""

from __future__ import annotations

import logging
from typing import Any

from ultra_x2.exceptions import SpeechError
from ultra_x2.speech.transcriber import SAMPLE_RATE

logger = logging.getLogger(__name__)


class RobotMicrophone:
    """Listen to the robot's microphone via ROS 2 HAL audio.

    Subscribes to /aima/hal/audio/capture which publishes raw multichannel
    audio at 16 kHz, 16-bit signed (S16_LE). Takes the first microphone
    channel and accumulates frames until silence is detected, then returns
    a complete utterance as float32 PCM (like LocalRecorder).
    """

    def __init__(
        self,
        silence_threshold: float = 0.025,  # RMS below this counts as silence
        silence_duration: float = 0.6,     # stop after this much trailing silence
        max_duration: float = 15.0,        # hard cap on one utterance
        utterance_timeout_s: float = 20.0, # timeout waiting for subscription
    ) -> None:
        """
        Args:
            silence_threshold: RMS threshold for silence detection
            silence_duration: seconds of trailing silence before stopping
            max_duration: max seconds to record for one utterance
            utterance_timeout_s: timeout for ROS 2 subscription startup
        """
        self._silence_threshold = silence_threshold
        self._silence_duration = silence_duration
        self._max_duration = max_duration
        self._timeout_s = utterance_timeout_s

    def listen(self) -> Any:
        """Block until one utterance is captured from robot's mic.

        Accumulates audio frames, detects silence, returns mono float32 PCM.
        Uses official robot QoS settings (BEST_EFFORT, KEEP_LAST=500).
        """
        try:
            import rclpy
            from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
            import numpy as np
            from aimdk_msgs.msg import AudioCapture
        except ImportError as exc:
            raise SpeechError(
                "ROS 2 / aimdk_msgs not available. Make sure you're running on the robot "
                "with ROS 2 sourced: `source ~/Botifull/SLAM_stack/scripts/setup_env.sh`"
            ) from exc

        # Initialize ROS 2 if not already done
        if not rclpy.ok():
            rclpy.init()

        # Create a minimal node to subscribe
        node = rclpy.create_node("whisper_listener")

        # Use official robot QoS settings (from audio_tools/record_mic_split.py)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=500,
            durability=DurabilityPolicy.VOLATILE,
        )

        frames: list[Any] = []
        speech_started = False
        silent_frames = 0
        frame_count = [0]
        sample_rate = [SAMPLE_RATE]  # will be updated from first message
        mic_channels = [0]
        ref_channels = [0]

        def audio_callback(msg: AudioCapture) -> None:
            nonlocal speech_started, silent_frames
            try:
                # Extract raw PCM bytes (16-bit signed LE)
                pcm_bytes = bytes(msg.data.data)
                pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)

                # Get channel info from message (official structure)
                mic_channels[0] = msg.mic_channels
                ref_channels[0] = msg.ref_channels
                total_channels = msg.info.channels

                # Validate frame integrity
                if pcm_int16.size % total_channels != 0:
                    logger.warning(f"Invalid frame size: {pcm_int16.size} % {total_channels} != 0")
                    return

                # Reshape to per-channel: frames x channels
                frames_data = pcm_int16.reshape(-1, total_channels)

                # Take first mic channel (channel 0)
                pcm_channel0 = frames_data[:, 0].copy()

                # Convert to float32 [-1, 1]
                pcm_float32 = pcm_channel0.astype(np.float32) / 32768.0

                # Calculate RMS for silence detection
                rms = float(np.sqrt(np.mean(pcm_float32**2)))

                # Silence detection (like LocalRecorder)
                if rms >= self._silence_threshold:
                    speech_started = True
                    silent_frames = 0
                    frames.append(pcm_float32)
                elif speech_started:
                    silent_frames += 1
                    frames.append(pcm_float32)
                # before speech starts, silent frames are ignored

                # Update sample rate from message
                sample_rate[0] = msg.info.sample_rate

                frame_count[0] += 1
                logger.debug(
                    f"Frame #{frame_count[0]}: RMS={rms:.4f} "
                    f"(threshold={self._silence_threshold}), "
                    f"speech_started={speech_started}, silent_frames={silent_frames}, "
                    f"mics={mic_channels[0]} ref={ref_channels[0]}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error processing audio frame: {exc}")

        subscription = node.create_subscription(
            AudioCapture,
            "/aima/hal/audio/capture",
            audio_callback,
            qos_profile=qos,
        )

        logger.info("🎤 Listening to robot's HAL microphone (/aima/hal/audio/capture)…")
        start_time = node.get_clock().now()

        # Calculate frame duration and silence threshold in frames
        # (we'll estimate this from the first few frames)
        estimated_frame_duration_s = 0.02  # typical: 320 samples @ 16kHz
        silence_frames_needed = int(self._silence_duration / estimated_frame_duration_s)
        max_frames = int(self._max_duration / estimated_frame_duration_s)

        try:
            while len(frames) < max_frames:
                elapsed = (node.get_clock().now() - start_time).nanoseconds / 1e9
                if elapsed > self._timeout_s and not speech_started:
                    logger.warning(
                        f"Timeout waiting for speech after {self._timeout_s}s. "
                        "Check that /aima/hal/audio/capture is publishing."
                    )
                    break

                rclpy.spin_once(node, timeout_sec=0.1)

                # Check if we've detected enough silence to stop
                if speech_started and silent_frames >= silence_frames_needed:
                    logger.debug(f"Silence detected ({silent_frames} frames), stopping.")
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted.")
        finally:
            node.destroy_subscription(subscription)
            node.destroy_node()

        if not frames:
            return np.zeros(0, dtype="float32")

        result = np.concatenate(frames).flatten()
        logger.debug(
            f"Captured {len(frames)} frames, {len(result)} samples "
            f"({len(result)/sample_rate[0]:.1f}s @ {sample_rate[0]}Hz)"
        )
        return result
