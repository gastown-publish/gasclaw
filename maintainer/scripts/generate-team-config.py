#!/usr/bin/env python3
"""Generate OpenClaw multi-agent config from a gasclaw team preset YAML.

Usage:
    python3 generate-team-config.py <preset.yaml> [--output openclaw.json]

Each agent gets:
  - Its own OpenClaw agent entry with workspace, agentDir, sessions
  - A binding to a Telegram topic in the forum group
  - Per-agent tool allow/deny lists
  - A SOUL.md in its workspace defining its role

The coordinator sees all topics; specialists see only their own.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml


def create_telegram_topic(bot_token: str, chat_id: str, name: str, icon_color: int = 7322096) -> str:
    """Create a Telegram forum topic and return its message_thread_id."""
    import urllib.request
    url = f"https://api.telegram.org/bot{bot_token}/createForumTopic"
    data = json.dumps({"chat_id": chat_id, "name": name, "icon_color": icon_color}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                return str(result["result"]["message_thread_id"])
    except Exception as e:
        print(f"  Warning: Could not create topic '{name}': {e}", file=sys.stderr)
    return ""


def load_preset(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def generate_config(preset: dict, env: dict) -> dict:
    """Generate the full openclaw.json from a preset and env vars."""
    bot_token = env["TELEGRAM_BOT_TOKEN"]
    chat_id = env["TELEGRAM_CHAT_ID"]
    owner_id = env["TELEGRAM_OWNER_ID"]
    kimi_key = env["KIMI_API_KEY"]
    auth_token = env.get("AUTH_TOKEN", hashlib.sha256(os.urandom(32)).hexdigest())

    coordinator = preset["coordinator"]
    specialists = preset.get("agents", [])
    all_agents = [coordinator] + specialists

    # Create Telegram topics for each agent
    topic_map = {}
    print(f"Creating Telegram topics for {len(all_agents)} agents...")
    for agent in all_agents:
        agent_name = agent["name"]
        topic_id = create_telegram_topic(bot_token, chat_id, f"{agent.get('emoji', '')} {agent_name}".strip())
        if topic_id:
            topic_map[agent["id"]] = topic_id
            print(f"  {agent_name} -> topic {topic_id}")
        else:
            print(f"  {agent_name} -> topic creation failed (will use General)")

    # Build agent list
    openclaw_base = Path(os.path.expanduser("~/.openclaw"))
    agent_list = []
    bindings = []

    for agent in all_agents:
        agent_id = agent["id"]
        is_coordinator = agent_id == coordinator["id"]
        workspace = str(openclaw_base / f"workspace-{agent_id}")
        agent_dir = str(openclaw_base / f"agents/{agent_id}/agent")

        entry = {
            "id": agent_id,
            "identity": {
                "name": agent["name"],
                "emoji": agent.get("emoji", ""),
            },
            "workspace": workspace,
            "agentDir": agent_dir,
        }

        if is_coordinator:
            entry["default"] = True
            model_tier = agent.get("model_tier", "light")
        else:
            model_tier = "full"

        if agent.get("tools"):
            entry["tools"] = {}
            if agent["tools"].get("allow"):
                entry["tools"]["allow"] = agent["tools"]["allow"]
            if agent["tools"].get("deny"):
                entry["tools"]["deny"] = agent["tools"]["deny"]

        agent_list.append(entry)

        # Note: OpenClaw does not support per-topic bindings (threadId rejected).
        # All messages route to coordinator; per-topic systemPrompts guide delegation.

    # Coordinator gets a fallback binding (catches everything not matched)
    bindings.append({
        "agentId": coordinator["id"],
        "match": {"channel": "telegram"},
    })

    # Build topic config with per-topic systemPrompts for coordinator routing
    group_topics = {"1": {"requireMention": False}}
    for agent_id, topic_id in topic_map.items():
        agent_name = next((a["name"] for a in all_agents if a["id"] == agent_id), agent_id)
        is_coord = agent_id == coordinator["id"]
        if is_coord:
            prompt = (
                f"You are in the Coordinator/Tech Lead topic. "
                f"This is YOUR topic. Handle coordination, delegation, and high-level decisions directly."
            )
        else:
            prompt = (
                f"This is the {agent_name} topic. "
                f"Delegate to agent \"{agent_id}\" using sessions_send or sessions_spawn."
            )
        group_topics[topic_id] = {
            "requireMention": False,
            "systemPrompt": prompt,
        }

    config = {
        "agents": {
            "defaults": {
                "model": {"primary": "kimi-coding/k2p5"},
                "models": {"kimi-coding/k2p5": {}},
            },
            "list": agent_list,
        },
        "bindings": bindings,
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
                "allow": [a["id"] for a in all_agents],
            },
        },
        "env": {"KIMI_API_KEY": kimi_key},
    }

    return config, all_agents, topic_map


def write_agent_workspaces(agents: list, preset: dict, topic_map: dict):
    """Create SOUL.md in each agent's workspace."""
    openclaw_base = Path(os.path.expanduser("~/.openclaw"))
    coordinator_id = preset["coordinator"]["id"]
    preset_name = preset.get("name", "custom")

    for agent in agents:
        agent_id = agent["id"]
        is_coordinator = agent_id == coordinator_id
        workspace = openclaw_base / f"workspace-{agent_id}"
        agent_dir = openclaw_base / f"agents/{agent_id}/agent"
        sessions_dir = openclaw_base / f"agents/{agent_id}/sessions"

        workspace.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        topic_id = topic_map.get(agent_id, "N/A")
        team_members = "\n".join(
            f"  - {a['name']} ({a['id']}) — topic {topic_map.get(a['id'], 'N/A')}"
            for a in agents if a["id"] != agent_id
        )

        soul = f"""# {agent['name']}

Team: {preset_name} | Role: {'Coordinator' if is_coordinator else 'Specialist'}
Telegram Topic: {topic_id}

{agent.get('system_prompt', '').strip()}

## Team Members
{team_members}

## Rules
- Stay in your lane — only do work that matches your role
- Report progress and blockers to the Coordinator
- Use beads (bd) for persistent state tracking
- Run tests before creating PRs
- Keep PRs small and focused (<200 lines)
"""
        (workspace / "SOUL.md").write_text(soul)


def main():
    parser = argparse.ArgumentParser(description="Generate OpenClaw multi-agent config from preset")
    parser.add_argument("preset", help="Path to preset YAML file")
    parser.add_argument("--output", "-o", default=os.path.expanduser("~/.openclaw/openclaw.json"))
    parser.add_argument("--dry-run", action="store_true", help="Print config without writing")
    args = parser.parse_args()

    preset = load_preset(args.preset)
    print(f"Loaded preset: {preset['name']} ({preset['description']})")
    print(f"  Coordination: {preset['coordination']}")
    print(f"  Agents: 1 coordinator + {len(preset.get('agents', []))} specialists")

    env = {
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "TELEGRAM_OWNER_ID": os.environ.get("TELEGRAM_OWNER_ID", ""),
        "KIMI_API_KEY": os.environ.get("KIMI_API_KEY", ""),
        "AUTH_TOKEN": os.environ.get("AUTH_TOKEN", ""),
    }

    missing = [k for k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "KIMI_API_KEY"] if not env[k]]
    if missing:
        print(f"Error: Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    config, all_agents, topic_map = generate_config(preset, env)

    if args.dry_run:
        print(json.dumps(config, indent=2))
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, indent=2))
    print(f"Config written to {output_path}")

    write_agent_workspaces(all_agents, preset, topic_map)
    print(f"Agent workspaces created ({len(all_agents)} agents)")

    # Write topic map for reference
    topic_file = output_path.parent / "team-topics.json"
    topic_file.write_text(json.dumps(topic_map, indent=2))
    print(f"Topic map written to {topic_file}")


if __name__ == "__main__":
    main()
