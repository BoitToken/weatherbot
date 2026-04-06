# WeatherBot — AI-Powered Polymarket Weather Trading Bot

> Autonomous weather prediction market trader with 8-gate intelligence layer, live METAR data, and a full-featured web dashboard.

## 🎯 What It Does

WeatherBot monitors real-time weather data from 50+ airport stations worldwide, cross-references with forecast models, and identifies mispricings on Polymarket weather prediction markets. Every potential trade passes through an **8-gate intelligence checklist** before execution.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Dashboard (React)                  │
│  Overview │ Markets │ Signals │ Trades │ Explorer    │
│  METAR    │ Analytics│ Settings│                     │
└────────────────────────┬────────────────────────────┘
                         │ HTTPS (nginx)
┌────────────────────────▼────────────────────────────┐
│              FastAPI Backend (port 6010)             │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Data Loop │  │ Signal Loop  │  │ Paper Trader  │  │
│  │ (30 min)  │  │ (5 min)      │  │               │  │
│  └─────┬─────┘  └──────┬───────┘  └───────────────┘  │
│        │               │                              │
│  ┌─────▼─────────────────▼──────────────────────┐    │
│  │         8-Gate Intelligence Layer             │    │
│  │  1. Data Convergence (METAR+Forecast+History) │    │
│  │  2. Multi-Station Validation                  │    │
│  │  3. Bucket Coherence                          │    │
│  │  4. Binary Arbitrage Scanner                  │    │
│  │  5. Liquidity & Execution Check               │    │
│  │  6. Time Window Optimization                  │    │
│  │  7. Risk Manager (Kelly + Circuit Breakers)   │    │
│  │  8. Claude AI Confirmation                    │    │
│  └───────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐     │
│  │          Improvement Loop                    │     │
│  │  Daily analysis → Weekly review →            │     │
│  │  CEO-approved strategy changes only          │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────┬───────────────────────────────┘
                       │
           ┌───────────▼───────────┐
           │   PostgreSQL (polyedge) │
           │  7 tables, localhost    │
           └───────────────────────┘
```

## 📊 Data Sources

| Source | What | Refresh |
|--------|------|---------|
| **METAR** (aviationweather.gov) | Real-time airport temperatures, wind, visibility | Every 30 min |
| **Open-Meteo** | Hourly forecasts, daily highs/lows, 62 cities | On-demand |
| **Historical** (Open-Meteo Archive) | 5-year temperature patterns per city/date | On-demand |
| **Polymarket CLOB** | Market prices, order books, volume | Every 5 min |

## 🧠 The 8-Gate Intelligence System

Every trade MUST pass ALL gates. See [STRATEGY.md](STRATEGY.md) for full details.

| Gate | What It Checks | Auto-Kill If |
|------|---------------|-------------|
| 1. Data Convergence | 3 sources agree (METAR + forecast + historical) | <2 of 3 agree |
| 2. Multi-Station | Multiple airports for same city validate | Stations diverge >2°C |
| 3. Bucket Coherence | Temperature range prices sum correctly | Our bucket is overpriced |
| 4. Binary Arbitrage | YES + NO < $0.98 = free money | N/A (always passes) |
| 5. Liquidity | Order book has enough depth, spread < 8¢ | Spread >8¢ or thin book |
| 6. Time Window | Optimal trading hours for mispricing | <2 hours to resolution |
| 7. Risk Manager | Position limits, circuit breakers | Daily loss >10% |
| 8. Claude AI | Catches edge cases humans/models miss | Claude says SKIP |

## 📈 Improvement Loop

The bot learns from every trade:
- **Daily:** Win rate, P&L, per-station accuracy
- **Weekly:** Strategy review with findings → reported to CEO
- **Monthly:** Full strategy audit
- **Rule:** Strategy changes ONLY after CEO approval → updates STRATEGY.md

## 🚀 Live Infrastructure

- **Dashboard:** https://weatherbot.1nnercircle.club
- **API:** https://weatherbot.1nnercircle.club/api/health
- **PM2:** `weatherbot` (port 6010)
- **DB:** PostgreSQL `polyedge` on localhost:5432

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `metar_readings` | Raw METAR observations from 50+ stations |
| `temperature_trends` | Computed trends (°C/hour, projected highs/lows) |
| `weather_markets` | Polymarket weather markets we track |
| `signals` | Trading signals with full intelligence reports |
| `trades` | Executed trades (paper + live) with P&L |
| `bankroll` | Portfolio balance tracking |
| `station_accuracy` | Per-station prediction accuracy |

## 📡 API Endpoints

### Core
- `GET /api/health` — Health check + scheduler status
- `GET /api/bot/status` — Bot running state + last actions
- `GET /api/metar/latest` — Latest readings from all 45+ stations
- `GET /api/metar/{icao}` — Historical readings for one station

### Markets & Signals
- `GET /api/markets` — Tracked weather markets
- `GET /api/signals` — Generated trading signals
- `GET /api/trades` — Trade history with P&L
- `GET /api/trades/active` — Open positions
- `GET /api/bankroll` — Portfolio balance

### Explorer (Polymarket Proxy)
- `GET /api/explorer/markets` — Browse all Polymarket markets (bypasses ISP blocks)
- `GET /api/explorer/events` — Browse Polymarket events
- `GET /api/explorer/market/{id}` — Market detail + order book
- `GET /api/explorer/prices/{id}` — Price history

### Intelligence
- `GET /api/intelligence/daily` — Daily performance analysis
- `GET /api/intelligence/weekly` — Weekly strategy review
- `GET /api/intelligence/calibration` — Prediction calibration metrics
- `POST /api/intelligence/approve/{id}` — CEO approves strategy change

## 🛠️ Tech Stack

- **Backend:** Python 3.13 + FastAPI + Uvicorn
- **Frontend:** React + Vite
- **Database:** PostgreSQL 17
- **Scheduler:** APScheduler (30min data, 5min signals)
- **AI:** Claude Haiku (fast analysis) + Claude Sonnet (deep review)
- **Weather:** METAR + Open-Meteo (no API keys needed)
- **Markets:** Polymarket CLOB API + Gamma API

## 🚦 Current Status

- ✅ 45+ METAR stations reporting live data
- ✅ 1,691 weather markets discovered via CLOB scanner
- ✅ 8-gate intelligence layer operational
- ✅ Open-Meteo integration (62 cities)
- ✅ Improvement loop with CEO-approval gate
- ✅ Dashboard with 8 pages
- ✅ Polymarket Explorer proxy (bypasses India ISP blocks)
- 🟡 Paper trading mode (wallet not yet funded)
- 🟡 Settings endpoints being wired to real config
- ❌ Live trading (requires funded Polygon wallet)

## 📁 Project Structure

```
weatherbot/
├── src/
│   ├── main.py              # FastAPI app + all API endpoints
│   ├── config.py             # Configuration
│   ├── db.py                 # Sync DB helpers
│   ├── db_async.py           # Async DB wrapper
│   ├── data/
│   │   ├── metar_fetcher.py  # METAR station data
│   │   ├── openmeteo.py      # Open-Meteo forecast + historical
│   │   ├── historical.py     # Historical temperature patterns
│   │   └── city_map.py       # ICAO → city mapping
│   ├── markets/
│   │   └── polymarket_scanner.py  # CLOB pagination + keyword detection
│   ├── signals/
│   │   ├── signal_loop.py    # Main signal detection loop
│   │   ├── intelligence.py   # 8-gate pre-trade checklist
│   │   ├── mismatch_detector.py  # METAR vs market mismatch
│   │   ├── gaussian_model.py # Probability calculator
│   │   ├── claude_analyzer.py    # Claude AI analysis
│   │   └── signal_bus.py     # Signal storage + routing
│   ├── execution/
│   │   ├── paper_trader.py   # Paper trading engine
│   │   └── risk_manager.py   # Position limits + circuit breakers
│   └── learning/
│       └── improvement.py    # Learning engine + strategy proposals
├── dashboard/
│   ├── src/pages/            # React pages (Overview, Markets, Signals, etc.)
│   └── dist/                 # Built dashboard
├── STRATEGY.md               # Trading strategy (CEO-approved changes only)
├── SPEC.md                   # Feature spec
└── ecosystem.config.cjs      # PM2 config
```

## 🔒 Security

- Private keys stored in `.env` (never committed)
- Dashboard behind HTTPS (Let's Encrypt)
- Wallet address display-only in UI (no private key exposure)
- Kill switch for emergency trading halt
- Circuit breakers: daily loss limit, consecutive loss reducer

## 📝 License

Private repository. © 2026.
