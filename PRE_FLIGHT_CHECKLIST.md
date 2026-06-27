# Pre-Flight Checklist

Before testing voice control on the real robot, verify each step.

## 🛠️ Setup (One Time)

- [ ] Python 3.14+ installed: `python3 --version`
- [ ] Poetry installed: `poetry --version`
- [ ] API key set in `.env`: `grep ANTHROPIC_API_KEY .env` (not empty)
- [ ] Dependencies installed: `poetry lock && poetry install --extras voice`
- [ ] No error messages during install

## 🧪 DRY_RUN Mode (Safe, No Hardware)

Test the LLM and voice pipeline without hardware:

```bash
DRY_RUN=true poetry run python main.py
```

- [ ] Diagnostics pass (API key valid, dry-run enabled)
- [ ] Prompt: "DRY_RUN" appears in title
- [ ] Microphone activates (`🎤 listening…`)
- [ ] Speak: "stand up" → Whisper transcribes → Claude responds
- [ ] Response includes simulated action (no real motion)
- [ ] Can type `/personality curious` → personality switches
- [ ] "quit" exits cleanly

**Result:** Voice pipeline works. DRY_RUN validates STT + LLM + output.

## 📡 ROS 2 Discovery (Network Test)

Before live hardware, verify ROS 2 is discoverable:

```bash
# On the robot (via SSH):
ssh agi@<robot-ip>
source ~/Botifull/SLAM_stack/scripts/setup_env.sh
ros2 topic list | grep -E "(locomotion|audio|hand)"
ros2 service list | grep -E "(SetMcAction|PlayTts)"
```

- [ ] Topics are visible:
  - `/aima/mc/locomotion/velocity`
  - `/aima/hal/audio/capture`
  - `/aima/hal/joint/hand/command`
- [ ] Services are visible:
  - `/aimdk_5Fmsgs/srv/SetMcAction`
  - `/aimdk_5Fmsgs/srv/PlayTts`
  - `/aimdk_5Fmsgs/srv/SetMcInputSource`

**Result:** Robot's ROS 2 services are running and discoverable.

## 🎤 Audio Connection Test (Important)

Before running the voice agent, verify audio subscription works.

**Run this on the robot** (not on laptop):

```bash
# SSH into robot
ssh agi@<robot-ip>

# Source environment
source ~/Botifull/SLAM_stack/scripts/setup_env.sh

# Go to hackathon directory (wherever it is on robot)
cd /path/to/hackathon

# Run the test
poetry run python test_robot_audio.py 5
```

While running, **speak or make noise near the robot**.

- [ ] You see: `📍 Frame #1:`, `📍 Frame #2:`, etc.
- [ ] RMS values change when you speak (higher RMS = louder sound)
- [ ] After 5s: `✅ SUCCESS: Received N audio frames`

**Result:** Robot's microphone is broadcasting audio via ROS 2.

If it times out or fails, the microphone path isn't working yet. Check:
1. Is `/aima/hal/audio/capture` topic running on robot?
2. Are you on the robot (with ROS 2 sourced) when running the test?

## 🌐 Network Check

- [ ] Laptop is on same WiFi as robot (Bhargav or equivalent)
- [ ] Both systems are on same subnet: `ifconfig` on both, compare IP ranges
- [ ] Robot's IP is reachable: `ping <robot-ip>` (from laptop)
- [ ] SSH works: `ssh agi@<robot-ip>` (from laptop)

**Result:** Network is ready for ROS 2 DDS discovery.

## 🤖 Live Hardware (Read ALL before proceeding)

**CRITICAL SAFETY:** Read this entire section before proceeding.

### Pre-Test Safety
- [ ] Robot is on a safe surface (clear floor, no obstacles)
- [ ] You are standing clear of the robot (at least 2 meters away)
- [ ] Robot's battery is above 20% (check before starting)
- [ ] No people or pets near the robot during testing
- [ ] You have a clear path to power off the robot if needed

### Start with Text Mode (on laptop)
```bash
poetry run python main.py --dry-run
```
Test commands in simulation first (no hardware):
- [ ] Type: "stand up" → Claude responds (simulated)
- [ ] Type: "walk forward" → Claude responds (simulated, no actual motion)
- [ ] Confirm LLM understands basic commands

### Then Test Voice with Robot Microphone (on laptop)

**How it works:** Your laptop runs the voice loop, which connects to robot's audio via ROS 2 DDS auto-discovery (over WiFi).

```bash
DRY_RUN=false poetry run python main.py
```

First command: **just state queries, no motion**
- [ ] You see: `🎤 Will attempt robot's microphone (ROS 2) or fall back to your laptop mic…`
- [ ] You see: `🎤 listening…`
- [ ] Speak clearly: "what's your battery level?"
- [ ] Expected flow:
  - Whisper transcribes locally on your laptop
  - Claude asks robot for state via ROS 2
  - Robot responds (if ROS 2 connection works)
  - Claude speaks answer back
- [ ] **No motion should happen yet**
- [ ] Confirm: you heard the answer (battery %)

**If you hear "using your laptop's microphone instead":**
- Robot microphone couldn't connect via ROS 2 (network issue, ROS 2 not running, etc.)
- The voice pipeline still works (uses local laptop mic)
- You can still test LLM and motion commands
- Check robot's `/aima/hal/audio/capture` topic is running

### Then Test Single Motion (Posture Only)
Still with confirmation gates enabled (`REQUIRE_CONFIRMATION=true`):
- [ ] Speak: "stand up"
- [ ] Prompt appears: "⚠️ allow physical action set_posture(stand)? [y/N]"
- [ ] Type: `y`
- [ ] Watch robot: should transition to standing posture
- [ ] **Wait for motion to complete** (5-10 seconds)
- [ ] Confirm robot is now standing

### Test Stop
- [ ] Robot is standing (from previous test)
- [ ] Speak: "walk forward"
- [ ] Prompt: confirm motion
- [ ] Type: `y`
- [ ] Robot starts walking
- [ ] **Immediately speak: "stop"**
- [ ] Expected: robot halts, motion stops instantly
- [ ] Agent continues listening (doesn't exit)

### Test Small Walk
- [ ] Speak: "walk forward slowly for one second"
- [ ] Confirm motion
- [ ] Watch: robot should take a few small steps forward
- [ ] Speak: "stop"
- [ ] Robot halts

### Verify Fallback
Test graceful fallback to laptop mic:
- [ ] Disconnect from robot WiFi (or stop robot's ROS 2)
- [ ] Speak: "hello"
- [ ] Expected: "⚠️ ROS 2 not available, using your laptop's microphone"
- [ ] Voice loop continues with local mic
- [ ] LLM works (no robot commands available, but STT + LLM works)

## ✅ Full End-to-End (Optional, After Above)

Once single commands work:

```bash
poetry run python main.py
```

Sequence:
1. "stand up" → confirm → robot stands
2. "raise your right arm" → confirm → robot raises arm
3. "walk forward one meter" → confirm → robot walks
4. "stop" → robot stops, continues listening
5. "lower your arm" → confirm → robot lowers arm
6. "sit down" → confirm → robot sits
7. "goodbye" → loop exits

## 🚨 If Something Goes Wrong

### Robot Falls
- [ ] Immediately say "stop" or Ctrl+C
- [ ] Check agent system prompt (safety-first language in SYSTEM_PROMPT)
- [ ] Check robot's battery level
- [ ] Verify robot was in standing posture before motion

### ROS 2 Services Not Found
- [ ] Check robot's WiFi is on
- [ ] Verify same ROS_DOMAIN_ID (default=0, no config needed)
- [ ] Check `ros2 topic list` on robot shows services
- [ ] Restart robot's ROS 2 if needed

### Whisper Thinks English is Japanese
- [ ] Set `STT_LANGUAGE=en` in `.env`
- [ ] Or use larger model: `STT_MODEL=small`

### Microphone Not Working
- [ ] Check `System Preferences > Security & Privacy > Microphone` (macOS)
- [ ] Try: `poetry run ultra-x2-voice test.wav` (use a pre-recorded file)

## 📋 Summary

| Stage | Command | Safe? | Tests |
|-------|---------|-------|-------|
| DRY_RUN | `DRY_RUN=true poetry run python main.py` | ✅ Yes | STT, LLM, output |
| ROS 2 Discovery | `ros2 topic/service list` on robot | ✅ Yes | Network, services |
| State Query | "what's your battery?" | ✅ Yes | ROS 2 connection, LLM |
| Posture Change | "stand up" with confirm | ⚠️ Watch closely | First real motion |
| Stop | "stop" during motion | ⚠️ Critical | Safety override |
| Walking | "walk forward" with confirm | ⚠️ Stand clear | Main feature |

**Start with DRY_RUN, proceed step-by-step, test stop before any walking.**

---

**When everything passes:** The voice control is ready. Proceed to real-world testing or further refinement.
