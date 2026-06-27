#!/usr/bin/env python3
"""Quick test: verify robot's audio topic is broadcasting.

This test requires ROS 2 to be installed. It can be run in two ways:

OPTION 1 (Recommended): Run on the robot via SSH
  ssh agi@<robot-ip>
  source ~/Botifull/SLAM_stack/scripts/setup_env.sh
  cd /path/to/hackathon
  poetry run python test_robot_audio.py 5

OPTION 2: Install ROS 2 on laptop (optional, for development)
  If you have ROS 2 Humble installed locally:
  source /opt/ros/humble/setup.bash
  poetry run python test_robot_audio.py 5

Usage:
    poetry run python test_robot_audio.py [seconds_to_listen]

Example:
    poetry run python test_robot_audio.py 5  # Listen for 5 seconds
"""

from __future__ import annotations

import sys
import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def test_audio_subscription(duration_s: float = 5.0) -> bool:
    """Subscribe to /aima/hal/audio/capture and verify frames arrive."""
    try:
        import rclpy
        import numpy as np
        from aimdk_msgs.msg import AudioCapture
    except ImportError as exc:
        logger.error(f"❌ ROS 2 / aimdk_msgs not available: {exc}")
        logger.info("\nThis test requires ROS 2. Run it on the robot:")
        logger.info("  ssh agi@<robot-ip>")
        logger.info("  source ~/Botifull/SLAM_stack/scripts/setup_env.sh")
        logger.info("  cd /path/to/hackathon && poetry run python test_robot_audio.py 5")
        logger.info("\nOr install ROS 2 Humble on your laptop for local testing.")
        return False

    if not rclpy.ok():
        rclpy.init()

    node = rclpy.create_node("audio_test")
    frame_count = [0]
    sample_rate = [0]
    channels = [0]

    def callback(msg: AudioCapture) -> None:
        frame_count[0] += 1
        sample_rate[0] = msg.info.sample_rate
        channels[0] = msg.info.channels

        pcm_bytes = bytes(msg.data.data)
        pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)

        # RMS of first channel
        if channels[0] > 1:
            pcm_int16 = pcm_int16[::channels[0]]

        pcm_float32 = pcm_int16.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(pcm_float32**2)))

        logger.info(
            f"📍 Frame #{frame_count[0]}: {len(pcm_int16)} samples, "
            f"RMS={rms:.4f}, {sample_rate[0]}Hz, {channels[0]} channels"
        )

    sub = node.create_subscription(
        AudioCapture,
        "/aima/hal/audio/capture",
        callback,
        qos_profile=10,
    )

    logger.info(f"🎤 Subscribing to /aima/hal/audio/capture for {duration_s}s…")
    logger.info("   (Speak or make noise so we can see RMS values)")

    start = node.get_clock().now()
    try:
        while True:
            elapsed = (node.get_clock().now() - start).nanoseconds / 1e9
            if elapsed > duration_s:
                break
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        node.destroy_subscription(sub)
        node.destroy_node()

    success = frame_count[0] > 0
    if success:
        logger.info(
            f"\n✅ SUCCESS: Received {frame_count[0]} audio frames "
            f"@ {sample_rate[0]}Hz, {channels[0]} channels"
        )
        logger.info(f"   Estimated duration: {frame_count[0] * 0.02:.1f}s")
        logger.info("   ✓ Robot's audio topic is working!")
    else:
        logger.error("\n❌ FAILED: No audio frames received from /aima/hal/audio/capture")
        logger.error("   Check:")
        logger.error("   1. Robot's ROS 2 is running: ssh agi@<robot-ip> -> ros2 topic list")
        logger.error("   2. Topic exists: /aima/hal/audio/capture")
        logger.error("   3. Same WiFi: laptop and robot on same network")
        logger.error("   4. Same ROS_DOMAIN_ID (default=0)")

    return success


if __name__ == "__main__":
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    success = test_audio_subscription(duration)
    sys.exit(0 if success else 1)
