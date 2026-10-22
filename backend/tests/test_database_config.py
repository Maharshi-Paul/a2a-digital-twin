"""Tests for database URL normalization and asyncpg SSL configuration."""

import ssl
from core.database import _prepare_db_url_and_args
from core.config import settings


def test_postgres_protocol_normalization():
    # Test standard postgres://
    url, args = _prepare_db_url_and_args("postgres://user:pass@localhost:5432/db")
    assert url.startswith("postgresql+asyncpg://")

    # Test postgresql://
    url2, args2 = _prepare_db_url_and_args("postgresql://user:pass@localhost:5432/db")
    assert url2.startswith("postgresql+asyncpg://")


def test_asyncpg_sslmode_stripped():
    # Neon or Supabase connection string with sslmode=require
    raw = "postgresql://user:pass@ep-cool-1234.us-east-2.aws.neon.tech/neondb?sslmode=require"
    url, args = _prepare_db_url_and_args(raw)

    assert "sslmode" not in url
    assert "statement_cache_size" in args
    assert args["statement_cache_size"] == 0
    assert "ssl" in args
    assert isinstance(args["ssl"], ssl.SSLContext)


def test_statement_cache_size_configured():
    url, args = _prepare_db_url_and_args("postgresql+asyncpg://user:pass@localhost:5432/db")
    assert args.get("statement_cache_size") == settings.db_statement_cache_size
