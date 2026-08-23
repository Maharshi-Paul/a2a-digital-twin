"""Tests for the LLM-powered decision commentary service.

All tests mock the Gemini client — no real API calls are made.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fake ScoredOrder to avoid importing the full domain stack
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _FakeScoredOrder:
    order_id: int = 1
    external_id: str = "ORD-001"
    total_score: float = 0.7312
    sla_risk: float = 0.85
    wait_time_norm: float = 0.40
    inventory_readiness: float = 0.90
    congestion_factor: float = 0.60
    packing_factor: float = 0.55
    breakdown: dict = field(default_factory=lambda: {
        "sla_risk_weighted": 0.2975,
        "wait_weighted": 0.0600,
        "inventory_weighted": 0.2250,
        "congestion_weighted": 0.0600,
        "packing_weighted": 0.0825,
    })


def _scored() -> _FakeScoredOrder:
    return _FakeScoredOrder()


# ---------------------------------------------------------------------------
# Helpers to patch settings
# ---------------------------------------------------------------------------

def _patch_settings(**overrides):
    """Return a mock settings object with sensible defaults."""
    defaults = {
        "llm_provider": "gemini",
        "gemini_api_key": "sk-test-key",
        "llm_model": "gemini-2.5-flash-lite",
        "llm_commentary_timeout_seconds": 5.0,
        "llm_commentary_max_concurrency": 3,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    # Ensure attribute-style access works
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_noop_when_provider_none():
    """When LLM_PROVIDER=none, returns None with no network call."""
    mock_settings = _patch_settings(llm_provider="none")
    with patch(
        "domains.warehouse.services.decision_commentary.settings",
        mock_settings,
    ):
        # Reset the module-level semaphore so it picks up the mock
        import domains.warehouse.services.decision_commentary as mod
        mod._semaphore = None

        result = await mod.explain_decision(_scored())

    assert result is None


@pytest.mark.asyncio
async def test_noop_when_no_api_key(caplog):
    """When API key is None, returns None and logs a warning."""
    mock_settings = _patch_settings(gemini_api_key=None)
    with patch(
        "domains.warehouse.services.decision_commentary.settings",
        mock_settings,
    ):
        import domains.warehouse.services.decision_commentary as mod
        mod._semaphore = None

        with caplog.at_level(logging.WARNING):
            result = await mod.explain_decision(_scored())

    assert result is None
    assert "GEMINI_API_KEY is not set" in caplog.text


@pytest.mark.asyncio
async def test_returns_none_on_timeout():
    """When the LLM call times out, returns None without raising."""
    mock_settings = _patch_settings(llm_commentary_timeout_seconds=0.001)

    async def _slow_create(**kwargs):
        await asyncio.sleep(10)

    # client.aio.models.generate_content
    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = _slow_create

    with patch(
        "domains.warehouse.services.decision_commentary.settings",
        mock_settings,
    ), patch(
        "google.genai.Client",
        return_value=mock_client_instance,
    ):
        import domains.warehouse.services.decision_commentary as mod
        mod._semaphore = None

        result = await mod.explain_decision(_scored())

    assert result is None


@pytest.mark.asyncio
async def test_returns_commentary_on_success():
    """When the LLM call succeeds, returns the response text."""
    mock_settings = _patch_settings()

    mock_response = MagicMock()
    mock_response.text = "Order prioritized due to high SLA risk."

    mock_generate = AsyncMock(return_value=mock_response)
    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = mock_generate

    with patch(
        "domains.warehouse.services.decision_commentary.settings",
        mock_settings,
    ), patch(
        "google.genai.Client",
        return_value=mock_client_instance,
    ):
        import domains.warehouse.services.decision_commentary as mod
        mod._semaphore = None

        result = await mod.explain_decision(_scored())

    assert result is not None
    assert isinstance(result, str)
    assert len(result) < 500
    assert "SLA" in result
