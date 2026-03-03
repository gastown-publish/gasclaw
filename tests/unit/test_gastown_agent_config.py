"""Tests for gasclaw.gastown.agent_config."""

from __future__ import annotations

import subprocess

import pytest

from gasclaw.gastown.agent_config import configure_agent


class TestConfigureAgent:
    def test_sets_agent_command(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        cmd_strs = [" ".join(str(x) for x in c[0][0]) for c in calls]
        assert any("config" in s and "agent" in s and "set" in s for s in cmd_strs)

    def test_sets_default_agent(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        cmd_strs = [" ".join(str(x) for x in c[0][0]) for c in calls]
        assert any("default-agent" in s for s in cmd_strs)

    def test_default_agent_name_is_kimi_claude(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        set_cmd = [c for c in calls if "set" in c]
        assert any("kimi-claude" in c for c in set_cmd)
        default_cmd = [c for c in calls if "default-agent" in c]
        assert any("kimi-claude" in c for c in default_cmd)

    def test_default_command_uses_claude(self, monkeypatch):
        """Default agent command is plain claude (permissions via config file)."""
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        set_cmd = [c for c in calls if "set" in c]
        assert len(set_cmd) == 1
        assert set_cmd[0][-1] == "claude"

    def test_custom_agent_name(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent(agent_name="custom-agent", agent_command="claude --model kimi")
        cmd_strs = [" ".join(str(x) for x in c) for c in calls]
        assert any("custom-agent" in s for s in cmd_strs)
        assert any("claude --model kimi" in s for s in cmd_strs)

    def test_idempotent(self, monkeypatch):
        """Running configure_agent twice does not raise."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        configure_agent()

    def test_runs_two_commands(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        configure_agent()
        assert len(calls) == 2

    def test_check_true_passed(self, monkeypatch):
        """Both subprocess calls use check=True."""
        checks = []

        def mock_run(*a, **kw):
            checks.append(kw.get("check", False))
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        configure_agent()
        assert all(checks)

    def test_agent_set_failure_raises(self, monkeypatch):
        def mock_run(*a, **kw):
            cmd = a[0]
            if "set" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        with pytest.raises(subprocess.CalledProcessError):
            configure_agent()
