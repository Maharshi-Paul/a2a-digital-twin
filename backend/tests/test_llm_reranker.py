"""Tests for the LLM-assisted batch re-ranking service.

Covers the safety critical-path for the Gemini migration:
- successful rerank
- timeout -> fallback
- malformed/partial ID response -> fallback
- empty pending list -> no API call
- queue_engine_mode=rule_based -> zero API calls
- exactly one API call per tick
- pending count exceeding cap -> fallback
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from domains.warehouse.queue_engine import llm_reranker

def _patch_settings(**overrides):
    defaults = {
        "queue_engine_mode": "llm_batch",
        "llm_provider": "gemini",
        "gemini_api_key": "test_key",
        "llm_model": "gemini-2.5-flash-lite",
        "llm_rerank_timeout_seconds": 1.0,
        "llm_rerank_max_orders": 50,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock

def _make_orders(count=3):
    now = datetime.now(timezone.utc)
    return [
        {
            "external_id": f"ORD-{i}",
            "sla_deadline": now + timedelta(minutes=60),
            "created_at": now - timedelta(minutes=10),
            "inventory_readiness": 1.0,
            "item_count": 1,
        }
        for i in range(count)
    ]

@pytest.fixture
def mock_genai_client():
    mock_instance = MagicMock()
    mock_instance.aio.models.generate_content = AsyncMock()
    return mock_instance

@pytest.mark.asyncio
async def test_successful_rerank(mock_genai_client):
    orders = _make_orders(3)
    mock_settings = _patch_settings()
    
    # Simulate LLM returning reversed order
    llm_response = [
        {"order_id": "ORD-2", "reason": "Highest risk"},
        {"order_id": "ORD-1", "reason": "Medium risk"},
        {"order_id": "ORD-0", "reason": "Lowest risk"}
    ]
    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_response)
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        
        result = await llm_reranker.rerank(orders)
        
    assert result is not None
    assert len(result) == 3
    assert result[0]["order_id"] == "ORD-2"
    mock_genai_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_timeout_fallback(mock_genai_client):
    orders = _make_orders(2)
    mock_settings = _patch_settings(llm_rerank_timeout_seconds=0.001)
    
    async def _slow_create(**kwargs):
        await asyncio.sleep(10)
        
    mock_genai_client.aio.models.generate_content.side_effect = _slow_create

    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        
        result = await llm_reranker.rerank(orders)
        
    assert result is None  # Should fallback


@pytest.mark.asyncio
async def test_malformed_partial_response(mock_genai_client):
    orders = _make_orders(3)
    mock_settings = _patch_settings()
    
    # Missing ORD-0
    llm_response = [
        {"order_id": "ORD-2", "reason": "Highest risk"},
        {"order_id": "ORD-1", "reason": "Medium risk"}
    ]
    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_response)
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        result = await llm_reranker.rerank(orders)
        
    assert result is None


@pytest.mark.asyncio
async def test_empty_pending_list_no_api_call(mock_genai_client):
    mock_settings = _patch_settings()
    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        result = await llm_reranker.rerank([])
        
    assert result == []
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_queue_engine_mode_rule_based_no_api_call(mock_genai_client):
    orders = _make_orders(5)
    mock_settings = _patch_settings(queue_engine_mode="rule_based")
    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        result = await llm_reranker.rerank(orders)
        
    assert result is None
    mock_genai_client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_exactly_one_api_call_per_tick(mock_genai_client):
    orders = _make_orders(10)
    mock_settings = _patch_settings()
    
    # Must contain all 10
    llm_response = [{"order_id": f"ORD-{i}", "reason": "reason"} for i in range(10)]
    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_response)
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        result = await llm_reranker.rerank(orders)
        
    assert result is not None
    # Regardless of 10 orders, exactly one call
    mock_genai_client.aio.models.generate_content.assert_called_once()
    
    
@pytest.mark.asyncio
async def test_pending_count_exceeding_cap_fallback(mock_genai_client, caplog):
    orders = _make_orders(51)
    mock_settings = _patch_settings(llm_rerank_max_orders=50)
    
    with patch("domains.warehouse.queue_engine.llm_reranker.settings", mock_settings), \
         patch("google.genai.Client", return_value=mock_genai_client):
        with caplog.at_level(logging.INFO):
            result = await llm_reranker.rerank(orders)
        
    assert result is None
    mock_genai_client.aio.models.generate_content.assert_not_called()
    assert "Pending orders (51) exceed LLM_RERANK_MAX_ORDERS (50)" in caplog.text
