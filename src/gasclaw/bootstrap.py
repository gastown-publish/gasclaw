"""Startup orchestration for gasclaw.

Bootstrap sequence:
 1. Setup Kimi accounts
 2. Install Gastown (gt install + gt rig add)
 3. Configure agent (gt config agent set + default-agent)
 4. Start Dolt
 5. Configure OpenClaw
 6. Install skills
 7. Run openclaw doctor
 8. Start gt daemon
 9. Start Mayor
10. Send "Gasclaw is up" via Telegram

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
from gasclaw.gastown.installer import gastown_install, setup_kimi_accounts
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

_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


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

        # 2. Install Gastown (HQ must exist before configuring agents)
        logger.info("Installing Gastown with rig_url=%s", config.gt_rig_url)
        gastown_install(gt_root=gt_root, rig_url=config.gt_rig_url)

        # 3. Configure agent: Claude Code CLI backed by Kimi
        logger.info("Configuring Gastown agent")
        configure_agent()

        # 4. Start Dolt
        logger.info("Starting Dolt")
        start_dolt()
        dolt_started = True
        logger.info("Dolt started successfully")

        # 5. Configure OpenClaw (beads for memory, not files)
        openclaw_dir = Path.home() / ".openclaw"
        logger.info("Configuring OpenClaw in %s", openclaw_dir)
        write_openclaw_config(
            openclaw_dir=openclaw_dir,
            kimi_key=config.openclaw_kimi_key,
            bot_token=config.telegram_bot_token,
            owner_id=int(config.telegram_owner_id),
            gateway_port=config.gateway_port,
            gt_root=str(gt_root),
        )

        # 6. Install skills
        logger.info("Installing skills")
        install_skills(skills_src=_SKILLS_DIR, skills_dst=openclaw_dir / "skills")

        # 7. Start OpenClaw gateway
        logger.info("Starting OpenClaw gateway on port %d", config.gateway_port)
        start_openclaw(port=config.gateway_port, timeout=30)
        services_started = True
        logger.info("OpenClaw gateway started successfully")

        # 8. Read auth token for notifications
        auth_token = get_gateway_auth_token(openclaw_dir)
        if not auth_token:
            logger.warning("No auth token found, notifications may fail")

        # 9. Run openclaw doctor to verify config and fix issues
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

        # 10. Start daemon
        logger.info("Starting gt daemon")
        start_daemon()

        # 11. Start mayor
        logger.info("Starting mayor agent")
        start_mayor(agent="kimi-claude")
        logger.info("All services started successfully")

        # 12. Notify
        logger.info("Sending startup notification")
        notify_telegram("Gasclaw is up and running.", auth_token=auth_token)

    except Exception as e:  # noqa: BLE001
        logger.exception("Bootstrap failed at step")
        # Get auth token if available for error notifications
        error_token = auth_token if 'auth_token' in vars() else ""
        # Rollback: Stop any services that were started
        if services_started or dolt_started:
            logger.info("Attempting rollback")
            notify_telegram(
                f"Bootstrap failed: {e}. Rolling back...",
                auth_token=error_token,
            )
            try:
                stop_all()
                if services_started:
                    stop_openclaw()
                logger.info("Rollback completed")
            except Exception as rollback_error:  # noqa: BLE001
                # Log rollback error but raise original exception
                logger.error("Rollback failed: %s", rollback_error)
                notify_telegram(
                    f"Rollback error: {rollback_error}",
                    auth_token=error_token,
                )
        else:
            notify_telegram(f"Bootstrap failed: {e}", auth_token=error_token)

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

    try:
        while True:
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

            # Log health status
            logger.debug(
                "Health check: dolt=%s, daemon=%s, mayor=%s, agents=%d",
                report.dolt,
                report.daemon,
                report.mayor,
                len(report.agents),
            )

            # If not compliant, notify the overseer
            if not activity.get("compliant", True):
                logger.warning(
                    "Activity violation: last_commit_age=%s, deadline=%d",
                    activity.get("last_commit_age"),
                    config.activity_deadline,
                )
                notify_telegram(
                    f"ACTIVITY ALERT: No commits in {config.activity_deadline}s. "
                    f"Last commit age: {activity.get('last_commit_age', 'unknown')}s.\n"
                    f"System status:\n{report.summary()}"
                )

            # If any critical service is down, notify
            for svc in ["dolt", "daemon", "mayor"]:
                if getattr(report, svc) == "unhealthy":
                    logger.error("Service down: %s", svc)
                    notify_telegram(f"SERVICE DOWN: {svc} is unhealthy")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Monitor loop stopped by user")
