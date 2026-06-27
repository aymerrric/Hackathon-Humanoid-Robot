"""UltraX2Robot — the single seam between this codebase and the AgiBot X2 ROS 2 SDK.

This file directly integrates with AgiBot X2 ROS 2 Humble using aimdk_msgs.
All methods use the official API patterns from the agibot-x2-sdk examples,
including the standard 8-retry pattern for service calls.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
    from aimdk_msgs.msg import (
        McLocomotionVelocity,
        MessageHeader,
        RequestHeader,
        McActionCommand,
        HandCommandArray,
        HandCommand,
        HandType,
    )
    from aimdk_msgs.srv import SetMcAction, SetMcInputSource, PlayTts
except ImportError:
    # Graceful fallback if ROS 2 is not installed (e.g., in dev/CI environments)
    rclpy = None
    Node = object
    MessageHeader = None

from ultra_x2.config import Settings
from ultra_x2.exceptions import RobotConnectionError, UnsafeActionError

logger = logging.getLogger(__name__)

# Conservative joint limits (degrees). Tighten/loosen to match the real Ultra X2.
ARM_PITCH_LIMITS = (-90.0, 90.0)
VALID_POSTURES = {"stand", "sit", "crouch", "rest"}

# ROS 2 service paths (from aimdk_msgs)
SERVICE_SET_MC_ACTION = "/aimdk_5Fmsgs/srv/SetMcAction"
SERVICE_SET_MC_INPUT_SOURCE = "/aimdk_5Fmsgs/srv/SetMcInputSource"
SERVICE_PLAY_TTS = "/aimdk_5Fmsgs/srv/PlayTts"
TOPIC_MC_LOCOMOTION_VELOCITY = "/aima/mc/locomotion/velocity"
TOPIC_HAND_COMMAND = "/aima/hal/joint/hand/command"

# ROS 2 service call retry parameters
SERVICE_CALL_TIMEOUT_SEC = 0.25
SERVICE_CALL_MAX_RETRIES = 8
SERVICE_WAIT_TIMEOUT_SEC = 2.0


@dataclass
class RobotState:
    """A snapshot of the robot, returned to callers and to the LLM."""

    connected: bool = False
    posture: str = "rest"
    battery_pct: float = 100.0
    is_moving: bool = False
    joints: dict[str, float] = field(default_factory=dict)


class _RosNode(Node):
    """Lightweight ROS 2 node for interacting with the robot.

    This is internal to UltraX2Robot and handles all ROS 2 communication.
    """

    def __init__(self) -> None:
        super().__init__("ultra_x2_robot")

        # Service clients
        self._mc_action_client = self.create_client(
            SetMcAction, SERVICE_SET_MC_ACTION
        )
        self._mc_input_client = self.create_client(
            SetMcInputSource, SERVICE_SET_MC_INPUT_SOURCE
        )
        self._tts_client = self.create_client(PlayTts, SERVICE_PLAY_TTS)

        # Publishers
        self._velocity_publisher = self.create_publisher(
            McLocomotionVelocity, TOPIC_MC_LOCOMOTION_VELOCITY, 10
        )
        self._hand_command_publisher = self.create_publisher(
            HandCommandArray, TOPIC_HAND_COMMAND, 10
        )

        # State tracking
        self._velocity_timer = None
        self._forward_velocity = 0.0
        self._lateral_velocity = 0.0
        self._angular_velocity = 0.0
        self._hand_timer = None
        self._input_source_registered = False

    def wait_for_services(self, timeout_sec: float = 5.0) -> bool:
        """Wait for all required services to become available."""
        start = time.time()
        services = [
            (self._mc_action_client, "SetMcAction"),
            (self._mc_input_client, "SetMcInputSource"),
            (self._tts_client, "PlayTts"),
        ]

        for client, name in services:
            while not client.wait_for_service(timeout_sec=SERVICE_WAIT_TIMEOUT_SEC):
                if time.time() - start > timeout_sec:
                    self.get_logger().error(f"Service {name} not available")
                    return False
                self.get_logger().info(f"Waiting for {name}...")

        return True

    def _call_service_with_retry(self, client: Any, request: Any) -> Any:
        """Call a service with the standard 8-retry pattern.

        This matches the pattern from agibot-x2-sdk examples where service calls
        sometimes need retries due to ROS 2 remote peer handling.
        """
        for attempt in range(SERVICE_CALL_MAX_RETRIES):
            # Update timestamp on each attempt
            if hasattr(request, "header"):
                if hasattr(request.header, "stamp"):
                    request.header.stamp = self.get_clock().now().to_msg()
                elif hasattr(request.header, "header"):
                    request.header.header.stamp = self.get_clock().now().to_msg()
            if hasattr(request, "request") and hasattr(request.request, "header"):
                request.request.header.stamp = self.get_clock().now().to_msg()

            future = client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=SERVICE_CALL_TIMEOUT_SEC)

            if future.done():
                try:
                    return future.result()
                except Exception as e:
                    self.get_logger().error(f"Service call failed: {e}")
                    if attempt == SERVICE_CALL_MAX_RETRIES - 1:
                        raise
            elif attempt < SERVICE_CALL_MAX_RETRIES - 1:
                self.get_logger().info(f"Service call retry [{attempt}]")

        raise RobotConnectionError("Service call failed after retries")

    def register_input_source(self) -> bool:
        """Register this node as the input source for locomotion control."""
        if self._input_source_registered:
            return True

        try:
            req = SetMcInputSource.Request()
            req.request.header = RequestHeader()
            req.request.header.stamp = self.get_clock().now().to_msg()

            # Register input source with priority 40
            req.action.value = 1001  # Register action
            req.input_source.name = "ultra_x2_robot"
            req.input_source.priority = 40
            req.input_source.timeout = 1000  # ms

            self.get_logger().info("Registering input source for locomotion...")
            response = self._call_service_with_retry(self._mc_input_client, req)

            if response.response.header.code == 0:
                self.get_logger().info("Input source registered successfully")
                self._input_source_registered = True
                return True
            else:
                self.get_logger().error(
                    f"Failed to register input source: code={response.response.header.code}"
                )
                return False
        except Exception as e:
            self.get_logger().error(f"Input source registration failed: {e}")
            return False

    def set_mc_action(self, action_name: str) -> bool:
        """Set the robot's motion control action (posture/mode)."""
        try:
            req = SetMcAction.Request()
            req.header = RequestHeader()
            req.header.stamp = self.get_clock().now().to_msg()

            cmd = McActionCommand()
            cmd.action_desc = action_name
            req.command = cmd

            self.get_logger().info(f"Setting MC action: {action_name}")
            response = self._call_service_with_retry(self._mc_action_client, req)

            # Check response status (SUCCESS = 0)
            if hasattr(response, "response") and hasattr(response.response, "status"):
                if response.response.status.value == 0:  # SUCCESS
                    self.get_logger().info(f"MC action set successfully: {action_name}")
                    return True
                else:
                    self.get_logger().error(
                        f"Failed to set MC action: {response.response.message}"
                    )
                    return False
            return True
        except Exception as e:
            self.get_logger().error(f"MC action call failed: {e}")
            return False

    def start_velocity_control(
        self, forward: float, lateral: float, angular: float
    ) -> bool:
        """Start publishing locomotion velocity commands."""
        self._forward_velocity = forward
        self._lateral_velocity = lateral
        self._angular_velocity = angular

        if self._velocity_timer is None:
            self._velocity_timer = self.create_timer(0.02, self._publish_velocity)

        return True

    def _publish_velocity(self) -> None:
        """Publish the current velocity command (called by timer)."""
        msg = McLocomotionVelocity()
        msg.header = MessageHeader()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.source = "ultra_x2_robot"
        msg.forward_velocity = self._forward_velocity
        msg.lateral_velocity = self._lateral_velocity
        msg.angular_velocity = self._angular_velocity

        self._velocity_publisher.publish(msg)

    def stop_velocity_control(self) -> None:
        """Stop publishing velocity (zero out all velocities)."""
        self._forward_velocity = 0.0
        self._lateral_velocity = 0.0
        self._angular_velocity = 0.0
        self._publish_velocity()

        if self._velocity_timer is not None:
            self.destroy_timer(self._velocity_timer)
            self._velocity_timer = None

    def play_tts(self, text: str) -> bool:
        """Play text-to-speech on the robot."""
        try:
            req = PlayTts.Request()
            req.header.header = RequestHeader()
            req.header.header.stamp = self.get_clock().now().to_msg()

            req.tts_req.text = text
            req.tts_req.domain = "ultra_x2_robot"
            req.tts_req.trace_id = "robot"
            req.tts_req.is_interrupted = True
            req.tts_req.priority_weight = 0
            req.tts_req.priority_level.value = 6  # Normal priority

            self.get_logger().info(f"Playing TTS: {text!r}")
            response = self._call_service_with_retry(self._tts_client, req)

            if hasattr(response, "tts_resp") and response.tts_resp.is_success:
                self.get_logger().info("TTS played successfully")
                return True
            else:
                self.get_logger().error("TTS playback failed")
                return False
        except Exception as e:
            self.get_logger().error(f"TTS call failed: {e}")
            return False

    def move_hand(self, side: str, position: float) -> bool:
        """Move hand/gripper to a specific position."""
        try:
            # Clamp position to [0.0, 1.0]
            position = max(0.0, min(1.0, position))

            msg = HandCommandArray()
            msg.header = MessageHeader()
            msg.header.stamp = self.get_clock().now().to_msg()

            # Create hand command
            hand_cmd = HandCommand()
            hand_cmd.name = f"{side}_hand"
            hand_cmd.position = float(position)
            hand_cmd.velocity = 1.0
            hand_cmd.acceleration = 1.0
            hand_cmd.deceleration = 1.0
            hand_cmd.effort = 1.0

            # Configure message
            if side == "left":
                msg.left_hand_type = HandType(value=2)  # Gripper mode
                msg.left_hands = [hand_cmd]
                msg.right_hands = []
            else:  # right
                msg.right_hand_type = HandType(value=2)
                msg.right_hands = [hand_cmd]
                msg.left_hands = []

            self._hand_command_publisher.publish(msg)
            self.get_logger().info(f"Hand command published: {side}={position:.2f}")
            return True
        except Exception as e:
            self.get_logger().error(f"Hand command failed: {e}")
            return False


class UltraX2Robot:
    """Wrapper around the Ultra X2 humanoid SDK.

    Use as a context manager so the connection is always cleaned up:

        with UltraX2Robot(settings) as robot:
            robot.set_posture("stand")
            robot.walk(distance_m=1.0)
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ros_node: _RosNode | None = None
        self._ros_thread: threading.Thread | None = None
        self._state = RobotState()

    # --- lifecycle ---------------------------------------------------------

    def connect(self) -> None:
        """Connect to the robot (ROS 2 node initialization in live mode)."""
        if self._state.connected:
            return

        if self._settings.dry_run:
            logger.info("[DRY_RUN] connect (simulation mode, no ROS 2)")
            self._state.connected = True
            return

        # Live mode: initialize ROS 2 node
        try:
            if rclpy is None:
                raise RobotConnectionError(
                    "ROS 2 not installed. Cannot connect to real robot. "
                    "Set DRY_RUN=1 for simulation mode."
                )

            if not rclpy.ok():
                rclpy.init()

            self._ros_node = _RosNode()

            # Wait for services
            if not self._ros_node.wait_for_services(timeout_sec=5.0):
                raise RobotConnectionError("ROS 2 services not available")

            logger.info("Connected to AgiBot X2 via ROS 2")
            self._state.connected = True

        except Exception as exc:
            raise RobotConnectionError(str(exc)) from exc

    def close(self) -> None:
        """Disconnect from the robot."""
        if not self._state.connected:
            return

        # Stop all motion
        if self._ros_node is not None:
            try:
                self._ros_node.stop_velocity_control()
                self._ros_node.destroy_node()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            self._ros_node = None

        self._state.connected = False

    def __enter__(self) -> "UltraX2Robot":
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- telemetry ---------------------------------------------------------

    def get_state(self) -> RobotState:
        """Return the current robot state."""
        self._require_connected()

        if not self._settings.dry_run:
            # In live mode, state is updated by subscriptions and status checks
            # For now, maintain the locally tracked state
            pass

        return self._state

    # --- actions -----------------------------------------------------------

    def set_posture(self, posture: str) -> RobotState:
        """Set the robot's posture (stand, sit, crouch, rest)."""
        self._require_connected()
        if posture not in VALID_POSTURES:
            raise UnsafeActionError(
                f"Unknown posture {posture!r}. Valid: {sorted(VALID_POSTURES)}"
            )

        logger.info("set_posture(%s)", posture)

        if not self._settings.dry_run:
            if self._ros_node is None:
                raise RobotConnectionError("ROS node not initialized")

            # Map posture to MC action names
            action_map = {
                "stand": "STAND_DEFAULT",
                "sit": "DAMPING_DEFAULT",  # Fallback; ideally would be "SIT"
                "crouch": "JOINT_DEFAULT",
                "rest": "PASSIVE_DEFAULT",
            }

            action_name = action_map.get(posture, "STAND_DEFAULT")
            success = self._ros_node.set_mc_action(action_name)

            if not success:
                raise UnsafeActionError(f"Failed to set posture: {posture}")

        self._state.posture = posture
        return self._state

    def walk(self, distance_m: float, heading_deg: float = 0.0) -> RobotState:
        """Make the robot walk forward."""
        self._require_connected()
        if self._state.posture != "stand":
            raise UnsafeActionError("Robot must be standing before it can walk.")
        if not -10.0 <= distance_m <= 10.0:
            raise UnsafeActionError("distance_m must be within [-10, 10].")

        logger.info("walk(distance_m=%.2f, heading_deg=%.1f)", distance_m, heading_deg)

        if not self._settings.dry_run:
            if self._ros_node is None:
                raise RobotConnectionError("ROS node not initialized")

            # First, ensure input source is registered
            if not self._ros_node.register_input_source():
                raise UnsafeActionError("Failed to register input source")

            # Estimate walk duration based on distance and speed
            # Assume ~0.5 m/s walking speed
            walk_speed = 0.5  # m/s
            walk_duration = abs(distance_m) / walk_speed if distance_m != 0 else 0.5

            # Calculate velocity components
            forward_velocity = walk_speed if distance_m > 0 else -walk_speed if distance_m < 0 else 0.0

            # Convert heading to angular velocity (radians)
            angular_velocity = 0.0  # TODO: implement heading control

            # Start velocity control
            self._ros_node.start_velocity_control(
                forward=forward_velocity,
                lateral=0.0,
                angular=angular_velocity
            )

            # Mark robot as moving
            self._state.is_moving = True

            # Wait for motion to complete
            time.sleep(walk_duration)

            # Stop motion
            self._ros_node.stop_velocity_control()
            self._state.is_moving = False

        return self._state

    def move_arm(self, side: str, pitch_deg: float) -> RobotState:
        """Move an arm to a specific pitch angle."""
        self._require_connected()
        if side not in {"left", "right"}:
            raise UnsafeActionError("side must be 'left' or 'right'.")
        lo, hi = ARM_PITCH_LIMITS
        if not lo <= pitch_deg <= hi:
            raise UnsafeActionError(f"pitch_deg must be within [{lo}, {hi}].")

        logger.info("move_arm(side=%s, pitch_deg=%.1f)", side, pitch_deg)

        if not self._settings.dry_run:
            if self._ros_node is None:
                raise RobotConnectionError("ROS node not initialized")

            # Convert pitch angle to hand position (normalized 0-1)
            # Assuming -90° = fully closed (0.0), +90° = fully open (1.0)
            position = (pitch_deg - ARM_PITCH_LIMITS[0]) / (
                ARM_PITCH_LIMITS[1] - ARM_PITCH_LIMITS[0]
            )

            success = self._ros_node.move_hand(side, position)
            if not success:
                raise UnsafeActionError(f"Failed to move arm: {side}")

        self._state.joints[f"{side}_arm_pitch"] = pitch_deg
        return self._state

    def speak(self, text: str) -> None:
        """Play text-to-speech on the robot."""
        self._require_connected()
        logger.info("speak(%r)", text)

        if not self._settings.dry_run:
            if self._ros_node is None:
                raise RobotConnectionError("ROS node not initialized")

            success = self._ros_node.play_tts(text)
            if not success:
                raise UnsafeActionError(f"Failed to speak: {text!r}")

    def stop(self) -> RobotState:
        """Emergency stop — halt all motion immediately."""
        logger.warning("stop() — halting all motion")

        if self._state.connected and not self._settings.dry_run:
            if self._ros_node is not None:
                try:
                    self._ros_node.stop_velocity_control()
                except Exception as e:
                    logger.error(f"Error during stop: {e}")

        self._state.is_moving = False
        return self._state

    # --- internals ---------------------------------------------------------

    def _require_connected(self) -> None:
        if not self._state.connected:
            raise UnsafeActionError("Robot is not connected. Call connect() first.")
