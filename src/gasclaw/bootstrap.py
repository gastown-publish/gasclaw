"""Startup orchestration for gasclaw.

Bootstrap sequence:
 1. Load config from env vars (already done by caller)
 2. Setup Kimi accounts
 3. Write agent config
 4. Install Gastown
 5. Start Dolt
 6. Configure OpenClaw
 7. Install skills
 8. Run openclaw doctor
 9. Start gt daemon
10. Start Mayor
11. Send "Gasclaw is up" via Telegram
12. Enter health monitor loop (foreground)

Rollback on failure:
- If bootstrap fails at any step, previously started services are stopped
and a failure notification is sent.
"""

from __future__ import annotations

import time
from pathlib import Path

from gasclaw.config import GasclawConfig
from gasclaw.gastown.agent_config import write_agent_config
from gasclaw.gastown.installer import gastown_install, setup_kimi_accounts
from gasclaw.gastown.lifecycle import start_daemon, start_dolt, start_mayor, stop_all
from gasclaw.health import check_agent_activity, check_health
from gasclaw.openclaw.doctor import run_doctor
from gasclaw.openclaw.installer import write_openclaw_config
from gasclaw.openclaw.skill_manager import install_skills
from gasclaw.updater.notifier import notify_telegram

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
        # 1. Setup Kimi accounts for Gastown agents
        setup_kimi_accounts(config.gastown_kimi_keys)

        # 2. Write agent config
        write_agent_config(gt_root)

        # 3. Install Gastown
        gastown_install(gt_root=gt_root, rig_url=config.gt_rig_url)

        # 4. Start Dolt
        start_dolt()
        dolt_started = True

        # 5. Configure OpenClaw
        openclaw_dir = Path.home() / ".openclaw"
        write_openclaw_config(
            openclaw_dir=openclaw_dir,
            kimi_key=config.openclaw_kimi_key,
            bot_token=config.telegram_bot_token,
            owner_id=config.telegram_owner_id,
        )

        # 6. Install skills
        install_skills(skills_src=_SKILLS_DIR, skills_dst=openclaw_dir / "skills")

        # 6.5. Run openclaw doctor to verify config and fix issues
        doctor_result = run_doctor(repair=True)
        if not doctor_result.healthy:
            notify_telegram(f"openclaw doctor found issues:\n{doctor_result.output[:500]}")

        # 7. Start daemon
        start_daemon()

        # 8. Start mayor
        start_mayor(agent="kimi-claude")
        services_started = True

        # 9. Notify
        notify_telegram("Gasclaw is up and running.")

    except Exception as e:
        # Rollback: Stop any services that were started
        if services_started or dolt_started:
            notify_telegram(f"Bootstrap failed: {e}. Rolling back...")
            try:
                stop_all()
            except Exception as rollback_error:
                # Log rollback error but raise original exception
                notify_telegram(f"Rollback error: {rollback_error}")
        else:
            notify_telegram(f"Bootstrap failed: {e}")

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

    try:
        while True:
            report = check_health()
            activity = check_agent_activity(
                project_dir=config.project_dir,
                deadline_seconds=config.activity_deadline,
            )
            report.activity = activity

            # If not compliant, notify the overseer
            if not activity.get("compliant", True):
                notify_telegram(
                    f"ACTIVITY ALERT: No commits in {config.activity_deadline}s. "
                    f"Last commit age: {activity.get('last_commit_age', 'unknown')}s.\n"
                    f"System status:\n{report.summary()}"
                )

            # If any critical service is down, notify
            for svc in ["dolt", "daemon", "mayor"]:
                if getattr(report, svc) == "unhealthy":
                    notify_telegram(f"SERVICE DOWN: {svc} is unhealthy")

            time.sleep(interval)
    except KeyboardInterrupt:
        pass
