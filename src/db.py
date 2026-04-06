"""
Database module for WeatherBot.
Provides async PostgreSQL connection pool and helper functions.
"""
import asyncio
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from src import config

# Global connection pool
_pool: Optional[SimpleConnectionPool] = None
_pool_lock = asyncio.Lock()


def get_pool() -> SimpleConnectionPool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=config.DB_URL
        )
    return _pool


@contextmanager
def get_connection():
    """Context manager for database connections."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


async def execute(query: str, params: tuple = None) -> None:
    """
    Execute a query without returning results (INSERT, UPDATE, DELETE).
    
    Args:
        query: SQL query string
        params: Query parameters tuple
    """
    def _execute():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _execute)


async def fetch_one(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """
    Fetch a single row from the database.
    
    Args:
        query: SQL query string
        params: Query parameters tuple
        
    Returns:
        Dictionary with column names as keys, or None if no results
    """
    def _fetch():
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return dict(result) if result else None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def fetch_all(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """
    Fetch all rows from the database.
    
    Args:
        query: SQL query string
        params: Query parameters tuple
        
    Returns:
        List of dictionaries with column names as keys
    """
    def _fetch():
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(row) for row in results]
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def close_pool():
    """Close all connections in the pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


# Initialize database tables if they don't exist
async def init_tables():
    """Create required database tables if they don't exist."""
    
    tables_sql = """
    -- METAR readings table
    CREATE TABLE IF NOT EXISTS metar_readings (
        id SERIAL PRIMARY KEY,
        station_icao VARCHAR(4) NOT NULL,
        observation_time TIMESTAMP NOT NULL,
        raw_metar TEXT NOT NULL,
        temperature_c FLOAT,
        dewpoint_c FLOAT,
        wind_speed_kt FLOAT,
        wind_dir INTEGER,
        visibility_m FLOAT,
        pressure_hpa FLOAT,
        cloud_cover VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(station_icao, observation_time)
    );
    
    CREATE INDEX IF NOT EXISTS idx_metar_station_time 
    ON metar_readings(station_icao, observation_time DESC);
    
    -- Temperature trends table
    CREATE TABLE IF NOT EXISTS temperature_trends (
        id SERIAL PRIMARY KEY,
        station_icao VARCHAR(4) NOT NULL,
        calculated_at TIMESTAMP DEFAULT NOW(),
        trend_per_hour FLOAT,
        projected_high FLOAT,
        projected_low FLOAT,
        confidence FLOAT,
        num_readings INTEGER,
        UNIQUE(station_icao, calculated_at)
    );
    
    CREATE INDEX IF NOT EXISTS idx_trends_station_time 
    ON temperature_trends(station_icao, calculated_at DESC);
    
    -- TAF forecasts table
    CREATE TABLE IF NOT EXISTS taf_forecasts (
        id SERIAL PRIMARY KEY,
        station_icao VARCHAR(4) NOT NULL,
        issue_time TIMESTAMP NOT NULL,
        valid_from TIMESTAMP NOT NULL,
        valid_to TIMESTAMP NOT NULL,
        raw_taf TEXT NOT NULL,
        forecast_high FLOAT,
        forecast_low FLOAT,
        significant_weather TEXT,
        wind_changes TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(station_icao, issue_time)
    );
    
    CREATE INDEX IF NOT EXISTS idx_taf_station_time 
    ON taf_forecasts(station_icao, issue_time DESC);
    """
    
    for statement in tables_sql.split(';'):
        statement = statement.strip()
        if statement:
            await execute(statement)
