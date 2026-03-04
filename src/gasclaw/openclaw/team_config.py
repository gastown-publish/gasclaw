"""Multi-agent team configuration with smart coordinator routing.

Generates openclaw.json configs where all Telegram messages route to
a coordinator agent. Per-topic systemPrompts tell the coordinator which
specialist to delegate to via sessions_send/sessions_spawn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentSpec:
    """Describes one agent in a team preset."""

    id: str
    name: str
    emoji: str = ""
    system_prompt: str = ""
    is_coordinator: bool = False
    tools_allow: list[str] = field(default_factory=list)
    tools_deny: list[str] = field(default_factory=list)


@dataclass
class TopicRoute:
    """Maps a Telegram topic to an agent with a routing prompt."""

    topic_id: str
    agent_id: str
    system_prompt: str


def build_topic_routes(
    agents: list[AgentSpec],
    topic_map: dict[str, str],
) -> list[TopicRoute]:
    """Build per-topic systemPrompts for coordinator-based routing.

    Each specialist topic gets a prompt instructing the coordinator
    to delegate via sessions_send. The coordinator's own topic gets
    a prompt telling it to handle directly.
    """
    routes: list[TopicRoute] = []
    for agent in agents:
        tid = topic_map.get(agent.id, "")
        if not tid:
            continue
        if agent.is_coordinator:
            prompt = (
                f"You are in the {agent.name} topic. "
                f"This is YOUR topic. Handle coordination, delegation, "
                f"and high-level decisions directly."
            )
        else:
            prompt = (
                f"This is the {agent.name} topic. "
                f'Delegate to agent "{agent.id}" using the sessions_send tool.'
            )
        routes.append(TopicRoute(topic_id=tid, agent_id=agent.id, system_prompt=prompt))
    return routes


def build_group_topics(
    routes: list[TopicRoute],
) -> dict[str, dict[str, Any]]:
    """Build the groups.<id>.topics config dict from routes.

    General topic (1) is always enabled with requireMention=False.
    """
    topics: dict[str, dict[str, Any]] = {
        "1": {"requireMention": False},
    }
    for route in routes:
        topics[route.topic_id] = {
            "requireMention": False,
            "systemPrompt": route.system_prompt,
        }
    return topics


def build_agent_list(agents: list[AgentSpec], openclaw_base: Path) -> list[dict]:
    """Build the agents.list config array."""
    result = []
    for agent in agents:
        entry: dict[str, Any] = {
            "id": agent.id,
            "identity": {"name": agent.name, "emoji": agent.emoji},
            "workspace": str(openclaw_base / f"workspace-{agent.id}"),
            "agentDir": str(openclaw_base / f"agents/{agent.id}/agent"),
        }
        if agent.is_coordinator:
            entry["default"] = True
        tools: dict[str, list[str]] = {}
        if agent.tools_allow:
            tools["allow"] = agent.tools_allow
        if agent.tools_deny:
            tools["deny"] = agent.tools_deny
        if tools:
            entry["tools"] = tools
        result.append(entry)
    return result


def build_coordinator_soul(
    coordinator: AgentSpec,
    specialists: list[AgentSpec],
    topic_map: dict[str, str],
    chat_id: str,
) -> str:
    """Generate the coordinator's SOUL.md with delegation rules."""
    rows = []
    for agent in specialists:
        tid = topic_map.get(agent.id, "?")
        rows.append(f"| {agent.name} ({agent.id}) | {tid} | `sessions_send` |")
    table = "\n".join(rows)

    coord_topic = topic_map.get(coordinator.id, "?")

    return f"""# {coordinator.name} — Coordinator

You are the **{coordinator.name}** (coordinator) of the team.
All Telegram messages route to you first.

## Topic-Based Routing

Each message includes a `systemPrompt` that tells you which topic it's in.
Use it to route immediately.

| If in General (1) or Coordinator ({coord_topic}) | Handle directly or triage |
|---------------------------------------------------|---------------------------|

| Specialist (name / id) | Topic | Delegate via |
|------------------------|-------|--------------|
{table}

## How to Delegate

`sessions_send` and `sessions_spawn` are **OpenClaw tools** (not shell commands).
Call them as tool actions with `agentId` and `message`.

## How to Post to Topics

Use the `sendMessage` tool:
- channel: "telegram"
- to: "{chat_id}"
- content: your message
- messageThreadId: topic number

## Rules

- Read the systemPrompt to know which topic you're in
- Delegate specialist work — don't do everything yourself
- Acknowledge fast: "On it" or "Delegated to [specialist]"
- Be concise in Telegram
- Use beads for tracking decisions
"""


def build_specialist_soul(
    agent: AgentSpec,
    all_agents: list[AgentSpec],
    topic_map: dict[str, str],
    chat_id: str,
) -> str:
    """Generate a specialist agent's SOUL.md."""
    tid = topic_map.get(agent.id, "?")
    teammates = "\n".join(
        f"  - {a.name} ({a.id})"
        for a in all_agents
        if a.id != agent.id
    )
    return f"""# {agent.name}

Topic: {tid} | Chat: {chat_id}

{agent.system_prompt.strip()}

## Reporting

Post results to your topic using the sendMessage tool:
- channel: "telegram", to: "{chat_id}", messageThreadId: {tid}

## Team

{teammates}

## Rules

- Stay in your lane — only do work matching your role
- Report progress to your topic
- Use beads (bd) for persistent state
- Run tests before creating PRs
"""


def generate_team_config(
    agents: list[AgentSpec],
    topic_map: dict[str, str],
    *,
    bot_token: str,
    chat_id: str,
    owner_id: str,
    kimi_key: str,
    auth_token: str,
    openclaw_base: Path,
    model: str = "kimi-coding/k2p5",
) -> dict:
    """Generate the full openclaw.json for a multi-agent team.

    All messages route to the coordinator via a single Telegram binding.
    Per-topic systemPrompts guide the coordinator on delegation.
    """
    routes = build_topic_routes(agents, topic_map)
    group_topics = build_group_topics(routes)
    agent_list = build_agent_list(agents, openclaw_base)

    return {
        "agents": {
            "defaults": {
                "model": {"primary": model},
                "models": {model: {}},
            },
            "list": agent_list,
        },
        "bindings": [
            {
                "agentId": next(a.id for a in agents if a.is_coordinator),
                "match": {"channel": "telegram"},
            },
        ],
        "channels": {
            "telegram": {
                "enabled": True,
                "botToken": bot_token,
                "dmPolicy": "allowlist",
                "allowFrom": [owner_id],
                "groupPolicy": "allowlist",
                "groupAllowFrom": [owner_id],
                "streaming": "off",
                "network": {"autoSelectFamily": False},
                "actions": {"sendMessage": True},
                "groups": {
                    chat_id: {
                        "requireMention": False,
                        "groupPolicy": "open",
                        "topics": group_topics,
                    },
                },
            },
        },
        "messages": {"ackReactionScope": "none", "ackReaction": ""},
        "commands": {"native": "auto", "nativeSkills": "auto", "restart": True},
        "gateway": {
            "port": 18789,
            "mode": "local",
            "auth": {"mode": "token", "token": auth_token},
        },
        "plugins": {"slots": {"memory": "none"}},
        "tools": {
            "exec": {"security": "full"},
            "agentToAgent": {
                "enabled": True,
                "allow": [a.id for a in agents],
            },
        },
        "env": {"KIMI_API_KEY": kimi_key},
    }


def write_team_workspaces(
    agents: list[AgentSpec],
    topic_map: dict[str, str],
    chat_id: str,
    openclaw_base: Path,
    knowledge_dir: Path | None = None,
) -> dict[str, Path]:
    """Create workspace dirs and SOUL.md for each agent.

    Returns mapping of agent_id -> workspace Path.
    """
    workspaces: dict[str, Path] = {}

    for agent in agents:
        ws = openclaw_base / f"workspace-{agent.id}"
        ws.mkdir(parents=True, exist_ok=True)
        agent_dir = openclaw_base / f"agents/{agent.id}/agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        sessions_dir = openclaw_base / f"agents/{agent.id}/sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        if agent.is_coordinator:
            others = [a for a in agents if not a.is_coordinator]
            soul = build_coordinator_soul(agent, others, topic_map, chat_id)
        else:
            soul = build_specialist_soul(agent, agents, topic_map, chat_id)
        (ws / "SOUL.md").write_text(soul)

        if knowledge_dir and knowledge_dir.is_dir():
            dest = ws / "knowledge"
            dest.mkdir(exist_ok=True)
            for md in knowledge_dir.glob("*.md"):
                (dest / md.name).write_text(md.read_text())

        workspaces[agent.id] = ws

    return workspaces


def load_preset_agents(preset_path: Path) -> list[AgentSpec]:
    """Load agents from a gasclaw team preset YAML file."""
    import yaml

    data = yaml.safe_load(preset_path.read_text())
    agents: list[AgentSpec] = []

    coord = data["coordinator"]
    agents.append(AgentSpec(
        id=coord["id"],
        name=coord["name"],
        emoji=coord.get("emoji", ""),
        system_prompt=coord.get("system_prompt", ""),
        is_coordinator=True,
        tools_allow=coord.get("tools", {}).get("allow", []),
        tools_deny=coord.get("tools", {}).get("deny", []),
    ))

    agents.extend(
        AgentSpec(
            id=spec["id"],
            name=spec["name"],
            emoji=spec.get("emoji", ""),
            system_prompt=spec.get("system_prompt", ""),
            is_coordinator=False,
            tools_allow=spec.get("tools", {}).get("allow", []),
            tools_deny=spec.get("tools", {}).get("deny", []),
        )
        for spec in data.get("agents", [])
    )

    return agents
