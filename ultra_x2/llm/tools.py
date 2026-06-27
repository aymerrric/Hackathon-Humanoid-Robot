"""Robot capabilities exposed to the LLM as tools.

Each entry pairs a JSON-schema tool definition (sent to Claude) with a Python
callable that runs it against an `UltraX2Robot`. `physical=True` marks actions
that move the hardware — the agent gates those behind human confirmation.

`strict: True` guarantees the tool input validates exactly against the schema,
so the dispatcher can trust the argument shapes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ultra_x2.robot import RobotState, UltraX2Robot


@dataclass(frozen=True)
class Tool:
    definition: dict[str, Any]  # the schema sent to Claude
    run: Callable[[UltraX2Robot, dict[str, Any]], Any]
    physical: bool  # True if it actuates hardware (gated by confirmation)


def _result(value: Any) -> str:
    """Serialize a tool result into the string Claude expects back."""
    if isinstance(value, RobotState):
        return str(dataclasses.asdict(value))
    return "ok" if value is None else str(value)


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOLS: dict[str, Tool] = {
    "get_state": Tool(
        definition=_schema(
            "get_state",
            "Read the robot's current state: connection, posture, battery, motion, joints.",
            properties={},
            required=[],
        ),
        run=lambda robot, _args: robot.get_state(),
        physical=False,
    ),
    "set_posture": Tool(
        definition=_schema(
            "set_posture",
            "Change the robot's whole-body posture.",
            properties={
                "posture": {
                    "type": "string",
                    "enum": ["stand", "sit", "crouch", "rest"],
                    "description": "Target posture.",
                }
            },
            required=["posture"],
        ),
        run=lambda robot, args: robot.set_posture(args["posture"]),
        physical=True,
    ),
    "walk": Tool(
        definition=_schema(
            "walk",
            "Walk forward/backward a distance. Robot must already be standing.",
            properties={
                "distance_m": {
                    "type": "number",
                    "description": "Meters to walk; negative is backward. Range [-10, 10].",
                },
                "heading_deg": {
                    "type": "number",
                    "description": "Heading offset in degrees (0 = straight ahead).",
                },
            },
            required=["distance_m"],
        ),
        run=lambda robot, args: robot.walk(
            distance_m=args["distance_m"],
            heading_deg=args.get("heading_deg", 0.0),
        ),
        physical=True,
    ),
    "move_arm": Tool(
        definition=_schema(
            "move_arm",
            "Raise or lower one arm to a pitch angle in degrees.",
            properties={
                "side": {"type": "string", "enum": ["left", "right"]},
                "pitch_deg": {
                    "type": "number",
                    "description": "Arm pitch in degrees. Range [-90, 90].",
                },
            },
            required=["side", "pitch_deg"],
        ),
        run=lambda robot, args: robot.move_arm(
            side=args["side"], pitch_deg=args["pitch_deg"]
        ),
        physical=True,
    ),
    "speak": Tool(
        definition=_schema(
            "speak",
            "Say something out loud through the robot's speaker.",
            properties={"text": {"type": "string", "description": "What to say."}},
            required=["text"],
        ),
        run=lambda robot, args: robot.speak(args["text"]),
        physical=False,
    ),
    "stop": Tool(
        definition=_schema(
            "stop",
            "Emergency stop: immediately halt all motion.",
            properties={},
            required=[],
        ),
        run=lambda robot, _args: robot.stop(),
        physical=False,
    ),
}


def tool_definitions() -> list[dict[str, Any]]:
    """The `tools=` payload for the Messages API."""
    return [t.definition for t in TOOLS.values()]
