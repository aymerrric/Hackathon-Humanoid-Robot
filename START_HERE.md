# Start Here: Voice Control Quick Test

You got the error `ROS 2 not installed` because ROS 2 isn't on your laptop yet. **Don't install it yet** — test the voice pipeline first in DRY_RUN mode.

## Step 1: Test Voice Pipeline (Right Now, 2 minutes)

This tests Whisper STT + Claude LLM without needing ROS 2 or the robot.

```bash
poetry run python main.py --dry-run
```

You'll see:
```
Ultra X2 agent [DRY_RUN] — model claude-opus-4-8, personality friendly.
🎤 Will attempt robot's microphone (ROS 2) or fall back to your laptop mic…
🎤 listening…
```

**Now speak a command:**
```
you (heard)> stand up and walk forward
x2 > I'll help you stand up and walk forward. Let me check the robot's current state first...
    [simulated motion - robot stands and walks in DRY_RUN]
```

✅ **Success**: If you can speak and Claude responds, your voice pipeline works.

### What This Tests
- ✅ Your microphone
- ✅ Whisper speech-to-text
- ✅ Claude LLM
- ✅ Response generation
- ✅ Voice output (macOS `say`)

## Step 2: Install ROS 2 (If You Want Robot Control)

After verifying voice works, install ROS 2 to control the real robot:

```bash
# macOS:
brew install ros

# Then source it before running:
source /opt/ros/humble/setup.bash
poetry run python main.py
```

## Step 3: Connect to Real Robot

Once ROS 2 is installed:
1. Connect your laptop to the same WiFi as the robot (Bhargav)
2. Run: `source /opt/ros/humble/setup.bash && poetry run python main.py`
3. Speak: "stand up"
4. Confirm the action when prompted
5. Watch the robot stand up

---

## Commands to Try (in DRY_RUN mode)

```
"stand up"                           → simulated standing
"walk forward one meter"             → simulated walking
"raise your right arm"               → simulated arm motion
"what's your battery level?"         → LLM queries state
"sit down"                           → simulated sitting
"/personality curious"               → switches personality
"quit"                               → exits
```

## If Something Goes Wrong

**"what language is this" error in Whisper?**
→ Set `STT_LANGUAGE=en` in `.env`

**Microphone not working?**
→ Check System Preferences > Security & Privacy > Microphone (macOS)

**Poetry install fails?**
→ Run: `poetry lock && poetry install --extras voice`

---

**Now run:** `poetry run python main.py --dry-run`

Once that works, come back to install ROS 2 for real robot control.
