# Issue 0: Setup

**Branch**: `feature/issue-0-setup`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop`
**Milestone**: M0 - Setup

## Objective
Establish the foundational scaffolding, tooling, and documentation for the Multi-Agent Market Intelligence project (P-11), adhering to strict engineering rules.

## Acceptance Criteria
- [x] `docs/issue_0_setup.md`, `.agents/rules/workflow.md`, `README.md`, `docs/roadmap.md` created
- [x] `.venv` and virtual environment setup with dependencies installed
- [x] `pyproject.toml` configured with `dev`, `all`, and layer groups, plus strict tools configuration (ruff, mypy, pytest)
- [x] `Makefile` is fully documented and includes all lifecycle and quality targets
- [x] Empty directories created: `src/multi_agent_market_intelligence/`, `tests/unit/`, `tests/integration/`, `infra/`, `docs/`, `scripts/`
- [x] `tests/unit/test_smoke.py` created and marked with `@pytest.mark.issue_0`
- [x] `scripts/bootstrap_github.sh` created
- [x] `make check` and `make test-issue ID=0` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
git init -b main
git commit --allow-empty -m "chore: initial commit"
git checkout -b develop
git checkout -b feature/issue-0-setup
```

### 2. Workflow Rules & Documentation
- **File**: `.agents/rules/workflow.md`
- **Change**: Define the comprehensive engineering rules for the project (Git flow, phases, quality gates, Makefile, English-only).
- **File**: `README.md`
- **Change**: Draft project architecture (LangGraph/Orchestrator, Research Agent, Trading Analyst, Risk Manager).
- **File**: `docs/roadmap.md`
- **Change**: Define project milestones (M1 to M5) and the 15-25 atomic issues mapped to them.

### 3. Project Configuration & Dependencies
- **File**: `pyproject.toml`
- **Change**: Configure project metadata, dependencies, optional groups (`dev`, `all`), and strictly configure `ruff`, `mypy`, and `pytest` (`issue_0` marker).
- **File**: `.gitignore`
- **Change**: Add standard Python, OS, and IDE ignores.
- **File**: `.env.example`
- **Change**: Add placeholder environment variables.

### 4. Makefile Automation
- **File**: `Makefile`
- **Change**: Create all specified targets (`help`, `venv`, `deps`, `lint`, `format`, `typecheck`, `check`, `test`, `test-unit`, `test-integration`, `test-issue`, `ci`, `clean`, `start-issue`, `finish-issue`, `finish-milestone`) with self-documentation.

### 5. Scaffolding & Smoke Test
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Create empty init file.
- **File**: `tests/unit/test_smoke.py`
- **Change**: Create a basic test importing the package, marked with `@pytest.mark.issue_0`.
- **File**: `scripts/bootstrap_github.sh`
- **Change**: Create bash script for GitHub CLI initialization of repo, milestones, and issues.
- **File**: `scripts/.gitkeep`, `infra/.gitkeep`, `tests/integration/.gitkeep`
- **Change**: Create empty files to ensure directories are tracked.

### 6. Verification & Quality Gates
```bash
make venv
make deps
make test-issue ID=0
make check
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=0 MSG="chore(setup): day 0 scaffolding"
```
