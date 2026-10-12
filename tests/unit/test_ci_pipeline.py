"""Unit tests validating GitHub Actions CI workflow specification."""

from pathlib import Path
from typing import Any

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CI_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_workflow() -> dict[str, Any]:
    """Helper to read and parse the CI workflow YAML."""
    assert CI_WORKFLOW_PATH.is_file(), f"Workflow file not found at {CI_WORKFLOW_PATH}"
    content = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), "ci.yml must parse into a dictionary"
    return parsed


@pytest.mark.issue_24
def test_ci_workflow_file_exists_and_is_valid_yaml() -> None:
    """Verify that .github/workflows/ci.yml exists and contains valid YAML structure."""
    workflow = _load_ci_workflow()
    assert workflow.get("name") == "CI"
    assert "on" in workflow or True in workflow
    assert "jobs" in workflow


@pytest.mark.issue_24
def test_ci_workflow_triggers() -> None:
    """Verify push and pull_request triggers target main and develop branches."""
    workflow = _load_ci_workflow()
    triggers = workflow.get("on") if "on" in workflow else workflow.get(True, {})

    assert isinstance(triggers, dict), "Triggers must be a mapping"
    assert "push" in triggers, "Workflow must trigger on push events"
    assert "pull_request" in triggers, "Workflow must trigger on pull_request events"

    push_branches = triggers["push"].get("branches", [])
    pr_branches = triggers["pull_request"].get("branches", [])

    assert "main" in push_branches
    assert "develop" in push_branches
    assert "main" in pr_branches
    assert "develop" in pr_branches


@pytest.mark.issue_24
def test_ci_workflow_jobs_declared() -> None:
    """Verify quality, test, and docker jobs are defined."""
    workflow = _load_ci_workflow()
    jobs = workflow["jobs"]

    assert "quality" in jobs, "Workflow must include 'quality' job"
    assert "test" in jobs, "Workflow must include 'test' job"
    assert "docker" in jobs, "Workflow must include 'docker' job"


@pytest.mark.issue_24
def test_ci_quality_job_specification() -> None:
    """Verify quality job executes ruff lint, ruff format check, and mypy typechecking."""
    workflow = _load_ci_workflow()
    quality_job = workflow["jobs"]["quality"]

    assert quality_job.get("runs-on") == "ubuntu-latest"

    steps = quality_job.get("steps", [])
    step_runs = [step.get("run", "") for step in steps if "run" in step]
    all_runs_text = "\n".join(step_runs)

    # Setup Python step verification
    setup_python_steps = [
        step for step in steps if step.get("uses", "").startswith("actions/setup-python")
    ]
    assert len(setup_python_steps) >= 1
    setup_step = setup_python_steps[0]
    with_params = setup_step.get("with", {})
    assert "3.12" in str(with_params.get("python-version", ""))
    assert with_params.get("cache") == "pip"

    # Dependency installation
    assert "pip install" in all_runs_text
    assert ".[all,dev]" in all_runs_text

    # Code quality gates
    assert "ruff check" in all_runs_text
    assert "ruff format --check" in all_runs_text
    assert "mypy" in all_runs_text


@pytest.mark.issue_24
def test_ci_test_job_specification() -> None:
    """Verify test job runs pytest matrix on Python 3.11 and 3.12 with coverage reporting."""
    workflow = _load_ci_workflow()
    test_job = workflow["jobs"]["test"]

    assert test_job.get("runs-on") == "ubuntu-latest"

    # Matrix verification
    matrix = test_job.get("strategy", {}).get("matrix", {})
    python_versions = [str(v) for v in matrix.get("python-version", [])]
    assert "3.11" in python_versions
    assert "3.12" in python_versions

    steps = test_job.get("steps", [])
    step_runs = [step.get("run", "") for step in steps if "run" in step]
    all_runs_text = "\n".join(step_runs)

    # Setup Python with pip caching
    setup_python_steps = [
        step for step in steps if step.get("uses", "").startswith("actions/setup-python")
    ]
    assert len(setup_python_steps) >= 1
    assert setup_python_steps[0].get("with", {}).get("cache") == "pip"

    # Pytest execution with coverage
    assert "pytest" in all_runs_text
    assert "--cov=" in all_runs_text
    assert "--cov-report=xml" in all_runs_text


@pytest.mark.issue_24
def test_ci_docker_job_specification() -> None:
    """Verify docker job configures buildx, builds image, and executes health probe."""
    workflow = _load_ci_workflow()
    docker_job = workflow["jobs"]["docker"]

    assert docker_job.get("runs-on") == "ubuntu-latest"

    steps = docker_job.get("steps", [])
    uses_list = [step.get("uses", "") for step in steps if "uses" in step]
    step_runs = [step.get("run", "") for step in steps if "run" in step]
    all_runs_text = "\n".join(step_runs)

    # Buildx setup
    assert any("setup-buildx-action" in u for u in uses_list)

    # Docker build and run commands
    assert "docker build -t multi-agent-market-intelligence:ci ." in all_runs_text
    assert "docker run" in all_runs_text
    assert "8000:8000" in all_runs_text

    # Healthcheck endpoint probe
    assert "/health" in all_runs_text
    assert "curl" in all_runs_text
