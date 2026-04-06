"""
WeatherBot FastAPI Server
API endpoints for dashboard + scheduler for data/signal loops.
All endpoints query REAL database — no stubs, no mocks.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
import logging
import traceback

from src import config
from src.db import fetch_all, fetch_one, execute, init_tables, close_pool, get_pool
from src.db_async import get_async_pool

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler
scheduler = AsyncIOScheduler()

# Track scan times
_last_data_scan: Optional[datetime] = None
_last_signal_scan: Optional[datetime] = None
_startup_time: Optional[datetime] = None

# Signal loop instance (initialized on startup)
_signal_loop = None
_improvement_engine = None


async def scheduled_data_scan():
    """Run data collection cycle on schedule."""
    global _last_data_scan
    try:
        from src.data.data_loop import run_single_cycle
        logger.info("⏰ Scheduled data scan starting...")
        await run_single_cycle()
        _last_data_scan = datetime.utcnow()
        logger.info(f"✅ Data scan complete at {_last_data_scan.isoformat()}")
    except Exception as e:
        logger.error(f"❌ Data scan failed: {e}\n{traceback.format_exc()}")


async def scheduled_signal_scan():
    """Run signal detection on schedule."""
    global _last_signal_scan, _signal_loop
    try:
        if _signal_loop is None:
            logger.warning("Signal loop not initialized, skipping")
            return
        logger.info("⏰ Scheduled signal scan starting...")
        await _signal_loop.run_once()
        _last_signal_scan = datetime.utcnow()
        logger.info(f"✅ Signal scan complete at {_last_signal_scan.isoformat()}")
    except Exception as e:
        logger.error(f"❌ Signal scan failed: {e}\n{traceback.format_exc()}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown."""
    global _last_data_scan, _startup_time, _signal_loop

    logger.info("🚀 WeatherBot starting...")
    _startup_time = datetime.utcnow()
    await init_tables()

    # Initialize signal loop
    try:
        from src.signals.signal_loop import SignalLoop
        from src.data.city_map import CITY_TO_ICAO
        async_pool = get_async_pool()
        _signal_loop = SignalLoop(
            db_pool=async_pool,
            city_map=CITY_TO_ICAO,
            anthropic_api_key=config.ANTHROPIC_API_KEY,
            min_edge_for_claude=float(getattr(config, 'MIN_EDGE_ALERT', 0.15)),
            min_edge_for_trade=float(getattr(config, 'MIN_EDGE_AUTO_TRADE', 0.25)),
        )
        logger.info("✅ Signal loop initialized")
    except Exception as e:
        logger.error(f"⚠️ Signal loop init failed (will retry): {e}")
    
    # Initialize improvement engine
    try:
        from src.learning.improvement import ImprovementEngine
        async_pool = get_async_pool()
        _improvement_engine = ImprovementEngine(async_pool, config)
        logger.info("✅ Improvement engine initialized")
    except Exception as e:
        logger.error(f"⚠️ Improvement engine init failed: {e}")

    # Run initial data fetch
    try:
        from src.data.data_loop import run_single_cycle
        await run_single_cycle()
        _last_data_scan = datetime.utcnow()
        logger.info(f"✅ Initial data fetch complete: {_last_data_scan.isoformat()}")
    except Exception as e:
        logger.error(f"⚠️ Initial data fetch failed: {e}")

    # Initialize bankroll if empty
    try:
        existing = await fetch_one("SELECT id FROM bankroll LIMIT 1")
        if not existing:
            await execute(
                "INSERT INTO bankroll (total_usd, available_usd, in_positions_usd, daily_pnl) VALUES (0, 0, 0, 0)"
            )
            logger.info("✅ Initial bankroll record created")
    except Exception as e:
        logger.error(f"⚠️ Bankroll init failed: {e}")

    # Start scheduler
    scheduler.add_job(scheduled_data_scan, 'interval', minutes=30, id='data_loop', replace_existing=True)
    scheduler.add_job(scheduled_signal_scan, 'interval', minutes=5, id='signal_loop', replace_existing=True)
    scheduler.start()
    logger.info("✅ Scheduler started (data: 30min, signals: 5min)")
    logger.info("✅ WeatherBot ready")

    yield

    # Shutdown
    logger.info("🛑 WeatherBot shutting down...")
    scheduler.shutdown(wait=False)
    await close_pool()


app = FastAPI(
    title="WeatherBot — PolyEdge",
    version="0.2.0",
    lifespan=lifespan
)

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
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.2.0",
        "scheduler": scheduler.running,
        "last_data_scan": _last_data_scan.isoformat() if _last_data_scan else None,
        "last_signal_scan": _last_signal_scan.isoformat() if _last_signal_scan else None,
    }


@app.get("/api/bot/status")
async def bot_status():
    uptime = (datetime.utcnow() - _startup_time).total_seconds() if _startup_time else 0
    return {
        "running": scheduler.running,
        "mode": getattr(config, 'MODE', 'paper'),
        "last_data_scan": _last_data_scan.isoformat() if _last_data_scan else None,
        "last_signal_scan": _last_signal_scan.isoformat() if _last_signal_scan else None,
        "uptime_seconds": int(uptime),
        "signal_loop_ready": _signal_loop is not None,
    }


# =============================================================================
# Manual Triggers
# =============================================================================

@app.post("/api/bot/scan-now")
async def trigger_scan():
    """Manually trigger a full data + signal scan."""
    results = {}
    try:
        await scheduled_data_scan()
        results["data_scan"] = "completed"
    except Exception as e:
        results["data_scan"] = f"failed: {str(e)}"

    try:
        await scheduled_signal_scan()
        results["signal_scan"] = "completed"
    except Exception as e:
        results["signal_scan"] = f"failed: {str(e)}"

    return {"status": "scan_triggered", "results": results, "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# METAR Data
# =============================================================================

@app.get("/api/metar/latest")
async def get_latest_metar():
    query = """
        SELECT DISTINCT ON (station_icao)
            station_icao, temperature_c, dewpoint_c,
            wind_speed_kt, wind_dir, raw_metar,
            observed_at as observation_time, fetched_at as created_at
        FROM metar_readings
        ORDER BY station_icao, observed_at DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


@app.get("/api/metar/{icao}")
async def get_metar_history(icao: str, hours: int = 24):
    icao = icao.upper()
    since = datetime.utcnow() - timedelta(hours=hours)
    query = """
        SELECT station_icao, temperature_c, dewpoint_c,
               wind_speed_kt, raw_metar,
               observed_at as observation_time
        FROM metar_readings
        WHERE station_icao = %s AND observed_at >= %s
        ORDER BY observed_at DESC
    """
    results = await fetch_all(query, (icao, since))
    if not results:
        raise HTTPException(status_code=404, detail=f"No data for {icao}")
    return {"station": icao, "data": results, "count": len(results)}


# =============================================================================
# Markets — queries REAL weather_markets table
# =============================================================================

@app.get("/api/markets")
async def get_active_markets():
    query = """
        SELECT market_id, title, city, station_icao, threshold_type,
               threshold_value, threshold_unit, resolution_date,
               yes_price, no_price, volume_usd, liquidity_usd,
               last_updated, active
        FROM weather_markets
        WHERE active = true
        ORDER BY last_updated DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


# =============================================================================
# Signals — queries REAL signals table
# =============================================================================

@app.get("/api/signals")
async def get_signals(limit: int = 50):
    query = """
        SELECT id, market_id, station_icao, city, side,
               our_probability, market_price, edge, confidence,
               claude_reasoning, was_traded, skip_reason, created_at
        FROM signals
        ORDER BY created_at DESC
        LIMIT %s
    """
    results = await fetch_all(query, (limit,))
    return {"data": results, "count": len(results)}


@app.get("/api/signals/pending")
async def get_pending_signals():
    query = """
        SELECT id, market_id, station_icao, city, side,
               our_probability, market_price, edge, confidence,
               claude_reasoning, created_at
        FROM signals
        WHERE was_traded = false AND confidence = 'HIGH'
        ORDER BY edge DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


# =============================================================================
# Trades — correct column names from actual schema
# =============================================================================

@app.get("/api/trades")
async def get_trades(limit: int = 100):
    query = """
        SELECT id, signal_id, market_id, market_title, side,
               entry_price, shares, size_usd, edge_at_entry,
               status, exit_price, pnl_usd, pnl_pct,
               resolved_at, entry_at, metadata
        FROM trades
        ORDER BY entry_at DESC
        LIMIT %s
    """
    try:
        results = await fetch_all(query, (limit,))
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch trades: {e}")
        return {"data": [], "count": 0}


@app.get("/api/trades/active")
async def get_active_trades():
    query = """
        SELECT id, signal_id, market_id, market_title, side,
               entry_price, shares, size_usd, edge_at_entry,
               status, entry_at, metadata
        FROM trades
        WHERE status IN ('open', 'paper_open', 'live_open')
        ORDER BY entry_at DESC
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch active trades: {e}")
        return {"data": [], "count": 0}


# =============================================================================
# P&L & Analytics — correct column names
# =============================================================================

@app.get("/api/pnl/daily")
async def get_daily_pnl(days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    query = """
        SELECT
            DATE(resolved_at) as date,
            COUNT(*) as trades,
            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl_usd) as total_pnl,
            AVG(pnl_usd) as avg_pnl
        FROM trades
        WHERE resolved_at IS NOT NULL AND resolved_at >= %s
        GROUP BY DATE(resolved_at)
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
    """Query REAL bankroll table."""
    try:
        result = await fetch_one(
            "SELECT total_usd, available_usd, in_positions_usd, daily_pnl, timestamp as last_updated FROM bankroll ORDER BY timestamp DESC LIMIT 1"
        )
        if result:
            return {
                "total": float(result.get("total_usd", 0) or 0),
                "available": float(result.get("available_usd", 0) or 0),
                "in_positions": float(result.get("in_positions_usd", 0) or 0),
                "daily_pnl": float(result.get("daily_pnl", 0) or 0),
                "last_updated": result.get("last_updated", "").isoformat() if result.get("last_updated") else None,
            }
        return {"total": 0, "available": 0, "in_positions": 0, "daily_pnl": 0, "last_updated": None}
    except Exception as e:
        logger.error(f"Failed to fetch bankroll: {e}")
        return {"total": 0, "available": 0, "in_positions": 0, "daily_pnl": 0, "last_updated": None}


@app.get("/api/analytics/win-rate")
async def get_win_rate(days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    query = """
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            CASE WHEN COUNT(*) > 0
                THEN ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2)
                ELSE 0 END as win_rate_pct,
            COALESCE(SUM(pnl_usd), 0) as total_pnl,
            COALESCE(AVG(edge_at_entry), 0) as avg_edge
        FROM trades
        WHERE resolved_at IS NOT NULL AND resolved_at >= %s
    """
    try:
        result = await fetch_one(query, (since,))
        return result or {"total_trades": 0, "wins": 0, "win_rate_pct": 0, "total_pnl": 0, "avg_edge": 0}
    except Exception as e:
        logger.error(f"Failed to fetch win rate: {e}")
        return {"total_trades": 0, "wins": 0, "win_rate_pct": 0, "total_pnl": 0, "avg_edge": 0}


# =============================================================================
# DB Stats (for dashboard verification)
# =============================================================================

@app.get("/api/stats")
async def get_db_stats():
    """Return row counts for all tables — useful for verifying real data."""
    tables = ["metar_readings", "temperature_trends", "weather_markets", "signals", "trades", "bankroll", "station_accuracy"]
    stats = {}
    for table in tables:
        try:
            result = await fetch_one(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = result["count"] if result else 0
        except:
            stats[table] = "error"
    return {"tables": stats, "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# Polymarket Explorer — Proxy to bypass ISP blocks
# =============================================================================

@app.get("/api/explorer/markets")
async def explore_markets(category: str = None, search: str = None, limit: int = 50, cursor: str = "MA=="):
    """Proxy to Polymarket — browse all markets. Bypasses ISP blocks."""
    import httpx
    params = {"limit": limit, "next_cursor": cursor}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://clob.polymarket.com/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
        
        markets = data.get("data", [])
        
        # Filter by search text
        if search:
            search_lower = search.lower()
            markets = [m for m in markets if search_lower in m.get("question", "").lower()]
        
        # Filter by category keyword
        if category:
            cat_lower = category.lower()
            markets = [
                m for m in markets 
                if cat_lower in m.get("question", "").lower() 
                or cat_lower in str(m.get("tags", [])).lower()
            ]
        
        return {
            "data": markets,
            "count": len(markets),
            "next_cursor": data.get("next_cursor"),
            "source": "polymarket_proxy"
        }
    except Exception as e:
        logger.error(f"Explorer markets error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch markets: {str(e)}")


@app.get("/api/explorer/events")
async def explore_events(tag: str = None, search: str = None, limit: int = 20):
    """Proxy to Polymarket events."""
    import httpx
    params = {"limit": limit, "active": "true", "closed": "false"}
    if tag:
        params["tag"] = tag
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://gamma-api.polymarket.com/events", params=params)
            resp.raise_for_status()
            data = resp.json()
        
        # Ensure data is a list
        if not isinstance(data, list):
            data = data.get("data", []) if isinstance(data, dict) else []
        
        # Filter by search
        if search:
            search_lower = search.lower()
            data = [
                e for e in data 
                if search_lower in e.get("title", "").lower() 
                or search_lower in e.get("question", "").lower()
            ]
        
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"Explorer events error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch events: {str(e)}")


@app.get("/api/explorer/market/{condition_id}")
async def get_market_detail(condition_id: str):
    """Get detailed market data including order book."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get market data
            market_resp = await client.get(f"https://clob.polymarket.com/markets/{condition_id}")
            market_resp.raise_for_status()
            market = market_resp.json()
            
            # Get order book
            try:
                book_resp = await client.get(f"https://clob.polymarket.com/book?token_id={condition_id}")
                book_resp.raise_for_status()
                order_book = book_resp.json()
            except:
                order_book = {"bids": [], "asks": []}
        
        return {
            "market": market,
            "order_book": order_book
        }
    except Exception as e:
        logger.error(f"Explorer market detail error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch market detail: {str(e)}")


@app.get("/api/explorer/prices/{condition_id}")
async def get_price_history(condition_id: str, interval: str = "1h", fidelity: int = 60):
    """Get price history for charting."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://clob.polymarket.com/prices-history",
                params={"market": condition_id, "interval": interval, "fidelity": fidelity}
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Explorer price history error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch price history: {str(e)}")


# =============================================================================
# Intelligence & Improvement — NEW ENDPOINTS
# =============================================================================

@app.get("/api/intelligence/daily")
async def get_daily_analysis():
    """Get daily performance analysis from improvement engine."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        analysis = await _improvement_engine.daily_analysis()
        return analysis
    except Exception as e:
        logger.error(f"Daily analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate daily analysis: {str(e)}")


@app.get("/api/intelligence/weekly")
async def get_weekly_review():
    """Get weekly strategy review with findings and proposals."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        review = await _improvement_engine.weekly_review()
        return review
    except Exception as e:
        logger.error(f"Weekly review error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate weekly review: {str(e)}")


@app.get("/api/intelligence/calibration")
async def get_probability_calibration():
    """Get probability model calibration metrics."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        calibration = await _improvement_engine.calibrate_probability_model()
        return calibration
    except Exception as e:
        logger.error(f"Calibration error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate calibration: {str(e)}")


@app.post("/api/intelligence/approve/{proposal_id}")
async def approve_proposal(proposal_id: str):
    """CEO approves a strategy change proposal.
    
    NOTE: This is a placeholder. Real implementation would:
    1. Fetch proposal from DB
    2. Parse parameter changes
    3. Update STRATEGY.md
    4. Update config values
    5. Log approval in changelog
    """
    # TODO: Implement proposal approval workflow
    return {
        "status": "approved",
        "proposal_id": proposal_id,
        "message": "Proposal approval not yet implemented. See STRATEGY.md for manual updates.",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6010)
