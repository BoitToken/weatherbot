# Shared Backend — PolyEdge Trade Management Platform
**The Brain Behind All Bots**  
**Created:** 2026-04-06  

---

## Overview

One backend manages ALL Polymarket bots (Weather, Sports, Crypto, Macro, etc.). Shared infrastructure for execution, risk management, learning, and strategy evolution.

We call it **PolyEdge** internally.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PolyEdge Backend                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐           │
│  │            BOT REGISTRY                           │           │
│  │  ├─ WeatherBot (METAR + Gaussian)                 │           │
│  │  ├─ SportsBot (Odds arb + News alpha)             │           │
│  │  ├─ CryptoBot (Black-Scholes + Pyth)              │           │
│  │  ├─ MacroBot (Fed/CPI data release)               │           │
│  │  ├─ EsportsBot (Pinnacle odds lag)                │           │
│  │  └─ Future bots register here...                  │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │            SIGNAL BUS                             │           │
│  │  Every bot emits signals in a standard format:    │           │
│  │  {                                                │           │
│  │    bot: "sports",                                 │           │
│  │    market_id: "0x...",                            │           │
│  │    side: "YES",                                   │           │
│  │    our_probability: 0.72,                         │           │
│  │    market_price: 0.58,                            │           │
│  │    edge: 0.14,                                    │           │
│  │    confidence: 0.85,                              │           │
│  │    source: "pinnacle_devig",                      │           │
│  │    expires_at: "2026-04-06T22:00:00Z",            │           │
│  │    metadata: { sport: "NBA", teams: [...] }       │           │
│  │  }                                                │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │        RISK MANAGER (Central Gatekeeper)          │           │
│  │  Before ANY trade executes, Risk Manager checks:  │           │
│  │                                                   │           │
│  │  1. Position limits:                              │           │
│  │     ├─ Per trade: ≤ 5% of total bankroll          │           │
│  │     ├─ Per bot: ≤ 25% of total bankroll           │           │
│  │     ├─ Per market: ≤ 10% of total bankroll        │           │
│  │     └─ Daily exposure: ≤ 40% of total bankroll    │           │
│  │                                                   │           │
│  │  2. Circuit breakers:                             │           │
│  │     ├─ Daily loss > 10% → halt ALL bots           │           │
│  │     ├─ Bot-specific loss > 15% weekly → halt bot  │           │
│  │     └─ 5 consecutive losses → reduce sizing 50%   │           │
│  │                                                   │           │
│  │  3. Correlation check:                            │           │
│  │     ├─ Don't bet same direction on correlated     │           │
│  │     │  events (e.g. BTC > $100K + BTC > $95K)     │           │
│  │     └─ Max correlated exposure: 15% bankroll      │           │
│  │                                                   │           │
│  │  4. Kelly sizing:                                 │           │
│  │     size = bankroll * (edge * confidence) / odds   │           │
│  │     Capped at ¼ Kelly for safety                  │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │        EXECUTION ENGINE (Polymarket CLOB)         │           │
│  │  ├─ Polygon wallet management (USDC balance)      │           │
│  │  ├─ Order placement via py-clob-client            │           │
│  │  ├─ Limit order strategy:                         │           │
│  │  │   Place 0.5¢ better than market for fills      │           │
│  │  ├─ Order lifecycle:                              │           │
│  │  │   Placed → Filled/Partial → Active → Resolved  │           │
│  │  ├─ Stale order cleanup: cancel after 5 min       │           │
│  │  ├─ Pre-resolution exit: sell if edge flips       │           │
│  │  └─ Gas management: batch transactions on Polygon │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │        TRADE LEDGER (PostgreSQL)                  │           │
│  │  Every trade logged with full context:            │           │
│  │  ├─ id, bot, market_id, market_title              │           │
│  │  ├─ side (YES/NO), entry_price, size_usd          │           │
│  │  ├─ edge_at_entry, confidence_at_entry            │           │
│  │  ├─ data_source (pinnacle, draftkings, metar...) │           │
│  │  ├─ signal_timestamp, entry_timestamp             │           │
│  │  ├─ exit_price, exit_timestamp, exit_reason       │           │
│  │  ├─ outcome (win/loss/push), pnl_usd, pnl_pct    │           │
│  │  ├─ resolution_timestamp                          │           │
│  │  └─ metadata (JSON: sport, teams, weather data..) │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │        LEARNING ENGINE (The Secret Weapon)        │           │
│  │                                                   │           │
│  │  CONTINUOUS IMPROVEMENT LOOP:                     │           │
│  │                                                   │           │
│  │  1. ACCURACY TRACKING (per bot, per source)       │           │
│  │     ├─ Predicted probability vs actual outcome     │           │
│  │     ├─ Brier score per bot per category            │           │
│  │     ├─ Calibration curve: are 70% signals         │           │
│  │     │  winning 70% of the time?                   │           │
│  │     └─ If not → adjust probability model          │           │
│  │                                                   │           │
│  │  2. EDGE DECAY ANALYSIS                           │           │
│  │     ├─ How fast do Polymarket prices catch up?    │           │
│  │     ├─ Optimal entry window: X min after signal   │           │
│  │     ├─ Edge half-life per category                │           │
│  │     └─ Adjust speed vs size tradeoff              │           │
│  │                                                   │           │
│  │  3. SOURCE RELIABILITY RANKING                    │           │
│  │     ├─ Which sportsbook is most accurate?          │           │
│  │     ├─ Which METAR stations are most calibrated?  │           │
│  │     ├─ Which Twitter accounts break news fastest? │           │
│  │     └─ Weight signals by source reliability       │           │
│  │                                                   │           │
│  │  4. STRATEGY EVOLUTION                            │           │
│  │     ├─ Weekly: Claude Sonnet reviews all trades   │           │
│  │     │  "Here are 200 trades. What patterns do     │           │
│  │     │   you see? What should we change?"          │           │
│  │     ├─ Monthly: full strategy retrospective       │           │
│  │     │  Edge by category, time of day, sport,      │           │
│  │     │  market size, entry delay                   │           │
│  │     ├─ Auto-tune parameters:                      │           │
│  │     │  min_edge, kelly_fraction, max_position,    │           │
│  │     │  stale_order_timeout, entry_delay            │           │
│  │     └─ A/B testing: run two strategies in         │           │
│  │        parallel, converge to winner               │           │
│  │                                                   │           │
│  │  5. PATTERN DETECTION                             │           │
│  │     ├─ Time-of-day patterns (markets mispriced    │           │
│  │     │  more at 3AM EST when US traders sleep)     │           │
│  │     ├─ Day-of-week patterns (NFL Sunday volume)   │           │
│  │     ├─ Market-size patterns (small markets more   │           │
│  │     │  mispriced but harder to fill)              │           │
│  │     └─ Competitor detection (other bots entering  │           │
│  │        same arb → edge shrinking → adapt)         │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌──────────────────────────────────────────────────┐           │
│  │        ALERTS & DASHBOARD                         │           │
│  │  ├─ Telegram bot:                                 │           │
│  │  │   🟢 Trade placed: NBA Lakers YES @ 62¢ ($50) │           │
│  │  │   ✅ Trade won: +$31 (62% → $1.00)             │           │
│  │  │   ❌ Trade lost: -$50                           │           │
│  │  │   🚨 Circuit breaker: daily loss limit hit      │           │
│  │  │   📊 Daily summary: 8W/3L, +$142, edge 5.2%   │           │
│  │  │                                                │           │
│  │  ├─ React Dashboard:                              │           │
│  │  │   ├─ Live P&L curve (real-time via WebSocket)  │           │
│  │  │   ├─ Active positions table with live prices   │           │
│  │  │   ├─ Signal queue (flagged but unplaced)       │           │
│  │  │   ├─ Bot status: running/paused/error          │           │
│  │  │   ├─ Win rate charts by bot, sport, edge tier │           │
│  │  │   ├─ Edge decay heatmap                        │           │
│  │  │   ├─ Sportsbook accuracy leaderboard           │           │
│  │  │   └─ Manual override: pause bot, force exit    │           │
│  │  │                                                │           │
│  │  └─ Email weekly digest:                          │           │
│  │      ├─ Total P&L, win rate, best/worst trades    │           │
│  │      ├─ Strategy recommendations from Claude       │           │
│  │      └─ Parameter adjustments applied             │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- Core trade ledger
CREATE TABLE trades (
  id SERIAL PRIMARY KEY,
  bot TEXT NOT NULL,                    -- 'weather', 'sports', 'crypto'
  market_id TEXT NOT NULL,             -- Polymarket condition ID
  market_title TEXT,                   -- Human-readable
  side TEXT NOT NULL,                  -- 'YES' or 'NO'
  entry_price DECIMAL(10,4),          -- Price paid per share
  shares DECIMAL(12,4),               -- Number of shares
  size_usd DECIMAL(10,2),             -- Total USD cost
  edge_at_entry DECIMAL(6,4),         -- Edge when trade placed
  confidence DECIMAL(6,4),            -- Model confidence 0-1
  our_probability DECIMAL(6,4),       -- What we think true prob is
  market_probability DECIMAL(6,4),    -- What market was pricing
  data_source TEXT,                    -- 'pinnacle', 'metar', 'pyth'
  signal_at TIMESTAMP NOT NULL,       -- When signal was generated
  entry_at TIMESTAMP NOT NULL,        -- When trade was placed
  exit_price DECIMAL(10,4),           -- Price if sold before resolution
  exit_at TIMESTAMP,
  exit_reason TEXT,                    -- 'resolution', 'edge_flip', 'circuit_breaker'
  outcome TEXT,                        -- 'win', 'loss', 'push', 'open'
  pnl_usd DECIMAL(10,2),
  pnl_pct DECIMAL(8,4),
  resolved_at TIMESTAMP,
  metadata JSONB,                     -- Sport, teams, city, temp, etc.
  created_at TIMESTAMP DEFAULT NOW()
);

-- Bankroll tracking
CREATE TABLE bankroll_snapshots (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP DEFAULT NOW(),
  total_usd DECIMAL(12,2),
  available_usd DECIMAL(12,2),       -- Not in active positions
  in_positions_usd DECIMAL(12,2),
  unrealized_pnl DECIMAL(10,2),
  daily_pnl DECIMAL(10,2),
  weekly_pnl DECIMAL(10,2)
);

-- Signal log (every signal, even if not traded)
CREATE TABLE signals (
  id SERIAL PRIMARY KEY,
  bot TEXT NOT NULL,
  market_id TEXT,
  market_title TEXT,
  side TEXT,
  edge DECIMAL(6,4),
  confidence DECIMAL(6,4),
  our_probability DECIMAL(6,4),
  market_price DECIMAL(6,4),
  data_source TEXT,
  was_traded BOOLEAN DEFAULT FALSE,
  skip_reason TEXT,                   -- 'below_threshold', 'position_limit', 'circuit_breaker'
  created_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB
);

-- Bot performance metrics (daily rollup)
CREATE TABLE bot_daily_stats (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  bot TEXT NOT NULL,
  trades_placed INT,
  trades_won INT,
  trades_lost INT,
  total_pnl DECIMAL(10,2),
  avg_edge DECIMAL(6,4),
  avg_confidence DECIMAL(6,4),
  win_rate DECIMAL(6,4),
  brier_score DECIMAL(6,4),          -- Calibration accuracy
  edge_decay_avg_min DECIMAL(8,2),   -- Avg minutes for market to catch up
  best_data_source TEXT,
  UNIQUE(date, bot)
);

-- Learning parameters (auto-tuned weekly)
CREATE TABLE strategy_params (
  id SERIAL PRIMARY KEY,
  bot TEXT NOT NULL,
  param_name TEXT NOT NULL,           -- 'min_edge', 'kelly_fraction', etc.
  param_value DECIMAL(10,4),
  prev_value DECIMAL(10,4),
  changed_at TIMESTAMP DEFAULT NOW(),
  reason TEXT,                        -- 'auto_tune: win_rate dropped below 55%'
  UNIQUE(bot, param_name)
);

-- Source reliability tracking
CREATE TABLE source_accuracy (
  id SERIAL PRIMARY KEY,
  source_name TEXT NOT NULL,          -- 'pinnacle', 'draftkings', 'metar_RJTT'
  category TEXT,                      -- 'sportsbook', 'weather_station', 'news_account'
  total_signals INT DEFAULT 0,
  correct_signals INT DEFAULT 0,
  accuracy DECIMAL(6,4),
  avg_edge_when_correct DECIMAL(6,4),
  last_updated TIMESTAMP DEFAULT NOW(),
  UNIQUE(source_name)
);
```

---

## API Endpoints

```
# Bots
GET    /api/bots                      # List all bots + status
POST   /api/bots/:name/pause          # Pause a bot
POST   /api/bots/:name/resume         # Resume a bot

# Signals
GET    /api/signals                   # Recent signals (all bots)
GET    /api/signals?bot=sports        # Filtered by bot
GET    /api/signals/queue             # Untrades high-edge signals

# Trades
GET    /api/trades                    # All trades
GET    /api/trades/active             # Open positions
GET    /api/trades/:id                # Trade detail
POST   /api/trades/:id/exit           # Force exit a position

# P&L
GET    /api/pnl/daily                 # Daily P&L chart data
GET    /api/pnl/weekly                # Weekly rollup
GET    /api/pnl/by-bot                # P&L broken down by bot
GET    /api/pnl/by-sport              # P&L by sport/category

# Analytics
GET    /api/analytics/win-rate        # Win rate over time
GET    /api/analytics/edge-decay      # How fast edges close
GET    /api/analytics/calibration     # Predicted vs actual probability
GET    /api/analytics/sources         # Source reliability ranking

# Strategy
GET    /api/strategy/params           # Current tuning parameters
POST   /api/strategy/tune             # Manual parameter override
GET    /api/strategy/recommendations  # Claude weekly analysis

# Bankroll
GET    /api/bankroll                  # Current bankroll status
GET    /api/bankroll/history          # Bankroll over time
```

---

## Learning Engine — How It Continuously Improves

### Daily Auto-Analysis (Cron, 6AM UTC)

```python
async def daily_analysis():
    """Run every morning. Analyze yesterday's trades."""
    
    trades = get_yesterday_trades()
    
    # 1. Update source accuracy
    for source in unique_sources(trades):
        update_source_accuracy(source, trades)
    
    # 2. Check calibration
    # Group trades by predicted probability bucket (50-60%, 60-70%, etc.)
    # Check: are 70% predictions winning 70% of the time?
    calibration = calculate_calibration(trades)
    if calibration.max_deviation > 0.10:
        alert("⚠️ Calibration drift detected: {calibration.worst_bucket}")
    
    # 3. Update edge decay metrics
    for trade in trades:
        time_to_market_correction = trade.market_caught_up_at - trade.signal_at
        log_edge_decay(trade.bot, time_to_market_correction)
    
    # 4. Update daily stats table
    insert_daily_stats(trades)
```

### Weekly Strategy Review (Cron, Sunday 9AM UTC)

```python
async def weekly_review():
    """Claude Sonnet analyzes the week's trading."""
    
    trades = get_week_trades()
    stats = calculate_weekly_stats(trades)
    
    prompt = f"""
    Here are this week's Polymarket trading results:
    
    Trades: {stats.total} | Won: {stats.won} | Lost: {stats.lost}
    Win Rate: {stats.win_rate}%
    Total P&L: ${stats.pnl}
    Avg Edge at Entry: {stats.avg_edge}%
    
    By Bot:
    {format_bot_stats(stats.by_bot)}
    
    By Data Source:
    {format_source_stats(stats.by_source)}
    
    Losing trades with edge > 10%:
    {format_trades(stats.high_edge_losses)}
    
    Questions:
    1. What patterns do you see in our losing trades?
    2. Should we adjust any edge thresholds?
    3. Which data sources are performing best/worst?
    4. Any new strategies we should test?
    5. What parameter changes do you recommend?
    """
    
    analysis = await claude_sonnet(prompt)
    
    # Auto-apply safe recommendations
    for rec in analysis.parameter_changes:
        if rec.change_pct < 20:  # Only auto-apply small changes
            update_strategy_param(rec.bot, rec.param, rec.new_value, rec.reason)
    
    # Send digest
    send_telegram(f"📊 Weekly Review\n{analysis.summary}")
    send_email("Weekly PolyEdge Report", analysis.full_report)
```

### Monthly Deep Dive (Cron, 1st of month)

```python
async def monthly_deep_dive():
    """Full strategy retrospective with Claude Opus."""
    
    trades = get_month_trades()
    
    # Generate comprehensive analysis
    analysis = await claude_opus(f"""
    Full month trading retrospective. {len(trades)} trades.
    
    {format_full_trade_log(trades)}
    
    Analyze:
    1. Overall strategy health — are we improving or degrading?
    2. Edge sustainability — is competition increasing?
    3. New category opportunities — should we add/remove bots?
    4. Risk management — any close calls or systemic risks?
    5. Optimal bankroll allocation across bots
    6. 3 concrete improvements for next month
    """)
    
    # Save to knowledge base
    save_monthly_report(analysis)
```

---

## Build Timeline (Combined)

| Week | SportsBot | WeatherBot | Shared Backend |
|------|-----------|-----------|---------------|
| **W1** | Odds scraper (Pinnacle, DK, Betfair) + de-vig engine | METAR/TAF poller for 50 cities | DB schema + Trade ledger + Signal bus |
| **W2** | News engine (Twitter, ESPN) + signal engine | Claude scanner + probability engine | Risk Manager + Execution engine |
| **W3** | Paper trading (1 week) | Paper trading (1 week) | Dashboard v1 + Telegram alerts |
| **W4** | Go live ($500) | Go live ($500) | Learning engine + daily analysis |
| **W5-6** | Scale to $2K + expand sports | Scale to $2K + expand cities | Weekly review cron + auto-tune |
| **W7-8** | Add injury news alpha | Add PIREP data | Monthly deep dive + A/B testing |

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Language** | Python 3.11+ | Best Polymarket SDK, ML libs, async |
| **Framework** | FastAPI | Async, fast, WebSocket support |
| **Database** | PostgreSQL | Our existing DB, JSON support |
| **Queue** | Redis (or in-memory) | Signal bus, rate limiting |
| **Dashboard** | React + Vite | Consistent with our other projects |
| **Real-time** | WebSocket | Live P&L, position updates |
| **Alerts** | Telegram Bot API | Instant mobile notifications |
| **Hosting** | Our VPS (187.77.189.126) | Already running, free |
| **Wallet** | ethers.js + py-clob-client | Polygon/USDC execution |
| **AI** | Claude Haiku (scan) + Sonnet (review) | Signal parsing + strategy |

---

## Starting Capital Allocation

| Bot | Initial Allocation | Rationale |
|-----|-------------------|-----------|
| SportsBot | $1,500 (60%) | Highest edge confidence, 0% fees |
| WeatherBot | $750 (30%) | Proven by ColdMath, but we're new |
| Reserve | $250 (10%) | Emergency buffer, gas fees |
| **Total** | **$2,500** | |

Rebalance monthly based on bot-specific win rates.

---

## Success Criteria

### Month 1 (Validation)
- [ ] Both bots running 24/7 without crashes
- [ ] 100+ paper trades completed
- [ ] 50+ live trades completed
- [ ] Win rate > 55% across both bots
- [ ] No circuit breaker triggered more than once
- [ ] Daily P&L tracking working

### Month 3 (Scaling)
- [ ] $5K+ total bankroll
- [ ] 200+ trades/month
- [ ] Win rate > 58%
- [ ] Learning engine auto-tuned at least 3 parameters
- [ ] 3rd bot (CryptoBot or MacroBot) in paper trading

### Month 6 (Maturity)
- [ ] $20K+ bankroll
- [ ] 4+ bots active
- [ ] Win rate stable at 60%+
- [ ] Fully automated: no manual intervention needed
- [ ] Monthly Claude strategy review showing improvement trend

---

*Powered by Claude + OpenClaw + Actual Intelligence*
