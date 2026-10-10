#!/usr/bin/env bash
set -e

echo "Creating GitHub repository..."
gh repo create multi-agent-market-intelligence --public --source=. --remote=origin --push

echo "Pushing branches..."
git push -u origin main
git push -u origin develop

echo "Creating milestones..."
gh api repos/{owner}/{repo}/milestones -f title="M1 - Core Infrastructure & Orchestrator Setup" > /dev/null
gh api repos/{owner}/{repo}/milestones -f title="M2 - Research Agent Implementation" > /dev/null
gh api repos/{owner}/{repo}/milestones -f title="M3 - Trading Analyst Implementation" > /dev/null
gh api repos/{owner}/{repo}/milestones -f title="M4 - Risk & Portfolio Manager Implementation" > /dev/null
gh api repos/{owner}/{repo}/milestones -f title="M5 - FastAPI API, Integration & Delivery" > /dev/null

echo "Creating issues..."
# M1
gh issue create --title "Orchestrator base class and DAG design" --body "Implementation of Issue 1" --milestone 1
gh issue create --title "State management protocol" --body "Implementation of Issue 2" --milestone 1
gh issue create --title "Message passing mechanisms" --body "Implementation of Issue 3" --milestone 1
gh issue create --title "Base Agent interface" --body "Implementation of Issue 4" --milestone 1
gh issue create --title "Orchestrator integration tests setup" --body "Implementation of Issue 5" --milestone 1
# M2
gh issue create --title "News extraction tools" --body "Implementation of Issue 6" --milestone 2
gh issue create --title "Financial reports loader" --body "Implementation of Issue 7" --milestone 2
gh issue create --title "Sentiment analysis logic" --body "Implementation of Issue 8" --milestone 2
gh issue create --title "Research Agent execution flow" --body "Implementation of Issue 9" --milestone 2
gh issue create --title "Research Agent mock tests" --body "Implementation of Issue 10" --milestone 2
# M3
gh issue create --title "Technical indicators calculator" --body "Implementation of Issue 11" --milestone 3
gh issue create --title "Fundamental data loader" --body "Implementation of Issue 12" --milestone 3
gh issue create --title "Trading signal generator" --body "Implementation of Issue 13" --milestone 3
gh issue create --title "Trading Analyst execution flow" --body "Implementation of Issue 14" --milestone 3
gh issue create --title "Trading Analyst signal tests" --body "Implementation of Issue 15" --milestone 3
# M4
gh issue create --title "Global risk limits configuration" --body "Implementation of Issue 16" --milestone 4
gh issue create --title "Portfolio state tracker" --body "Implementation of Issue 17" --milestone 4
gh issue create --title "Signal validation logic" --body "Implementation of Issue 18" --milestone 4
gh issue create --title "Risk & Portfolio Manager execution flow" --body "Implementation of Issue 19" --milestone 4
gh issue create --title "Risk Manager integration tests" --body "Implementation of Issue 20" --milestone 4
# M5
gh issue create --title "FastAPI setup and routing" --body "Implementation of Issue 21" --milestone 5
gh issue create --title "API endpoints for portfolio" --body "Implementation of Issue 22" --milestone 5
gh issue create --title "Docker and docker-compose configuration" --body "Implementation of Issue 23" --milestone 5
gh issue create --title "GitHub Actions CI pipeline" --body "Implementation of Issue 24" --milestone 5
gh issue create --title "Final end-to-end integration test" --body "Implementation of Issue 25" --milestone 5

echo "Done."
