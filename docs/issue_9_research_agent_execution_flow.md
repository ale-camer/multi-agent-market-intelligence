# Issue 9: Research Agent Execution Flow

**Branch**: `feature/issue-9-research-agent-execution-flow`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #10)
**Milestone**: M2 - Research Agent Implementation

## Objective
Implement the autonomous `ResearchAgent` integrating news extraction, financial reports loading, and sentiment analysis into a cohesive execution flow. Subclassing `BaseAgent`, the `ResearchAgent` processes `MarketIntelligenceState`, extracts multi-source intelligence for target ticker symbols, computes directional sentiment scores and confidence levels, produces structured `ResearchArtifact`s adhering to state reducer channels, broadcasts intelligence notifications via `MessageBus`, and provides an orchestrator node handler adapter.

## Acceptance Criteria
- [x] `src/multi_agent_market_intelligence/research/agent.py` implements `ResearchAgent(BaseAgent)`:
  - Initializes with configurable `AgentConfig` (default role `AgentRole.RESEARCH`), `MessageBus`, `NewsExtractor`, `FinancialReportLoader`, `FinancialSentimentAnalyzer`, and default `symbols`.
  - Implements `process(state: MarketIntelligenceState) -> dict[str, Any]` executing the full research cycle:
    1. Resolves target symbols from state context (or defaults).
    2. Fetches and parses news articles with sentiment scoring.
    3. Ingests or generates financial reports (10-K, 10-Q) with section-targeted sentiment.
    4. Computes composite confidence-weighted sentiment per symbol.
    5. Produces typed `ResearchArtifact`s including a consolidated intelligence summary.
    6. Publishes market intelligence notifications over the `MessageBus`.
    7. Returns state update dict with `artifacts`, `current_step="research"`, and context enrichment.
  - Implements `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Provides `create_research_node_handler(agent: ResearchAgent | None = None)` producing a callable `NodeHandler` compatible with `MarketIntelligenceOrchestrator`.
- [x] `src/multi_agent_market_intelligence/research/__init__.py` exposes `ResearchAgent` and `create_research_node_handler`.
- [x] `src/multi_agent_market_intelligence/agents/__init__.py` and `src/multi_agent_market_intelligence/__init__.py` re-export `ResearchAgent`.
- [x] Unit tests in `tests/unit/test_research_agent.py` marked with `@pytest.mark.issue_9` validating:
  - Agent instantiation with default and custom tools/config.
  - End-to-end `process` execution for single and multiple symbols.
  - Generated `ResearchArtifact` attributes, sentiment values, and metadata.
  - Message publishing to `MessageBus`.
  - Audit logging via template `execute(state)` method (`AgentExecutionRecord`).
  - Orchestrator node handler adapter execution in standalone and DAG context.
  - Error isolation and defensive handling for empty context or missing data.
- [x] `make check` (ruff lint, ruff format check, mypy strict) and `make test-issue ID=9` pass cleanly.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=9 NAME=research-agent-execution-flow
```

### 2. Autonomous Research Agent Implementation
- **File**: `src/multi_agent_market_intelligence/research/agent.py`
- **Change**: Implement `ResearchAgent(BaseAgent)`:
  - Constructor accepting `config`, `message_bus`, `news_extractor`, `report_loader`, `sentiment_analyzer`, `symbols`.
  - Synchronous `process(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Asynchronous `process_async(state: MarketIntelligenceState) -> dict[str, Any]`.
  - Factory `create_research_node_handler(agent: ResearchAgent | None = None) -> Callable[[OrchestratorState], dict[str, Any]]`.

### 3. Package Exports
- **File**: `src/multi_agent_market_intelligence/research/__init__.py`
- **Change**: Export `ResearchAgent` and `create_research_node_handler`.
- **File**: `src/multi_agent_market_intelligence/agents/__init__.py`
- **Change**: Re-export `ResearchAgent`.
- **File**: `src/multi_agent_market_intelligence/__init__.py`
- **Change**: Re-export `ResearchAgent` and `create_research_node_handler`.

### 4. Unit Testing
- **File**: `tests/unit/test_research_agent.py`
- **Change**: Comprehensive unit tests tagged with `@pytest.mark.issue_9`:
  - Lifecycle and status transitions (IDLE -> RUNNING -> SUCCESS).
  - Single and multi-ticker research execution flow.
  - Synthesis artifact creation with composite sentiment score.
  - MessageBus message broadcast verification.
  - State reducer compatibility with `append_artifacts`.
  - Orchestrator node handler function validation.

### 5. Verification & Quality Gates
```bash
make format
make check
make test-issue ID=9
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=9 MSG="feat(research): implement ResearchAgent execution flow and orchestrator adapter"
```

## Decisions
- **Subclassing BaseAgent**: Inherits all Milestone 1 agent primitives, including template execution (`execute`), status tracking (`AgentStatus`), duration profiling, error recovery, and inbox message handling.
- **Hierarchical Artifact Generation**: The Research Agent produces both granular artifacts (individual news articles and financial reports with their respective sentiment scores) and a consolidated summary artifact per ticker. This provides detailed auditability while giving downstream agents (`TradingAnalyst`) a high-level composite signal.
- **Orchestrator Adapter Pattern**: Providing `create_research_node_handler()` enables plugging the concrete `ResearchAgent` directly into the `MarketIntelligenceOrchestrator` without modifying existing orchestrator DAG code or breaking backward compatibility with default handlers.
