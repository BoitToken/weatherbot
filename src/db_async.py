"""
Async database wrapper that provides asyncpg-like interface over psycopg2.
Used by signal_loop, polymarket_scanner, mismatch_detector which expect pool.acquire() pattern.
Converts $1,$2 asyncpg params to %s psycopg2 params automatically.
"""
import asyncio
import re
from contextlib import asynccontextmanager
from psycopg2.extras import RealDictCursor
from src.db import get_pool
import logging

logger = logging.getLogger(__name__)


def _convert_params(query, args):
    """Convert asyncpg $1,$2 style to psycopg2 %s style."""
    if not args:
        return query, None
    # Replace $1, $2, ... $N with %s
    converted = re.sub(r'\$\d+', '%s', query)
    return converted, args


class AsyncConnection:
    """Wraps a psycopg2 connection to look like asyncpg."""

    def __init__(self, conn):
        self._conn = conn

    async def fetchrow(self, query, *args):
        """Fetch single row (asyncpg-style)."""
        q, p = _convert_params(query, args)
        loop = asyncio.get_event_loop()
        def _exec():
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(q, p)
                return cur.fetchone()
        return await loop.run_in_executor(None, _exec)

    async def fetch(self, query, *args):
        """Fetch multiple rows (asyncpg-style)."""
        q, p = _convert_params(query, args)
        loop = asyncio.get_event_loop()
        def _exec():
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(q, p)
                return cur.fetchall()
        return await loop.run_in_executor(None, _exec)

    async def execute(self, query, *args):
        """Execute query (asyncpg-style)."""
        q, p = _convert_params(query, args)
        loop = asyncio.get_event_loop()
        def _exec():
            with self._conn.cursor() as cur:
                cur.execute(q, p)
            self._conn.commit()
        return await loop.run_in_executor(None, _exec)


class AsyncPoolWrapper:
    """Wraps psycopg2 SimpleConnectionPool to look like asyncpg pool."""

    @asynccontextmanager
    async def acquire(self):
        pool = get_pool()
        conn = pool.getconn()
        try:
            yield AsyncConnection(conn)
        finally:
            pool.putconn(conn)


def get_async_pool():
    """Get the async pool wrapper."""
    return AsyncPoolWrapper()


# Register JSON adapter for psycopg2
import psycopg2.extras
import json

class JsonAdapter:
    def __init__(self, obj):
        self.obj = obj
    def getquoted(self):
        return psycopg2.extensions.QuotedString(json.dumps(self.obj)).getquoted()

psycopg2.extensions.register_adapter(dict, lambda d: psycopg2.extras.Json(d))
