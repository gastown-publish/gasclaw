#!/bin/bash
# Persistent AIS Gateway Watchdog — FULLY INDEPENDENT of OpenClaw gateway.
# Runs in its own tmux session. Uses kimi-cli (via ais) and direct Telegram API.
# Never depends on the gateway for monitoring or notifications.
set -uo pipefail

LOG="/workspace/logs/gateway-watchdog.log"
STATE="/workspace/state"
STALE_THRESHOLD="${GATEWAY_STALE_THRESHOLD:-300}"
CHECK_INTERVAL="${WATCHDOG_INTERVAL:-120}"
CHAT_ID="${TELEGRAM_CHAT_ID:--1003759869133}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
DOCTOR_TOPIC="477"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [watchdog] $*" | tee -a "$LOG"; }

# Direct Telegram API — does NOT use OpenClaw gateway
notify() {
    local msg="$1"
    local topic="${2:-$DOCTOR_TOPIC}"
    curl -sf --max-time 10 \
        "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d message_thread_id="${topic}" \
        -d parse_mode="HTML" \
        -d text="$msg" > /dev/null 2>&1 || true
}

# Restart gateway — does NOT depend on gateway being up
restart_gateway() {
    local reason="$1"
    log "Gateway $reason — restarting"
    pkill -f "openclaw-gateway" 2>/dev/null || true
    sleep 3
    openclaw doctor --fix --yes >> "$LOG" 2>&1 || true
    nohup openclaw gateway run >> /workspace/logs/openclaw-gateway.log 2>&1 &
    local new_pid=$!
    echo "$new_pid" > "$STATE/gateway.pid"
    log "Gateway restarted (PID $new_pid)"
    notify "<b>Watchdog:</b> Gateway restarted. Reason: ${reason}"
}

# Spawn kimi-cli agent via AIS — does NOT depend on gateway
spawn_doctor_agent() {
    local reason="$1"
    log "Spawning AIS doctor agent (gateway-independent): $reason"

    # Don't spawn if one is already running
    if ais ls 2>/dev/null | grep -q "watchdog-doctor"; then
        log "Doctor agent already running — skipping spawn"
        return
    fi

    # The doctor agent uses kimi-cli directly, NOT the OpenClaw gateway.
    # It has shell access and can restart/fix anything.
    local prompt="You are the gasclaw infrastructure doctor. You run via kimi-cli, INDEPENDENT of the OpenClaw gateway.

Issue: ${reason}

Read /opt/knowledge/ for system docs. Then diagnose and fix:

STEP 1 — Check if gateway needs restart:
  pgrep -f openclaw-gateway || echo DEAD
  If dead: pkill -f openclaw-gateway; sleep 2; openclaw doctor --fix --yes; nohup openclaw gateway run >> /workspace/logs/openclaw-gateway.log 2>&1 &

STEP 2 — Check Dolt:
  dolt sql -q 'SELECT 1' 2>&1
  If dead: cd /workspace/gt && nohup dolt sql-server --config .dolt-data/config.yaml >> /workspace/logs/dolt.log 2>&1 &

STEP 3 — Check Gastown:
  pgrep -f 'gt daemon' || echo DEAD
  gt status 2>&1
  If dead: cd /workspace/gt && nohup gt up >> /workspace/logs/gastown.log 2>&1 &

STEP 4 — Check tmux sessions:
  tmux ls

STEP 5 — Check logs:
  tail -30 /workspace/logs/openclaw-gateway.log
  tail -10 /workspace/logs/gateway-watchdog.log

STEP 6 — Log in beads:
  export BD_ROOT=/workspace/beads/doctor
  bd new 'issue: ${reason}' --body 'details of diagnosis and fix'

STEP 7 — Report via DIRECT Telegram API (NOT OpenClaw sendMessage):
  curl -s 'https://api.telegram.org/bot${BOT_TOKEN}/sendMessage' -d chat_id='${CHAT_ID}' -d message_thread_id='${DOCTOR_TOPIC}' -d text='your concise summary'

IMPORTANT: You do NOT depend on the OpenClaw gateway. Use shell commands and direct API calls only."

    ais create watchdog-doctor -a kimi -A 1 \
        -d /workspace/gasclaw \
        --yolo \
        -c "$prompt" 2>> "$LOG" || {
        log "Failed to spawn AIS doctor — falling back to direct restart"
        restart_gateway "$reason"
    }
}

check_gateway() {
    local gw_pid
    gw_pid=$(pgrep -f "openclaw-gateway" 2>/dev/null | head -1)

    if [ -z "$gw_pid" ]; then
        log "Gateway process NOT FOUND"
        # FIRST: restart immediately (fast, no dependency)
        restart_gateway "process not found"
        # THEN: spawn doctor for deeper diagnosis
        spawn_doctor_agent "Gateway was dead — restarted, but need root cause analysis"
        return 1
    fi

    local gw_log="/workspace/logs/openclaw-gateway.log"
    if [ -f "$gw_log" ]; then
        local last_mod
        last_mod=$(stat -c %Y "$gw_log" 2>/dev/null || echo 0)
        local now
        now=$(date +%s)
        local age=$((now - last_mod))
        if [ "$age" -gt "$STALE_THRESHOLD" ]; then
            log "Gateway log stale (${age}s > ${STALE_THRESHOLD}s)"
            # Kill stale gateway and restart
            restart_gateway "log stale for ${age}s — frozen"
            spawn_doctor_agent "Gateway was frozen (no log activity for ${age}s) — restarted, investigating"
            return 1
        fi
    fi

    return 0
}

check_dolt() {
    if ! pgrep -f "dolt sql-server" > /dev/null 2>&1; then
        log "Dolt not running — spawning doctor"
        spawn_doctor_agent "Dolt SQL server not running"
        return 1
    fi
    return 0
}

check_gastown() {
    if ! pgrep -f "gt daemon" > /dev/null 2>&1; then
        log "Gastown daemon not running — spawning doctor"
        spawn_doctor_agent "Gastown daemon (gt) not running"
        return 1
    fi
    return 0
}

cleanup_old_doctors() {
    if ais ls 2>/dev/null | grep -q "watchdog-doctor"; then
        ais kill watchdog-doctor 2>/dev/null || true
        log "Cleaned up old doctor session"
    fi
}

# Main loop
log "=== Persistent AIS Watchdog started (interval=${CHECK_INTERVAL}s) ==="
log "=== GATEWAY-INDEPENDENT: uses kimi-cli + direct Telegram API ==="
notify "<b>Watchdog:</b> Persistent AIS gateway watchdog started (independent of gateway)"

cycle=0
while true; do
    cycle=$((cycle + 1))
    echo "$cycle" > "$STATE/watchdog-cycle"

    # Every 10 cycles, clean up old doctor sessions
    if [ $((cycle % 10)) -eq 0 ]; then
        cleanup_old_doctors
    fi

    # Run checks (all gateway-independent)
    check_gateway
    check_dolt
    check_gastown

    # Every 30 cycles (~1h), post a heartbeat via direct Telegram API
    if [ $((cycle % 30)) -eq 0 ]; then
        gw_status="unknown"
        pgrep -f "openclaw-gateway" > /dev/null 2>&1 && gw_status="running" || gw_status="DOWN"
        dolt_status="unknown"
        pgrep -f "dolt sql-server" > /dev/null 2>&1 && dolt_status="running" || dolt_status="DOWN"
        gt_status="unknown"
        pgrep -f "gt daemon" > /dev/null 2>&1 && gt_status="running" || gt_status="DOWN"
        tmux_count=$(tmux ls 2>/dev/null | wc -l)

        notify "<b>Watchdog Heartbeat</b> (cycle $cycle)
Gateway: $gw_status
Dolt: $dolt_status
Gastown: $gt_status
Tmux sessions: $tmux_count"
    fi

    sleep "$CHECK_INTERVAL"
done
