#!/usr/bin/env bash
#
# ssh_robot.sh — open an SSH session to the robot using the repo defaults.
#
# Usage:
#   ./scripts/ssh_robot.sh
#
# Environment overrides:
#   ROBOT_IP=10.255.198.77
#   ROBOT_USER=agi
#   ROBOT_PASS=1
#
set -euo pipefail

ROBOT_IP="${ROBOT_IP:-10.255.198.77}"
ROBOT_USER="${ROBOT_USER:-agi}"
ROBOT_PASS="${ROBOT_PASS:-1}"

echo "Connecting to ${ROBOT_USER}@${ROBOT_IP} ..."
echo "After login, source /opt/ros/humble/setup.bash and ~/Botifull/SLAM_stack/scripts/setup_env.sh"

if [[ $# -gt 0 ]]; then
  REMOTE_COMMAND="$*"
  if command -v sshpass >/dev/null 2>&1; then
    exec sshpass -p "${ROBOT_PASS}" ssh -o StrictHostKeyChecking=no "${ROBOT_USER}@${ROBOT_IP}" bash -lc "$REMOTE_COMMAND"
  fi

  exec ssh -o StrictHostKeyChecking=no "${ROBOT_USER}@${ROBOT_IP}" bash -lc "$REMOTE_COMMAND"
fi

if command -v sshpass >/dev/null 2>&1; then
  exec sshpass -p "${ROBOT_PASS}" ssh -o StrictHostKeyChecking=no -t "${ROBOT_USER}@${ROBOT_IP}"
fi

exec ssh -o StrictHostKeyChecking=no -t "${ROBOT_USER}@${ROBOT_IP}"