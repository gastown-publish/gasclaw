"""Configure Gastown agent via gt config CLI commands.

Agents use Claude Code CLI backed by Kimi K2.5 via ANTHROPIC_BASE_URL.
The bootstrap sets the proxy env vars so every spawned ``claude`` process
talks to Kimi's API instead of Anthropic's.

Permission bypass is configured in the Claude config file (not via CLI
flag) because ``--dangerously-skip-permissions`` is rejected under root.
"""

from __future__ import annotations

import subprocess

__all__ = ["configure_agent"]


def configure_agent(
    *,
    agent_name: str = "kimi-claude",
    agent_command: str = "claude",
) -> None:
    """Register a custom agent and set it as the default.

    Uses the real Gastown ``gt config`` CLI to persist agent settings
    in the town configuration.  Must be called after ``gt install``.

    The command is plain ``claude`` — permission bypass is handled by
    the Claude config file written during bootstrap, and the Kimi
    backend is handled by ANTHROPIC_BASE_URL env vars.

    Args:
        agent_name: Name for the agent alias.
        agent_command: Shell command Gastown invokes for this agent.

    """
    subprocess.run(
        ["gt", "config", "agent", "set", agent_name, agent_command],
        check=True,
    )
    subprocess.run(
        ["gt", "config", "default-agent", agent_name],
        check=True,
    )
