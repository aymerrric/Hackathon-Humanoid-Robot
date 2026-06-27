# Audio Architecture: How Robot Microphone Works

## Overview

The robot has a built-in microphone that publishes audio via ROS 2. Your laptop can subscribe to this audio stream over the network and use it for voice recognition.

```
Robot (AgiBot X2)              Your Laptop
┌────────────────┐             ┌─────────────┐
│ Built-in Mic   │             │ Whisper STT │
│       ↓        │             │     ↑       │
│ ROS 2 Topic    │  ROS 2 DDS  │ rclpy       │
│ /aima/hal/     │◄──────────► │ subscriber  │
│ audio/capture  │   (WiFi)    │ to audio    │
└────────────────┘             └─────────────┘
```

## How It Works

1. **Robot publishes audio frames** continuously to `/aima/hal/audio/capture`
   - Format: 16 kHz, 16-bit PCM (S16_LE), multichannel
   - Rate: ~50 frames/sec (20ms per frame)

2. **Your laptop subscribes** via ROS 2 DDS auto-discovery
   - rclpy automatically finds the robot's topic on your network
   - Requires: same WiFi + same ROS_DOMAIN_ID (default=0)

3. **RobotMicrophone accumulates frames** with silence detection
   - Collects frames while you speak
   - Stops when it detects 0.6s of silence
   - Returns complete utterance (~1-3 seconds of audio)

4. **Whisper transcribes locally** on your laptop
   - No cloud, no API calls needed
   - Works offline

## Where to Run Voice Commands

### Primary Test: Run on Your Laptop
```bash
poetry run python main.py
```

This runs on your laptop and:
- Tries to connect to robot's audio via ROS 2
- Falls back to local laptop mic if ROS 2 unavailable
- Captures from whichever source is available

### Diagnostic Test: Run on Robot (Optional)
```bash
# SSH to robot
ssh agi@<robot-ip>
source ~/Botifull/SLAM_stack/scripts/setup_env.sh

# Run audio test
cd /path/to/hackathon
poetry run python test_robot_audio.py 5
```

This verifies the audio topic is publishing. You should see RMS values changing when you speak.

## Fallback Behavior

If ROS 2 is unavailable (no network, robot offline, etc.):

```
First attempt: RobotMicrophone (ROS 2)
          ↓
      (fails)
          ↓
Fallback: LocalRecorder (your laptop mic)
          ↓
Voice loop continues with laptop audio
```

Both sources produce the same output format (float32 PCM), so the rest of the pipeline is unaffected.

## Troubleshooting

| Problem | Cause | Check |
|---------|-------|-------|
| "using laptop mic instead" | ROS 2 not connecting | Robot's `/aima/hal/audio/capture` running? |
| Silent frames only | Microphone not capturing | Speak louder near robot's mic |
| Timeout waiting for audio | Topic not found | `ros2 topic list` on robot shows topic? |
| ROS 2 / aimdk_msgs error | Running test on laptop | Run test_robot_audio.py **on the robot** via SSH |

## Key Files

- **ultra_x2/speech/robot_microphone.py** — ROS 2 subscriber, frame accumulation, silence detection
- **ultra_x2/speech/recorder.py** — Local laptop mic (fallback)
- **test_robot_audio.py** — Diagnostic tool to verify audio topic
- **main.py** — Tries RobotMicrophone first, falls back if needed

## Network Requirements

✅ Both systems on same WiFi
✅ Both systems have same ROS_DOMAIN_ID (default=0)
✅ No firewall blocking UDP multicast (DDS discovery)

If on different networks, ROS 2 DDS discovery won't work (no mDNS). Would need manual ROS_MASTER_URI setup (more complex).

---

**When testing:** Just run `poetry run python main.py` on your laptop. It will automatically try to connect to the robot's audio and fall back gracefully if needed.
