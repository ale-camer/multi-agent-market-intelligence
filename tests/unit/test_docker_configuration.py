"""Unit tests validating Dockerfile, .dockerignore, and docker-compose configurations."""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.issue_23
def test_dockerfile_existence_and_directives() -> None:
    """Verify Dockerfile exists and configures valid base image, workdir, and instructions."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile must exist at repository root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Base image verification
    assert "FROM python:3.12-slim" in content or "FROM python:3.1" in content
    assert "WORKDIR /app" in content

    # Python environment optimization
    assert "PYTHONDONTWRITEBYTECODE=1" in content
    assert "PYTHONUNBUFFERED=1" in content

    # Security: Non-root user execution
    assert "useradd" in content
    assert "USER appuser" in content

    # Network exposure
    assert "EXPOSE 8000" in content

    # Built-in healthcheck probe
    assert "HEALTHCHECK" in content
    assert "/health" in content

    # Execution command
    assert "uvicorn" in content
    assert "multi_agent_market_intelligence.api.app:app" in content
    assert "--port" in content and "8000" in content


@pytest.mark.issue_23
def test_dockerignore_configuration() -> None:
    """Verify .dockerignore excludes virtualenvs, caches, and repository metadata."""
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    assert dockerignore_path.is_file(), ".dockerignore must exist at repository root"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip()}

    # Verify critical exclusions
    assert ".git" in lines
    assert ".venv" in lines
    assert "__pycache__" in lines
    assert ".pytest_cache" in lines
    assert ".mypy_cache" in lines
    assert ".ruff_cache" in lines


@pytest.mark.issue_23
def test_docker_compose_syntax_and_specification() -> None:
    """Verify docker-compose.yml syntax and service configuration."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist at repository root"

    raw_yaml = compose_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_yaml)

    assert isinstance(parsed, dict), "docker-compose.yml must be valid YAML"
    assert "services" in parsed, "docker-compose.yml must define services"

    services = parsed["services"]
    assert "api" in services, "Service 'api' must be declared in docker-compose.yml"

    api_service = services["api"]

    # Ports verification
    ports = api_service.get("ports", [])
    assert any("8000:8000" in str(p) for p in ports), "Must map host port 8000 to container 8000"

    # Healthcheck verification
    assert "healthcheck" in api_service, "Service must specify healthcheck"
    healthcheck = api_service["healthcheck"]
    test_cmd = str(healthcheck.get("test", ""))
    assert "/health" in test_cmd

    # Environment settings
    env = api_service.get("environment", [])
    env_str = str(env)
    assert "API_PORT" in env_str or "8000" in env_str


@pytest.mark.issue_23
def test_pyproject_contains_uvicorn_dependency() -> None:
    """Verify pyproject.toml defines uvicorn in dependencies."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    assert "uvicorn" in content, "uvicorn must be listed in pyproject.toml"


@pytest.mark.issue_23
def test_makefile_contains_docker_targets() -> None:
    """Verify Makefile contains docker helper targets."""
    makefile_path = PROJECT_ROOT / "Makefile"
    content = makefile_path.read_text(encoding="utf-8")
    assert "docker-build:" in content
    assert "docker-run:" in content
    assert "docker-compose-up:" in content
    assert "docker-compose-down:" in content
