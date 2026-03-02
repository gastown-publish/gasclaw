"""Tests for gasclaw.gastown.installer."""

from __future__ import annotations

import subprocess

import tomlkit

from gasclaw.gastown.installer import gastown_install, setup_kimi_accounts


class TestSetupKimiAccounts:
    def test_creates_config_toml_per_key(self, tmp_path):
        setup_kimi_accounts(["sk-key1", "sk-key2"], accounts_dir=tmp_path)
        assert (tmp_path / "1" / "config.toml").exists()
        assert (tmp_path / "2" / "config.toml").exists()

    def test_config_toml_format(self, tmp_path):
        setup_kimi_accounts(["sk-test-key"], accounts_dir=tmp_path)
        doc = tomlkit.loads((tmp_path / "1" / "config.toml").read_text())
        assert doc["providers"]["kimi-api"]["api_key"] == "sk-test-key"
        assert doc["providers"]["kimi-api"]["base_url"] == "https://api.kimi.com/coding/v1"

    def test_accounts_numbered_from_one(self, tmp_path):
        setup_kimi_accounts(["a", "b", "c"], accounts_dir=tmp_path)
        assert (tmp_path / "1").is_dir()
        assert (tmp_path / "2").is_dir()
        assert (tmp_path / "3").is_dir()

    def test_idempotent(self, tmp_path):
        setup_kimi_accounts(["sk-key1"], accounts_dir=tmp_path)
        setup_kimi_accounts(["sk-key1"], accounts_dir=tmp_path)
        doc = tomlkit.loads((tmp_path / "1" / "config.toml").read_text())
        assert doc["providers"]["kimi-api"]["api_key"] == "sk-key1"

    def test_empty_keys_list_creates_no_accounts(self, tmp_path):
        """Empty keys list should not create any account directories."""
        from pathlib import Path
        setup_kimi_accounts([], accounts_dir=tmp_path)
        # No subdirectories should be created
        assert list(tmp_path.iterdir()) == []

    def test_uses_default_accounts_dir_when_none_provided(self, monkeypatch, tmp_path):
        """setup_kimi_accounts uses ~/.kimi-accounts when accounts_dir is None."""
        from pathlib import Path
        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        setup_kimi_accounts(["sk-test"], accounts_dir=None)

        # Should create account in ~/.kimi-accounts/1/
        assert (tmp_path / ".kimi-accounts" / "1" / "config.toml").exists()


class TestGastownInstall:
    def test_runs_gt_install(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        gastown_install(gt_root=tmp_path, rig_url="/project")
        cmds = [c[0][0] for c in calls]
        assert any("gt" in str(cmd) and "install" in str(cmd) for cmd in cmds)

    def test_runs_gt_rig_add(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        gastown_install(gt_root=tmp_path, rig_url="/project")
        cmds = [c[0][0] for c in calls]
        assert any("rig" in str(cmd) for cmd in cmds)
