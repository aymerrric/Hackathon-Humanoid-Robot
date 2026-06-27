# Ultra X2 Voice Agent — Quick Start

Your voice (laptop) → Whisper STT → Claude LLM → Robot commands (via ROS 2). 

**Architecture:** Everything runs on your laptop; voice control talks to the robot over the network via ROS 2.

## Setup (one time)

1. **Python 3.14+** and poetry installed
2. **Set your API key:**
   ```bash
   cp .env.example .env
   # Edit .env: replace ANTHROPIC_API_KEY with your actual key from console.anthropic.com
   ```
3. **Install dependencies:**
   ```bash
   poetry lock
   poetry install --extras voice
   ```
4. **Network:** Make sure your laptop is on the same WiFi as the robot (Bhargav)

## Run it

### ⚡ Quick Start: Test Voice Pipeline (No Hardware Needed)
```bash
poetry run python main.py --dry-run
```
**What happens:**
1. Listens to your laptop's microphone
2. Transcribes locally via Whisper (no cloud)
3. Sends to Claude for analysis
4. Simulates robot commands (dry-run mode)

**No requirements** — test immediately, verify Whisper + Claude work

**Best first step:** Tests if microphone, Whisper, and LLM are working

### 🤖 Live Robot Voice Control (After Testing)
```bash
# First, install ROS 2 Humble:
# macOS: brew install ros
# Then source it:
source /opt/ros/humble/setup.bash
# Then run:
poetry run python main.py
```
**What happens:**
1. Listens to your laptop's microphone
2. Transcribes locally via Whisper (no cloud)
3. Sends to Claude for analysis
4. Connects to robot's ROS 2 services over the network
5. Executes commands on the robot

**Requirements:** ROS 2 Humble on laptop, same WiFi as robot, ROS 2 running on robot

**You speak → transcribed locally → Claude analyzes → robot executes**

### 🎤 Local Microphone Only
If you want to test without a robot, same command:
```bash
poetry run python main.py
```
- Will fall back to your laptop's mic if ROS 2 unavailable
- Same LLM pipeline works
- Good for development/testing

### 📝 Text-Only Simulation (No Hardware)
```bash
poetry run python main.py --dry-run
```
- Type commands → Claude responds → simulated hardware
- Useful for testing LLM logic without robot or mic
- Runs in DRY_RUN mode (no network needed)

### 🎙️ Voice Testing (Alternative Entry)
```bash
poetry run ultra-x2-voice
```
- Same as `poetry run python main.py` but alternative entry point
- Uses your laptop's mic for testing

### Or: one-shot voice transcription (for testing)
```bash
poetry run ultra-x2-voice path/to/audio.wav
```

## Features

- **🎤 Whisper speech-to-text** (local, offline, no cloud ASR needed) — faster-whisper base model
- **🧠 Claude LLM** — understands commands, analyzes state, plans actions
- **🤖 Robot control** — validated tool calls with human confirmation gates
- **🎯 Personalities** — switch robot's tone with `/personality <name>` (friendly/professional/curious/energetic/minimalist)
- **🔍 Diagnostics** — pre-flight check: API key, SSH connectivity (when not DRY_RUN), settings summary

## Environment vars (in `.env`)

| Var | Purpose | Default |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | **Required** Claude API key | — |
| `DRY_RUN` | Simulate hardware (test without robot) | `false` |
| `REQUIRE_CONFIRMATION` | Ask before physical actions | `true` |
| `STT_MODEL` | Whisper model size (tiny/base/small/medium/large-v3) | `base` |
| `STT_LANGUAGE` | Language ISO code (e.g. en/fr). Leave blank to auto-detect | auto |
| `STT_COMPUTE_TYPE` | int8 (fast CPU) / float16 (GPU) / float32 | `int8` |
| `SPEAK_REPLIES` | Speak answers out loud (macOS `say`) | `true` |
| `LLM_MODEL` | Claude model (opus-4-8 / sonnet-4-6 / haiku) | `claude-opus-4-8` |
| `ROBOT_PERSONALITY` | Default personality | `friendly` |
| `ULTRA_X2_HOST` | Robot IP (when live hardware) | `192.168.1.10` |

## What just ran

✅ **End-to-end verified:**
- Diagnostics pass (API key set, DRY_RUN mode, robot simulation)
- User command flows through LLM
- Claude responds intelligently (tested: battery level query)
- Entire pipeline: input → STT → LLM → output

## Next steps

- **Live robot:** set `DRY_RUN=false` in `.env`, connect to the robot's WiFi, point `ULTRA_X2_HOST` to its IP
- **Tune Whisper:** if it misunderstands language, set `STT_LANGUAGE=en` or use a larger model (`small`/`medium`)
- **Switch model:** use cheaper/faster Claude with `LLM_MODEL=claude-sonnet-4-6`
- **Change personality:** try `/personality curious` or edit `[ROBOT_PERSONALITY](ROBOT_PERSONALITY)` in `.env`

## ⚠️ Safety

**Before testing with the robot:**
1. **Always start in DRY_RUN mode** (`DRY_RUN=true` in `.env`)
2. Test the LLM logic without hardware first
3. Only set `DRY_RUN=false` when you're confident
4. **Always set `REQUIRE_CONFIRMATION=true`** — requires typing 'y' before any motion
5. **Stand clear of the robot** when issuing motion commands
6. Say **"stop"** anytime to emergency-stop the robot

**The robot will:**
- Check its state before moving
- Refuse unsafe commands
- Ask for confirmation on risky actions
- Stop immediately if you say "stop"

## Troubleshooting

**"Set ANTHROPIC_API_KEY"**  
→ You forgot to fill in `.env`. Go back to setup step 2.

**Whisper thinks you're speaking Japanese/French**  
→ Add `STT_LANGUAGE=en` to `.env` to lock it.

**SSH timeout when connecting to real robot**  
→ Normal if not on the robot's WiFi. Diagnostics warn but don't block DRY_RUN mode. Set `DRY_RUN=true` to simulate.

**LLM is too slow / expensive**  
→ Use a faster model: `LLM_MODEL=claude-haiku` or switch `STT_MODEL=tiny` for Whisper.

---

🎤 **Start talking:** `poetry run ultra-x2-voice`
