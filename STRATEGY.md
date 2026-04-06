# WeatherBot — Trading Strategy Document
**Version:** 1.0 (Initial)
**Status:** PENDING CEO APPROVAL for changes
**Last Updated:** 2026-04-06

## Rule: This document is updated ONLY after CEO approval. Bot proposes → CEO approves → strategy updates.

---

## Pre-Trade Intelligence Checklist

Every trade MUST pass ALL gates. If ANY gate fails, trade is BLOCKED.

### Gate 1: Data Convergence (3 sources must agree)
```
Source A: METAR (airport sensor — actual current temperature)
Source B: Open-Meteo (forecast model — projected high/low)
Source C: Historical baseline (what this city did on this date, 10yr average)

Rule: If 2/3 sources agree on direction → proceed
Rule: If all 3 disagree → SKIP (low confidence)
Rule: If METAR says threshold already hit → highest confidence (99%+)
```

### Gate 2: Multi-Station Validation
```
For cities with multiple airports:
  NYC: KJFK, KLGA, KEWR — all 3 must agree within ±1°C
  London: EGLL, EGKK — must agree within ±1°C
  Tokyo: RJTT, RJAA — must agree within ±1°C

Rule: If stations diverge > 2°C → reduce confidence by 30%
Rule: Single-station cities: skip this gate (auto-pass)
```

### Gate 3: Bucket Coherence Check
```
For temperature range markets (e.g., "55-60°F", "60-65°F"):
  Sum all bucket prices for same city/date
  If sum > 105% → overpriced buckets exist (opportunity)
  If sum < 95% → underpriced buckets exist (opportunity)
  
Rule: If our target bucket is overpriced (implied prob > our estimate) → NO BET on that bucket
Rule: If our target bucket is underpriced → BET (edge confirmed by market inefficiency)
```

### Gate 4: Binary Arbitrage Check
```
For any YES/NO market:
  If YES + NO < $0.98 → BUY BOTH (guaranteed profit)
  If YES + NO > $1.02 → market is efficient, need real edge

Rule: Binary arb trades bypass all other gates (risk-free)
Rule: Max $100 per binary arb (liquidity constraint)
```

### Gate 5: Liquidity & Execution
```
Check order book:
  - Bid/ask spread < 3¢ → good liquidity
  - Bid/ask spread 3-8¢ → acceptable, reduce size by 50%
  - Bid/ask spread > 8¢ → SKIP (too expensive to enter/exit)
  
  - Available liquidity at our price > 2x our order size → proceed
  - Available liquidity < our order size → SKIP or reduce size
```

### Gate 6: Time Window
```
Optimal trading windows (local time of the city):
  6-8 AM: Overnight forecast not yet priced in (highest edge)
  After METAR refresh: 30-min window before market catches up
  2-4 PM: High temp likely recorded, market may not reflect yet
  
Rule: Edge decays as resolution time approaches
Rule: Don't enter if < 2 hours to resolution (unless binary arb)
```

### Gate 7: Risk Manager
```
Position limits:
  - Max 5% of bankroll per trade
  - Max 15% total exposure (all open positions)
  - Max 3 trades per city per day
  - Daily loss limit: 10% of bankroll → HALT all trading
  - 5 consecutive losses → reduce size by 50%
  - Quarter Kelly sizing (conservative)

Exit rules:
  - If current_price / entry_price > 3x → consider selling early
  - If edge decays below 5% → sell position
  - If resolution < 1 hour and in profit → hold to resolution
```

### Gate 8: Claude AI Confirmation
```
Only for trades that pass Gates 1-7.
Prompt includes:
  - METAR data + trend
  - Open-Meteo forecast
  - Historical pattern
  - Market price + our probability
  - Any weather alerts/warnings

Claude response required:
  - TRADE / ALERT_ONLY / SKIP
  - Confidence: HIGH / MEDIUM / LOW
  - Any factors the model might miss

Rule: Claude says SKIP → we SKIP (even if numbers look good)
Rule: Claude says TRADE + HIGH confidence → auto-execute
Rule: Claude says TRADE + MEDIUM → alert CEO, wait for approval
```

---

## Improvement Loop Protocol

### Daily (Automated)
1. Calculate: win rate, avg edge, avg P&L, per-station accuracy
2. Compare predicted probability vs actual outcome for every resolved trade
3. If accuracy < 55% over last 20 trades → FLAG for review
4. Store all metrics in station_accuracy + daily summary table

### Weekly (Claude Sonnet Analysis)
1. Run weekly review: "Analyze this week's trades. What patterns emerge? What went wrong?"
2. Identify: which stations are miscalibrated, which time windows worked best, which strategies had best ROI
3. Generate findings report
4. **Send findings to CEO via Telegram/Dashboard**
5. **CEO approves or rejects proposed changes**
6. If approved → update STRATEGY.md + adjust bot parameters

### Monthly (Deep Review)
1. Full strategy audit: is the overall approach working?
2. Compare to baseline (what if we'd just bet randomly on weather?)
3. Propose major strategy changes if needed
4. CEO approval required for any structural changes

---

## Strategy Change Log

| Date | Change | Proposed By | CEO Approved | Applied |
|------|--------|-------------|-------------|---------|
| 2026-04-06 | Initial strategy document | Ahsbot | PENDING | NO |

---

## Current Parameters

```yaml
min_edge_auto_trade: 0.25      # 25% edge → auto-execute
min_edge_alert: 0.15           # 15% edge → alert only
max_position_usd: 50           # Max $50 per trade
max_position_pct: 5            # Max 5% of bankroll
kelly_fraction: 0.25           # Quarter Kelly
circuit_breaker_daily_loss: 10 # Halt at 10% daily loss
max_trades_per_city_day: 3     # Max 3 trades per city per day
min_liquidity_multiple: 2      # Need 2x our size in order book
max_spread_cents: 8            # Skip if spread > 8¢
min_hours_to_resolution: 2     # Don't enter < 2 hours out
confidence_sources_required: 2  # 2 of 3 data sources must agree
```
