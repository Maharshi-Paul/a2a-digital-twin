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

    # ── Redis ──────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── API ────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ── Queue Engine ───────────────────────────────────────────────────
    queue_tick_seconds: float = 2.0

    # ── Priority Weights ───────────────────────────────────────────────
    w_sla_risk: float = 0.35
    w_wait_time: float = 0.15
    w_inventory_readiness: float = 0.25
    w_aisle_congestion: float = 0.10
    w_packing_capacity: float = 0.15

    # ── Simulation ─────────────────────────────────────────────────────
    simulation_lambda: float = 3.0  # orders per minute (Poisson λ)
    simulation_seed: int = 42

    # ── LLM ────────────────────────────────────────────────────────────
    llm_provider: str = "none"


settings = Settings()
