#!/usr/bin/env bash
#
# change_face.sh — connect to the AgiBot X2 over WiFi and change its face (emoji).
#
# It SSHes into the robot (which already runs ROS 2 + the face_ui service) and
# calls the /face_ui_proxy/play_emoji service there.
#
# Usage:
#   ./scripts/change_face.sh                # default: happy (90), play once
#   ./scripts/change_face.sh 200            # adore
#   ./scripts/change_face.sh 180 2          # angry, looping
#
# Emotion IDs (from PlayEmoji.srv):
#   1 blink   60 bored   70 abnormal   80 sleepy   90 happy   100 very-happy
#   110 sad   130 confused   140 shock   160 serious   170 thinking
#   180 angry   190 double-angry   200 adore   210 double-adore   220 charging
# Mode: 1 = play once, 2 = loop.
#
set -euo pipefail

# --- config (edit if needed) ----------------------------------------------
ROBOT_IP="${ROBOT_IP:-10.255.198.77}"
ROBOT_USER="${ROBOT_USER:-agi}"      # <-- change if SSH login fails
ROBOT_PASS="${ROBOT_PASS:-1}"
# ---------------------------------------------------------------------------

EMOTION_ID="${1:-90}"   # default: happy
MODE="${2:-1}"          # default: play once
PRIORITY="${3:-10}"

# The command we run *on the robot*. Tries to source ROS 2 + the aimdk overlay
# from common locations, then calls the face service.
REMOTE_CMD=$(cat <<EOF
set -e
# The robot's aimdk_msgs install has a non-standard layout, so its own
# setup.bash registers nothing. setup_env.sh is the wrapper that fixes that
# and brings in the aimdk_msgs types + ROS 2 env (it's what ~/.bashrc sources).
source ~/Botifull/SLAM_stack/scripts/setup_env.sh
echo "Calling face service: emotion=${EMOTION_ID} mode=${MODE} priority=${PRIORITY}"
# Filter out FastDDS/RTPS connect/disconnect spam so the real response is visible.
ros2 service call /face_ui_proxy/play_emoji aimdk_msgs/srv/PlayEmoji \
  "{emotion_id: ${EMOTION_ID}, mode: ${MODE}, priority: ${PRIORITY}}" 2>&1 \
  | grep -vE "RTPS_|Stateful|Stateless|matched_(reader|writer)|Reader Proxy|Writer proxy|Remote Reader"
EOF
)

echo "Connecting to ${ROBOT_USER}@${ROBOT_IP} ..."

if command -v sshpass >/dev/null 2>&1; then
  sshpass -p "${ROBOT_PASS}" ssh -o StrictHostKeyChecking=no \
    "${ROBOT_USER}@${ROBOT_IP}" "${REMOTE_CMD}"
else
  echo "(sshpass not installed — you'll be prompted for the password: ${ROBOT_PASS})"
  echo "  tip: 'brew install hudochenkov/sshpass/sshpass' to automate it."
  ssh -o StrictHostKeyChecking=no "${ROBOT_USER}@${ROBOT_IP}" "${REMOTE_CMD}"
fi
