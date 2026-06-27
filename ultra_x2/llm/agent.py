"""RobotAgent — drives the Ultra X2 from natural language via Claude tool use.

This is a manual agentic loop (not the SDK tool-runner) on purpose: physical
robots need a human-confirmation gate and per-call logging before any motion
command executes. The manual loop is where that gate lives.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import anthropic

from ultra_x2.config import Settings
from ultra_x2.exceptions import RobotError
from ultra_x2.llm import tools as tools_mod
from ultra_x2.llm.personalities import get_personality
from ultra_x2.robot import UltraX2Robot

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You control an Ultra X2 humanoid robot through the provided tools.

⚠️ SAFETY FIRST — these are CRITICAL:
- ALWAYS check the robot's state with get_state before ANY motion.
- NEVER assume the robot is standing. ALWAYS verify with get_state first.
- NEVER command motion without confirming state (battery, posture, etc.).
- REFUSE any command that seems risky or could cause a fall.
- If the user says "stop", IMMEDIATELY use the stop tool.
- Use the stop tool if anything seems wrong.

Motion sequence (ALWAYS follow this):
1. Check state with get_state
2. If not standing, set_posture("stand") first
3. Wait for confirmation the posture change is done
4. Then do the motion (walk, raise arm, etc.)
5. Use small, deliberate movements only

If a tool reports an error, STOP and explain to the user what happened.
Do NOT retry failed commands.

When in doubt, err on the side of safety. Ask the user for confirmation
for any risky action.
"""

# A confirmer takes a human-readable description of a physical action and returns
# True to allow it. Default CLI implementation is in main.py.
Confirmer = Callable[[str], bool]


class RobotAgent:
    def __init__(
        self,
        client: anthropic.Anthropic,
        robot: UltraX2Robot,
        settings: Settings,
        confirmer: Confirmer | None = None,
        personality: str | None = None,
    ) -> None:
        self._client = client
        self._robot = robot
        self._settings = settings
        self._confirmer = confirmer
        self._messages: list[dict[str, Any]] = []  # conversation history
        # Use provided personality or fall back to settings
        self._personality = get_personality(personality or settings.personality)
        self._system_prompt = self._build_system_prompt()

    def send(self, user_message: str, max_steps: int = 8) -> str:
        """Send a user instruction and run the tool loop until Claude is done.

        Returns Claude's final natural-language reply.
        """
        self._messages.append({"role": "user", "content": user_message})

        for _step in range(max_steps):
            response = self._client.messages.create(
                model=self._settings.llm_model,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=self._system_prompt,
                tools=tools_mod.tool_definitions(),
                messages=self._messages,
            )
            # Preserve the full content (incl. thinking blocks) in history.
            self._messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return self._final_text(response.content)

            tool_results = [
                self._run_tool_block(block)
                for block in response.content
                if block.type == "tool_use"
            ]
            self._messages.append({"role": "user", "content": tool_results})

        return "Stopped: reached the maximum number of tool steps."

    # --- helpers -----------------------------------------------------------

    def _run_tool_block(self, block: Any) -> dict[str, Any]:
        tool = tools_mod.TOOLS.get(block.name)
        if tool is None:
            return self._error_result(block.id, f"Unknown tool: {block.name}")

        if tool.physical and not self._approve(block.name, block.input):
            return self._error_result(block.id, "Action denied by operator.")

        try:
            value = tool.run(self._robot, dict(block.input))
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tools_mod._result(value),
            }
        except RobotError as exc:
            # Hand the error back to Claude so it can recover gracefully.
            return self._error_result(block.id, f"{type(exc).__name__}: {exc}")

    def _approve(self, name: str, args: Any) -> bool:
        if not self._settings.require_confirmation or self._confirmer is None:
            return True
        return self._confirmer(f"{name}({dict(args)})")

    @staticmethod
    def _error_result(tool_use_id: str, message: str) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": message,
            "is_error": True,
        }

    @staticmethod
    def _final_text(content: list[Any]) -> str:
        return "".join(b.text for b in content if b.type == "text").strip()

    def _build_system_prompt(self) -> str:
        """Build the system prompt with personality injected."""
        base = SYSTEM_PROMPT.strip()
        style = self._personality.style_guide.strip()
        return f"{base}\n\n## Personality: {self._personality.name}\n\n{style}"

    def set_personality(self, personality_name: str) -> None:
        """Switch to a different personality mid-conversation."""
        self._personality = get_personality(personality_name)
        self._system_prompt = self._build_system_prompt()
        logger.info(f"Personality changed to: {self._personality.name}")
