"""LLM-powered decision commentary — read-only narration layer.

Generates short, human-readable explanations of decisions the rule-based
queue engine already made.  Never influences scoring, priority, or
negotiation outcomes.

Set ``LLM_PROVIDER=gemini`` and ``GEMINI_API_KEY`` to enable.
When ``LLM_PROVIDER=none`` (default), every call is a no-op.
"""

from __future__ import annotations

import asyncio
import logging

from core.config import settings
from domains.warehouse.queue_engine.scorer import ScoredOrder

logger = logging.getLogger(__name__)

# Semaphore is created lazily on first use so the event-loop is guaranteed
# to exist.  Module-level creation would bind to the wrong loop.
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.llm_commentary_max_concurrency)
    return _semaphore


_SYSTEM_PROMPT = (
    "You are explaining a warehouse scheduling decision that has already "
    "been made by a rule-based system. Describe the reasoning in 1–3 plain "
    "sentences for a dashboard viewer. Do not suggest alternative decisions "
    "or second-guess the outcome."
)


async def explain_decision(scored: ScoredOrder) -> str | None:
    """Generate a short explanation for a completed scoring decision.

    Returns ``None`` immediately when:
    - ``LLM_PROVIDER`` is not ``"gemini"``
    - ``GEMINI_API_KEY`` is not set
    - The Gemini API call fails or times out

    This function is designed to be called as a fire-and-forget background
    task and must never raise.
    """
    # ── Guard: disabled or un-configured ──────────────────────────────
    if settings.llm_provider != "gemini":
        return None

    if not settings.gemini_api_key:
        logger.warning(
            "LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set — "
            "skipping commentary"
        )
        return None

    # ── Build a compact prompt from the scored order ──────────────────
    prompt = (
        f"Order {scored.external_id} (ID {scored.order_id}) was scored "
        f"{scored.total_score:.4f} and ranked in the priority queue.\n\n"
        f"Factor breakdown:\n"
        f"  SLA risk:             {scored.sla_risk:.2f} "
        f"(weighted {scored.breakdown.get('sla_risk_weighted', 0):.4f})\n"
        f"  Wait time:            {scored.wait_time_norm:.2f} "
        f"(weighted {scored.breakdown.get('wait_weighted', 0):.4f})\n"
        f"  Inventory readiness:  {scored.inventory_readiness:.2f} "
        f"(weighted {scored.breakdown.get('inventory_weighted', 0):.4f})\n"
        f"  Congestion (inverse): {scored.congestion_factor:.2f} "
        f"(weighted {scored.breakdown.get('congestion_weighted', 0):.4f})\n"
        f"  Packing capacity:     {scored.packing_factor:.2f} "
        f"(weighted {scored.breakdown.get('packing_weighted', 0):.4f})\n\n"
        f"Explain why this order received this priority."
    )

    # ── Call Gemini with concurrency + timeout guards ─────────────────
    sem = _get_semaphore()
    try:
        async with sem:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.llm_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        max_output_tokens=150,
                    )
                ),
                timeout=settings.llm_commentary_timeout_seconds,
            )
            text = response.text.strip() if response.text else None
            return text if text else None

    except asyncio.TimeoutError:
        logger.warning("LLM commentary timed out for order %s", scored.external_id)
        return None
    except Exception:
        logger.warning(
            "LLM commentary failed for order %s", scored.external_id, exc_info=True
        )
        return None
