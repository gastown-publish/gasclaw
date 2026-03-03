"""Tests for gasclaw.gastown.installer."""

from __future__ import annotations

import subprocess

import pytest
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
            subprocess,
            "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        gastown_install(gt_root=tmp_path, rig_url="/project")
        cmds = [c[0][0] for c in calls]
        assert any("gt" in str(cmd) and "install" in str(cmd) for cmd in cmds)

    def test_runs_gt_rig_add(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append((a, kw)) or subprocess.CompletedProcess(a[0], 0),
        )
        gastown_install(gt_root=tmp_path, rig_url="/project")
        cmds = [c[0][0] for c in calls]
        assert any("rig" in str(cmd) for cmd in cmds)

    def test_gt_install_failure_raises(self, monkeypatch, tmp_path):
        """gt install failure raises CalledProcessError."""

        def mock_run(*a, **kw):
            cmd = a[0] if a else []
            if "install" in str(cmd):
                raise subprocess.CalledProcessError(1, cmd, stderr=b"install failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        try:
            gastown_install(gt_root=tmp_path, rig_url="/project")
            pytest.fail("Expected CalledProcessError")
        except subprocess.CalledProcessError as e:
            assert e.returncode == 1
            assert "install" in str(e.cmd)

    def test_gt_rig_add_failure_raises(self, monkeypatch, tmp_path):
        """gt rig add failure raises CalledProcessError."""

        def mock_run(*a, **kw):
            cmd = a[0] if a else []
            if "rig" in str(cmd) and "add" in str(cmd):
                raise subprocess.CalledProcessError(2, cmd, stderr=b"rig add failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        try:
            gastown_install(gt_root=tmp_path, rig_url="/project")
            pytest.fail("Expected CalledProcessError")
        except subprocess.CalledProcessError as e:
            assert e.returncode == 2
            assert "rig" in str(e.cmd)

    def test_missing_gt_binary_raises(self, monkeypatch, tmp_path):
        """Missing gt binary raises FileNotFoundError."""

        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")

        monkeypatch.setattr(subprocess, "run", raise_not_found)
        try:
            gastown_install(gt_root=tmp_path, rig_url="/project")
            pytest.fail("Expected FileNotFoundError")
        except FileNotFoundError:
            pass

    def test_gt_install_timeout_raises(self, monkeypatch, tmp_path):
        """gt install timeout raises TimeoutExpired."""

        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0] if a else ["gt"], timeout=60)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        try:
            gastown_install(gt_root=tmp_path, rig_url="/project")
            pytest.fail("Expected TimeoutExpired")
        except subprocess.TimeoutExpired:
            pass

    def test_check_true_passed_to_subprocess(self, monkeypatch, tmp_path):
        """check=True is passed to subprocess.run for proper error handling."""
        calls = []

        def mock_run(*a, **kw):
            calls.append(kw.get("check", False))
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        gastown_install(gt_root=tmp_path, rig_url="/project")

        # Both calls should have check=True
        assert all(calls), f"Expected all calls to have check=True, got {calls}"
        assert len(calls) == 2
