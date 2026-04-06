# Sports Intelligence Strategy — Polymarket Trading
**Version:** 1.0 (CEO-Approved 2026-04-06)
**Status:** BUILD PLAN — Awaiting implementation
**Parent System:** WeatherBot (shared infrastructure)

---

## MARKET LANDSCAPE (Live Data — April 2026)

| Category | Active Markets | Total Volume | Total Liquidity |
|----------|---------------|-------------|-----------------|
| All Sports | 424 | $3.2B | $224M |
| NHL (Stanley Cup, Draft) | 30+ | $120M+ | $10M+ |
| NBA (Finals, MVP, Draft) | 50+ | $500M+ | $40M+ |
| Soccer (La Liga, UCL, World Cup) | 60+ | $400M+ | $30M+ |
| FIFA World Cup 2026 | 40+ | $800M+ | $60M+ |
| NFL (2027 season futures) | 20+ | $50M+ | $5M+ |
| MLB (World Series) | 20+ | $100M+ | $8M+ |

**Key insight:** Unlike weather (0 active markets), sports has 424+ active markets with $224M in liquidity RIGHT NOW. This is immediately tradable.

---

## THE 4 SPORTS EDGES (Priority Order)

### Edge 1: Cross-Platform Odds Arbitrage (Primary — Lowest Risk)
**What:** Compare Polymarket prices vs DraftKings, FanDuel, Bet365, Pinnacle odds. When Polymarket is mispriced vs the sharp sportsbook line → trade.

**Why it works:** Sportsbooks employ armies of quants and have decades of data. Their lines are extremely sharp. Polymarket is set by retail bettors who often misprice. When Polymarket implied probability diverges >5% from Pinnacle (sharpest book) → edge exists.

**Example:**
```
Pinnacle: Lakers win NBA Finals → 12% implied probability
Polymarket: Lakers win NBA Finals → 7¢ (7% implied)
Edge: 5% → BUY YES at 7¢ (expected value positive)
```

**Data source:** The Odds API (free tier: 500 req/month, covers NFL/NBA/MLB/NHL/Soccer)
**Scan frequency:** Every 5 minutes
**Min edge:** 5% implied probability difference
**Position size:** $5-25 per trade (Kelly-sized)

### Edge 2: Logical/Correlation Arbitrage (High Conviction)
**What:** Find mathematical impossibilities between related markets.

**Examples on Polymarket RIGHT NOW:**
- "Will Colorado Avalanche win 2026 Stanley Cup?" at X%
- "Will an NHL Western Conference team win?" must be ≥ X%
- If individual team probabilities in a group sum to >100% → overpriced

**How to detect:**
```python
# For mutually exclusive markets (e.g., "Who wins the Stanley Cup?")
teams = get_all_team_markets("2026 NHL Stanley Cup")
total_implied = sum(team.yes_price for team in teams)
if total_implied > 1.05:  # >105% sum = guaranteed arb
    # Find most overpriced, sell it
    # Or buy cheapest, total should be 100%
```

**Data source:** Polymarket CLOB only (no external needed)
**Scan frequency:** Every 2 minutes
**Risk:** Zero (mathematical certainty)

### Edge 3: Live Event Momentum (Highest Returns, Highest Risk)
**What:** During live games, Polymarket is SLOW to reprice. When a goal is scored / key player injured → price should move but takes 30-120 seconds.

**Example:**
```
Pre-game: Arsenal win Champions League quarter-final → 62¢
Minute 75: Arsenal scores 2-1 → actual probability now ~85%
Polymarket: Still showing 68¢ (took 2 min to reprice)
Edge: Buy at 68¢, true value 85¢ → 17¢ edge
```

**Data source:** Live scores API (free: ESPN API, football-data.org, API-Football)
**Scan frequency:** Every 30 seconds during live events
**Position size:** $10-50 (time-sensitive, larger because higher conviction)

### Edge 4: Futures Value + Statistical Models (Long-Term Alpha)
**What:** Use advanced stats (ELO, SPI, xG, WAR, PER) to calculate "true" probability, compare to Polymarket price.

**Example:**
```
FiveThirtyEight ELO model: Celtics win 2026 NBA Finals → 22%
Polymarket: Celtics → 15¢
Edge: 7% → BUY
```

**Data sources:** 
- Basketball: basketball-reference.com, NBA API
- Soccer: FBref, Understat (xG models)
- Baseball: FanGraphs, Baseball-Reference (WAR)
- Hockey: Natural Stat Trick, MoneyPuck
**Position size:** $10-25 (longer hold, diversified)

---

## ARCHITECTURE: Segregated Intelligence

```
┌─────────────────────────────────────────────────┐
│              POLYEDGE BOT (shared)               │
│                                                  │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │   WEATHER     │    │      SPORTS           │   │
│  │ INTELLIGENCE  │    │   INTELLIGENCE        │   │
│  │              │    │                       │   │
│  │ • NOAA GFS   │    │ • Odds API (books)    │   │
│  │ • Open-Meteo  │    │ • Live Scores API     │   │
│  │ • METAR       │    │ • ESPN/Stats APIs     │   │
│  │ • Historical  │    │ • Polymarket Scanner  │   │
│  │              │    │ • Correlation Engine  │   │
│  │ Strategy A    │    │                       │   │
│  │ Strategy B    │    │ Edge 1: Cross-Odds    │   │
│  │              │    │ Edge 2: Logical Arb   │   │
│  │              │    │ Edge 3: Live Momentum │   │
│  │              │    │ Edge 4: Stats Models  │   │
│  └──────┬───────┘    └──────────┬────────────┘   │
│         │                       │                │
│         └───────────┬───────────┘                │
│                     │                            │
│         ┌───────────▼──────────┐                 │
│         │   SHARED RISK MGR    │                 │
│         │  • Max positions     │                 │
│         │  • Daily loss limit  │                 │
│         │  • Kelly sizing      │                 │
│         │  • Execution engine  │                 │
│         └───────────┬──────────┘                 │
│                     │                            │
│         ┌───────────▼──────────┐                 │
│         │    TRADE EXECUTOR    │                 │
│         │  (paper / live)      │                 │
│         └──────────────────────┘                 │
└─────────────────────────────────────────────────┘
```

---

## WHAT NEEDS TO BE BUILT

### New Backend Files (src/sports/)

| File | Purpose | Priority |
|------|---------|----------|
| `src/sports/__init__.py` | Module init | P0 |
| `src/sports/odds_fetcher.py` | The Odds API integration — fetch DraftKings/FanDuel/Pinnacle lines | P0 |
| `src/sports/polymarket_sports_scanner.py` | Scan Polymarket for sports markets, categorize, parse | P0 |
| `src/sports/cross_odds_engine.py` | Compare sportsbook odds vs Polymarket → find edges | P0 |
| `src/sports/correlation_engine.py` | Detect logical arbitrage (sum >100%, subset violations) | P0 |
| `src/sports/live_scores.py` | Live score feeds during games (ESPN API / football-data.org) | P1 |
| `src/sports/momentum_engine.py` | Live event momentum signals during games | P1 |
| `src/sports/stats_models.py` | ELO/SPI/xG statistical probability models | P2 |
| `src/sports/sports_signal_loop.py` | Main sports scanning loop (orchestrates all 4 edges) | P0 |

### New API Endpoints (src/main.py)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/sports/markets` | All active sports markets from Polymarket (categorized) |
| `GET /api/sports/odds/{sport}` | Sportsbook odds for a sport (NBA/NHL/MLB/Soccer) |
| `GET /api/sports/signals` | Sports-generated signals (cross-odds, arb, momentum) |
| `GET /api/sports/arbitrage` | Current logical arbitrage opportunities |
| `GET /api/sports/comparison` | Polymarket vs sportsbook odds comparison table |
| `GET /api/sports/live` | Live games + real-time odds movement |
| `GET /api/sports/performance` | Sports strategy performance metrics |

### New DB Tables

```sql
CREATE TABLE sports_markets (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(255) UNIQUE,
    question TEXT,
    sport VARCHAR(50),          -- nba, nhl, mlb, soccer, nfl, etc
    league VARCHAR(100),        -- NBA, Premier League, La Liga, etc
    event_type VARCHAR(50),     -- championship, match, mvp, draft, etc
    team_a VARCHAR(200),
    team_b VARCHAR(200),
    yes_price NUMERIC,
    no_price NUMERIC,
    volume_usd NUMERIC,
    liquidity_usd NUMERIC,
    resolution_date TIMESTAMPTZ,
    group_id VARCHAR(255),      -- links related markets (e.g., all Stanley Cup teams)
    metadata JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE sportsbook_odds (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50),
    event_name TEXT,
    bookmaker VARCHAR(100),     -- draftkings, fanduel, pinnacle, bet365
    market_type VARCHAR(50),    -- moneyline, spread, total, futures
    outcome VARCHAR(200),
    odds_decimal NUMERIC,
    implied_probability NUMERIC,
    polymarket_id VARCHAR(255), -- linked Polymarket market if matched
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sports_signals (
    id SERIAL PRIMARY KEY,
    edge_type VARCHAR(50),      -- cross_odds, logical_arb, live_momentum, stats_model
    sport VARCHAR(50),
    market_id VARCHAR(255),
    market_title TEXT,
    polymarket_price NUMERIC,
    fair_value NUMERIC,         -- our calculated fair value
    edge_pct NUMERIC,
    confidence VARCHAR(20),
    signal VARCHAR(20),         -- BUY, SELL, SKIP
    reasoning TEXT,
    data_sources JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE live_events (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50),
    event_id VARCHAR(255),
    home_team VARCHAR(200),
    away_team VARCHAR(200),
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    status VARCHAR(50),         -- scheduled, live, finished
    minute INTEGER,
    period VARCHAR(20),
    key_events JSONB,           -- goals, injuries, red cards, etc
    linked_market_ids TEXT[],
    last_updated TIMESTAMPTZ DEFAULT NOW()
);
```

### Dashboard Updates (dashboard/src/pages/)

| Component | Purpose |
|-----------|---------|
| `SportsIntelligence.jsx` | Main sports dashboard — odds comparison, signals, arb opportunities |
| `LiveEvents.jsx` | Real-time game tracker with momentum signals |
| Sidebar update | Add "Sports" section with sub-pages |

### External API Keys Needed

| Service | Free Tier | Covers | Action |
|---------|-----------|--------|--------|
| **The Odds API** | 500 req/month | NFL, NBA, MLB, NHL, Soccer odds from 20+ books | Sign up at the-odds-api.com |
| **football-data.org** | 10 req/min | Premier League, Champions League, La Liga, etc | Free API key |
| **ESPN API** | Unofficial/free | Live scores all sports | No key needed |
| **NBA API** | Free | NBA stats, box scores | No key needed (nba_api python) |
| **FBref/Understat** | Scrape | xG models, advanced soccer stats | No key |

**Only The Odds API requires signup.** Everything else is free/no-key.

---

## BUILD PHASES

### Phase 1: Core Sports Scanner + Cross-Odds (THIS SPRINT)
1. Create `src/sports/` module structure
2. Build Polymarket sports scanner (categorize 424+ markets)
3. Integrate The Odds API (cross-reference sportsbook lines)
4. Build cross-odds comparison engine (find >5% edges)
5. Build logical/correlation arbitrage detector
6. Add 7 API endpoints
7. Create DB tables
8. Build SportsIntelligence.jsx dashboard page

### Phase 2: Live Events + Momentum (NEXT SPRINT)
9. Live scores integration (ESPN + football-data.org)
10. Momentum engine for in-play signals
11. LiveEvents.jsx dashboard

### Phase 3: Statistical Models (AFTER PROVING EDGE)
12. ELO/SPI models for major leagues
13. xG models for soccer
14. WAR-based models for MLB
15. Backtesting framework

---

## RISK MANAGEMENT (Sports-Specific)

```yaml
max_sports_exposure: 500        # Max $500 total in sports positions
max_single_sport: 200           # Max $200 in any one sport
max_single_position: 25         # Max $25 per trade
kelly_fraction: 0.20            # 20% Kelly (conservative)
min_edge_cross_odds: 5          # Min 5% edge for cross-odds trades
min_edge_logical_arb: 2         # Min 2% edge for logical arb (risk-free)
min_edge_momentum: 10           # Min 10% edge for momentum (higher risk)
max_correlation_per_event: 3    # Max 3 related positions per event
circuit_breaker_daily: 50       # Halt at $50 daily sports loss
```

---

## CEO DECISION NEEDED

1. **The Odds API key** — free tier (500 req/month) or paid ($20/mo for 10K req)? Free is enough to start.
2. **Priority sport** — Focus on one first? Recommendation: **NHL Stanley Cup** (playoffs starting soon, high volume, well-defined market structure) or **Soccer** (Champions League QF live now, highest edge opportunity with live momentum)
3. **Approve Phase 1 build?**
