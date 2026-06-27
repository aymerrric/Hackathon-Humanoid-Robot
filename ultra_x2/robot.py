"""UltraX2Robot — the single seam between this codebase and the vendor SDK.

Every method here is the *stable* interface the rest of the app depends on.
The vendor SDK is only ever touched inside this file: each method body has a
`# TODO(vendor)` marker showing exactly where the real call goes. Until then,
methods run in simulation so you can build the full stack without hardware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ultra_x2.config import Settings
from ultra_x2.exceptions import RobotConnectionError, UnsafeActionError

logger = logging.getLogger(__name__)

# Conservative joint limits (degrees). Tighten/loosen to match the real Ultra X2.
ARM_PITCH_LIMITS = (-90.0, 90.0)
VALID_POSTURES = {"stand", "sit", "crouch", "rest"}


@dataclass
class RobotState:
    """A snapshot of the robot, returned to callers and to the LLM."""

    connected: bool = False
    posture: str = "rest"
    battery_pct: float = 100.0
    is_moving: bool = False
    joints: dict[str, float] = field(default_factory=dict)


class UltraX2Robot:
    """Wrapper around the Ultra X2 humanoid SDK.

    Use as a context manager so the connection is always cleaned up:

        with UltraX2Robot(settings) as robot:
            robot.set_posture("stand")
            robot.walk(distance_m=1.0)
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sdk: Any = None  # the vendor client handle, set in connect()
        self._state = RobotState()

    # --- lifecycle ---------------------------------------------------------

    def connect(self) -> None:
        if self._state.connected:
            return
        if self._settings.dry_run:
            logger.info("[DRY_RUN] connect → %s:%s", self._settings.robot_host,
                        self._settings.robot_port)
        else:
            try:
                # TODO(vendor): replace with the real SDK client construction, e.g.
                #   from ultra_x2_sdk import Client
                #   self._sdk = Client(host=self._settings.robot_host,
                #                       port=self._settings.robot_port,
                #                       api_key=self._settings.robot_api_key)
                #   self._sdk.connect()
                raise NotImplementedError(
                    "Wire up the Ultra X2 SDK in UltraX2Robot.connect()."
                )
            except Exception as exc:  # noqa: BLE001 — normalize to our error type
                raise RobotConnectionError(str(exc)) from exc
        self._state.connected = True

    def close(self) -> None:
        if not self._state.connected:
            return
        if not self._settings.dry_run and self._sdk is not None:
            # TODO(vendor): self._sdk.disconnect()
            pass
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
            # TODO(vendor): hydrate self._state from the real telemetry, e.g.
            #   t = self._sdk.telemetry()
            #   self._state.battery_pct = t.battery
            #   self._state.posture = t.posture
            #   self._state.is_moving = t.moving
            pass
        return self._state

    # --- actions -----------------------------------------------------------

    def set_posture(self, posture: str) -> RobotState:
        self._require_connected()
        if posture not in VALID_POSTURES:
            raise UnsafeActionError(
                f"Unknown posture {posture!r}. Valid: {sorted(VALID_POSTURES)}"
            )
        logger.info("set_posture(%s)", posture)
        if not self._settings.dry_run:
            # TODO(vendor): self._sdk.set_posture(posture)
            pass
        self._state.posture = posture
        return self._state

    def walk(self, distance_m: float, heading_deg: float = 0.0) -> RobotState:
        self._require_connected()
        if self._state.posture != "stand":
            raise UnsafeActionError("Robot must be standing before it can walk.")
        if not -10.0 <= distance_m <= 10.0:
            raise UnsafeActionError("distance_m must be within [-10, 10].")
        logger.info("walk(distance_m=%.2f, heading_deg=%.1f)", distance_m, heading_deg)
        if not self._settings.dry_run:
            # TODO(vendor): self._sdk.walk(distance=distance_m, heading=heading_deg)
            pass
        return self._state

    def move_arm(self, side: str, pitch_deg: float) -> RobotState:
        self._require_connected()
        if side not in {"left", "right"}:
            raise UnsafeActionError("side must be 'left' or 'right'.")
        lo, hi = ARM_PITCH_LIMITS
        if not lo <= pitch_deg <= hi:
            raise UnsafeActionError(f"pitch_deg must be within [{lo}, {hi}].")
        logger.info("move_arm(side=%s, pitch_deg=%.1f)", side, pitch_deg)
        if not self._settings.dry_run:
            # TODO(vendor): self._sdk.move_arm(side=side, pitch=pitch_deg)
            pass
        self._state.joints[f"{side}_arm_pitch"] = pitch_deg
        return self._state

    def speak(self, text: str) -> None:
        self._require_connected()
        logger.info("speak(%r)", text)
        if not self._settings.dry_run:
            # TODO(vendor): self._sdk.tts(text)
            pass

    def stop(self) -> RobotState:
        """Emergency stop — halt all motion immediately."""
        logger.warning("stop() — halting all motion")
        if self._state.connected and not self._settings.dry_run:
            # TODO(vendor): self._sdk.stop()
            pass
        self._state.is_moving = False
        return self._state

    # --- internals ---------------------------------------------------------

    def _require_connected(self) -> None:
        if not self._state.connected:
            raise UnsafeActionError("Robot is not connected. Call connect() first.")
