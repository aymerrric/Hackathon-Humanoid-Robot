# Official AgiBot X2 SDK Alignment

This implementation is built against the **official AgiBot X2 ROS 2 SDK** patterns.
Reference: https://x2-aimdk.agibot.com/en/latest/index.html

## What we use from the official SDK

### ROS 2 Services (from aimdk_msgs)
✅ **SetMcAction** — mode/posture control
- Used by: `robot.set_posture()`
- Official action names: STAND_DEFAULT, SIT, CROUCH, PASSIVE_DEFAULT
- Sequence: must be stable standing before locomotion

✅ **SetMcInputSource** — registers input source before velocity commands
- Used by: `robot.walk()` (automatic registration)
- Critical: must call before publishing McLocomotionVelocity

✅ **PlayTts** — text-to-speech on robot speakers
- Used by: `robot.speak()`
- Follows official request/response structure

### ROS 2 Topics (pub/sub)
✅ **McLocomotionVelocity** — continuous velocity-based locomotion
- Used by: `robot.walk()`
- Publishers on: `/aima/mc/locomotion/velocity`
- Rate: 20Hz (timer period 0.02s)

✅ **HandCommandArray** — gripper/hand control
- Used by: `robot.move_arm()`
- Publishers on: `/aima/hal/joint/hand/command`

✅ **AudioCapture** — microphone input
- Subscribed by: `RobotMicrophone` (ultra_x2/speech/robot_microphone.py)
- Topic: `/aima/hal/audio/capture`
- Format: 16kHz, 16-bit PCM (S16_LE), multichannel

### Message Patterns
✅ **MessageHeader** with timestamps
- Automatically added by: `_RosNode._publish_velocity()`

✅ **RequestHeader** for service calls
- Automatically added by: `set_mc_action()`, `play_tts()`

### Service Call Retry Pattern
✅ **8 retries with 250ms timeout** (official pattern)
- Implemented in: `_RosNode._call_service_with_retry()`
- Matches SDK examples exactly

## Safety Features (Official Requirements)

### Standing Preparation Mode
✅ **Agent enforces standing before motion**
- System prompt: "If not standing, set_posture('stand') first"
- Before walk: `get_state()` → verify standing → then `walk()`
- Matches official docs requirement

### State Checking
✅ **get_state() before motion**
- Returns: posture, battery %, motion status
- LLM agent calls this before any motion command
- Official requirement: verify robot stability

### Stop Command
✅ **Immediate motion halt**
- `robot.stop()` → zero velocity (highest priority)
- Always available, no confirmation needed
- Matches official safety pattern

## What's Different (Intentional)

| Feature | Official SDK | Our Implementation | Reason |
|---------|--------------|-------------------|--------|
| Deployment | On-robot ROS 2 node | Laptop rclpy client | Python doesn't run on robot |
| Network | Local via ROS 2 Humble | Remote via ROS 2 DDS | DDS auto-discovers over WiFi |
| Input | Robot buttons, vision | Laptop microphone + Whisper | Add voice interface |
| LLM | None in SDK | Claude with tool-use | Add intelligence layer |

## Testing Against Official SDK

### 1. Verify Services Available
```bash
# On robot
ros2 service list | grep -E "(SetMcAction|PlayTts|SetMcInputSource)"
```

Should show:
```
/aimdk_5Fmsgs/srv/SetMcAction
/aimdk_5Fmsgs/srv/PlayTts
/aimdk_5Fmsgs/srv/SetMcInputSource
```

### 2. Verify Topics Available
```bash
# On robot
ros2 topic list | grep -E "(locomotion|audio|hand)"
```

Should show:
```
/aima/mc/locomotion/velocity
/aima/hal/audio/capture
/aima/hal/joint/hand/command
```

### 3. Test with Official Tools (optional)
```bash
# From robot, run an official SDK example in parallel with our agent
# Our commands should compose with official tools
```

## Deviations from Official SDK (None Critical)

- **Input source auto-registration**: We do this automatically in `walk()`, official SDK example shows explicit calls. Both work.
- **State tracking**: We maintain local state; official SDK may have more telemetry. For voice control, our simplified state is sufficient.
- **Joint limits**: We use conservative estimates; adjust ARM_PITCH_LIMITS in robot.py if needed.

## When to Use Official SDK Examples

For features beyond voice control, reference:
- https://x2-aimdk.agibot.com/en/latest/index.html — official examples
- Copy message construction patterns from there
- All service retry logic already implemented in _RosNode

## Summary

✅ This codebase is **fully aligned** with the official AgiBot X2 ROS 2 SDK.
✅ All critical safety patterns are implemented.
✅ ROS 2 interface is standard (services, topics, message types).
✅ Extensions (voice, LLM) layer on top without breaking compatibility.

If something doesn't work, check:
1. Robot's services are running (`ros2 service list` on robot)
2. Same WiFi + same ROS_DOMAIN_ID (default=0)
3. Official SDK examples for any SDK API differences
