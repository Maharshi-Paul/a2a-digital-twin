"""Async SQLAlchemy engine, session factory, and dependency helper."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.config import settings


def _prepare_db_url_and_args(raw_url: str) -> tuple[str, dict]:
    """Normalize database URL for SQLAlchemy+asyncpg and configure connect_args.

    1. Ensures the dialect is postgresql+asyncpg://.
    2. Strips 'sslmode' query params (which asyncpg rejects with TypeError).
    3. Configures SSL ('require' or SSLContext) for managed providers (Neon, Render, etc.).
    4. Sets statement_cache_size=0 to support transaction poolers (PgBouncer/Neon).
    """
    # 1. Ensure asyncpg driver prefix
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+asyncpg://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]

    parts = urlsplit(raw_url)
    query_params = dict(parse_qsl(parts.query))

    # 2. Extract and remove sslmode and channel_binding if present
    sslmode = query_params.pop("sslmode", None)
    ssl_param = query_params.pop("ssl", None)
    query_params.pop("channel_binding", None)

    # Reconstruct URL without unsupported asyncpg query params
    clean_query = urlencode(query_params)
    clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, clean_query, parts.fragment))

    connect_args: dict = {
        "statement_cache_size": settings.db_statement_cache_size,
    }

    # 3. Determine if SSL is needed
    needs_ssl = (
        settings.db_ssl is True
        or (sslmode in ("require", "verify-ca", "verify-full"))
        or (ssl_param in ("require", "true", "1"))
        or (parts.hostname and parts.hostname not in ("localhost", "127.0.0.1", "db", "postgres"))
    )

    if settings.db_ssl is False:
        needs_ssl = False

    if needs_ssl:
        # asyncpg accepts ssl="require" or an SSLContext
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    return clean_url, connect_args


_clean_url, _connect_args = _prepare_db_url_and_args(settings.database_url)

engine = create_async_engine(
    _clean_url,
    echo=False,
    connect_args=_connect_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle,
)

# Unpooled engine specifically for DDL operations / schema creation as recommended by Neon
_unpooled_source = settings.database_url_unpooled or settings.database_url
_unpooled_url, _unpooled_args = _prepare_db_url_and_args(_unpooled_source)

unpooled_engine = create_async_engine(
    _unpooled_url,
    echo=False,
    connect_args=_unpooled_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
