# Issue 24: GitHub Actions CI Pipeline

**Branch**: `feature/issue-24-github-actions-ci-pipeline`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #24)
**Milestone**: M5 - FastAPI API, Integration & Delivery

## Objective
Establish an automated Continuous Integration (CI) pipeline using GitHub Actions to continuously validate code style, formatting, strict static typing, unit/integration test execution with coverage reporting, and Docker container build integrity across all pull requests and merges to `develop` and `main`. This establishes continuous automated quality gate enforcement closing the infrastructure automation phase of Milestone 5.

## Acceptance Criteria
- [x] `.github/workflows/ci.yml` workflow specification implements:
  - **Triggers**:
    - `push` events to `main` and `develop`.
    - `pull_request` events targeting `main` and `develop`.
  - **Job 1: `quality` (Lint & Typecheck)**:
    - Runs on `ubuntu-latest` with Python 3.12.
    - Caches pip dependency store using `actions/setup-python@v5`.
    - Installs project dependencies via `pip install -e ".[all,dev]"`.
    - Executes Ruff linter: `ruff check src tests`.
    - Executes Ruff format verification: `ruff format --check src tests`.
    - Executes strict Mypy typechecker: `mypy src`.
  - **Job 2: `test` (Test Suite & Coverage)**:
    - Runs on `ubuntu-latest` with Python matrix (`3.11`, `3.12`).
    - Caches pip dependency store.
    - Installs project dependencies via `pip install -e ".[all,dev]"`.
    - Executes full test suite with coverage: `pytest --cov=multi_agent_market_intelligence --cov-report=term --cov-report=xml tests`.
  - **Job 3: `docker` (Container Build & Health Validation)**:
    - Runs on `ubuntu-latest`.
    - Sets up Docker Buildx via `docker/setup-buildx-action@v3`.
    - Builds container image: `docker build -t multi-agent-market-intelligence:ci .`.
    - Launches container and validates health probe response from `http://localhost:8000/health`.
- [x] `tests/unit/test_ci_pipeline.py` marked with `@pytest.mark.issue_24` implements:
  - Verifies `.github/workflows/ci.yml` exists and parses as valid YAML.
  - Verifies workflow triggers (`push` and `pull_request` on `main` and `develop`).
  - Verifies presence of `quality`, `test`, and `docker` jobs.
  - Verifies essential quality check steps (`ruff check`, `ruff format`, `mypy`).
  - Verifies test execution step with pytest and coverage reporting.
  - Verifies Docker build and health verification steps.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=24` pass cleanly.
- [x] Full test suite (`make test`) passes with zero regressions.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=24 NAME=github-actions-ci-pipeline
```

### 2. GitHub Actions CI Workflow Specification
- **File**: `.github/workflows/ci.yml`
- **Change**: Define `quality`, `test`, and `docker` CI jobs with caching, matrix execution, and container health probe.

### 3. CI Workflow Verification Test Suite
- **File**: `tests/unit/test_ci_pipeline.py`
- **Change**: Implement YAML syntax and configuration validation tests tagged with `@pytest.mark.issue_24`.

### 4. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=24
make test
```

### 5. Git & Issue Finish
```bash
make finish-issue ID=24 MSG="ci: implement GitHub Actions automated workflow for linting, testing, and docker build"
```

## Decisions
- **Three-Tier Pipeline Separation**: Splits CI into `quality` (fast fail for lint/formatting/types), `test` (matrix validation across Python 3.11 and 3.12 with pytest-cov), and `docker` (container buildability and healthcheck verification) for clear diagnostic reporting and parallel execution.
- **Pip Layer Caching**: Employs `actions/setup-python` native cache mechanism (`cache: 'pip'`) to drastically accelerate pipeline execution on repeated workflow triggers.
- **Live Container Sanity Verification**: The `docker` job not only builds the image but starts the container and queries `http://localhost:8000/health`, preventing regressions in container entrypoint or port binding before deployment.
