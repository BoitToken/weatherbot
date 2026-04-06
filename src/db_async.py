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


class AsyncCursor:
    """Wraps psycopg2 cursor for async context manager."""
    
    def __init__(self, conn):
        self._conn = conn
        self._cursor = None
    
    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        self._cursor = await loop.run_in_executor(None, self._conn.cursor)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._cursor.close)
    
    async def execute(self, query, params=None):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._cursor.execute, query, params)
    
    async def fetchone(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._cursor.fetchone)
    
    async def fetchall(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._cursor.fetchall)
    
    @property
    def description(self):
        return self._cursor.description


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
    
    def cursor(self):
        """Return async cursor context manager."""
        return AsyncCursor(self._conn)
    
    async def commit(self):
        """Commit transaction."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._conn.commit)


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
    
    @asynccontextmanager
    async def connection(self):
        """Alias for acquire() — psycopg v3 style."""
        async with self.acquire() as conn:
            yield conn


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
