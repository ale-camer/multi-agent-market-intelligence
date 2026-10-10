import pytest

import multi_agent_market_intelligence


@pytest.mark.issue_0
def test_smoke() -> None:
    """Smoke test to ensure the package is importable."""
    assert multi_agent_market_intelligence is not None
