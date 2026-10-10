.PHONY: help venv deps lint format typecheck check test test-unit test-integration test-issue ci clean start-issue finish-issue finish-milestone

help:
	@echo "Available commands:"
	@echo "  help             - Show this help message"
	@echo "  venv             - Create virtual environment"
	@echo "  deps             - Install dependencies"
	@echo "  lint             - Run ruff check and format check"
	@echo "  format           - Run ruff format and auto-fix"
	@echo "  typecheck        - Run mypy"
	@echo "  check            - Run lint and typecheck"
	@echo "  test             - Run all tests"
	@echo "  test-unit        - Run unit tests"
	@echo "  test-integration - Run integration tests"
	@echo "  test-issue       - Run tests for a specific issue (requires ID=X)"
	@echo "  ci               - Run check and test"
	@echo "  clean            - Remove caches and build artifacts"
	@echo "  start-issue      - Start a new issue branch (requires ID=X NAME=short-name, optional TYPE=feature|fix)"
	@echo "  finish-issue     - Finish and PR an issue branch (requires ID=X MSG='commit message')"
	@echo "  finish-milestone - Finish and tag a milestone (requires MILESTONE=MX)"

venv:
	python3 -m venv .venv

deps:
	.venv/bin/pip install -e ".[all,dev]"

lint:
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests

format:
	.venv/bin/ruff format src tests
	.venv/bin/ruff check --fix src tests

typecheck:
	.venv/bin/mypy src

check: lint typecheck

test:
	.venv/bin/pytest tests

test-unit:
	.venv/bin/pytest tests/unit

test-integration:
	.venv/bin/pytest tests/integration

test-issue:
	@if [ -z "$(ID)" ]; then echo "Error: ID is required"; exit 1; fi
	.venv/bin/pytest -m issue_$(ID)

ci: check test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ build/ *.egg-info

start-issue:
	@if [ -z "$(ID)" ] || [ -z "$(NAME)" ]; then echo "Error: ID and NAME are required"; exit 1; fi
	$(eval TYPE ?= feature)
	git checkout develop
	git pull origin develop
	git checkout -b $(TYPE)/issue-$(ID)-$(NAME)

finish-issue:
	@if [ -z "$(ID)" ] || [ -z "$(MSG)" ]; then echo "Error: ID and MSG are required"; exit 1; fi
	@BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	if [[ ! "$$BRANCH" =~ issue-$(ID)- ]]; then \
		echo "Error: Current branch $$BRANCH does not match ID $(ID)"; exit 1; \
	fi
	$(MAKE) check
	git add -A
	git commit -m "$(MSG)"
	git push origin HEAD
	@if [ "$(ID)" = "0" ]; then \
		gh pr create --base develop --head $$BRANCH --title "$(MSG)" --body "Issue 0 Setup" || true; \
		gh pr merge $$BRANCH --squash --delete-branch || true; \
	else \
		gh pr create --base develop --head $$BRANCH --title "$(MSG)" --body "Closes #$(ID)" || true; \
		gh pr merge $$BRANCH --squash --delete-branch || true; \
		gh issue close $(ID) || true; \
	fi
	git checkout develop
	git pull origin develop

finish-milestone:
	@if [ -z "$(MILESTONE)" ]; then echo "Error: MILESTONE is required"; exit 1; fi
	git checkout develop
	git pull origin develop
	gh pr create --base main --head develop --title "chore: finish milestone $(MILESTONE)" --body "Merge develop to main for $(MILESTONE)" || true
	gh pr merge --merge || true
	git checkout main
	git pull origin main
	git tag -a $(MILESTONE) -m "Milestone $(MILESTONE)"
	git push origin $(MILESTONE)
	gh milestone edit $(MILESTONE) --state closed || true
	git checkout develop
