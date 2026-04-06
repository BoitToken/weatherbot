# WeatherBot — Development Log

## Build Timeline

### Phase 1: Foundation (2026-04-04 → 2026-04-05)
- ✅ PostgreSQL schema: 7 tables (metar_readings, temperature_trends, weather_markets, signals, trades, bankroll, station_accuracy)
- ✅ METAR fetcher: 50 airport stations, aviationweather.gov API
- ✅ Temperature trend calculator: linear regression, projected highs/lows
- ✅ Gaussian probability model for temperature thresholds
- ✅ Claude analyzer (Haiku for speed, Sonnet for deep analysis)
- ✅ Paper trader engine
- ✅ Risk manager with Kelly criterion sizing
- ✅ Dashboard scaffolding (React + Vite, 8 pages)
- ✅ FastAPI backend (16 endpoints, port 6010)
- ✅ APScheduler: data loop every 30 min, signal loop every 5 min
- ✅ DNS + SSL + nginx for weatherbot.1nnercircle.club

### Phase 2: Intelligence Layer (2026-04-06)
- ✅ Polymarket scanner rewrite: CLOB API pagination + text filtering (1,691 markets found)
- ✅ Explorer proxy: 4 API endpoints to bypass India ISP blocks
- ✅ Explorer dashboard page with search/filter/market detail
- ✅ Open-Meteo integration: 62 city coordinates, hourly + daily forecasts
- ✅ Historical temperature patterns: 5-year lookback via Open-Meteo Archive
- ✅ 8-gate intelligence layer (intelligence.py, 423 lines)
- ✅ Improvement loop engine (improvement.py, 263 lines)
- ✅ Signal loop wired to intelligence layer (all signals pass through 8 gates)
- ✅ 4 intelligence API endpoints (daily, weekly, calibration, approve)
- ✅ STRATEGY.md written (8 gates + parameters + improvement protocol)
- ✅ SPEC.md created (32 items, CEO requirements)
- ✅ METAR column name fix (observed_at → observation_time)

### Phase 3: Settings & Polish (In Progress)
- 🚧 Comprehensive Settings panel (8 sections, real backend storage)
- 🚧 Explorer filtering (active-only, categories, volume sorting)
- 🚧 Wallet balance integration (Polygon RPC)
- 🚧 Kill switch + bot control endpoints
- ❌ Live trading (requires funded wallet)

## Key Technical Decisions

### DB Async Wrapper (db_async.py)
FastAPI is async but psycopg2 is sync. Built a wrapper that:
- Provides asyncpg-style `pool.acquire()` + `conn.fetch()` API
- Converts `$1` params to `%s` (psycopg2 format)
- Returns dicts instead of tuples
- Thread pool executor for non-blocking DB calls

### Scanner Architecture
Polymarket has 3 APIs:
1. **CLOB API** (clob.polymarket.com) — real-time prices + order books, cursor-paginated
2. **Gamma API** (gamma-api.polymarket.com) — events, tag filtering (sometimes stale)
3. **Strapi API** — legacy, deprecated

We use CLOB as primary (cursor pagination through ALL markets + text filter for weather keywords). Gamma as backup for event discovery.

### Intelligence Layer Design
Modular gate system — each gate returns `GateResult(passed, confidence, details, data)`. Gates are independent and can be toggled on/off. Binary arbitrage gate (Gate 4) always passes but flags free money opportunities. Claude gate (Gate 8) only runs if all other gates pass (saves API costs).

### Improvement Loop Philosophy
Bot proposes strategy changes → CEO reviews findings → approves/rejects → only approved changes update STRATEGY.md parameters. This prevents the bot from overfitting to recent noise.

## Known Issues

1. **Scanner false positives:** "Meissner effect" matches on "temperature" keyword. Need negative keyword list for non-weather science markets.
2. **Closed markets in explorer:** CLOB API returns resolved markets. Need `accepting_orders: true` filter.
3. **METAR 204 responses:** Some Indian stations (VIDP, VIJP, VAPO) return 204 No Content intermittently.
4. **Settings TODO stubs:** Bot control endpoints exist in UI but aren't wired to real scheduler control yet.

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=     # For Claude analysis
DATABASE_URL=postgresql://node@localhost:5432/polyedge

# Optional (for live trading)
POLYMARKET_PRIVATE_KEY=  # Polygon wallet private key
POLYMARKET_API_KEY=      # CLOB API key (if needed)

# Auto-set
PORT=6010
```

## Deployment

```bash
# Start
pm2 start ecosystem.config.cjs

# Logs
pm2 logs weatherbot

# Restart
pm2 restart weatherbot

# Dashboard rebuild
cd dashboard && npm run build
```
