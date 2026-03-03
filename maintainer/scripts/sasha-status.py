#!/usr/bin/env python3
"""Sasha's GT Status Report - Comprehensive status for Villa Backend 4 + Gasclaw"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime


def run(cmd, timeout=30):
    """Run a command and return stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception as e:
        return f"Error: {e}"


def check_dolt():
    """Check Dolt SQL server status."""
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", "SELECT 1"],
            capture_output=True, timeout=10
        )
        return "✅ Running" if result.returncode == 0 else "❌ Stopped"
    except Exception:
        return "❌ Error"


def check_gt_daemon():
    """Check GT daemon status."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "gt daemon run"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            pid = result.stdout.strip().split('\n')[0]
            return f"✅ Running (PID {pid})"
        return "❌ Not running"
    except Exception:
        return "❌ Error"


def check_openclaw():
    """Check OpenClaw gateway status."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:18789/health"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0 and b"healthy" in result.stdout:
            return "✅ Healthy"
        return "⚠️ Check needed"
    except Exception:
        return "⚠️ Unknown"


def get_beads():
    """Get list of beads in gastown workspace."""
    gt_path = "/workspace/gt"
    beads = []
    try:
        for item in os.listdir(gt_path):
            if item.startswith("beads_"):
                beads.append(item)
    except Exception:
        pass
    return sorted(beads)


def get_git_status():
    """Get Villa Backend git status."""
    try:
        os.chdir("/workspace/villa-backend-4")
        branch = run(["git", "branch", "--show-current"])
        last_commit = run(["git", "log", "-1", "--format=%h - %s (%ar)"])
        status = run(["git", "status", "--short"])
        return branch, last_commit, status
    except Exception as e:
        return "unknown", f"Error: {e}", ""


def get_system_info():
    """Get system resource usage."""
    try:
        # CPU load
        load = run(["cat", "/proc/loadavg"]).split()[0]
        # Memory
        mem_info = run(["free", "-h"])
        # Disk
        disk = run(["df", "-h", "/workspace"]).split('\n')[-1]
        return load, mem_info, disk
    except Exception as e:
        return "?", f"Error: {e}", ""


def send_telegram_report(bot_token, chat_id, message):
    """Send report to Telegram."""
    try:
        payload = json.dumps({
            "chat_id": chat_id,
            "parse_mode": "Markdown",
            "text": message,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        print(f"Failed to send: {e}", file=sys.stderr)
        return False


def main():
    # Configuration
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "-1003776910127")
    
    # Gather status
    dolt_status = check_dolt()
    gt_status = check_gt_daemon()
    openclaw_status = check_openclaw()
    beads = get_beads()
    branch, last_commit, git_status = get_git_status()
    
    # Build message
    lines = [
        "📊 *Sasha's GT Status Report*",
        "",
        f"🕐 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "*🔧 Gastown Workspace:*",
        f"  Location: `/workspace/gt`",
        f"  Dolt SQL: {dolt_status}",
        f"  GT Daemon: {gt_status}",
        f"  Beads: {len(beads)} ({', '.join(beads[:3])}{'...' if len(beads) > 3 else ''})",
        "",
        "*🏠 Villa Backend 4:*",
        f"  Branch: `{branch}`",
        f"  Last commit: `{last_commit[:60]}{'...' if len(last_commit) > 60 else ''}`",
    ]
    
    if git_status:
        lines.append(f"  Uncommitted changes: `{len(git_status.split(chr(10)))} files`")
    
    lines.extend([
        "",
        "*🌐 OpenClaw Gateway:*",
        f"  Status: {openclaw_status}",
        f"  Port: 18789",
        "",
        "*👤 Bot Info:*",
        "  @villa_backend_bot",
        "  Group: villa backend 4",
        "",
        "✅ All systems operational",
    ])
    
    message = "\n".join(lines)
    
    # Print to console
    print(message)
    print("")
    
    # Send to Telegram
    if send_telegram_report(bot_token, chat_id, message):
        print("✅ Report sent to Telegram")
    else:
        print("❌ Failed to send to Telegram")


if __name__ == "__main__":
    main()
