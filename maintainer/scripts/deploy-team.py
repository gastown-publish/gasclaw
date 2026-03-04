#!/usr/bin/env python3
"""Deploy multi-agent team directly into the running container."""
import json
import os
import hashlib
import shutil
import urllib.request

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OWNER_ID = os.environ["TELEGRAM_OWNER_ID"]
KIMI_KEY = os.environ["KIMI_API_KEY"]
OPENCLAW_DIR = "/root/.openclaw"

try:
    with open(f"{OPENCLAW_DIR}/openclaw.json") as f:
        AUTH_TOKEN = json.load(f)["gateway"]["auth"]["token"]
except Exception:
    AUTH_TOKEN = hashlib.sha256(os.urandom(32)).hexdigest()

TEAM = [
    {"id": "coordinator", "name": "Tech Lead", "emoji": "\U0001f3af", "is_coordinator": True,
     "soul": "You are the Tech Lead and team coordinator for gasclaw.\n\nResponsibilities:\n- Decompose tasks and assign to specialists\n- Track progress, review deliverables, merge PRs when tests pass\n- Coordinate between agents using sessions_send\n- Post standup summaries and progress reports\n\nRules:\n- NEVER write implementation code yourself. Delegate.\n- You can see ALL team topics. Route work to the right specialist.\n- Use beads (bd) for persistent state tracking\n\nDaily: Morning standup, evening recap, PR triage.",
     "tools_allow": ["exec","read","write","sessions_list","sessions_send","sessions_spawn","cron"], "tools_deny": [],
     "mention": ["@lead","@coordinator","@techlead"]},
    {"id": "architect", "name": "System Architect", "emoji": "\U0001f4d0",
     "soul": "You are the System Architect.\n\nResponsibilities:\n- Design API contracts, data models, service boundaries\n- Write Architecture Decision Records (ADRs)\n- Define error handling patterns, config schemas\n- Output specs as markdown with mermaid diagrams",
     "tools_allow": ["exec","read","write","edit","glob","grep"], "tools_deny": ["cron"],
     "mention": ["@architect","@arch"]},
    {"id": "developer", "name": "Backend Developer", "emoji": "\U0001f528",
     "soul": "You are the Backend Developer.\n\nResponsibilities:\n- Implement features, business logic, route handlers\n- Write clean testable Python following CLAUDE.md conventions\n- Create focused PRs (<200 lines), run tests before pushing\n- Fix bugs reported by the Test Engineer",
     "tools_allow": ["exec","read","write","edit","apply_patch","glob","grep"], "tools_deny": ["cron"],
     "mention": ["@dev","@developer"]},
    {"id": "devops", "name": "DevOps Engineer", "emoji": "\U0001f680",
     "soul": "You are the DevOps Engineer.\n\nResponsibilities:\n- Maintain Dockerfiles, CI/CD pipelines (GitHub Actions)\n- Fix failing CI workflows, manage deployments\n- Container orchestration and infra-as-code",
     "tools_allow": ["exec","read","write","edit","glob","grep"], "tools_deny": ["cron"],
     "mention": ["@devops","@ops"]},
    {"id": "tester", "name": "Test Engineer", "emoji": "\U0001f9ea",
     "soul": "You are the Test Engineer and quality gate.\n\nResponsibilities:\n- Write unit + integration tests, ensure >80% coverage\n- Diagnose test failures, report root cause to developer\n- Nothing merges without passing tests\n- Run 'make test' and 'make lint' to verify\n\nRules: Never modify a test just to make it pass. Fix the code.",
     "tools_allow": ["exec","read","write","edit","glob","grep"], "tools_deny": ["cron"],
     "mention": ["@tester","@qa","@test"]},
    {"id": "reviewer", "name": "Code Reviewer", "emoji": "\U0001f440",
     "soul": "You are the Code Reviewer (READ-ONLY).\n\nResponsibilities:\n- Review PRs for correctness, style, performance, security\n- Provide structured feedback (must-fix vs nice-to-have)\n- Approve or request changes\n- NEVER write or edit code directly",
     "tools_allow": ["exec","read","glob","grep"], "tools_deny": ["write","edit","apply_patch","cron"],
     "mention": ["@reviewer","@review"]},
    {"id": "docs", "name": "Documentation Writer", "emoji": "\U0001f4dd",
     "soul": "You are the Documentation Writer.\n\nResponsibilities:\n- Maintain README, wiki, API docs, inline docstrings\n- Write developer guides and tutorials\n- Keep changelog updated, ensure docs match implementation",
     "tools_allow": ["exec","read","write","edit","glob","grep"], "tools_deny": ["cron"],
     "mention": ["@docs","@writer"]},
    {"id": "security", "name": "Security Auditor", "emoji": "\U0001f6e1",
     "soul": "You are the Security Auditor (READ-ONLY).\n\nResponsibilities:\n- Audit for vulnerabilities (injection, auth bypass, secrets)\n- Check hardcoded secrets, dependency CVEs\n- Block merges with critical security issues\n- NEVER write code directly, only flag issues",
     "tools_allow": ["exec","read","glob","grep"], "tools_deny": ["write","edit","apply_patch","cron"],
     "mention": ["@security","@audit"]},
]

print("Creating Telegram topics...")
topic_map = {}
for agent in TEAM:
    name = f"{agent['emoji']} {agent['name']}"
    try:
        data = json.dumps({"chat_id": CHAT_ID, "name": name}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createForumTopic",
            data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                tid = str(result["result"]["message_thread_id"])
                topic_map[agent["id"]] = tid
                print(f"  {agent['name']} -> topic {tid}")
            else:
                print(f"  {agent['name']} -> FAILED: {result}")
    except Exception as e:
        print(f"  {agent['name']} -> {e}")

print(f"\nTopics created: {len(topic_map)}/{len(TEAM)}")

agent_list = []
agent_bindings = []
for agent in TEAM:
    aid = agent["id"]
    entry = {
        "id": aid,
        "identity": {"name": agent["name"], "emoji": agent["emoji"]},
        "workspace": f"{OPENCLAW_DIR}/workspace-{aid}",
        "agentDir": f"{OPENCLAW_DIR}/agents/{aid}/agent",
        "groupChat": {"mentionPatterns": agent.get("mention", [])},
    }
    if agent.get("is_coordinator"):
        entry["default"] = True
    tools = {}
    if agent.get("tools_allow"):
        tools["allow"] = agent["tools_allow"]
    if agent.get("tools_deny"):
        tools["deny"] = agent["tools_deny"]
    if tools:
        entry["tools"] = tools
    agent_list.append(entry)

    # OpenClaw does not support per-topic bindings; coordinator routes via systemPrompts

agent_bindings.append({"agentId": "coordinator", "match": {"channel": "telegram"}})

agent_names = {a["id"]: a["name"] for a in TEAM}
group_topics = {"1": {"requireMention": False}}
for aid, tid in topic_map.items():
    is_coord = aid == "coordinator"
    if is_coord:
        prompt = "You are in the Coordinator/Tech Lead topic. Handle coordination and delegation directly."
    else:
        prompt = f"This is the {agent_names.get(aid, aid)} topic. Delegate to agent \"{aid}\" using sessions_send."
    group_topics[tid] = {"requireMention": False, "systemPrompt": prompt}

config = {
    "agents": {
        "defaults": {"model": {"primary": "kimi-coding/k2p5"}, "models": {"kimi-coding/k2p5": {}}},
        "list": agent_list,
    },
    "bindings": agent_bindings,
    "channels": {
        "telegram": {
            "enabled": True, "botToken": BOT_TOKEN,
            "dmPolicy": "allowlist", "allowFrom": [OWNER_ID],
            "groupPolicy": "allowlist", "groupAllowFrom": [OWNER_ID],
            "streaming": "off",
            "network": {"autoSelectFamily": False},
            "actions": {"sendMessage": True},
            "groups": {CHAT_ID: {"requireMention": False, "groupPolicy": "open", "topics": group_topics}},
        },
    },
    "messages": {"ackReactionScope": "none", "ackReaction": ""},
    "commands": {"native": "auto", "nativeSkills": "auto", "restart": True},
    "gateway": {"port": 18789, "mode": "local", "auth": {"mode": "token", "token": AUTH_TOKEN}},
    "plugins": {"slots": {"memory": "none"}},
    "tools": {
        "exec": {"security": "full"},
        "agentToAgent": {"enabled": True, "allow": [a["id"] for a in TEAM]},
    },
    "env": {"KIMI_API_KEY": KIMI_KEY},
}

with open(f"{OPENCLAW_DIR}/openclaw.json", "w") as f:
    json.dump(config, f, indent=2)
print(f"Config written: {len(agent_list)} agents, {len(agent_bindings)} bindings")

members_str = "\n".join(f"  - {a['name']} ({a['id']})" for a in TEAM)
for agent in TEAM:
    aid = agent["id"]
    ws = f"{OPENCLAW_DIR}/workspace-{aid}"
    adir = f"{OPENCLAW_DIR}/agents/{aid}/agent"
    sdir = f"{OPENCLAW_DIR}/agents/{aid}/sessions"
    for d in [ws, adir, sdir]:
        os.makedirs(d, exist_ok=True)

    role = "Coordinator" if agent.get("is_coordinator") else "Specialist"
    with open(f"{ws}/SOUL.md", "w") as f:
        f.write(f"# {agent['name']}\n\nRole: {role} | Topic: {topic_map.get(aid,'General')}\nProject: gasclaw (github.com/gastown-publish/gasclaw)\n\n{agent['soul']}\n\n## Team\n{members_str}\n")

    models = {"providers":{"kimi-coding":{"baseUrl":"https://api.kimi.com/coding/","api":"anthropic-messages",
        "models":[{"id":"k2p5","name":"Kimi","reasoning":True,"input":["text","image"],
                   "cost":{"input":0,"output":0,"cacheRead":0,"cacheWrite":0},"contextWindow":262144,"maxTokens":32768}],
        "apiKey":KIMI_KEY}}}
    with open(f"{adir}/models.json", "w") as f:
        json.dump(models, f, indent=2)

    skills_src = f"{OPENCLAW_DIR}/skills"
    skills_dst = f"{ws}/skills"
    os.makedirs(skills_dst, exist_ok=True)
    if os.path.isdir(skills_src):
        for item in os.listdir(skills_src):
            src_path = os.path.join(skills_src, item)
            dst_path = os.path.join(skills_dst, item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

with open(f"{OPENCLAW_DIR}/team-topics.json", "w") as f:
    json.dump(topic_map, f, indent=2)
print(f"Workspaces + SOUL.md created for {len(TEAM)} agents")
print("Done! Restart gateway to activate.")
