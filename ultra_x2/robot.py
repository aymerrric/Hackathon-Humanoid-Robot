"""UltraX2Robot — SSH-based control of AgiBot X2.

Instead of requiring ROS 2 locally, we SSH into the robot and execute ROS 2
commands there. This keeps the interface simple: Laptop Mic → Whisper → Claude →
SSH commands → Robot ROS 2 → Physical commands.

All operations use the official ROS 2 CLI (ros2 service call, ros2 topic pub, etc.)
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from ultra_x2.config import Settings
from ultra_x2.exceptions import RobotConnectionError, UnsafeActionError

logger = logging.getLogger(__name__)

VALID_POSTURES = {"stand", "sit", "crouch", "rest"}
ARM_PITCH_LIMITS = (-90.0, 90.0)


@dataclass
class RobotState:
    """A snapshot of the robot, returned to callers and to the LLM."""

    connected: bool = False
    posture: str = "rest"
    battery_pct: float = 100.0
    is_moving: bool = False
    joints: dict[str, float] = field(default_factory=dict)


class UltraX2Robot:
    """Control AgiBot X2 via SSH + ROS 2 on the robot."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state = RobotState()
        self._velocity_running = False

    def connect(self) -> None:
        """Test SSH connection to the robot."""
        if self._settings.dry_run:
            logger.info("DRY_RUN: simulating connection")
            self._state.connected = True
            return

        # Test SSH connectivity
        try:
            self._ssh_exec("echo 'Connected to robot'", timeout=5)
            logger.info("Connected to AgiBot X2 via SSH")
            self._state.connected = True
        except Exception as exc:
            raise RobotConnectionError(f"SSH connection failed: {exc}") from exc

    def close(self) -> None:
        """Disconnect from robot."""
        if self._velocity_running:
            self.stop()
        self._state.connected = False

    def __enter__(self) -> UltraX2Robot:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # =========================================================================
    # Private: SSH execution
    # =========================================================================

    def _ssh_exec(
        self,
        command: str,
        timeout: float = 10.0,
        check: bool = True,
    ) -> str:
        """Execute a command on the robot via SSH.

        Args:
            command: shell command to run on robot
            timeout: seconds to wait for completion
            check: raise if exit code != 0

        Returns:
            stdout from the command
        """
        # Source ROS 2 environment, then run command
        full_cmd = (
            f"source ~/Botifull/SLAM_stack/scripts/setup_env.sh && {command}"
        )

        # Use sshpass for non-interactive auth
        ssh_cmd = [
            "sshpass",
            "-p",
            self._settings.ultra_x2_password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{self._settings.ultra_x2_user}@{self._settings.ultra_x2_host}",
            full_cmd,
        ]

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired as exc:
            logger.error(f"SSH command timed out after {timeout}s: {command}")
            raise
        except subprocess.CalledProcessError as exc:
            logger.error(f"SSH command failed: {command}\nstderr: {exc.stderr}")
            raise

    # =========================================================================
    # Public: State & diagnostics
    # =========================================================================

    def get_state(self) -> RobotState:
        """Get current robot state (simulated for now)."""
        if not self._settings.dry_run:
            # In a real implementation, we'd query the robot's state via ROS 2
            # For now, return locally tracked state
            pass
        return self._state

    # =========================================================================
    # Public: Motion control
    # =========================================================================

    def set_posture(self, posture: str) -> RobotState:
        """Set robot's posture: stand, sit, crouch, rest."""
        if posture not in VALID_POSTURES:
            raise UnsafeActionError(
                f"Unknown posture {posture!r}. Valid: {sorted(VALID_POSTURES)}"
            )

        logger.info(f"set_posture({posture})")
        self._state.posture = posture

        if self._settings.dry_run:
            return self._state

        try:
            # Map posture to MC action names
            action_map = {
                "stand": "STAND_DEFAULT",
                "sit": "DAMPING_DEFAULT",
                "crouch": "JOINT_DEFAULT",
                "rest": "PASSIVE_DEFAULT",
            }
            action = action_map[posture]

            # Call SetMcAction service on robot via SSH
            cmd = (
                f"ros2 service call /aimdk_5Fmsgs/srv/SetMcAction "
                f"'aimdk_msgs/SetMcAction' '{{action_name: {action}}}'"
            )
            self._ssh_exec(cmd, timeout=10)
            return self._state
        except Exception as exc:
            raise UnsafeActionError(f"Failed to set posture {posture}: {exc}")

    def walk(
        self,
        forward: float = 0.0,
        lateral: float = 0.0,
        angular: float = 0.0,
        duration: float = 5.0,
    ) -> None:
        """Walk with given velocity (m/s, rad/s) for duration seconds."""
        logger.info(
            f"walk(forward={forward}, lateral={lateral}, angular={angular}, "
            f"duration={duration})"
        )

        if self._settings.dry_run:
            return

        self._velocity_running = True
        start_time = time.time()

        try:
            # Create a Python script to publish velocity on the robot
            script = f"""
import rclpy
import time
from aimdk_msgs.msg import McLocomotionVelocity, MessageHeader

rclpy.init()
node = rclpy.create_node('walk_command')
pub = node.create_publisher(McLocomotionVelocity, '/aima/mc/locomotion/velocity', 10)

# Register input source
from aimdk_msgs.srv import SetMcInputSource
client = node.create_client(SetMcInputSource, '/aimdk_5Fmsgs/srv/SetMcInputSource')
client.wait_for_service(timeout_sec=2)
req = SetMcInputSource.Request()
req.source = 'ultra_x2_robot'
client.call(req)

# Publish velocity
t0 = time.time()
while time.time() - t0 < {duration}:
    msg = McLocomotionVelocity()
    msg.header = MessageHeader()
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.source = 'ultra_x2_robot'
    msg.forward_velocity = {forward}
    msg.lateral_velocity = {lateral}
    msg.angular_velocity = {angular}
    pub.publish(msg)
    time.sleep(0.02)

rclpy.shutdown()
"""

            # Write and execute script on robot
            script_path = "/tmp/walk_cmd.py"
            self._ssh_exec(
                f"cat > {script_path} << 'EOF'\n{script}\nEOF",
                timeout=5,
            )
            self._ssh_exec(f"python3 {script_path}", timeout=int(duration) + 5)

        except Exception as exc:
            logger.error(f"Walk command failed: {exc}")
            raise UnsafeActionError(f"Walk failed: {exc}")
        finally:
            self._velocity_running = False

    def move_arm(self, side: str, position: float) -> None:
        """Move arm/gripper. side='left'|'right', position=[0.0, 1.0]."""
        side = side.lower()
        position = max(0.0, min(1.0, position))

        logger.info(f"move_arm({side}, {position})")

        if self._settings.dry_run:
            return

        try:
            # Publish hand command via SSH
            script = f"""
import rclpy
from aimdk_msgs.msg import HandCommandArray, HandCommand, HandType

rclpy.init()
node = rclpy.create_node('arm_command')
pub = node.create_publisher(HandCommandArray, '/aima/hal/joint/hand/command', 10)

msg = HandCommandArray()
cmd = HandCommand()
cmd.hand_type = HandType.LEFT if '{side}' == 'left' else HandType.RIGHT
cmd.target_position = {position}
msg.hand_commands.append(cmd)
pub.publish(msg)

rclpy.shutdown()
"""

            script_path = "/tmp/arm_cmd.py"
            self._ssh_exec(
                f"cat > {script_path} << 'EOF'\n{script}\nEOF",
                timeout=5,
            )
            self._ssh_exec(f"python3 {script_path}", timeout=5)

        except Exception as exc:
            logger.error(f"Move arm failed: {exc}")
            raise UnsafeActionError(f"Move arm failed: {exc}")

    def speak(self, text: str) -> None:
        """Play text-to-speech on the robot."""
        logger.info(f"speak({text!r})")

        if self._settings.dry_run:
            return

        try:
            # Escape quotes in text
            text_escaped = text.replace('"', '\\"')

            # Call PlayTts service via SSH
            cmd = (
                f"ros2 service call /aimdk_5Fmsgs/srv/PlayTts "
                f"'aimdk_msgs/PlayTts' "
                f"'{{tts_req: {{text: \"{text_escaped}\", "
                f"domain: ultra_x2_robot, trace_id: voice}}}}'"
            )
            self._ssh_exec(cmd, timeout=5)
        except Exception as exc:
            logger.error(f"TTS failed: {exc}")
            # Don't raise — TTS failure shouldn't block command execution

    def stop(self) -> None:
        """Emergency stop: zero velocity."""
        logger.info("stop()")

        if self._settings.dry_run:
            self._velocity_running = False
            return

        try:
            self._velocity_running = False
            # Publish zero velocity
            cmd = (
                "python3 -c \"import rclpy; from aimdk_msgs.msg import McLocomotionVelocity, MessageHeader; "
                "rclpy.init(); node = rclpy.create_node('stop'); pub = node.create_publisher(McLocomotionVelocity, '/aima/mc/locomotion/velocity', 10); "
                "msg = McLocomotionVelocity(); msg.header = MessageHeader(); msg.header.stamp = node.get_clock().now().to_msg(); "
                "msg.source = 'ultra_x2_robot'; msg.forward_velocity = 0; msg.lateral_velocity = 0; msg.angular_velocity = 0; "
                "pub.publish(msg); rclpy.shutdown()\""
            )
            self._ssh_exec(cmd, timeout=5)
        except Exception as exc:
            logger.error(f"Stop command failed: {exc}")
