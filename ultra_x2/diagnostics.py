"""SSH connectivity diagnostics for the robot.

Tests reachability before entering the chat loop so connection failures
surface clearly instead of mysteriously during the first command.
"""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def test_ssh_connectivity(
    host: str,
    user: str,
    port: int = 22,
    timeout_s: int = 8,
    password: str | None = None,
) -> tuple[bool, str]:
    """Test SSH connectivity to the robot.

    Returns (success, message). Message explains what worked or what failed.
    """
    # First: raw socket connectivity (is the host reachable at all?)
    try:
        sock = socket.create_connection((host, port), timeout=timeout_s)
        sock.close()
        socket_ok = True
    except (socket.timeout, socket.error) as exc:
        return False, f"Cannot reach {host}:{port} (socket timeout/error: {exc})"

    # Second: SSH login attempt. Use sshpass if available to send password non-interactively.
    # Fall back to a non-interactive ssh attempt (keys only) if no sshpass.
    if password and shutil.which("sshpass"):
        cmd = [
            "sshpass",
            "-p", password,
            "ssh",
            "-o", f"ConnectTimeout={timeout_s}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(port),
            "-T",
            f"{user}@{host}",
            "echo OK",
        ]
    else:
        # Fallback: SSH with public key only (no password prompt in BatchMode)
        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={timeout_s}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(port),
            "-T",
            f"{user}@{host}",
            "echo OK",
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 2)
        if result.returncode == 0 and "OK" in result.stdout:
            return True, f"✅ SSH {user}@{host}:{port} is reachable and responsive."
        else:
            stderr = result.stderr.strip() or result.stdout.strip()
            return False, f"SSH login failed: {stderr}"
    except subprocess.TimeoutExpired:
        return False, f"SSH to {host}:{port} timed out ({timeout_s}s)"
    except FileNotFoundError:
        return False, "ssh binary not found. Install OpenSSH client."
    except Exception as exc:  # noqa: BLE001
        return False, f"SSH diagnostic error: {exc}"


def diagnose(settings: Any) -> tuple[bool, str]:
    """Run full diagnostics. Return (all_ok, summary_message)."""
    lines = []

    # API key
    if settings.anthropic_api_key:
        lines.append("✅ ANTHROPIC_API_KEY is set")
    else:
        lines.append("❌ ANTHROPIC_API_KEY is NOT set (see .env.example)")

    # DRY_RUN mode
    if settings.dry_run:
        lines.append("ℹ️  DRY_RUN mode: no hardware commands will execute")
    else:
        # Only test SSH if not in dry-run
        lines.append("🔍 Testing SSH connectivity to the robot…")
        ok, msg = test_ssh_connectivity(
            host=settings.robot_host,
            user=settings.robot_user,
            port=settings.robot_ssh_port,
            timeout_s=settings.robot_ssh_timeout_s,
            password=settings.robot_password,
        )
        lines.append(f"  {msg}")
        if not ok:
            return False, "\n".join(lines)

    lines.append(f"🤖 Robot: {settings.robot_host}:{settings.robot_ssh_port}")
    lines.append(f"🧠 LLM: {settings.llm_model}")
    lines.append(f"🎤 STT: {settings.stt_model} (language: {settings.stt_language or 'auto'})")
    lines.append("")

    return True, "\n".join(lines)


def main() -> int:
    """Run diagnostics and print the report."""
    from ultra_x2.config import load_settings
    settings = load_settings()
    ok, msg = diagnose(settings)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
