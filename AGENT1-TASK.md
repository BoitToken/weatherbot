# AGENT 1: Weather Trading Engine — Make It Actually Trade

You are fixing a trading bot that was reported as complete but has ZERO trades, ZERO signals, and empty data tables. The dashboard looks nice but the engine behind it is hollow. Your job is to make it actually work end-to-end.

## Current State
- PM2 process 'weatherbot' running (FastAPI + APScheduler)
- DB: polyedge (PostgreSQL, localhost:5432, user: node)
- METAR data: 1,178 readings (this works)
- noaa_forecasts table: 0 rows (NOAA not integrated)
- signals table: 0 rows (signal loop produces nothing)
- trades table: 0 rows (no paper trades)
- weather_markets table: 0 rows (scanner broken)
- Scheduler runs data scan every 30 min, signal scan every 5 min (but produces nothing)

## Architecture
- src/main.py — FastAPI app with APScheduler
- src/signals/signal_loop.py — main signal orchestrator (Strategy A + B)
- src/signals/strategy_a.py — 'Forecast Edge' (NOAA vs market price)
- src/signals/intelligence.py — 8-gate intelligence layer (Strategy B)
- src/signals/mismatch_detector.py — finds edge between forecast and market
- src/signals/signal_bus.py — emits trading signals with Kelly sizing
- src/signals/claude_analyzer.py — AI confirmation gate
- src/data/noaa_forecast.py — NOAA module (exists but never fetches)
- src/data/openmeteo.py — Open-Meteo module
- src/data/metar_fetcher.py — METAR fetcher (working)
- src/execution/paper_trader.py — paper trade executor
- src/execution/risk_manager.py — position/loss limits
- src/learning/improvement.py — trade outcome analysis
- src/config.py — DB_URL=postgresql://node@localhost:5432/polyedge

## YOUR TASKS (in order)

### 1. NOAA GFS Integration
- src/data/noaa_forecast.py needs to actually fetch from api.weather.gov
- Endpoint: https://api.weather.gov/gridpoints/{office}/{x},{y}/forecast
- Target cities and their grid points:
  - NYC (KJFK): OKX/33,37
  - Chicago (KORD): LOT/75,72
  - Atlanta (KATL): FFC/52,87
  - Dallas (KDFW): FWD/83,104
  - Miami (KMIA): MFL/75,50
  - Seattle (KSEA): SEW/124,67
- For London/Seoul, use Open-Meteo as primary (NOAA only covers US)
- Store results in noaa_forecasts table
- MUST have real data after your work

### 2. Fix Polymarket Market Scanner
- The scanner needs to find temperature bucket markets
- Polymarket Gamma API: https://gamma-api.polymarket.com/markets
- Search with keywords: 'temperature', 'high temp', 'weather', 'degrees'
- Also try CLOB API: https://clob.polymarket.com/markets
- NOTE: 0 active weather markets may exist right now (seasonal). That's OK.
- Scanner must be CAPABLE of finding them. Store in weather_markets table.

### 3. Wire Strategy A End-to-End
- src/signals/strategy_a.py must:
  a. Call NOAA/Open-Meteo for forecast
  b. Get temperature bucket markets from scanner
  c. Find the bucket matching forecast temp
  d. Compare bucket price to entry threshold (<=15 cents)
  e. Emit BUY signal if mispriced
- If no weather markets exist, log 'No active weather markets found' and skip

### 4. Wire Strategy B (8-Gate)
- src/signals/intelligence.py gates need real data:
  - Gate 1: METAR (have it) + forecast (from step 1) + historical baseline
  - Gate 2: Multi-station (METAR exists for multiple stations per city)
- If no markets, skip gracefully

### 5. Early Exit Logic
- When a held position reaches 45 cents, emit SELL signal
- Don't wait for market resolution

### 6. Improvement Loop Connection
- Wire daily_analysis() to scheduler (daily at midnight UTC)

### 7. Signal Loop MUST Produce Output
- Even with 0 weather markets, log what was tried and that 0 markets found
- With markets present, MUST produce signals and paper trades

## VERIFICATION (run AFTER you're done)
```bash
cd /data/.openclaw/workspace/projects/weatherbot
source .venv/bin/activate
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://node@localhost:5432/polyedge')
cur = conn.cursor()
for table in ['noaa_forecasts', 'signals', 'trades', 'weather_markets', 'metar_readings']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}: {cur.fetchone()[0]} rows')
conn.close()
"
```

- noaa_forecasts MUST have > 0 rows
- signals MAY be 0 if no weather markets (but logs must show scan attempt)

## DO NOT
- Don't mock/fake data. Use real API calls.
- Don't modify the dashboard. Focus on data/signal/execution pipeline.
- Don't touch sports code. Agent 2 handles that.

## After changes, restart:
```bash
pm2 restart weatherbot
sleep 5
pm2 logs weatherbot --lines 30 --nostream
```

When finished: `openclaw system event --text "Done: Agent 1 Weather Engine — NOAA integrated, pipeline verified" --mode now`
