# WeatherBot — Dual Strategy Trading System
**Version:** 2.0 (Dual Strategy — CEO Approved 2026-04-06)
**Status:** ACTIVE
**Last Updated:** 2026-04-06

## Rule: This document is updated ONLY after CEO approval. Bot proposes → CEO approves → strategy updates.

---

## DUAL STRATEGY ARCHITECTURE

WeatherBot runs TWO strategies in parallel. Each generates independent signals. Both feed into the same risk manager and trade executor.

### Strategy A: "Forecast Edge" (Twitter/carverfomo strategy)
**Philosophy:** Dead simple. Forecast says X, market says Y, buy X.
**Edge source:** NOAA GFS forecast accuracy (85-90% at 1-2 day) vs casual bettor mispricing
**Signal:** `if market_price < entry_threshold AND forecast_probability > 0.70 → BUY`

### Strategy B: "Intelligence Layer" (Our 8-gate strategy)  
**Philosophy:** Multi-source convergence with safety gates
**Edge source:** Data convergence (METAR + forecast + historical + multi-station) finding deeper mispricings
**Signal:** Must pass all 8 gates before trade execution

### Parallel Operation
- Both strategies scan independently on their own intervals
- Strategy A: every 2 minutes (speed is edge)
- Strategy B: every 5 minutes (depth is edge)
- Shared risk manager prevents conflicts (same market, same direction = ONE position, larger size)
- Trade log tags each trade with strategy source (A or B) for performance comparison
- Weekly review compares win rates, edge, ROI per strategy
- Whichever has higher Sharpe ratio over 30-day window gets increased allocation

---

## STRATEGY A: Forecast Edge (Simple)

### Core Logic
```python
# Every 2 minutes:
for city in TARGET_CITIES:
    forecast = get_noaa_forecast(city)  # Primary: NOAA GFS
    if not forecast:
        forecast = get_openmeteo_forecast(city)  # Fallback
    
    # Get all temperature bucket markets for this city
    markets = get_temp_bucket_markets(city, tomorrow)
    
    # Find the bucket containing the forecasted temperature
    target_bucket = find_bucket(markets, forecast.high_temp)
    
    if target_bucket.price <= ENTRY_THRESHOLD:  # ≤ 15¢
        # Forecast says 85%+ but market says ≤15% → BUY
        signal = BUY(target_bucket, size=position_size)
    
    # Check held positions for exit
    for position in open_positions:
        if position.current_price >= EXIT_THRESHOLD:  # ≥ 45¢
            signal = SELL(position)  # Take profit, don't wait for resolution
```

### Parameters
```yaml
entry_threshold_cents: 15      # Buy at ≤ 15¢ (implied prob ≤ 15%)
exit_threshold_cents: 45       # Sell at ≥ 45¢ (don't wait for resolution)
scan_interval_seconds: 120     # Every 2 minutes
position_size_usd: 2.00        # Start small, scale after proof
max_trades_per_scan: 5         # Max 5 trades per scan cycle
forecast_confidence_min: 0.70  # Only trade when forecast confidence > 70%
```

### Data Sources (Priority Order)
1. **NOAA GFS** (primary) — api.weather.gov — FREE, no key, 85-90% accurate at 1-2 day
2. **Open-Meteo** (secondary) — open-meteo.com — FREE, global coverage, European ECMWF model
3. **METAR** (validation) — aviationweather.gov — real-time airport sensors, confirms current conditions

### Target Markets
Temperature bucket markets ONLY. Format: "What will the high temperature be in [city] on [date]?"
- Buckets: 5°F ranges (e.g., "40-45°F", "45-50°F")
- Resolution: actual recorded high temperature at reference station

### Target Cities (must have active Polymarket temp bucket markets)
```yaml
primary:
  - NYC:     [KJFK, KLGA, KEWR]
  - London:  [EGLL, EGKK]
  - Chicago: [KORD, KMDW]
  - Seoul:   [RKSI]
secondary:
  - Atlanta:  [KATL]
  - Dallas:   [KDFW]
  - Miami:    [KMIA]
  - Seattle:  [KSEA]
```

---

## STRATEGY B: Intelligence Layer (8-Gate)

### Gate 1: Data Convergence (3 sources must agree)
```
Source A: METAR (airport sensor — actual current temperature)
Source B: Open-Meteo / NOAA (forecast model — projected high/low)
Source C: Historical baseline (what this city did on this date, 10yr average)

Rule: If 2/3 sources agree on direction → proceed
Rule: If all 3 disagree → SKIP (low confidence)
Rule: If METAR says threshold already hit → highest confidence (99%+)
```

### Gate 2: Multi-Station Validation
```
NYC: KJFK, KLGA, KEWR — all 3 must agree within ±1°C
London: EGLL, EGKK — must agree within ±1°C
Single-station cities: auto-pass
```

### Gate 3: Bucket Coherence Check
```
Sum all bucket prices for same city/date
If sum > 105% → overpriced buckets exist (opportunity)
If sum < 95% → underpriced buckets exist (opportunity)
```

### Gate 4: Binary Arbitrage Check
```
If YES + NO < $0.98 → BUY BOTH (guaranteed profit, bypass all other gates)
Max $100 per binary arb
```

### Gate 5: Liquidity & Execution
```
Spread < 3¢ → good, full size
Spread 3-8¢ → acceptable, half size
Spread > 8¢ → SKIP
```

### Gate 6: Time Window
```
6-8 AM local: Overnight forecast not yet priced in (highest edge)
After METAR refresh: 30-min window
2-4 PM local: High temp likely recorded
Don't enter if < 2 hours to resolution (unless binary arb)
```

### Gate 7: Risk Manager
```
Kelly fraction: 0.25 (quarter Kelly)
Circuit breaker: halt at 10% daily loss
Max 3 trades per city per day
Max 5% of bankroll per position
```

### Gate 8: Claude AI Confirmation
```
Claude reviews signal + context
TRADE + HIGH → auto-execute
TRADE + MEDIUM → alert CEO
SKIP → we skip (even if numbers look good)
```

### Strategy B Parameters
```yaml
min_edge_auto_trade: 0.25      # 25% edge → auto-execute
min_edge_alert: 0.15           # 15% edge → alert only
max_position_usd: 50           # Max $50 per trade
scan_interval_seconds: 300     # Every 5 minutes
confidence_sources_required: 2  # 2 of 3 data sources must agree
```

---

## SHARED COMPONENTS

### Risk Manager (applies to BOTH strategies)
```yaml
max_daily_loss_pct: 10         # Halt all trading at 10% daily loss
max_open_positions: 20         # Never hold > 20 positions
max_exposure_per_city: 100     # Max $100 exposure per city
no_duplicate_positions: true   # If Strategy A and B signal same market → merge into one position
```

### Trade Executor
```yaml
mode: paper                    # paper | live (requires CEO approval to switch)
exchange: polymarket_clob      # Uses py-clob-client when live
slippage_tolerance: 0.02       # Max 2% slippage on execution
```

### Improvement Loop

#### Daily (Automated)
1. Calculate per-strategy: win rate, avg edge, avg P&L
2. Compare Strategy A vs B: which performed better?
3. Flag if either strategy drops below 55% win rate over 20 trades

#### Weekly (Claude Analysis → CEO Review)
1. Full strategy comparison report
2. Propose parameter adjustments
3. CEO approves/rejects
4. Only approved changes update this document

---

## STRATEGY PERFORMANCE TRACKING

| Metric | Strategy A (Forecast Edge) | Strategy B (8-Gate) |
|--------|---------------------------|---------------------|
| Win Rate Target | 73%+ (matching reference bot) | 65%+ (higher conviction) |
| Avg Edge | 15-25¢ per trade | 25-50¢ per trade |
| Trade Frequency | High (50-100/day) | Low (5-15/day) |
| Risk Profile | Many small bets | Fewer larger bets |
| Scan Interval | 2 min | 5 min |

---

## Strategy Change Log

| Date | Change | Proposed By | CEO Approved | Applied |
|------|--------|-------------|-------------|---------|
| 2026-04-06 | v1.0 Initial strategy | Ahsbot | PENDING | NO |
| 2026-04-06 | v2.0 Dual strategy (Forecast Edge + 8-Gate parallel) | Ahsbot | YES | YES |
| 2026-04-06 | Add NOAA GFS, 2-min scans, 45¢ exit, temp bucket targeting | Ahsbot | YES | IN PROGRESS |
