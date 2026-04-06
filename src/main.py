"""
WeatherBot FastAPI Server
Provides API endpoints for dashboard + scheduler for data/signal loops.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from src import config
from src.db import fetch_all, fetch_one, init_tables, close_pool

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown."""
    # Startup
    logger.info("🚀 WeatherBot starting...")
    await init_tables()
    
    # Start scheduler (commented out until data/signal modules are ready)
    # scheduler.add_job(data_loop, 'interval', minutes=30, id='data_loop')
    # scheduler.add_job(signal_loop, 'interval', minutes=5, id='signal_loop')
    # scheduler.start()
    logger.info("✅ WeatherBot ready")
    
    yield
    
    # Shutdown
    logger.info("🛑 WeatherBot shutting down...")
    # scheduler.shutdown()
    await close_pool()


app = FastAPI(
    title="WeatherBot — PolyEdge",
    version="0.1.0",
    lifespan=lifespan
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# =============================================================================
# Health & Status
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0"
    }


@app.get("/api/bot/status")
async def bot_status():
    """Bot running status."""
    return {
        "running": True,  # scheduler.running if scheduler else False
        "mode": config.MODE,
        "last_data_scan": None,  # TODO: Track in DB
        "last_signal_scan": None,  # TODO: Track in DB
        "uptime_seconds": 0,  # TODO: Calculate
    }


# =============================================================================
# METAR Data
# =============================================================================

@app.get("/api/metar/latest")
async def get_latest_metar():
    """Get latest METAR reading for each station."""
    query = """
        SELECT DISTINCT ON (station_icao)
            station_icao,
            observation_time,
            temperature_c,
            dewpoint_c,
            wind_speed_kt,
            wind_dir,
            raw_metar,
            created_at
        FROM metar_readings
        ORDER BY station_icao, observation_time DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


@app.get("/api/metar/{icao}")
async def get_metar_history(icao: str, hours: int = 24):
    """Get METAR history for a specific station."""
    icao = icao.upper()
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = """
        SELECT 
            station_icao,
            observation_time,
            temperature_c,
            dewpoint_c,
            wind_speed_kt,
            raw_metar
        FROM metar_readings
        WHERE station_icao = %s
        AND observation_time >= %s
        ORDER BY observation_time DESC
    """
    results = await fetch_all(query, (icao, since))
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No data found for {icao}")
    
    return {"station": icao, "data": results, "count": len(results)}


# =============================================================================
# Markets
# =============================================================================

@app.get("/api/markets")
async def get_active_markets():
    """Get active weather markets from Polymarket."""
    # TODO: Query markets table when markets module is ready
    # For now, return empty list
    return {"data": [], "count": 0}


# =============================================================================
# Signals
# =============================================================================

@app.get("/api/signals")
async def get_signals(limit: int = 50):
    """Get recent signals."""
    # TODO: Query signals table when signals module is ready
    return {"data": [], "count": 0}


@app.get("/api/signals/pending")
async def get_pending_signals():
    """Get high-confidence untrades (pending manual approval)."""
    # TODO: Query signals where status='pending' and confidence='HIGH'
    return {"data": [], "count": 0}


# =============================================================================
# Trades
# =============================================================================

@app.get("/api/trades")
async def get_trades(limit: int = 100):
    """Get trade history."""
    query = """
        SELECT 
            id,
            signal_id,
            city,
            side,
            entry_price,
            size_usd,
            edge_pct,
            status,
            pnl,
            created_at,
            closed_at
        FROM trades
        ORDER BY created_at DESC
        LIMIT %s
    """
    try:
        results = await fetch_all(query, (limit,))
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch trades: {e}")
        # Return empty if table doesn't exist yet
        return {"data": [], "count": 0}


@app.get("/api/trades/active")
async def get_active_trades():
    """Get open positions."""
    query = """
        SELECT 
            id,
            signal_id,
            city,
            side,
            entry_price,
            size_usd,
            edge_pct,
            status,
            created_at
        FROM trades
        WHERE status IN ('paper_open', 'live_open')
        ORDER BY created_at DESC
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch active trades: {e}")
        return {"data": [], "count": 0}


# =============================================================================
# P&L & Analytics
# =============================================================================

@app.get("/api/pnl/daily")
async def get_daily_pnl(days: int = 30):
    """Get daily P&L data."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = """
        SELECT 
            DATE(closed_at) as date,
            COUNT(*) as trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl) as total_pnl,
            AVG(pnl) as avg_pnl
        FROM trades
        WHERE closed_at IS NOT NULL
        AND closed_at >= %s
        GROUP BY DATE(closed_at)
        ORDER BY date DESC
    """
    try:
        results = await fetch_all(query, (since,))
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch daily P&L: {e}")
        return {"data": [], "count": 0}


@app.get("/api/bankroll")
async def get_bankroll():
    """Get current bankroll status."""
    # TODO: Track bankroll in settings/config table
    # For now return mock data
    return {
        "total": 1000.0,
        "available": 950.0,
        "in_positions": 50.0,
        "last_updated": datetime.utcnow().isoformat()
    }


@app.get("/api/analytics/win-rate")
async def get_win_rate(days: int = 30):
    """Get win rate over time."""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = """
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate_pct,
            SUM(pnl) as total_pnl,
            AVG(edge_pct) as avg_edge
        FROM trades
        WHERE closed_at IS NOT NULL
        AND closed_at >= %s
    """
    try:
        result = await fetch_one(query, (since,))
        return result or {
            "total_trades": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "avg_edge": 0.0
        }
    except Exception as e:
        logger.error(f"Failed to fetch win rate: {e}")
        return {
            "total_trades": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "avg_edge": 0.0
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6010)
