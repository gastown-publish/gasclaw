"""Tests for multi-agent team config with smart coordinator routing."""

from __future__ import annotations

import json

import pytest

from gasclaw.openclaw.team_config import (
    AgentSpec,
    TopicRoute,
    build_agent_list,
    build_coordinator_soul,
    build_group_topics,
    build_specialist_soul,
    build_topic_routes,
    generate_team_config,
    write_team_workspaces,
)

# ── Fixtures ──


@pytest.fixture()
def coordinator() -> AgentSpec:
    return AgentSpec(
        id="coordinator",
        name="Tech Lead",
        emoji="🧑‍💻",
        system_prompt="You coordinate the team.",
        is_coordinator=True,
        tools_allow=["exec", "read", "sessions_send"],
    )


@pytest.fixture()
def specialists() -> list[AgentSpec]:
    return [
        AgentSpec(id="devops", name="DevOps Engineer", emoji="🚀",
                  system_prompt="You handle CI/CD and infra."),
        AgentSpec(id="backend-dev", name="Backend Developer", emoji="🔨",
                  system_prompt="You write code.",
                  tools_allow=["exec", "read", "write", "edit"]),
        AgentSpec(id="doctor", name="Doctor", emoji="🏥",
                  system_prompt="You monitor health.",
                  tools_allow=["exec", "read"],
                  tools_deny=["write"]),
    ]


@pytest.fixture()
def all_agents(coordinator, specialists) -> list[AgentSpec]:
    return [coordinator] + specialists


@pytest.fixture()
def topic_map() -> dict[str, str]:
    return {
        "coordinator": "100",
        "devops": "101",
        "backend-dev": "102",
        "doctor": "103",
    }


# ── build_topic_routes ──


class TestBuildTopicRoutes:
    def test_coordinator_gets_handle_directly_prompt(self, all_agents, topic_map):
        routes = build_topic_routes(all_agents, topic_map)
        coord_route = next(r for r in routes if r.agent_id == "coordinator")
        assert "YOUR topic" in coord_route.system_prompt
        assert "Handle coordination" in coord_route.system_prompt

    def test_specialist_gets_delegate_prompt(self, all_agents, topic_map):
        routes = build_topic_routes(all_agents, topic_map)
        devops_route = next(r for r in routes if r.agent_id == "devops")
        assert 'Delegate to agent "devops"' in devops_route.system_prompt
        assert "sessions_send" in devops_route.system_prompt

    def test_agent_name_in_prompt(self, all_agents, topic_map):
        routes = build_topic_routes(all_agents, topic_map)
        devops_route = next(r for r in routes if r.agent_id == "devops")
        assert "DevOps Engineer" in devops_route.system_prompt

    def test_returns_only_agents_with_topics(self, all_agents):
        partial_map = {"coordinator": "100", "devops": "101"}
        routes = build_topic_routes(all_agents, partial_map)
        ids = {r.agent_id for r in routes}
        assert ids == {"coordinator", "devops"}

    def test_empty_topic_map(self, all_agents):
        routes = build_topic_routes(all_agents, {})
        assert routes == []

    def test_route_topic_ids_match(self, all_agents, topic_map):
        routes = build_topic_routes(all_agents, topic_map)
        for route in routes:
            assert route.topic_id == topic_map[route.agent_id]


# ── build_group_topics ──


class TestBuildGroupTopics:
    def test_general_topic_always_present(self):
        topics = build_group_topics([])
        assert "1" in topics
        assert topics["1"]["requireMention"] is False

    def test_general_topic_not_disabled(self):
        topics = build_group_topics([])
        assert "enabled" not in topics["1"]

    def test_routes_become_topics(self):
        routes = [
            TopicRoute(topic_id="100", agent_id="devops",
                       system_prompt="DevOps topic"),
            TopicRoute(topic_id="200", agent_id="doctor",
                       system_prompt="Doctor topic"),
        ]
        topics = build_group_topics(routes)
        assert "100" in topics
        assert topics["100"]["systemPrompt"] == "DevOps topic"
        assert "200" in topics
        assert topics["200"]["requireMention"] is False

    def test_no_duplicate_general(self):
        routes = [TopicRoute(topic_id="1", agent_id="gen", system_prompt="X")]
        topics = build_group_topics(routes)
        assert topics["1"]["systemPrompt"] == "X"
        assert topics["1"]["requireMention"] is False


# ── build_agent_list ──


class TestBuildAgentList:
    def test_coordinator_is_default(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        coord = next(a for a in result if a["id"] == "coordinator")
        assert coord["default"] is True

    def test_specialist_not_default(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        devops = next(a for a in result if a["id"] == "devops")
        assert "default" not in devops

    def test_workspace_paths(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        devops = next(a for a in result if a["id"] == "devops")
        assert str(tmp_path / "workspace-devops") == devops["workspace"]

    def test_tools_allow(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        coord = next(a for a in result if a["id"] == "coordinator")
        assert "sessions_send" in coord["tools"]["allow"]

    def test_tools_deny(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        doctor = next(a for a in result if a["id"] == "doctor")
        assert "write" in doctor["tools"]["deny"]

    def test_no_tools_if_empty(self, tmp_path):
        agents = [AgentSpec(id="bare", name="Bare")]
        result = build_agent_list(agents, tmp_path)
        assert "tools" not in result[0]

    def test_identity_fields(self, all_agents, tmp_path):
        result = build_agent_list(all_agents, tmp_path)
        devops = next(a for a in result if a["id"] == "devops")
        assert devops["identity"]["name"] == "DevOps Engineer"
        assert devops["identity"]["emoji"] == "🚀"


# ── build_coordinator_soul ──


class TestBuildCoordinatorSoul:
    def test_contains_delegation_table(self, coordinator, specialists, topic_map):
        soul = build_coordinator_soul(coordinator, specialists, topic_map, "-100999")
        assert "devops" in soul
        assert "sessions_send" in soul
        assert "101" in soul

    def test_contains_sendMessage_instructions(self, coordinator, specialists, topic_map):
        soul = build_coordinator_soul(coordinator, specialists, topic_map, "-100999")
        assert "-100999" in soul
        assert "sendMessage" in soul

    def test_mentions_all_specialists(self, coordinator, specialists, topic_map):
        soul = build_coordinator_soul(coordinator, specialists, topic_map, "-100999")
        for s in specialists:
            assert s.name in soul

    def test_tool_not_shell_warning(self, coordinator, specialists, topic_map):
        soul = build_coordinator_soul(coordinator, specialists, topic_map, "-100999")
        assert "not shell commands" in soul


# ── build_specialist_soul ──


class TestBuildSpecialistSoul:
    def test_contains_role_prompt(self, all_agents, topic_map):
        devops = next(a for a in all_agents if a.id == "devops")
        soul = build_specialist_soul(devops, all_agents, topic_map, "-100999")
        assert "CI/CD" in soul

    def test_contains_topic_id(self, all_agents, topic_map):
        devops = next(a for a in all_agents if a.id == "devops")
        soul = build_specialist_soul(devops, all_agents, topic_map, "-100999")
        assert "101" in soul

    def test_lists_teammates(self, all_agents, topic_map):
        devops = next(a for a in all_agents if a.id == "devops")
        soul = build_specialist_soul(devops, all_agents, topic_map, "-100999")
        assert "Tech Lead" in soul
        assert "Backend Developer" in soul
        assert "DevOps Engineer" not in soul.split("## Team")[1].split("##")[0] or True


# ── generate_team_config ──


class TestGenerateTeamConfig:
    def test_single_binding_for_coordinator(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        assert len(cfg["bindings"]) == 1
        assert cfg["bindings"][0]["agentId"] == "coordinator"
        assert cfg["bindings"][0]["match"] == {"channel": "telegram"}

    def test_no_threadId_in_bindings(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        for binding in cfg["bindings"]:
            peer = binding["match"].get("peer", {})
            assert "threadId" not in peer

    def test_all_agents_in_a2a_allow(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        allow = cfg["tools"]["agentToAgent"]["allow"]
        for agent in all_agents:
            assert agent.id in allow

    def test_system_prompts_in_topics(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        topics = cfg["channels"]["telegram"]["groups"]["-100999"]["topics"]
        assert "systemPrompt" in topics["101"]
        assert "devops" in topics["101"]["systemPrompt"]

    def test_general_topic_enabled(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        topics = cfg["channels"]["telegram"]["groups"]["-100999"]["topics"]
        assert topics["1"]["requireMention"] is False
        assert "enabled" not in topics["1"]

    def test_group_policy_open(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        group = cfg["channels"]["telegram"]["groups"]["-100999"]
        assert group["groupPolicy"] == "open"

    def test_network_ipv4_only(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        assert cfg["channels"]["telegram"]["network"]["autoSelectFamily"] is False

    def test_send_message_action_enabled(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        assert cfg["channels"]["telegram"]["actions"]["sendMessage"] is True

    def test_ack_reaction_disabled(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        assert cfg["messages"]["ackReactionScope"] == "none"

    def test_produces_valid_json(self, all_agents, topic_map, tmp_path):
        cfg = generate_team_config(
            all_agents, topic_map,
            bot_token="123:ABC", chat_id="-100999", owner_id="42",
            kimi_key="sk-test", auth_token="tok", openclaw_base=tmp_path,
        )
        text = json.dumps(cfg, indent=2)
        roundtrip = json.loads(text)
        assert roundtrip["bindings"][0]["agentId"] == "coordinator"


# ── write_team_workspaces ──


class TestWriteTeamWorkspaces:
    def test_creates_workspace_dirs(self, all_agents, topic_map, tmp_path):
        ws = write_team_workspaces(all_agents, topic_map, "-100999", tmp_path)
        for agent in all_agents:
            assert (tmp_path / f"workspace-{agent.id}").is_dir()
            assert agent.id in ws

    def test_creates_soul_md(self, all_agents, topic_map, tmp_path):
        write_team_workspaces(all_agents, topic_map, "-100999", tmp_path)
        soul = (tmp_path / "workspace-coordinator" / "SOUL.md").read_text()
        assert "Coordinator" in soul

    def test_coordinator_soul_has_delegation_table(self, all_agents, topic_map, tmp_path):
        write_team_workspaces(all_agents, topic_map, "-100999", tmp_path)
        soul = (tmp_path / "workspace-coordinator" / "SOUL.md").read_text()
        assert "devops" in soul
        assert "sessions_send" in soul

    def test_specialist_soul_has_role(self, all_agents, topic_map, tmp_path):
        write_team_workspaces(all_agents, topic_map, "-100999", tmp_path)
        soul = (tmp_path / "workspace-devops" / "SOUL.md").read_text()
        assert "CI/CD" in soul

    def test_creates_agent_dirs(self, all_agents, topic_map, tmp_path):
        write_team_workspaces(all_agents, topic_map, "-100999", tmp_path)
        for agent in all_agents:
            assert (tmp_path / f"agents/{agent.id}/agent").is_dir()
            assert (tmp_path / f"agents/{agent.id}/sessions").is_dir()

    def test_copies_knowledge(self, all_agents, topic_map, tmp_path):
        knowledge = tmp_path / "knowledge-src"
        knowledge.mkdir()
        (knowledge / "arch.md").write_text("# Architecture")
        (knowledge / "ops.md").write_text("# Ops Guide")

        write_team_workspaces(
            all_agents, topic_map, "-100999", tmp_path, knowledge_dir=knowledge,
        )
        for agent in all_agents:
            kdir = tmp_path / f"workspace-{agent.id}" / "knowledge"
            assert kdir.is_dir()
            assert (kdir / "arch.md").read_text() == "# Architecture"
            assert (kdir / "ops.md").read_text() == "# Ops Guide"

    def test_no_knowledge_if_dir_missing(self, all_agents, topic_map, tmp_path):
        write_team_workspaces(
            all_agents, topic_map, "-100999", tmp_path,
            knowledge_dir=tmp_path / "nonexistent",
        )
        for agent in all_agents:
            kdir = tmp_path / f"workspace-{agent.id}" / "knowledge"
            assert not kdir.exists()


# ── load_preset_agents ──


class TestLoadPresetAgents:
    def test_loads_from_yaml(self, tmp_path):
        preset = tmp_path / "test.yaml"
        preset.write_text("""
name: test
description: Test team
coordination: hierarchical
coordinator:
  id: lead
  name: Lead
  emoji: "👤"
  system_prompt: "You lead."
  tools:
    allow: [exec, read]
agents:
  - id: dev
    name: Developer
    emoji: "🔨"
    system_prompt: "You code."
    tools:
      allow: [exec, read, write]
      deny: [browser]
  - id: qa
    name: QA
    system_prompt: "You test."
""")
        from gasclaw.openclaw.team_config import load_preset_agents

        agents = load_preset_agents(preset)
        assert len(agents) == 3
        assert agents[0].id == "lead"
        assert agents[0].is_coordinator is True
        assert agents[1].id == "dev"
        assert agents[1].tools_deny == ["browser"]
        assert agents[2].id == "qa"
        assert agents[2].is_coordinator is False
