# Ultra X2 — Robot SDK Wrapper + LLM Control

A project template for building applications on top of the **Ultra X2** humanoid
robot SDK, with a built-in **LLM control layer** (Claude) that turns natural-language
instructions into safe, validated robot actions.

```
┌─────────────┐   natural language    ┌──────────────────┐   tool calls   ┌────────────────┐
│   You / UI  │ ───────────────────▶  │  LLM Agent       │ ─────────────▶ │  UltraX2Robot  │
│             │ ◀─────────────────── │  (Claude + tools) │ ◀───────────── │  (SDK wrapper) │
└─────────────┘   responses/status    └──────────────────┘  action results └───────┬────────┘
                                                                                     │
                                                                            ┌────────▼────────┐
                                                                            │  Ultra X2 SDK   │
                                                                            │  (vendor lib)   │
                                                                            └─────────────────┘
```

## Layout

```
ultra_x2/
├── __init__.py
├── config.py            # Settings (env-driven)
├── robot.py             # UltraX2Robot — the wrapper around the vendor SDK
├── exceptions.py        # Typed errors
└── llm/
    ├── __init__.py
    ├── client.py        # Anthropic client factory
    ├── tools.py         # Robot capabilities exposed to the LLM as tools
    └── agent.py         # LLM ⇄ robot control loop (tool use)
main.py                  # Demo entry point
pyproject.toml           # Project metadata + dependencies (Poetry)
.env.example
```

## Why a wrapper?

The vendor SDK is wrapped behind `UltraX2Robot` so the rest of the codebase depends
on a stable, typed interface — not on vendor call signatures that change between
firmware/SDK versions. Swap the vendor calls in `ultra_x2/robot.py` only; nothing
downstream changes.

## Quick start

```bash
poetry install               # installs deps into a managed virtualenv
cp .env.example .env          # then fill in ANTHROPIC_API_KEY (and robot host)
poetry run ultra-x2           # runs in DRY_RUN mode by default — no real motion
# or: poetry run python main.py
```

> ⚠️ **Safety.** Physical actions (`walk`, `move_arm`, `set_posture`, …) are gated:
> by default the agent runs with `require_confirmation=True`, so each motion command
> is shown to you for approval before it reaches the robot. `DRY_RUN=true` (the
> default) additionally short-circuits all hardware calls so you can develop without
> a robot attached. Flip both off only when you're ready to drive real hardware.

## Filling in the vendor SDK

Every method in `ultra_x2/robot.py` has a `# TODO(vendor)` marker showing where the
real Ultra X2 SDK call goes. Replace the simulated bodies with the actual SDK and
delete the `DRY_RUN` short-circuits you no longer need.

## SSH into the robot

```bash
./scripts/ssh_robot.sh
```

Inside the robot shell, source the ROS environment before checking packages or LiDAR:

```bash
source /opt/ros/humble/setup.bash
source ~/Botifull/SLAM_stack/scripts/setup_env.sh
ros2 pkg list | grep -Ei 'lidar|slam|navigation|pointcloud|pcl'
ros2 topic list | grep -i lidar
ros2 topic info /aima/hal/sensor/lidar_chest_front/lidar_pointcloud -v
```
