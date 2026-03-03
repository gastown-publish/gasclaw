#!/usr/bin/env python3
"""Gastown status report — sends to the gastown Telegram topic.

Reports on BOTH:
- Gasclaw (the containerized maintainer)
- Gastown (the gt/ workspace inside container)
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error


def run(cmd, timeout=30):
    """Run a command and return stdout, or empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def pid_alive(pid_file):
    """Check if a PID file exists and the process is alive."""
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return None


def check_dolt_status():
    """Check if Dolt SQL server is running."""
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", "SELECT 1"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def check_process_running(pattern):
    """Check if a process matching pattern is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_gastown_beads(gt_path):
    """Get list of beads in gastown workspace."""
    beads = []
    try:
        for item in os.listdir(gt_path):
            if item.startswith("beads_"):
                bead_path = os.path.join(gt_path, item)
                if os.path.isdir(bead_path):
                    beads.append(item)
    except Exception:
        pass
    return sorted(beads)


def main():
    repo = os.environ.get("MAINTENANCE_REPO", "gastown-publish/gasclaw")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    group_id = os.environ.get("STATUS_GROUP_ID", "-1003759869133")
    thread_id = os.environ.get("STATUS_THREAD_ID", "114")

    if not bot_token:
        print("TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # --- Gather Gasclaw status ---
    open_prs_raw = run(["gh", "pr", "list", "--repo", repo, "--state", "open",
                        "--json", "number,title", "--limit", "10"])
    open_prs = json.loads(open_prs_raw) if open_prs_raw else []

    open_issues_raw = run(["gh", "issue", "list", "--repo", repo, "--state", "open",
                           "--json", "number,title", "--limit", "10"])
    open_issues = json.loads(open_issues_raw) if open_issues_raw else []

    # Maintenance state
    maint_status = "unknown"
    maint_cycle = "?"
    last_completed = "?"
    try:
        with open("/workspace/state/maintenance.json") as f:
            mstate = json.load(f)
        maint_status = mstate.get("status", "unknown")
        maint_cycle = str(mstate.get("cycle", "?"))
        lc = mstate.get("last_completed", "?")
        last_completed = lc[:19] if len(lc) > 19 else lc
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        pass

    # Claude Code agent status
    claude_pid = pid_alive("/workspace/state/claude.pid")
    claude_status = f"running (PID {claude_pid})" if claude_pid else "stopped"

    # Gateway status
    gw_pid = pid_alive("/workspace/state/gateway.pid")
    gw_status = f"running (PID {gw_pid})" if gw_pid else "stopped"

    # Test results
    test_summary = "unknown"
    try:
        with open("/workspace/logs/test-results.log") as f:
            lines = f.readlines()
        if lines:
            last_line = lines[-1].strip()
            import re
            m = re.search(r"\d+ passed.*", last_line)
            if m:
                test_summary = m.group(0)
    except FileNotFoundError:
        pass

    # Recent commits
    recent_commits = []
    commits_raw = run(["git", "-C", "/workspace/gasclaw", "log", "--oneline",
                       "-5", "--format=%h %s"])
    if commits_raw:
        recent_commits = [c for c in commits_raw.split("\n") if c.strip()]

    # --- Gather Gastown status (inside container) ---
    gt_path = "/workspace/gt"
    gastown_available = os.path.isdir(gt_path)
    
    dolt_running = False
    gt_beads = []
    gt_daemon_running = False
    
    if gastown_available:
        # Check Dolt
        dolt_running = check_dolt_status()
        
        # Check beads
        gt_beads = get_gastown_beads(gt_path)
        
        # Check daemon
        gt_daemon_running = check_process_running("gt daemon run")

    # --- Build message ---
    lines = ["📊 *Gasclaw + Gastown Status*", ""]

    # Gasclaw section
    lines.append("*🐾 Gasclaw:*")
    lines.append(f"  🤖 Claude: {claude_status}")
    lines.append(f"  🌐 Gateway: {gw_status}")
    lines.append(f"  🔄 Maint: {maint_status} (#{maint_cycle})")
    lines.append("")

    # Gastown section
    lines.append("*🏘️ Gastown (in container):*")
    if gastown_available:
        dolt_icon = "✅" if dolt_running else "❌"
        daemon_icon = "✅" if gt_daemon_running else "❌"
        
        lines.append(f"  🗄️ Dolt SQL: {dolt_icon}")
        lines.append(f"  👹 Daemon: {daemon_icon}")
        lines.append(f"  📿 Beads: {len(gt_beads)}")
        if gt_beads[:3]:
            lines.append(f"    _{', '.join(gt_beads[:3])}{'...' if len(gt_beads) > 3 else ''}_")
    else:
        lines.append("  ⚠️ Not initialized")
    lines.append("")

    # Tests
    lines.append(f"*🧪 Tests:* {test_summary}")
    lines.append("")

    # PRs
    lines.append(f"*📥 Open PRs ({len(open_prs)}):*")
    for pr in open_prs[:3]:
        title = pr['title'].replace('_', '\\_').replace('*', '\\*')[:40]
        lines.append(f"  • #{pr['number']} {title}{'...' if len(pr['title']) > 40 else ''}")
    if not open_prs:
        lines.append("  None")
    lines.append("")

    # Issues
    lines.append(f"*🐛 Open Issues ({len(open_issues)}):*")
    for issue in open_issues[:3]:
        title = issue['title'].replace('_', '\\_').replace('*', '\\*')[:40]
        lines.append(f"  • #{issue['number']} {title}{'...' if len(issue['title']) > 40 else ''}")
    if not open_issues:
        lines.append("  None")

    msg = "\n".join(lines)

    # --- Send ---
    payload = json.dumps({
        "chat_id": group_id,
        "message_thread_id": int(thread_id),
        "parse_mode": "Markdown",
        "text": msg,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("ok"):
            print("Status sent")
        else:
            print(f"API error: {result}", file=sys.stderr)
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
