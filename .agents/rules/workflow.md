# Workflow Rules

This document contains the engineering rules for the Multi-Agent Market Intelligence project.

## 1. Git Flow & Branches
- **Two permanent branches**: `main` (production, always green) and `develop` (integration).
- **NEVER** work directly on `main` or `develop`.
- Issue branches are created from `develop` with format `feature/issue-X-name` or `fix/issue-X-name`.
- PRs from issue branches to `develop` use **Squash Merge**.
- PRs from `develop` to `main` use **Merge Commit** (without squash) when closing a milestone.
- **Conventional Commits** must be used for all commits: `type(scope): description`.

## 2. Issue Methodology (Two Phases)
- **Phase A (Plan)**: Create `docs/issue_X_name.md`. No code is written. Wait for user to run `make start-issue`.
- **Phase B (Implementation)**: Implement the plan. Execute quality gates, mark acceptance criteria, update status, and return to user.
- The `docs/issue_X_name.md` file is the **ONLY** source of truth for the issue plan.

## 3. Automation (Makefile & Quality Gates)
- All workflows must use the `Makefile`.
- `make check` (ruff + mypy) and `make test-issue ID=X` must pass before delivering Phase B.
- Tests must be marked with `@pytest.mark.issue_X` and registered in `pyproject.toml`.
- Virtual environments must reside in `.venv`. Make targets must invoke binaries from `.venv/bin/`.

## 4. Execution Rules
- **USER** executes Git and GitHub commands (e.g., `make start-issue`, `make finish-issue`, `make finish-milestone`).
- **AGENT** executes local verification commands (`make venv`, `make deps`, `make check`, `make test`, etc.).

## 5. Autonomy
- Technical design decisions, ambiguity resolution, and minor architecture choices should be made autonomously to avoid blocking.
- Any decision made must be briefly documented in the `## Decisions` section of the issue document.

## 6. Language
- **English ONLY** for all code, variables, docstrings, commit messages, and documentation (`README`, `docs/`, `.agents/`).

## 7. Communication
- Keep responses ultra-brief. State what was done, show check results, and provide the next command for the user.
