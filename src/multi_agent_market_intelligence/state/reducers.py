"""Deterministic channel reducer functions for LangGraph state."""

from typing import Any

from multi_agent_market_intelligence.state.models import (
    AgentExecutionRecord,
    ResearchArtifact,
    RiskDecision,
    TradingSignal,
)


def append_signals(
    existing: list[TradingSignal] | None,
    update: list[TradingSignal | dict[str, Any]] | TradingSignal | dict[str, Any] | None,
) -> list[TradingSignal]:
    """Append new trading signals to the channel, converting raw dicts if needed."""
    result: list[TradingSignal] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, TradingSignal):
            result.append(item)
        elif isinstance(item, dict):
            result.append(TradingSignal.model_validate(item))
        else:
            raise TypeError(f"Expected TradingSignal or dict, got {type(item).__name__}")
    return result


def append_artifacts(
    existing: list[ResearchArtifact] | None,
    update: list[ResearchArtifact | dict[str, Any]] | ResearchArtifact | dict[str, Any] | None,
) -> list[ResearchArtifact]:
    """Append new research artifacts to the channel, converting raw dicts if needed."""
    result: list[ResearchArtifact] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, ResearchArtifact):
            result.append(item)
        elif isinstance(item, dict):
            result.append(ResearchArtifact.model_validate(item))
        else:
            raise TypeError(f"Expected ResearchArtifact or dict, got {type(item).__name__}")
    return result


def append_decisions(
    existing: list[RiskDecision] | None,
    update: list[RiskDecision | dict[str, Any]] | RiskDecision | dict[str, Any] | None,
) -> list[RiskDecision]:
    """Append new risk decisions to the channel, converting raw dicts if needed."""
    result: list[RiskDecision] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, RiskDecision):
            result.append(item)
        elif isinstance(item, dict):
            result.append(RiskDecision.model_validate(item))
        else:
            raise TypeError(f"Expected RiskDecision or dict, got {type(item).__name__}")
    return result


def append_records(
    existing: list[AgentExecutionRecord] | None,
    update: (
        list[AgentExecutionRecord | dict[str, Any]] | AgentExecutionRecord | dict[str, Any] | None
    ),
) -> list[AgentExecutionRecord]:
    """Append agent execution records for audit tracking."""
    result: list[AgentExecutionRecord] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, AgentExecutionRecord):
            result.append(item)
        elif isinstance(item, dict):
            result.append(AgentExecutionRecord.model_validate(item))
        else:
            raise TypeError(f"Expected AgentExecutionRecord or dict, got {type(item).__name__}")
    return result


def append_messages(
    existing: list[dict[str, Any]] | None,
    update: list[dict[str, Any]] | dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Append messages to the communication channel without duplicating cumulative returns."""
    result: list[dict[str, Any]] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, dict):
            result.append(item)
        else:
            raise TypeError(f"Expected message dict, got {type(item).__name__}")
    return result


def append_errors(
    existing: list[str] | None,
    update: list[str] | str | None,
) -> list[str]:
    """Append error strings to the errors channel."""
    result: list[str] = list(existing) if existing is not None else []
    if update is None:
        return result

    items = list(update) if isinstance(update, list) else [update]
    if len(result) > 0 and len(items) >= len(result) and items[: len(result)] == result:
        items = items[len(result) :]

    for item in items:
        if isinstance(item, str):
            result.append(item)
        else:
            raise TypeError(f"Expected error string, got {type(item).__name__}")
    return result


def merge_dict(
    existing: dict[str, Any] | None,
    update: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge dictionary updates shallowly into existing dictionary."""
    result: dict[str, Any] = dict(existing) if existing is not None else {}
    if update is not None:
        result.update(update)
    return result
