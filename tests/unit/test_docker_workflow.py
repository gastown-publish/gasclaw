"""Tests for GitHub Actions Docker workflow validation."""

from __future__ import annotations

import yaml


class TestDockerWorkflow:
    """Validate Docker CI/CD workflow configuration."""

    def test_workflow_yaml_is_valid(self):
        """Docker workflow YAML parses correctly."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert workflow["name"] == "Build and Publish Docker Image"
        # 'on' in YAML is parsed as True (boolean)
        assert True in workflow or "on" in workflow
        assert "jobs" in workflow

    def test_workflow_has_required_jobs(self):
        """Workflow has test and build jobs."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert "test" in workflow["jobs"]
        assert "build" in workflow["jobs"]
        assert workflow["jobs"]["build"]["needs"] == "test"

    def test_build_job_has_multi_platform(self):
        """Build job configures multi-platform builds."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        build_steps = workflow["jobs"]["build"]["steps"]
        build_push_step = next(
            s for s in build_steps if s.get("id") == "push"
        )

        assert "linux/amd64" in build_push_step["with"]["platforms"]
        assert "linux/arm64" in build_push_step["with"]["platforms"]

    def test_workflow_uses_ghcr(self):
        """Workflow targets GitHub Container Registry."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        assert workflow["env"]["REGISTRY"] == "ghcr.io"
        assert workflow["env"]["IMAGE_NAME"] == "${{ github.repository }}"

    def test_workflow_triggers_on_push_to_main(self):
        """Workflow triggers on push to main branch."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        # 'on' in YAML is parsed as True (boolean)
        triggers = workflow.get(True) or workflow.get("on")
        assert "push" in triggers
        assert "main" in triggers["push"]["branches"]

    def test_workflow_triggers_on_tags(self):
        """Workflow triggers on version tags."""
        workflow_path = ".github/workflows/docker.yml"
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        # 'on' in YAML is parsed as True (boolean)
        triggers = workflow.get(True) or workflow.get("on")
        assert "v*" in triggers["push"]["tags"]
