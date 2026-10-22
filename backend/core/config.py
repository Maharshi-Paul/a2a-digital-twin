"""Pydantic-based application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://wdt_user:wdt_pass@localhost:5432/warehouse_twin"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle: int = 300
    db_pool_pre_ping: bool = True
    db_ssl: bool | None = None
    db_statement_cache_size: int = 0

    # ── Redis ──────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10
    redis_ssl_cert_reqs: str = "none"

    # ── API ────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    frontend_url: str | None = None
    cors_origin_regex: str | None = r"^https:\/\/.*\.vercel\.app$"
    admin_token: str | None = None

    # ── Queue Engine ───────────────────────────────────────────────────
    queue_tick_seconds: float = 10.0
    queue_engine_idle_when_empty: bool = True
    queue_engine_mode: str = "rule_based"  # "rule_based" | "llm_batch"
    llm_rerank_timeout_seconds: float = 1.0  # ~50% of queue_tick_seconds
    llm_rerank_max_orders: int = 50  # safety cap; fallback if exceeded

    # ── Priority Weights ───────────────────────────────────────────────
    w_sla_risk: float = 0.35
    w_wait_time: float = 0.15
    w_inventory_readiness: float = 0.25
    w_aisle_congestion: float = 0.10
    w_packing_capacity: float = 0.15

    # ── Simulation ─────────────────────────────────────────────────────
    simulation_lambda: float = 3.0  # orders per minute (Poisson λ)
    simulation_min_lambda: float = 0.5
    simulation_max_lambda: float = 10.0
    simulation_sla_min: int = 15  # minutes
    simulation_sla_max: int = 60  # minutes
    simulation_max_items_per_order: int = 5
    simulation_seed: int = 42
    simulation_config_path: str | None = None  # optional YAML/JSON override

    # ── LLM ────────────────────────────────────────────────────────────
    llm_provider: str = "none"
    gemini_api_key: str | None = None
    llm_model: str = "gemini-2.5-flash-lite"
    llm_commentary_timeout_seconds: float = 5.0
    llm_commentary_max_concurrency: int = 3


settings = Settings()
