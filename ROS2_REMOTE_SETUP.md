# ROS 2 Remote Connection Setup

Your laptop runs the voice agent and connects to the robot's ROS 2 services **over the network**.

## Architecture

```
Your Laptop                              Robot (AgiBot X2)
┌─────────────────────────┐             ┌──────────────────────┐
│ poetry run python       │             │ ROS 2 Humble        │
│   - Whisper STT         │             │ - aimdk_msgs        │
│   - Claude LLM          │             │ - Services:         │
│   - rclpy (client)      │ ◄──ROS 2──► │   SetMcAction       │
│   - Your microphone      │    DDS     │   SetMcInputSource  │
│   - Hand control        │  Discovery │   PlayTts           │
│                         │             │ - Topics:           │
│                         │             │   /aima/hal/audio/  │
│                         │             │   /aima/mc/         │
└─────────────────────────┘             └──────────────────────┘
```

## Requirements

✅ **Same WiFi network** — both systems on Bhargav (or bridged)
✅ **Same ROS_DOMAIN_ID** — default is 0 (no config needed)
✅ **ROS 2 Humble on robot** — already installed
✅ **ROS 2 Humble on laptop** — needed for rclpy to work (install from https://docs.ros.org/en/humble/Installation/)
   - macOS: `brew install ros` (via Homebrew)
   - Linux: Follow official docs
   - Windows: WSL2 + ROS 2
✅ **Before running:** `source /opt/ros/humble/setup.bash`

## How it works

1. **ROS 2 DDS Discovery**: When you run `poetry run python main.py`, rclpy initializes
2. **Service/Topic Discovery**: Your laptop's rclpy automatically discovers:
   - Robot's services: `/SetMcAction`, `/PlayTts`, etc.
   - Robot's topics: `/aima/hal/audio/capture`, `/aima/mc/locomotion/velocity`
3. **Remote Calls**: When the agent calls a service, it goes over the network to the robot
4. **Voice Control**: Your microphone → transcribe locally → LLM → robot commands

## Testing the connection

Before running the full voice agent, verify ROS 2 discovery:

### Option 1: Install ROS 2 locally on laptop (optional)
```bash
# If you want to verify connection before running the agent
# (Not required for the voice agent to work)
source /opt/ros/humble/setup.bash
ros2 topic list
# Should show robot's topics like /aima/hal/audio/capture
```

### Option 2: Just run and check logs
```bash
poetry run python main.py
```
If rclpy connects successfully, you'll see:
```
INFO ultra_x2.robot: Connected via SSH to agi@10.104.218.77:22
🎤 Will attempt robot's microphone (ROS 2) or fall back to your laptop mic…
```

Then listen for audio. If successful:
```
🎤 listening…
(speak something)
you (heard)> [transcription]
x2 > [response]
```

## Troubleshooting

**"ROS 2 / aimdk_msgs not available"**
→ You're not on the robot, so it falls back to your laptop mic. This is expected.

**Robot's services not discovered**
→ Check:
1. Both on same WiFi: `ifconfig` on both, verify same subnet
2. Both have same ROS_DOMAIN_ID: (default=0, should work)
3. Robot's ROS 2 is running: `ssh agi@robot` then `ros2 topic list`

**Voice gets stuck waiting for robot**
→ ROS 2 discovery can take 10-30 seconds on first connection. Be patient.

## How robot.py uses remote ROS 2

The updated `ultra_x2/robot.py` creates an rclpy node that:
- **Connects to services** via network: `SetMcAction`, `SetMcInputSource`, `PlayTts`
- **Publishes to topics** over network: `/aima/mc/locomotion/velocity`, `/aima/hal/joint/hand/command`
- **Subscribes to topics** over network: `/aima/hal/audio/capture` (for microphone)

All of this happens automatically via ROS 2 DDS — no SSH, no manual networking needed.

## Network architecture notes

- **DDS (Data Distribution Service)** handles all discovery automatically
- Each system publishes its available services/topics
- Your laptop's rclpy finds them via UDP multicast (on same network)
- Calls go directly robot→laptop, no central broker needed
- Works on WiFi, ethernet, or any local network with mDNS

## Security note

ROS 2 Humble DDS is **not encrypted by default** on local networks. For this hackathon, that's fine. In production, use ROS 2 Security.
