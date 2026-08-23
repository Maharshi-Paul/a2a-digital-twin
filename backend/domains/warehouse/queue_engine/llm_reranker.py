"""LLM-assisted batch re-ranking service.

Sends all pending orders to Gemini in a single API call per tick and receives
a ranked ordering with optional per-order reasoning.

Returns ``None`` on any failure — the caller should fall back to the
rule-based scorer.  Never retries within a tick.

Set ``QUEUE_ENGINE_MODE=llm_batch`` and ``LLM_PROVIDER=gemini``
plus ``GEMINI_API_KEY`` to enable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from google import genai
from google.genai import types

from core.config import settings

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a warehouse order scheduling engine. Given a set of pending orders "
    "with their SLA deadlines, wait times, inventory readiness, and current "
    "warehouse load context, rank them from highest to lowest priority.\n\n"
    "Return ONLY a JSON array of objects in rank order (highest priority first). "
    "Each object must have exactly two keys:\n"
    '  - "order_id": the external_id string of the order\n'
    '  - "reason": a concise explanation (15 words max)\n\n'
    "Return nothing else — no prose, no markdown, no code fences. "
    "The JSON array must contain every order_id submitted, with no duplicates "
    "and no extra entries."
)


@dataclass(frozen=True, slots=True)
class _OrderSummary:
    """Minimal order data sent to LLM for ranking."""
    external_id: str
    sla_deadline_iso: str
    created_at_iso: str
    age_minutes: float
    minutes_until_sla: float
    inventory_readiness: float
    item_count: int


def _build_prompt(
    orders: list[_OrderSummary],
    avg_congestion: float,
    packing_util: float,
) -> str:
    """Build a compact JSON prompt with all orders' ranking-relevant data."""
    order_data = [
        {
            "order_id": o.external_id,
            "age_minutes": round(o.age_minutes, 1),
            "minutes_until_sla": round(o.minutes_until_sla, 1),
            "inventory_readiness": round(o.inventory_readiness, 2),
            "item_count": o.item_count,
        }
        for o in orders
    ]
    context = {
        "orders": order_data,
        "warehouse_context": {
            "avg_zone_congestion": round(avg_congestion, 2),
            "packing_utilization": round(packing_util, 2),
        },
    }
    return json.dumps(context, separators=(",", ":"))


def _validate_response(
    raw: str,
    submitted_ids: set[str],
) -> list[dict[str, str]] | None:
    """Parse and validate LLM's response.

    Returns a list of ``{"order_id": ..., "reason": ...}`` dicts in rank order,
    or ``None`` if the response is invalid.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("LLM rerank response is not valid JSON")
        return None

    if not isinstance(parsed, list):
        logger.warning("LLM rerank response is not a JSON array")
        return None

    returned_ids: list[str] = []
    result: list[dict[str, str]] = []

    for item in parsed:
        if not isinstance(item, dict):
            logger.warning("LLM rerank item is not a dict: %s", item)
            return None
        oid = item.get("order_id")
        if oid is None:
            logger.warning("LLM rerank item missing order_id")
            return None
        oid = str(oid)
        returned_ids.append(oid)
        reason = str(item.get("reason", ""))[:100]  # cap reason length
        result.append({"order_id": oid, "reason": reason})

    returned_set = set(returned_ids)

    # Check for duplicates
    if len(returned_set) != len(returned_ids):
        logger.warning("LLM rerank response contains duplicate order IDs")
        return None

    # Check exact match with submitted IDs
    if returned_set != submitted_ids:
        missing = submitted_ids - returned_set
        extra = returned_set - submitted_ids
        logger.warning(
            "LLM rerank ID mismatch — missing: %s, extra: %s", missing, extra
        )
        return None

    return result


async def rerank(
    pending_orders: list[dict],
    avg_congestion: float = 0.0,
    packing_util: float = 0.0,
) -> list[dict[str, str]] | None:
    """Batch-rerank pending orders via a single LLM API call.

    Parameters
    ----------
    pending_orders
        List of dicts with keys: ``external_id``, ``sla_deadline``,
        ``created_at``, ``inventory_readiness``, ``item_count``.
    avg_congestion
        Average zone congestion (0-1).
    packing_util
        Overall packing station utilization (0-1).

    Returns
    -------
    list[dict] | None
        Ordered list of ``{"order_id": str, "reason": str}`` dicts
        (highest priority first), or ``None`` on any failure.
    """
    # ── Guard: disabled or un-configured ──────────────────────────────
    if settings.queue_engine_mode != "llm_batch":
        return None

    if settings.llm_provider != "gemini":
        return None

    if not settings.gemini_api_key:
        logger.warning(
            "QUEUE_ENGINE_MODE=llm_batch but GEMINI_API_KEY is not set — "
            "falling back to rule-based"
        )
        return None

    # ── Guard: empty order list ───────────────────────────────────────
    if not pending_orders:
        return []

    # ── Guard: exceeds max orders cap ─────────────────────────────────
    if len(pending_orders) > settings.llm_rerank_max_orders:
        logger.info(
            "Pending orders (%d) exceed LLM_RERANK_MAX_ORDERS (%d) — "
            "falling back to rule-based for this tick",
            len(pending_orders),
            settings.llm_rerank_max_orders,
        )
        return None

    # ── Try building prompt and calling API ───────────────────────────
    try:
        now = datetime.now(timezone.utc)
        summaries: list[_OrderSummary] = []

        for o in pending_orders:
            sla = o["sla_deadline"]
            created = o["created_at"]
            age_minutes = (now - created).total_seconds() / 60.0
            minutes_until_sla = (sla - now).total_seconds() / 60.0
            summaries.append(
                _OrderSummary(
                    external_id=o["external_id"],
                    sla_deadline_iso=sla.isoformat(),
                    created_at_iso=created.isoformat(),
                    age_minutes=max(age_minutes, 0.0),
                    minutes_until_sla=max(minutes_until_sla, 0.0),
                    inventory_readiness=o.get("inventory_readiness", 1.0),
                    item_count=o.get("item_count", 1),
                )
            )

        submitted_ids = {s.external_id for s in summaries}
        prompt = _build_prompt(summaries, avg_congestion, packing_util)

        # Estimate max_tokens: ~60 tokens per order for overhead + reason
        max_tokens = max(500, len(summaries) * 60)

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    max_output_tokens=max_tokens,
                )
            ),
            timeout=settings.llm_rerank_timeout_seconds,
        )
        raw_text = response.text.strip() if response.text else ""

    except asyncio.TimeoutError:
        logger.warning(
            "LLM rerank timed out after %.1fs",
            settings.llm_rerank_timeout_seconds,
        )
        return None
    except Exception:
        logger.warning("LLM rerank API call failed", exc_info=True)
        return None

    # ── Validate and return ───────────────────────────────────────────
    result = _validate_response(raw_text, submitted_ids)
    if result is None:
        logger.warning("LLM rerank response failed validation")
        logger.debug("Raw failed response (len=%d): %r", len(raw_text), raw_text)
        return None

    logger.debug("LLM rerank succeeded for %d orders", len(result))
    return result
