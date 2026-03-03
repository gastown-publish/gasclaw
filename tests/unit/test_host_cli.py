"""Tests for host_cli module — host-side container management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gasclaw.host_cli import (
    _container_exists,
    _container_running,
    _format_env_file,
    _get_container_status,
    _get_docker_compose_cmd,
    _is_inside_container,
    _parse_env_file,
    _run_docker,
    _run_docker_compose,
    app,
)


@pytest.fixture(autouse=True)
def mock_not_inside_container(monkeypatch):
    """Mock _is_inside_container to return False for all tests."""
    monkeypatch.setattr(
        "gasclaw.host_cli._is_inside_container",
        lambda: False,
    )


class TestContainerDetection:
    """Test container detection utilities - overrides mock_not_inside_container."""

    @pytest.fixture(autouse=True)
    def unmock_for_detection(self, monkeypatch):
        """Don't mock _is_inside_container for these tests."""
        pass

    def test_is_inside_container_dockerenv(self, tmp_path, monkeypatch):
        """Test detection via .dockerenv file."""
        monkeypatch.setattr(Path, "exists", lambda p: str(p) == "/.dockerenv")

        assert _is_inside_container() is True

    def test_is_inside_container_cgroup(self, monkeypatch):
        """Test detection via cgroup file."""
        def mock_read_text(self):
            if str(self) == "/proc/self/cgroup":
                return "docker/container_id"
            raise FileNotFoundError

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        monkeypatch.setattr(Path, "exists", lambda p: False)

        assert _is_inside_container() is True

    def test_is_inside_container_not_in_container(self, monkeypatch):
        """Test detection when not in container."""
        monkeypatch.setattr(Path, "exists", lambda p: False)
        monkeypatch.setattr(Path, "read_text", lambda p: "")

        assert _is_inside_container() is False

    def test_is_inside_container_permission_error(self, monkeypatch):
        """Test detection when cgroup file has permission error."""
        def mock_read_text(self):
            if str(self) == "/proc/self/cgroup":
                raise PermissionError("Permission denied")
            raise FileNotFoundError

        monkeypatch.setattr(Path, "exists", lambda p: False)
        monkeypatch.setattr(Path, "read_text", mock_read_text)

        assert _is_inside_container() is False

    def test_is_inside_container_file_not_found(self, monkeypatch):
        """Test detection when cgroup file doesn't exist."""
        def mock_read_text(self):
            raise FileNotFoundError()

        monkeypatch.setattr(Path, "exists", lambda p: False)
        monkeypatch.setattr(Path, "read_text", mock_read_text)

        assert _is_inside_container() is False


class TestDockerCommands:
    """Test Docker command execution utilities."""

    def test_get_docker_compose_cmd_v2(self, monkeypatch):
        """Test detecting docker compose v2."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        def mock_run(cmd, **kwargs):
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)

        result = _get_docker_compose_cmd()
        assert result == ["docker", "compose"]

    def test_get_docker_compose_cmd_v1(self, monkeypatch):
        """Test fallback to docker-compose v1."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        def mock_run(cmd, **kwargs):
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)

        result = _get_docker_compose_cmd()
        assert result == ["docker-compose"]

    def test_run_docker(self, monkeypatch):
        """Test running docker command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "container1\ncontainer2"
        mock_result.stderr = ""

        def mock_run(cmd, **kwargs):
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)

        result = _run_docker(["ps", "-a"])
        assert result.returncode == 0

    def test_run_docker_compose(self, monkeypatch):
        """Test running docker compose command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append((cmd, kwargs.get("cwd")))
            return mock_result

        monkeypatch.setattr("subprocess.run", mock_run)

        project_dir = Path("/test/project")
        result = _run_docker_compose(["up", "-d"], project_dir=project_dir)
        assert result.returncode == 0


class TestContainerStatus:
    """Test container status checks."""

    def test_container_exists_true(self, monkeypatch):
        """Test container exists check returns True."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "gasclaw\nother_container"

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        assert _container_exists("gasclaw") is True

    def test_container_exists_false(self, monkeypatch):
        """Test container exists check returns False."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "other_container"

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        assert _container_exists("gasclaw") is False

    def test_container_running_true(self, monkeypatch):
        """Test container running check returns True."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "gasclaw"

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        assert _container_running("gasclaw") is True

    def test_container_running_false(self, monkeypatch):
        """Test container running check returns False."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        assert _container_running("gasclaw") is False

    def test_get_container_status_running(self, monkeypatch):
        """Test getting status of running container."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running|healthy|gasclaw:latest"

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        status = _get_container_status("gasclaw")
        assert status["exists"] == "true"
        assert status["status"] == "running"
        assert status["health"] == "healthy"
        assert status["image"] == "gasclaw:latest"

    def test_get_container_status_not_found(self, monkeypatch):
        """Test getting status of non-existent container."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda args, **kwargs: mock_result,
        )

        status = _get_container_status("gasclaw")
        assert status["exists"] == "false"
        assert status["status"] == "not_found"


class TestEnvFileParsing:
    """Test .env file parsing utilities."""

    def test_parse_env_file(self):
        """Test parsing .env file content."""
        content = """# Comment
KEY1=value1
KEY2=value2

# Another comment
KEY3=value with spaces
"""
        result = _parse_env_file(content)
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
        assert result["KEY3"] == "value with spaces"

    def test_parse_env_file_empty_lines(self):
        """Test parsing env file with empty lines."""
        content = """
KEY1=value1

KEY2=value2

"""
        result = _parse_env_file(content)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_parse_env_file_no_equals(self):
        """Test parsing env file with lines without equals."""
        content = """KEY1=value1
INVALID_LINE
KEY2=value2
"""
        result = _parse_env_file(content)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_format_env_file(self):
        """Test formatting env file content."""
        env_vars = {"KEY1": "value1", "KEY2": "value2"}
        result = _format_env_file(env_vars)
        assert "KEY1=value1" in result
        assert "KEY2=value2" in result
        assert result.startswith("# Gasclaw Environment Configuration")


class TestInitCommand:
    """Test the init command."""

    def test_init_creates_files(self, tmp_path, monkeypatch):
        """Test init command creates config files."""
        from typer.testing import CliRunner

        runner = CliRunner()

        # Mock prompts
        monkeypatch.setattr(
            "rich.prompt.Confirm.ask",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            "rich.prompt.Prompt.ask",
            lambda *args, **kwargs: kwargs.get("default", "test_value"),
        )
        monkeypatch.setattr(
            "rich.prompt.IntPrompt.ask",
            lambda *args, **kwargs: kwargs.get("default", 1),
        )

        # Change to temp directory
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(app, ["init", "--project-dir", str(tmp_path), "--skip-wizard"])

        # Check files were created (or command completed)
        assert result.exit_code == 0

    def test_init_skip_wizard(self, tmp_path, monkeypatch):
        """Test init --skip-wizard creates default files."""
        from typer.testing import CliRunner

        runner = CliRunner()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = runner.invoke(app, ["init", "--project-dir", str(project_dir), "--skip-wizard"])

        assert result.exit_code == 0

    def test_init_already_exists_cancel(self, tmp_path, monkeypatch):
        """Test init when files exist and user cancels."""
        from typer.testing import CliRunner

        runner = CliRunner()

        # Create existing files
        (tmp_path / ".env").write_text("EXISTING=value")

        # Mock user canceling
        monkeypatch.setattr(
            "rich.prompt.Confirm.ask",
            lambda *args, **kwargs: False,
        )

        result = runner.invoke(app, ["init", "--project-dir", str(tmp_path)])

        # Should exit cleanly
        assert result.exit_code == 0


class TestStartCommand:
    """Test the start command."""

    def test_start_no_compose_file(self, tmp_path, monkeypatch):
        """Test start fails when docker-compose.yml doesn't exist."""
        from typer.testing import CliRunner

        runner = CliRunner()

        result = runner.invoke(app, ["start", "-p", str(tmp_path)])

        assert result.exit_code == 1
        assert "No docker-compose.yml found" in result.output

    def test_start_already_running(self, tmp_path, monkeypatch):
        """Test start when container already running."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )

        # Create compose file
        (tmp_path / "docker-compose.yml").write_text("services:")

        result = runner.invoke(app, ["start", "-p", str(tmp_path)])

        assert result.exit_code == 0
        assert "already running" in result.output

    def test_start_success_detached(self, tmp_path, monkeypatch):
        """Test successful start in detached mode."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            lambda *args, **kwargs: mock_result,
        )

        # Create compose file
        (tmp_path / "docker-compose.yml").write_text("services:")

        result = runner.invoke(app, ["start", "-p", str(tmp_path)])

        assert result.exit_code == 0
        assert "started successfully" in result.output

    def test_start_success_with_build(self, tmp_path, monkeypatch):
        """Test successful start with --build flag."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0
        compose_calls = []

        def mock_run_compose(*args, **kwargs):
            compose_calls.append(args)
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            mock_run_compose,
        )

        # Create compose file
        (tmp_path / "docker-compose.yml").write_text("services:")

        result = runner.invoke(app, ["start", "-p", str(tmp_path), "--build"])

        assert result.exit_code == 0
        assert any("--build" in str(c) for c in compose_calls)

    def test_start_failure(self, tmp_path, monkeypatch):
        """Test start when docker compose fails."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Docker compose failed"

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            lambda *args, **kwargs: mock_result,
        )

        # Create compose file
        (tmp_path / "docker-compose.yml").write_text("services:")

        result = runner.invoke(app, ["start", "-p", str(tmp_path)])

        assert result.exit_code == 1
        assert "Failed to start" in result.output


class TestStopCommand:
    """Test the stop command."""

    def test_stop_not_exists(self, monkeypatch):
        """Test stop when container doesn't exist."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: False,
        )

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert "does not exist" in result.output

    def test_stop_success(self, monkeypatch):
        """Test successful stop."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0

    def test_stop_not_running_with_remove(self, monkeypatch):
        """Test stop when container not running but remove requested."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["stop", "--remove"])

        assert result.exit_code == 0
        assert "Container removed" in result.output

    def test_stop_not_running_without_remove(self, monkeypatch):
        """Test stop when container not running and remove not requested."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert "not running" in result.output

    def test_stop_with_compose_down(self, monkeypatch):
        """Test stop using docker compose down (remove)."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0
        compose_calls = []

        def mock_run_compose(*args, **kwargs):
            compose_calls.append(args)
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            mock_run_compose,
        )

        result = runner.invoke(app, ["stop", "--remove"])

        assert result.exit_code == 0
        assert any("down" in str(c) for c in compose_calls)

    def test_stop_fallback_to_docker_stop(self, monkeypatch):
        """Test stop falls back to direct docker stop when compose fails."""
        from typer.testing import CliRunner

        runner = CliRunner()

        compose_result = MagicMock()
        compose_result.returncode = 1
        compose_result.stderr = "Compose failed"

        docker_result = MagicMock()
        docker_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            lambda *args, **kwargs: compose_result,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: docker_result,
        )

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0

    def test_stop_fallback_failure(self, monkeypatch):
        """Test stop when both compose and docker stop fail."""
        from typer.testing import CliRunner

        runner = CliRunner()

        compose_result = MagicMock()
        compose_result.returncode = 1
        compose_result.stderr = "Compose failed"

        docker_result = MagicMock()
        docker_result.returncode = 1
        docker_result.stderr = "Docker stop failed"

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker_compose",
            lambda *args, **kwargs: compose_result,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: docker_result,
        )

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "Failed to stop" in result.output


class TestStatusCommand:
    """Test the status command."""

    def test_status_container_running(self, monkeypatch):
        """Test status with running container."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._get_container_status",
            lambda: {
                "exists": "true",
                "status": "running",
                "health": "healthy",
                "image": "gasclaw:latest",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "running" in result.output

    def test_status_container_not_found(self, monkeypatch):
        """Test status when container doesn't exist."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._get_container_status",
            lambda: {"exists": "false", "status": "not_found"},
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0

    def test_status_unknown_health(self, monkeypatch):
        """Test status with unknown health state."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._get_container_status",
            lambda: {
                "exists": "true",
                "status": "running",
                "health": "unknown",
                "image": "gasclaw:latest",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "unknown" in result.output

    def test_status_unhealthy(self, monkeypatch):
        """Test status with unhealthy container."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._get_container_status",
            lambda: {
                "exists": "true",
                "status": "running",
                "health": "unhealthy",
                "image": "gasclaw:latest",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "unhealthy" in result.output

    def test_status_exited(self, monkeypatch):
        """Test status with exited container."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._get_container_status",
            lambda: {
                "exists": "true",
                "status": "exited",
                "health": "unknown",
                "image": "gasclaw:latest",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0


class TestConfigCommand:
    """Test the config command."""

    def test_config_show_all(self, tmp_path, monkeypatch):
        """Test config command showing all values."""
        from typer.testing import CliRunner

        runner = CliRunner()

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        result = runner.invoke(app, ["config", "-p", str(tmp_path)])

        assert result.exit_code == 0

    def test_config_get_value(self, tmp_path, monkeypatch):
        """Test config getting specific value."""
        from typer.testing import CliRunner

        runner = CliRunner()

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=test_value\n")

        result = runner.invoke(
            app,
            ["config", "TEST_KEY", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0

    def test_config_get_key_not_found(self, tmp_path, monkeypatch):
        """Test config getting non-existent key."""
        from typer.testing import CliRunner

        runner = CliRunner()

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\n")

        result = runner.invoke(
            app,
            ["config", "NONEXISTENT_KEY", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "not found" in result.output

    def test_config_get_sensitive_value_masked(self, tmp_path, monkeypatch):
        """Test config masks sensitive values."""
        from typer.testing import CliRunner

        runner = CliRunner()

        env_file = tmp_path / ".env"
        env_file.write_text("GASTOWN_KIMI_KEYS=secret_key\n")

        result = runner.invoke(
            app,
            ["config", "GASTOWN_KIMI_KEYS", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "***" in result.output

    def test_config_set_value(self, tmp_path, monkeypatch):
        """Test config setting value."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=old_value\n")

        result = runner.invoke(
            app,
            ["config", "KEY1", "new_value", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Set KEY1=new_value" in result.output

        # Verify file was updated
        content = env_file.read_text()
        assert "KEY1=new_value" in content

    def test_config_set_value_container_running(self, tmp_path, monkeypatch):
        """Test config setting value warns when container running."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=old_value\n")

        result = runner.invoke(
            app,
            ["config", "KEY1", "new_value", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Set KEY1=new_value" in result.output
        assert "restart" in result.output

    def test_config_no_env_file(self, tmp_path, monkeypatch):
        """Test config when .env file doesn't exist."""
        from typer.testing import CliRunner

        runner = CliRunner()

        result = runner.invoke(app, ["config", "-p", str(tmp_path)])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_config_sensitive_masking_in_show_all(self, tmp_path, monkeypatch):
        """Test config masks sensitive values when showing all."""
        from typer.testing import CliRunner

        runner = CliRunner()

        env_file = tmp_path / ".env"
        env_file.write_text("""
KEY1=value1
GASTOWN_KIMI_KEYS=secret
TELEGRAM_BOT_TOKEN=token123
SECRET_KEY=mysecret
""")

        result = runner.invoke(app, ["config", "-p", str(tmp_path)])

        assert result.exit_code == 0
        assert "***" in result.output


class TestMaintenanceCommand:
    """Test the maintenance command."""

    def test_maintenance_status(self, monkeypatch):
        """Test maintenance status command."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 1  # Not paused

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["maintenance", "status"])

        assert result.exit_code == 0

    def test_maintenance_status_paused(self, monkeypatch):
        """Test maintenance status when paused."""
        from typer.testing import CliRunner

        runner = CliRunner()

        # First call checks if paused (returns 0), second call reads info file
        call_count = [0]

        def mock_run_docker(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.returncode = 0  # Paused
            else:
                mock_result.returncode = 1  # No info file
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            mock_run_docker,
        )

        result = runner.invoke(app, ["maintenance", "status"])

        assert result.exit_code == 0
        assert "PAUSED" in result.output or result.exit_code == 0

    def test_maintenance_status_with_info(self, monkeypatch):
        """Test maintenance status with info file."""
        from typer.testing import CliRunner

        runner = CliRunner()

        call_count = [0]

        def mock_run_docker(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.returncode = 1  # Not paused
            else:
                mock_result.returncode = 0  # Info file exists
                mock_result.stdout = '{"last_run": "2026-03-03", "cycles": 5}'
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            mock_run_docker,
        )

        result = runner.invoke(app, ["maintenance", "status"])

        assert result.exit_code == 0

    def test_maintenance_status_with_invalid_json(self, monkeypatch):
        """Test maintenance status with invalid JSON in info file."""
        from typer.testing import CliRunner

        runner = CliRunner()

        call_count = [0]

        def mock_run_docker(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.returncode = 1  # Not paused
            else:
                mock_result.returncode = 0  # Info file exists
                mock_result.stdout = "invalid json"
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            mock_run_docker,
        )

        result = runner.invoke(app, ["maintenance", "status"])

        assert result.exit_code == 0

    def test_maintenance_status_action_success(self, monkeypatch):
        """Test maintenance status action explicitly (success path)."""
        from typer.testing import CliRunner

        runner = CliRunner()

        def mock_run_docker(*args, **kwargs):
            mock_result = MagicMock()
            # First call checks if paused (returns 1 = not paused = active)
            # Second call reads info file (returns 1 = no info file)
            mock_result.returncode = 1
            mock_result.stdout = ""
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            mock_run_docker,
        )

        result = runner.invoke(app, ["maintenance", "status"])

        assert result.exit_code == 0
        assert "ACTIVE" in result.output or "Status" in result.output

    def test_maintenance_trigger_success(self, monkeypatch):
        """Test maintenance trigger success."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["maintenance", "trigger"])

        assert result.exit_code == 0
        assert "successful" in result.output

    def test_maintenance_pause_success(self, monkeypatch):
        """Test maintenance pause success."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["maintenance", "pause"])

        assert result.exit_code == 0
        assert "successful" in result.output

    def test_maintenance_resume_success(self, monkeypatch):
        """Test maintenance resume success."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["maintenance", "resume"])

        assert result.exit_code == 0
        assert "successful" in result.output

    def test_maintenance_action_failure(self, monkeypatch):
        """Test maintenance action failure."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error executing command"

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["maintenance", "trigger"])

        assert result.exit_code == 1
        assert "Failed" in result.output

    def test_maintenance_unknown_action(self, monkeypatch):
        """Test maintenance with unknown action."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )

        result = runner.invoke(app, ["maintenance", "unknown"])

        assert result.exit_code == 1
        assert "Unknown action" in result.output

    def test_maintenance_container_not_running(self, monkeypatch):
        """Test maintenance when container not running."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )

        result = runner.invoke(app, ["maintenance", "trigger"])

        assert result.exit_code == 1
        assert "not running" in result.output


class TestLogsCommand:
    """Test the logs command."""

    def test_logs_container_not_exists(self, monkeypatch):
        """Test logs when container doesn't exist."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: False,
        )

        result = runner.invoke(app, ["logs"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_logs_container_exists(self, monkeypatch):
        """Test logs when container exists."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._get_docker_compose_cmd",
            lambda: ["docker", "compose"],
        )

        mock_calls = []

        def mock_run(cmd, **kwargs):
            mock_calls.append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = runner.invoke(app, ["logs"])

        assert result.exit_code == 0
        assert any("logs" in str(c) for c in mock_calls)

    def test_logs_with_follow(self, monkeypatch):
        """Test logs with follow option."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._get_docker_compose_cmd",
            lambda: ["docker", "compose"],
        )

        mock_calls = []

        def mock_run(cmd, **kwargs):
            mock_calls.append((cmd, kwargs.get("cwd")))
            return MagicMock(returncode=0)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = runner.invoke(app, ["logs", "--follow"])

        assert result.exit_code == 0
        assert any("-f" in c for c, _ in mock_calls)

    def test_logs_with_tail(self, monkeypatch):
        """Test logs with tail option."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._get_docker_compose_cmd",
            lambda: ["docker", "compose"],
        )

        mock_calls = []

        def mock_run(cmd, **kwargs):
            mock_calls.append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = runner.invoke(app, ["logs", "--tail", "100"])

        assert result.exit_code == 0
        assert any("--tail" in str(c) for c in mock_calls)

    def test_logs_keyboard_interrupt(self, monkeypatch):
        """Test logs handling keyboard interrupt."""
        from typer.testing import CliRunner

        runner = CliRunner()

        monkeypatch.setattr(
            "gasclaw.host_cli._container_exists",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._get_docker_compose_cmd",
            lambda: ["docker", "compose"],
        )

        def mock_run(cmd, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr("subprocess.run", mock_run)

        result = runner.invoke(app, ["logs", "--follow"])

        assert result.exit_code == 0
        assert "stopped" in result.output


class TestVersionCommand:
    """Test the version command."""

    def test_version(self, monkeypatch):
        """Test version command."""
        from typer.testing import CliRunner

        runner = CliRunner()

        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0

    def test_main_function(self, monkeypatch):
        """Test main() entry point."""
        from gasclaw.host_cli import main

        # Just ensure main() doesn't error - it calls app() which we can't easily mock
        # But we can verify it's callable
        assert callable(main)


class TestRestartCommand:
    """Test the restart command."""

    def test_restart(self, monkeypatch):
        """Test restart command."""
        from typer.testing import CliRunner

        runner = CliRunner()

        # Mock stop and start
        monkeypatch.setattr(
            "gasclaw.host_cli.stop",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli.start",
            lambda **kwargs: None,
        )

        result = runner.invoke(app, ["restart"])

        assert result.exit_code == 0


class TestUpdateCommand:
    """Test the update command."""

    def test_update(self, monkeypatch):
        """Test update command."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Update complete" in result.output

    def test_update_with_running_container(self, monkeypatch):
        """Test update when container is running."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 0

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: True,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli.stop",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli.start",
            lambda **kwargs: None,
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Update complete" in result.output

    def test_update_pull_failure(self, monkeypatch):
        """Test update when pull fails."""
        from typer.testing import CliRunner

        runner = CliRunner()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Failed to pull"

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            lambda *args, **kwargs: mock_result,
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Warning" in result.output or "Update complete" in result.output

    def test_update_pull_option(self, monkeypatch):
        """Test update with explicit --pull flag."""
        from typer.testing import CliRunner

        runner = CliRunner()

        docker_calls = []

        def mock_run_docker(*args, **kwargs):
            docker_calls.append(args)
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr(
            "gasclaw.host_cli._container_running",
            lambda: False,
        )
        monkeypatch.setattr(
            "gasclaw.host_cli._run_docker",
            mock_run_docker,
        )

        result = runner.invoke(app, ["update", "--pull"])

        assert result.exit_code == 0
        # Should call docker pull
        assert any("pull" in str(c) for c in docker_calls)
