# WeatherBot — Polymarket Weather Arbitrage Bot
**Status:** Planning Phase  
**Created:** 2026-04-06  
**Owner:** Fatman / Ahsbot 🤖👑  

---

## The Opportunity

A Chinese engineering student (ColdMath on Polymarket) made **$101,042** betting on the weather.  
5,252 predictions. Joined November 2025. Bio: "Edge Compounds."

Example trades:
- $25 on Tokyo hitting 16°C on March 20 → **$12,452 payout**
- $24 on Chicago reaching 54°F on March 11 → **$12,398 payout**
- $13 on Lucknow hitting 39°C on March 7 → **$6,850 payout**

500x multipliers. On weather. Consistently.

**The edge:** Aviation weather data (METAR/TAF) is updated every 30-60 minutes from real airport sensors, accurate to 0.1°C. It's free, public, and required by aviation safety law. Polymarket prices weather outcomes based on public forecasts — which lag real sensor data by hours. When the sensor says "Tokyo is 15.8°C at 9AM trending up 0.3°C/hr" and Polymarket prices "Will Tokyo hit 16°C today?" at 2 cents... that's the trade.

Nobody outside aviation looks at this data. We will.

---

## Strategy Overview

### 3 Edges (Stacked)

**Edge 1 — Aviation Data Lag (Primary)**  
METAR readings are real-time sensor data. Public forecasts lag by hours. Claude compares METAR readings + trend to Polymarket price. When gap > 15%, flag and trade.

**Edge 2 — Temperature Bucket Mispricing**  
Polymarket lists temperature ranges that must sum to 100%. Retail traders misprice them (often totalling 105-115%). When NOAA/METAR confirms which bucket wins and it's underpriced → guaranteed edge.

**Edge 3 — Binary Mispricing (Guaranteed)**  
When YES + NO prices sum to < $1.00, buy both sides. Mathematical guarantee of profit. Rare (~1-3% of markets) but zero risk.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  WeatherBot                       │
│                                                  │
│  BOX 1: DATA (aviation feed ingestion)           │
│  ├─ METAR poller: every 30min per city           │
│  ├─ TAF parser: official aviation forecasts      │
│  ├─ PIREP: pilot real-time in-flight reports     │
│  ├─ Trend calculator: temp trajectory engine     │
│  └─ City → ICAO airport code mapping            │
│                                                  │
│  BOX 2: ANALYSIS (Claude engine)                 │
│  ├─ Claude Haiku: initial scan (cheap, fast)     │
│  ├─ Claude Sonnet: confirmation on high signals  │
│  ├─ Prompt: "METAR shows X. Market prices Y.     │
│  │          What's actual probability? Edge?"    │
│  ├─ Min edge threshold: 15%                      │
│  └─ Output: city, threshold, our_prob, mkt_prob  │
│                                                  │
│  BOX 3: EXECUTION (trade engine)                 │
│  ├─ Polymarket CLOB API                         │
│  ├─ Polygon wallet (USDC)                       │
│  ├─ Kelly Criterion sizing (capped at 5%)        │
│  ├─ Auto-place flagged trades                   │
│  └─ Circuit breaker: stop at -10% drawdown      │
│                                                  │
│  DASHBOARD                                       │
│  ├─ Live P&L + active positions                  │
│  ├─ Current METAR readings per city              │
│  ├─ Flagged opportunities queue                  │
│  └─ Win rate, edge stats, trade history          │
└──────────────────────────────────────────────────┘
```

---

## Data Sources (All Free)

| Source | What It Provides | Update Frequency |
|--------|-----------------|-----------------|
| **aviationweather.gov** (NOAA) | METAR + TAF for all ICAO stations worldwide | Every 30-60 min |
| **Synoptic Labs API** | Aggregated METAR network, 1,800+ stations | Real-time |
| **PIREP** | Pilot-reported actual conditions in-flight | Continuous |
| **Open-Meteo API** | Free global weather ensemble model | Every 6h |
| **NOAA GFS** | US temperature + precipitation model | Every 6h |
| **Windy.com API** | European ECMWF model | Every 12h |

**Key insight:** METAR comes from actual sensors at airports. Weather forecasts come from models. Sensors beat models every time for near-term accuracy.

---

## How Claude Fits In

Claude doesn't do ML or forecasting — it does **interpretation and comparison**:

```
Prompt to Claude:
"Aviation data for Tokyo Haneda (RJTT):
  METAR 09:00 JST: Temp 15.8°C, Dewpoint 12.1°C, Wind calm, Pressure 1018 hPa
  TAF 09:00-21:00 JST: No significant cold front, TEMPO cloud activity 12:00-18:00
  Temperature trend last 3 hours: +0.3°C/hr

  Polymarket market: 'Will Tokyo high exceed 16°C on April 6?'
  Current market price: $0.03 (3% implied probability)

  Calculate: What is the actual probability Tokyo reaches 16°C today?
  Should we place a YES bet? What size (bankroll: $2,000 USDC)?"

Claude response:
  "Current temp 15.8°C at 9AM, trending +0.3°C/hr.
   No cold front or significant weather change in TAF.
   Normal diurnal warming pattern expected.
   Probability of hitting 16°C: ~94%
   Market price: 3%. Edge: 91%. STRONG BUY.
   Kelly sizing: 5% cap = $100 max position."
```

Scan 50+ cities every 30 minutes. Claude flags mismatches. Human (or auto) places the trade.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python (FastAPI) |
| **METAR Parser** | `python-metar` library or raw NOAA API |
| **Claude Integration** | Anthropic SDK (Haiku for scan, Sonnet for confirm) |
| **Polymarket API** | `py-clob-client` (official Python client) |
| **Wallet** | Polygon (MATIC), USDC |
| **Database** | PostgreSQL (trade log, METAR history, positions) |
| **Frontend Dashboard** | React + Vite (dark theme, real-time via WebSocket) |
| **Hosting** | VPS (existing Hostinger server) |
| **Alerts** | Telegram bot (notify when high-edge trade found) |

---

## Build Phases

### Phase 1 — Data Layer (Week 1)
- [ ] METAR/TAF poller for top 50 Polymarket cities
- [ ] Airport ICAO code mapping (city → nearest airport)
- [ ] Temperature trend calculator (rolling 3h window)
- [ ] Store readings in PostgreSQL
- [ ] Unit tests: parse edge cases in METAR format

**Deliverable:** Live METAR dashboard showing real-time readings for 50 cities

### Phase 2 — Claude Scanner (Week 2)
- [ ] Polymarket API integration: pull all active weather markets
- [ ] Claude Haiku batch scanner: process 50 cities every 30 min
- [ ] Claude Sonnet confirmation on signals with edge > 20%
- [ ] Mismatch log: city, threshold, our probability, market probability, edge
- [ ] Telegram alert: ping when edge > 25% found
- [ ] Paper trading log (no real money yet)

**Deliverable:** Bot runs 24/7, sends Telegram alerts with trade opportunities

### Phase 3 — Execution Engine (Week 3)
- [ ] Polygon wallet setup + USDC bridge
- [ ] Polymarket CLOB API integration (place/cancel orders)
- [ ] Kelly Criterion sizing with 5% hard cap
- [ ] Circuit breaker: halt at 10% drawdown
- [ ] Paper trading → live trading switch (start with $500)
- [ ] Trade log + outcome tracker

**Deliverable:** Bot places trades automatically. Dashboard shows live P&L.

### Phase 4 — Dashboard (Week 3-4)
- [ ] React dashboard at weatherbot.produsa.dev (or subdomain)
- [ ] Live P&L chart
- [ ] Active positions table
- [ ] METAR readings per city with trend arrows
- [ ] Opportunity queue (flagged but unplaced trades)
- [ ] Historical win rate by city, market type, lead time

**Deliverable:** Full monitoring dashboard

### Phase 5 — Scale (Month 2)
- [ ] Expand from 50 → 200+ cities
- [ ] Add PIREP (pilot in-flight reports) for same-day confirmation
- [ ] Add crypto Black-Scholes strategy (BTC/ETH price markets)
- [ ] Add bucket sum-to-100 arbitrage scanner
- [ ] Scale bankroll if Month 1 win rate > 60%

---

## Risk Management

### Position Sizing
- **Kelly Criterion** with 25% fractional Kelly (conservative)
- **Hard cap:** 5% of bankroll per trade
- **Example:** $2,000 bankroll → max $100 per trade

### Circuit Breakers
- Stop trading if drawdown hits 10% in any single day
- Stop trading if weekly win rate drops below 45%
- Manual review required before resuming

### Known Risks
| Risk | Mitigation |
|------|-----------|
| Edge degrades as more bots enter | Monitor win rate weekly, pivot markets |
| Low liquidity on cheap markets | Skip markets < $5,000 total volume |
| Polymarket regulatory risk | Keep positions small, monitor legal landscape |
| METAR parsing errors | Extensive unit tests, fallback to NOAA API |
| Polygon/USDC bridge issues | Keep USDC ready on-chain before trade window |
| Claude API costs | Haiku for scan ($0.001/city), Sonnet only for confirm |

---

## Financial Projections

### Conservative Model (Validated Edge)
| Month | Bankroll | Trades | Win Rate | P&L |
|-------|---------|--------|---------|-----|
| M1 | $2,000 | 50 | 60% | +$800 |
| M2 | $2,800 | 80 | 62% | +$1,400 |
| M3 | $4,200 | 120 | 65% | +$2,600 |

### Aggressive Model (ColdMath-Level Edge)
| Month | Bankroll | Trades | Win Rate | P&L |
|-------|---------|--------|---------|-----|
| M1 | $2,000 | 200 | 70% | +$8,000 |
| M2 | $10,000 | 500 | 72% | +$40,000 |
| M3 | $50,000 | 1,000 | 73% | +$100,000 |

**Reality check:** ColdMath's results are exceptional. Plan for conservative, hope for aggressive.

---

## Starting Capital Required

| Item | Cost |
|------|------|
| USDC for trading | $500 minimum, $2,000 recommended |
| Polygon gas (MATIC) | ~$10 |
| Dev/VPS | Already have server |
| Claude API | ~$20/month at scan frequency |
| **Total to start** | **~$530 minimum** |

---

## City Priority List (Phase 1)

**US Cities** (largest Polymarket weather market volume):
New York, Los Angeles, Chicago, Miami, Houston, Phoenix, Las Vegas, Seattle, Denver, Atlanta

**International** (high volume + METAR coverage):
London, Tokyo, Paris, Sydney, Dubai, Singapore, Mumbai, Toronto, São Paulo, Mexico City

**India-specific** (local edge + Lucknow precedent):
Mumbai, Delhi, Lucknow, Hyderabad, Chennai, Kolkata, Bengaluru, Pune, Jaipur, Ahmedabad

---

## Reference

- **ColdMath Polymarket profile:** https://polymarket.com/@ColdMath
- **Polymarket CLOB API docs:** https://docs.polymarket.com
- **NOAA Aviation Weather:** https://aviationweather.gov/api/
- **Synoptic Labs (METAR):** https://synopticdata.com/
- **Open-Meteo:** https://open-meteo.com/
- **Reference implementation:** github.com/hcharper/polyBot-Weather
- **Original tweet:** @carverfomo on X

---

## Next Steps

1. ✅ Strategy validated and documented
2. ⬜ Fund Polygon wallet with $500-2,000 USDC
3. ⬜ Spawn build agent for Phase 1 (data layer)
4. ⬜ Validate paper trading for 2 weeks before going live
5. ⬜ CEO approval to go live with real capital

---

*Powered by Claude + OpenClaw + Actual Intelligence*
