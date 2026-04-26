"""Startup orchestration for gasclaw.

Bootstrap sequence:
 1. Setup Kimi accounts
 2. Configure git/dolt identity (required for gt install)
 3. Start Dolt (required for gt rig add)
 4. Initialize Dolt rig (gt dolt init-rig)
 5. Install Gastown (gt install + gt rig add --adopt --url)
 6. Configure agent (gt config agent set + default-agent)
 7. Configure OpenClaw
 8. Install skills
 9. Run openclaw doctor
10. Start OpenClaw gateway
11. Start gt daemon
12. Start Mayor
13. Send "Gasclaw is up" via Telegram

Rollback on failure:
- If bootstrap fails at any step, previously started services are stopped
and a failure notification is sent.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from gasclaw.config import GasclawConfig
from gasclaw.gastown.agent_config import configure_agent
from gasclaw.gastown.installer import gastown_install, setup_git_identity, setup_kimi_accounts
from gasclaw.gastown.lifecycle import start_daemon, start_dolt, start_mayor, stop_all
from gasclaw.health import check_agent_activity, check_health
from gasclaw.kimigas.key_pool import KeyPool
from gasclaw.kimigas.proxy import build_claude_env, write_claude_config
from gasclaw.logging_config import get_logger
from gasclaw.openclaw.auth import get_gateway_auth_token
from gasclaw.openclaw.doctor import run_doctor
from gasclaw.openclaw.installer import write_openclaw_config
from gasclaw.openclaw.lifecycle import start_openclaw, stop_openclaw
from gasclaw.openclaw.skill_manager import install_skills
from gasclaw.updater.notifier import notify_telegram

logger = get_logger(__name__)


def _get_skills_dir() -> Path:
    """Get skills directory, handling both installed and volume-mounted cases.

    Returns:
        Path to the skills directory.
    """
    # First try the installed location (pip install)
    installed_path = Path(__file__).parent.parent.parent / "skills"
    if installed_path.exists():
        return installed_path

    # Fallback to common volume mount locations
    for fallback in ["/opt/gasclaw/skills", "/workspace/gasclaw/skills", "/app/skills"]:
        path = Path(fallback)
        if path.exists():
            return path

    # Default to installed path even if it doesn't exist (will fail later with clear error)
    return installed_path


def bootstrap(config: GasclawConfig, *, gt_root: Path = Path("/workspace/gt")) -> None:
    """Run the full bootstrap sequence.

    Args:
        config: Validated gasclaw configuration.
        gt_root: Where to install Gastown.

    Raises:
        RuntimeError: If bootstrap fails, after attempting rollback.

    """
    # Track started services for rollback
    dolt_started = False
    services_started = False
    auth_token = ""

    try:
        # 1. Setup Kimi proxy: Claude Code UI talks to Kimi backend
        key_count = len(config.gastown_kimi_keys)
        logger.info("Configuring Kimi proxy for Claude Code (%d keys)", key_count)
        setup_kimi_accounts(config.gastown_kimi_keys)
        pool = KeyPool(config.gastown_kimi_keys)
        active_key = pool.get_key()
        kimi_env = build_claude_env(active_key)
        os.environ.update(kimi_env)
        write_claude_config(active_key, config_dir=kimi_env["CLAUDE_CONFIG_DIR"])
        logger.info("ANTHROPIC_BASE_URL set to Kimi backend (key via pool)")

        # 2. Configure git/dolt identity (required before gt install)
        logger.info("Configuring git and dolt identity")
        setup_git_identity()

        # 3. Start Dolt (must be running before gt rig add)
        logger.info("Starting Dolt")
        start_dolt(port=config.dolt_port)
        dolt_started = True

        # Verify Dolt is accepting SQL queries before proceeding
        # This ensures the database is ready for beads operations
        logger.info("Verifying Dolt readiness...")
        _verify_dolt_ready(port=config.dolt_port)
        logger.info("Dolt started successfully")

        # 4. Install Gastown (includes gt dolt init-rig and gt rig add --adopt --url)
        logger.info("Installing Gastown with rig_url=%s", config.gt_rig_url)
        gastown_install(gt_root=gt_root, rig_url=config.gt_rig_url)

        # 5. Configure agent: Claude Code CLI backed by Kimi
        logger.info("Configuring Gastown agent")
        configure_agent()

        # 6. Configure OpenClaw (beads for memory, not files)
        openclaw_dir = Path.home() / ".openclaw"
        logger.info("Configuring OpenClaw in %s", openclaw_dir)

        # Create .openclaw with restricted permissions (700) (#324)
        openclaw_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(openclaw_dir, 0o700)

        # Get first group ID if available for Telegram group support (#321)
        group_id = config.telegram_group_ids[0] if config.telegram_group_ids else ""

        write_openclaw_config(
            openclaw_dir=openclaw_dir,
            kimi_key=config.openclaw_kimi_key,
            bot_token=config.telegram_bot_token,
            owner_id=int(config.telegram_owner_id),
            group_id=group_id,
            gateway_port=config.gateway_port,
            gt_root=str(gt_root),
            agent_count=config.gt_agent_count,  # Pass agent count for multiple agents (#322)
        )

        # 7. Install skills
        logger.info("Installing skills")
        skills_src = _get_skills_dir()
        install_skills(skills_src=skills_src, skills_dst=openclaw_dir / "skills")

        # 8. Start OpenClaw gateway
        logger.info("Starting OpenClaw gateway on port %d", config.gateway_port)
        start_openclaw(port=config.gateway_port, timeout=180)  # Increased timeout (#317)
        services_started = True
        logger.info("OpenClaw gateway started successfully")

        # 9. Read auth token for notifications
        auth_token = get_gateway_auth_token(openclaw_dir) or ""
        if not auth_token:
            logger.warning("No auth token found, notifications may fail")

        # 10. Run openclaw doctor to verify config and fix issues
        logger.info("Running openclaw doctor")
        doctor_result = run_doctor(repair=True)
        if not doctor_result.healthy:
            logger.warning("Openclaw doctor found issues: %s", doctor_result.output[:500])
            notify_telegram(
                f"openclaw doctor found issues:\n{doctor_result.output[:500]}",
                auth_token=auth_token,
            )
        else:
            logger.info("Openclaw doctor check passed")

        # 11. Start daemon
        logger.info("Starting gt daemon")
        start_daemon(gt_root=str(gt_root))

        # 12. Start mayor
        logger.info("Starting mayor agent")
        start_mayor(agent="claude", gt_root=str(gt_root))
        logger.info("All services started successfully")

        # 13. Notify
        logger.info("Sending startup notification")
        notify_telegram("Gasclaw is up and running.", auth_token=auth_token)

    except Exception as e:  # noqa: BLE001
        logger.exception("Bootstrap failed at step")
        # Rollback: Stop any services that were started
        if services_started or dolt_started:
            logger.info("Attempting rollback")
            notify_telegram(
                f"Bootstrap failed: {e}. Rolling back...",
                auth_token=auth_token,
            )
            try:
                stop_all(gt_root=str(gt_root))
                if services_started:
                    stop_openclaw()
                logger.info("Rollback completed")
            except Exception as rollback_error:  # noqa: BLE001
                # Log rollback error but raise original exception
                logger.error("Rollback failed: %s", rollback_error)
                notify_telegram(
                    f"Rollback error: {rollback_error}",
                    auth_token=auth_token,
                )
        else:
            notify_telegram(f"Bootstrap failed: {e}", auth_token=auth_token)

        # Re-raise the original exception
        raise RuntimeError(f"Bootstrap failed: {e}") from e


def monitor_loop(
    config: GasclawConfig,
    *,
    interval: int | None = None,
) -> None:
    """Foreground health monitor loop.

    The overseer (OpenClaw) uses this data to:
    - Check all agents are alive and active
    - Enforce the activity benchmark (push/PR every hour)
    - Rotate keys on rate limits
    - Restart failed agents

    Args:
        config: Gasclaw configuration.
        interval: Seconds between checks (default from config.monitor_interval).

    """
    if interval is None:
        interval = config.monitor_interval

    logger.info("Starting monitor loop with interval=%d seconds", interval)

    # Initialize key pool for health checks
    key_pool = KeyPool(config.gastown_kimi_keys)

    # Notification state: only alert on transitions (healthy <-> unhealthy)
    # and skip the first ~10 min after start (warmup grace period).
    prev_service_state = {"dolt": None, "daemon": None, "mayor": None}
    prev_activity_compliant = None
    cycle = 0
    grace_cycles = max(1, int(600 / max(interval, 1)))

    try:
        while True:
            cycle += 1
            report = check_health(
                gateway_port=config.gateway_port,
                dolt_port=config.dolt_port,
                key_pool=key_pool,
            )
            activity = check_agent_activity(
                project_dir=config.project_dir,
                deadline_seconds=config.activity_deadline,
            )
            report.activity = activity

            logger.debug(
                "Health check: dolt=%s, daemon=%s, mayor=%s, agents=%d",
                report.dolt,
                report.daemon,
                report.mayor,
                len(report.agents),
            )

            in_grace = cycle <= grace_cycles

            compliant = activity.get("compliant", True)
            if not compliant:
                logger.warning(
                    "Activity violation: last_commit_age=%s, deadline=%d",
                    activity.get("last_commit_age"),
                    config.activity_deadline,
                )
            if not in_grace and compliant != prev_activity_compliant:
                if not compliant and prev_activity_compliant is not False:
                    notify_telegram(
                        f"ACTIVITY ALERT: No commits in {config.activity_deadline}s. "
                        f"Last commit age: {activity.get('last_commit_age', 'unknown')}s."
                    )
                elif compliant and prev_activity_compliant is False:
                    notify_telegram("ACTIVITY OK: commit activity resumed.")
            prev_activity_compliant = compliant

            for svc in ("dolt", "daemon", "mayor"):
                cur = getattr(report, svc)
                if cur == "unhealthy":
                    logger.error("Service down: %s", svc)
                if not in_grace and cur != prev_service_state[svc]:
                    if cur == "unhealthy" and prev_service_state[svc] != "unhealthy":
                        notify_telegram(f"SERVICE DOWN: {svc} is unhealthy")
                    elif cur == "healthy" and prev_service_state[svc] == "unhealthy":
                        notify_telegram(f"SERVICE RECOVERED: {svc} is healthy")
                prev_service_state[svc] = cur

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Monitor loop stopped by user")


def _verify_dolt_ready(*, port: int = 3307, timeout: int = 30) -> None:
    """Verify Dolt is accepting TCP connections on the SQL server port.

    Args:
        port: Dolt SQL server port.
        timeout: Max seconds to wait for readiness.

    Raises:
        TimeoutError: If Dolt is not ready within the timeout.
    """
    import socket

    deadline = time.time() + timeout

    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect(("127.0.0.1", port))
            sock.close()
            return
        except (ConnectionRefusedError, OSError):
            sock.close()
        time.sleep(1)

    raise TimeoutError(f"Dolt not accepting connections after {timeout}s on port {port}")
