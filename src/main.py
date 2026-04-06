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
    global _last_data_scan, _startup_time, _signal_loop, _improvement_engine

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
            observation_time, created_at
        FROM metar_readings
        ORDER BY station_icao, observation_time DESC
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
               observation_time
        FROM metar_readings
        WHERE station_icao = %s AND observation_time >= %s
        ORDER BY observation_time DESC
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

def detect_category(question: str) -> str:
    """Detect market category from question text."""
    q = question.lower()
    
    weather_kw = ['temperature', 'weather', 'rain', 'snow', 'celsius', 'fahrenheit', '°f', '°c', 'heat wave', 'cold front', 'forecast', 'high temp', 'low temp']
    sports_kw = ['ncaa', 'nba', 'nfl', 'mlb', 'nhl', 'premier league', 'champions league', 'world cup', 'super bowl', 'touchdown', 'goal', 'match', 'game', 'playoffs', 'series', 'vs.', 'vs ']
    politics_kw = ['president', 'election', 'vote', 'congress', 'senate', 'governor', 'democrat', 'republican', 'biden', 'trump', 'parliament', 'prime minister']
    crypto_kw = ['bitcoin', 'ethereum', 'btc', 'eth', 'crypto', 'token', 'blockchain', 'defi', 'solana', 'sol']
    economics_kw = ['gdp', 'inflation', 'fed', 'interest rate', 'unemployment', 'recession', 'stock', 's&p', 'nasdaq', 'dow jones']
    science_kw = ['ai', 'artificial intelligence', 'spacex', 'nasa', 'climate', 'vaccine', 'disease', 'pandemic']
    entertainment_kw = ['oscar', 'grammy', 'box office', 'movie', 'album', 'taylor swift', 'drake', 'emmy']
    
    if any(kw in q for kw in weather_kw): return 'weather'
    if any(kw in q for kw in sports_kw): return 'sports'
    if any(kw in q for kw in politics_kw): return 'politics'
    if any(kw in q for kw in crypto_kw): return 'crypto'
    if any(kw in q for kw in economics_kw): return 'economics'
    if any(kw in q for kw in science_kw): return 'science'
    if any(kw in q for kw in entertainment_kw): return 'entertainment'
    return 'other'


@app.get("/api/explorer/markets")
async def explore_markets(category: str = None, search: str = None, limit: int = 50, cursor: str = "MA==", active_only: bool = True):
    """Proxy to Polymarket — filtered, categorized markets."""
    import httpx
    
    all_markets = []
    current_cursor = cursor
    pages_fetched = 0
    max_pages = 5  # Don't fetch too many pages
    
    async with httpx.AsyncClient(timeout=15) as client:
        while pages_fetched < max_pages and len(all_markets) < limit:
            params = {"limit": 100, "next_cursor": current_cursor}
            try:
                resp = await client.get("https://clob.polymarket.com/markets", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Explorer markets error: {e}")
                break
            
            batch = data.get("data", [])
            if not batch:
                break
            
            for market in batch:
                # Skip inactive markets (use 'active' field from API)
                if active_only and not market.get("active", True):
                    continue
                
                # Also skip if both closed AND not accepting orders (truly dead markets)
                if active_only and market.get("closed") and not market.get("accepting_orders"):
                    continue
                
                # Add category detection
                question = (market.get("question") or "").lower()
                market["_category"] = detect_category(question)
                
                # Apply category filter
                if category and market["_category"] != category.lower():
                    continue
                
                # Apply search filter
                if search and search.lower() not in question:
                    continue
                
                # Extract clean price data
                tokens = market.get("tokens", [])
                market["_yes_price"] = float(tokens[0].get("price", 0.5)) if tokens else 0.5
                market["_no_price"] = float(tokens[1].get("price", 0.5)) if len(tokens) > 1 else 0.5
                market["_volume"] = float(market.get("volume", 0) or 0)
                
                all_markets.append(market)
            
            current_cursor = data.get("next_cursor")
            if not current_cursor:
                break
            pages_fetched += 1
    
    # Sort by volume (most active first)
    all_markets.sort(key=lambda m: m.get("_volume", 0), reverse=True)
    
    return {
        "data": all_markets[:limit],
        "count": len(all_markets[:limit]),
        "next_cursor": current_cursor,
        "source": "polymarket_proxy"
    }


@app.get("/api/explorer/weather")
async def explore_weather_markets():
    """Our tracked weather markets from DB."""
    query = """
        SELECT market_id, title, city, station_icao, threshold_type, threshold_value,
               threshold_unit, resolution_date, yes_price, no_price, volume_usd, 
               liquidity_usd, active, last_updated
        FROM weather_markets 
        WHERE active = true
        ORDER BY volume_usd DESC NULLS LAST
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Weather markets error: {e}")
        return {"data": [], "count": 0}


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
# Intelligence Data — Forecasts, Historical, Combined View
# =============================================================================

@app.get("/api/intelligence/live-signals")
async def get_live_signals():
    """Run real-time intelligence analysis across all tracked markets.
    Returns probability estimates, expected returns, and trade recommendations.
    This is the LIVE TRADING SIGNAL BOARD."""
    from src.data.openmeteo import fetch_forecast
    
    try:
        # 1. Get all active weather markets from DB
        markets = await fetch_all("""
            SELECT * FROM weather_markets 
            WHERE active = true
            ORDER BY volume_usd DESC NULLS LAST
        """)
        
        # 2. Get latest METAR for each station
        metar = await fetch_all("""
            SELECT DISTINCT ON (station_icao)
                station_icao, temperature_c, observation_time
            FROM metar_readings 
            ORDER BY station_icao, observation_time DESC
        """)
        metar_map = {m['station_icao']: m for m in metar}
        
        # 3. Get trends
        trends = await fetch_all("""
            SELECT DISTINCT ON (station_icao)
                station_icao, trend_per_hour, projected_high, projected_low, confidence
            FROM temperature_trends 
            ORDER BY station_icao, calculated_at DESC
        """)
        trend_map = {t['station_icao']: t for t in trends}
        
        signals = []
        for market in markets:
            icao = market.get('station_icao', '')
            if not icao:
                continue
            
            metar_data = metar_map.get(icao, {})
            trend_data = trend_map.get(icao, {})
            
            if not metar_data:
                continue
            
            current_temp = float(metar_data.get('temperature_c', 0) or 0)
            threshold = float(market.get('threshold_value', 0) or 0)
            yes_price = float(market.get('yes_price', 0.5) or 0.5)
            no_price = float(market.get('no_price', 0.5) or 0.5)
            trend = float(trend_data.get('trend_per_hour', 0) or 0)
            projected_high = trend_data.get('projected_high')
            
            # Get forecast (cached, don't fetch every call)
            forecast_high = None
            try:
                forecast = await fetch_forecast(icao)
                if forecast:
                    forecast_high = forecast.get('forecast_high_c')
            except:
                pass
            
            # Calculate our probability
            # Simple model: based on data convergence
            votes_yes = 0
            total_sources = 0
            
            threshold_type = market.get('threshold_type', 'high_above')
            
            # Source 1: Current METAR
            total_sources += 1
            if threshold_type == 'high_above':
                if current_temp >= threshold:
                    votes_yes += 1  # Already hit
                elif projected_high and float(projected_high) >= threshold:
                    votes_yes += 0.7  # Trend says likely
            elif threshold_type == 'low_below':
                if current_temp <= threshold:
                    votes_yes += 1
            
            # Source 2: Forecast
            if forecast_high is not None:
                total_sources += 1
                if threshold_type == 'high_above' and forecast_high >= threshold:
                    votes_yes += 1
                elif threshold_type == 'low_below' and forecast_high <= threshold:
                    votes_yes += 1
            
            # Our probability estimate
            our_prob = min(0.95, max(0.05, votes_yes / max(total_sources, 1)))
            
            # Edge = our probability - market price
            edge_yes = our_prob - yes_price
            edge_no = (1 - our_prob) - no_price
            
            # Which side has better edge?
            if edge_yes > edge_no:
                recommended_side = "YES"
                edge = edge_yes
                entry_price = yes_price
            else:
                recommended_side = "NO"
                edge = edge_no
                entry_price = no_price
            
            # Expected return
            if entry_price > 0 and entry_price < 1:
                expected_return_pct = ((1.0 / entry_price) - 1) * our_prob * 100
            else:
                expected_return_pct = 0
            
            # Signal strength
            if edge >= 0.25:
                signal_status = "STRONG_BUY"  # Green flash
                auto_trade = True
            elif edge >= 0.15:
                signal_status = "BUY"  # Yellow
                auto_trade = False  # Alert only
            elif edge >= 0.05:
                signal_status = "WATCH"  # Gray
                auto_trade = False
            else:
                signal_status = "SKIP"
                auto_trade = False
            
            # Binary arbitrage check
            arb_total = yes_price + no_price
            is_arb = arb_total < 0.98
            
            signals.append({
                "market_id": market.get('market_id'),
                "title": market.get('title', ''),
                "city": market.get('city', ''),
                "station_icao": icao,
                "threshold": threshold,
                "threshold_type": threshold_type,
                "threshold_unit": market.get('threshold_unit', '°C'),
                
                # Current data
                "current_temp": current_temp,
                "trend_per_hour": trend,
                "projected_high": float(projected_high) if projected_high else None,
                "forecast_high": forecast_high,
                
                # Market prices
                "yes_price": yes_price,
                "no_price": no_price,
                "volume": float(market.get('volume_usd', 0) or 0),
                
                # Our analysis
                "our_probability": round(our_prob, 4),
                "recommended_side": recommended_side,
                "edge": round(edge, 4),
                "expected_return_pct": round(expected_return_pct, 2),
                
                # Signal
                "signal": signal_status,
                "auto_trade": auto_trade,
                "is_arbitrage": is_arb,
                "arb_total": round(arb_total, 4),
                
                # Data sources used
                "sources": {
                    "metar": True,
                    "forecast": forecast_high is not None,
                    "historical": False,  # Not fetched per-call for speed
                    "trend": trend != 0,
                },
                
                "resolution_date": str(market.get('resolution_date', '')),
                "last_updated": str(market.get('last_updated', '')),
            })
        
        # Sort by edge (strongest signals first)
        signals.sort(key=lambda s: abs(s['edge']), reverse=True)
        
        return {
            "signals": signals,
            "total_markets": len(markets),
            "actionable": sum(1 for s in signals if s['signal'] in ('STRONG_BUY', 'BUY')),
            "arbitrage": sum(1 for s in signals if s['is_arbitrage']),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Live signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trades/execute")
async def execute_trade(data: dict):
    """Execute a trade (paper or live based on mode)."""
    from src.execution.paper_trader import paper_trade
    
    try:
        market_id = data.get("market_id")
        side = data.get("side", "YES")
        size_usd = float(data.get("size_usd", 25))
        
        if not market_id:
            raise HTTPException(status_code=400, detail="market_id required")
        
        # Get current settings
        settings_row = await fetch_one("SELECT value FROM bot_settings WHERE key = 'trading_mode'")
        mode = settings_row['value'] if settings_row else '"paper"'
        
        # Execute paper trade (always paper for now)
        result = await paper_trade({
            "market_id": market_id,
            "side": side,
            "size_usd": size_usd,
            "mode": "paper",
        })
        
        return {
            "status": "executed",
            "trade": result,
            "mode": "paper",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute trade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/intelligence/forecast/{icao}")
async def get_forecast(icao: str):
    """Get Open-Meteo forecast for a station."""
    from src.data.openmeteo import fetch_forecast
    try:
        result = await fetch_forecast(icao.upper())
        if not result:
            raise HTTPException(status_code=404, detail=f"No forecast data for {icao}")
        return {"station": icao.upper(), **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/forecasts")
async def get_all_forecasts():
    """Get Open-Meteo forecasts for all tracked stations."""
    from src.data.openmeteo import fetch_all_forecasts, CITY_COORDS
    try:
        stations = list(CITY_COORDS.keys())
        results = await fetch_all_forecasts(stations)
        return {"data": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/historical/{icao}")
async def get_historical(icao: str):
    """Get historical temperature pattern for a station."""
    from src.data.historical import fetch_historical_pattern
    from datetime import datetime
    try:
        result = await fetch_historical_pattern(icao.upper(), datetime.utcnow())
        if not result:
            raise HTTPException(status_code=404, detail=f"No historical data for {icao}")
        return {"station": icao.upper(), **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/dashboard")
async def get_intelligence_dashboard():
    """Combined intelligence view — METAR + forecasts + trends + comparison.
    Returns all data needed for the Intelligence dashboard page."""
    from src.data.openmeteo import fetch_forecast, CITY_COORDS
    from src.data.city_map import CITY_TO_ICAO
    import asyncio
    
    try:
        # Get latest METAR data
        metar_data = await fetch_all("""SELECT DISTINCT ON (station_icao)
            station_icao, temperature_c, dewpoint_c, wind_speed_kt, wind_dir,
            observation_time, created_at
            FROM metar_readings ORDER BY station_icao, observation_time DESC""")
        
        # Get temperature trends
        trends = await fetch_all("""SELECT DISTINCT ON (station_icao)
            station_icao, trend_per_hour, projected_high, projected_low, confidence, num_readings
            FROM temperature_trends ORDER BY station_icao, calculated_at DESC""")
        trend_map = {t['station_icao']: t for t in trends}
        
        # Get Open-Meteo forecasts for top 10 stations (to keep response fast)
        top_stations = [m['station_icao'] for m in metar_data[:10]]
        forecasts = {}
        for icao in top_stations:
            try:
                f = await fetch_forecast(icao)
                if f:
                    forecasts[icao] = f
            except:
                pass
        
        # Build combined view per station
        stations = []
        for m in metar_data:
            icao = m['station_icao']
            trend = trend_map.get(icao, {})
            forecast = forecasts.get(icao, {})
            
            # Calculate data convergence (Gate 1 preview)
            metar_temp = m.get('temperature_c', 0)
            forecast_high = forecast.get('forecast_high_c')
            trend_projected = trend.get('projected_high')
            
            sources_agree = 0
            total_sources = 1  # METAR always counts
            if forecast_high is not None:
                total_sources += 1
                if abs(forecast_high - metar_temp) < 5:  # Within 5°C
                    sources_agree += 1
            if trend_projected is not None:
                total_sources += 1
                if abs(trend_projected - metar_temp) < 5:
                    sources_agree += 1
            
            stations.append({
                'station_icao': icao,
                'metar': {
                    'temperature_c': metar_temp,
                    'dewpoint_c': m.get('dewpoint_c'),
                    'wind_speed_kt': m.get('wind_speed_kt'),
                    'wind_dir': m.get('wind_dir'),
                    'observation_time': str(m.get('observation_time', '')),
                },
                'trend': {
                    'per_hour': trend.get('trend_per_hour'),
                    'projected_high': trend.get('projected_high'),
                    'projected_low': trend.get('projected_low'),
                    'confidence': trend.get('confidence'),
                },
                'forecast': {
                    'high_c': forecast_high,
                    'low_c': forecast.get('forecast_low_c'),
                    'hourly_temps': forecast.get('hourly_temps', [])[:12],
                    'precip_probs': forecast.get('precipitation_probs', [])[:12],
                },
                'convergence': {
                    'sources_agree': sources_agree,
                    'total_sources': total_sources,
                    'status': 'high' if sources_agree >= 2 else 'medium' if sources_agree == 1 else 'low',
                },
            })
        
        # Get signal count and recent activity
        signal_count = await fetch_all("SELECT COUNT(*) as count FROM signals")
        trade_count = await fetch_all("SELECT COUNT(*) as count FROM trades")
        
        return {
            'stations': stations,
            'station_count': len(stations),
            'signal_count': signal_count[0]['count'] if signal_count else 0,
            'trade_count': trade_count[0]['count'] if trade_count else 0,
            'forecast_count': len(forecasts),
            'trend_count': len(trends),
        }
    except Exception as e:
        logger.error(f"Intelligence dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Intelligence & Improvement — Analysis Endpoints
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


# =============================================================================
# Settings & Bot Control
# =============================================================================

@app.get("/api/settings")
async def get_settings():
    """Get all bot settings from DB and config."""
    try:
        # Fetch from bot_settings table
        query = "SELECT key, value FROM bot_settings"
        rows = await fetch_all(query)
        settings = {row["key"]: row["value"] for row in rows}
        
        # Add config defaults if missing
        if not settings:
            settings = {
                "max_position_size": 50,
                "max_portfolio_exposure": 15,
                "kelly_fraction": 0.25,
                "max_trades_per_city_per_day": 3,
                "daily_loss_limit": 10,
                "min_edge_auto_trade": 25,
                "min_edge_alert": 15,
                "min_confidence_sources": 2,
                "max_spread_cents": 8,
                "min_liquidity_multiple": 2,
                "min_hours_to_resolution": 2,
                "gates_enabled": {
                    "data_convergence": True,
                    "multi_station": True,
                    "bucket_coherence": True,
                    "binary_arbitrage": True,
                    "liquidity_check": True,
                    "time_window": True,
                    "risk_manager": True,
                    "claude_confirmation": True
                },
                "telegram_alerts": False,
                "telegram_chat_id": "",
                "alert_on_trade": True,
                "alert_on_signal": True,
                "alert_on_daily_summary": True,
                "refresh_interval_min": 15,
                "strategy_auto_proposals": True,
                "weekly_review_day": "Sunday",
                "weekly_review_time": "09:00",
                "auto_adjust_accuracy": True,
                "proposal_approval_mode": "require"
            }
        
        return {
            "settings": settings,
            "mode": getattr(config, 'MODE', 'paper'),
            "wallet_address": getattr(config, 'WALLET_ADDRESS', None)
        }
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        return {"settings": {}, "mode": "paper", "wallet_address": None}


@app.post("/api/settings")
async def save_settings(settings: dict):
    """Save bot settings to DB."""
    try:
        for key, value in settings.items():
            await execute(
                "INSERT INTO bot_settings (key, value, updated_at) VALUES (%s, %s::jsonb, NOW()) ON CONFLICT (key) DO UPDATE SET value = %s::jsonb, updated_at = NOW()",
                (key, str(value), str(value))
            )
        return {"status": "saved", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Save settings error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@app.post("/api/bot/start")
async def start_bot():
    """Start the trading bot."""
    global scheduler
    if not scheduler.running:
        scheduler.start()
    return {"status": "started", "running": scheduler.running, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/bot/pause")
async def pause_bot():
    """Pause — stop new trades but keep monitoring."""
    # TODO: Add pause flag to signal loop
    return {"status": "paused", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/bot/stop")
async def stop_bot():
    """Emergency stop — halt everything immediately."""
    global scheduler
    if scheduler.running:
        scheduler.pause()
    return {"status": "stopped", "running": scheduler.running, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/wallet/balance")
async def get_wallet_balance():
    """Get USDC + MATIC balance from Polygon."""
    import httpx
    
    wallet_address = getattr(config, 'WALLET_ADDRESS', None)
    if not wallet_address:
        return {"error": "Wallet address not configured", "usdc": 0, "matic": 0}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Get MATIC balance
            matic_resp = await client.post(
                "https://polygon-rpc.com",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [wallet_address, "latest"],
                    "id": 1
                }
            )
            matic_data = matic_resp.json()
            matic_wei = int(matic_data.get("result", "0x0"), 16)
            matic_balance = matic_wei / 1e18
            
            # Get USDC balance (ERC-20)
            usdc_contract = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
            # balanceOf(address) = 0x70a08231 + padded address
            data_param = "0x70a08231" + wallet_address[2:].zfill(64)
            
            usdc_resp = await client.post(
                "https://polygon-rpc.com",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{"to": usdc_contract, "data": data_param}, "latest"],
                    "id": 2
                }
            )
            usdc_data = usdc_resp.json()
            usdc_raw = int(usdc_data.get("result", "0x0"), 16)
            usdc_balance = usdc_raw / 1e6  # USDC has 6 decimals
        
        return {
            "usdc": round(usdc_balance, 2),
            "matic": round(matic_balance, 4),
            "wallet": wallet_address,
            "network": "Polygon Mainnet",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Wallet balance error: {e}")
        return {"error": str(e), "usdc": 0, "matic": 0}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6010)
