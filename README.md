# Multi-Agent Market Intelligence

An advanced multi-agent orchestration system that simulates a collaborative intelligence environment for portfolio management.

## Architecture
The system utilizes a central Orchestrator (based on LangGraph) to manage state and message passing between three specialized agents:
- **Research Agent**: Scours for news, parses financial reports, and generates sentiment analysis.
- **Trading Analyst**: Processes technical indicators and fundamental data to generate explicit trading signals.
- **Risk & Portfolio Manager**: Acts as the ultimate authority, validating signals against global risk limits and portfolio state to approve, veto, or size operations.

## Constraints
- Paper trading only.
- Loose coupling between agents via explicit message passing and state updates.
- Highly auditable decision-making processes.
