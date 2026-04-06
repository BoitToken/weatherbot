# WeatherBot — CEO Spec (Source of Truth)
**Source:** CEO feedback 2026-04-06 17:12 IST
**Status:** In Progress

---

## 1. Polymarket Explorer / Proxy (Dashboard Feature)

| # | Requirement | Status |
|---|------------|--------|
| 1.1 | Full Polymarket proxy accessible from dashboard (bypass India ISP block) | ❌ |
| 1.2 | Browse ALL Polymarket categories (not just weather) | ❌ |
| 1.3 | Live prices, order book depth, volume, price history charts | ❌ |
| 1.4 | Show our bot's positions overlaid on market data | ❌ |
| 1.5 | Search/filter markets by keyword, category, volume | ❌ |
| 1.6 | Dedicated "Explorer" tab in dashboard navigation | ❌ |

## 2. Intelligence Layer (Pre-Trade Checklist)

Every trade MUST pass through ALL checks before execution:

| # | Requirement | Status |
|---|------------|--------|
| 2.1 | METAR current temp + trend (primary signal) | ✅ Built |
| 2.2 | Open-Meteo forecast cross-reference (second opinion) | ❌ |
| 2.3 | Historical temperature patterns (same city/date, last 10 years) | ❌ |
| 2.4 | Multi-station cross-reference (e.g., KJFK vs KLGA vs KEWR for NYC) | ❌ |
| 2.5 | Temperature bucket arbitrage scanner (sum must = 100%, find overpriced) | ❌ |
| 2.6 | Binary arbitrage scanner (YES + NO < $1.00 = free money) | ❌ |
| 2.7 | Order book depth check (enough liquidity to fill?) | ❌ |
| 2.8 | Spread check (wide spread = risky fill) | ❌ |
| 2.9 | Time-of-day optimization (best windows for mispricing) | ❌ |
| 2.10 | Claude AI confirmation (catches edge cases) | ✅ Built |
| 2.11 | Risk manager approval (position limits, circuit breakers) | ✅ Built |
| 2.12 | ALL checks logged with pass/fail before trade executes | ❌ |

## 3. Improvement Loop (Learning Engine)

| # | Requirement | Status |
|---|------------|--------|
| 3.1 | Track every trade outcome: predicted probability vs actual result | ❌ |
| 3.2 | Per-station calibration: accuracy tracking per airport | 🟡 Table exists, not populated |
| 3.3 | Weekly analysis: what went wrong, what patterns emerge | ❌ |
| 3.4 | Strategy findings reported to CEO (Telegram or dashboard) | ❌ |
| 3.5 | CEO approves strategy changes before they're applied | ❌ |
| 3.6 | Strategy document (STRATEGY.md) updated only after CEO approval | ❌ |
| 3.7 | Auto-adjust RMSE/confidence based on historical accuracy | ❌ |
| 3.8 | Pattern detection: heat waves, cold fronts, marine layer | ❌ |
| 3.9 | Exit strategy: auto-sell when edge decays or 3x profit | ❌ |

## 4. Admin Panel / Settings

| # | Requirement | Status |
|---|------------|--------|
| 4.1 | Wallet configuration (address, balance display, never show full private key) | ❌ |
| 4.2 | Trading limits (max per trade, daily max, circuit breaker %) | 🟡 Backend exists, no UI |
| 4.3 | Paper → Live mode toggle | 🟡 Config exists, no UI |
| 4.4 | One-click kill switch to halt all trading | ❌ |
| 4.5 | View wallet balance (USDC + MATIC) | ❌ |

## 5. Fix Scanner (Unblocks Everything)

| # | Requirement | Status |
|---|------------|--------|
| 5.1 | Fix Polymarket Gamma API scanner (tag filtering broken) | ❌ |
| 5.2 | Paginate CLOB API + text-filter for weather keywords | ❌ |
| 5.3 | Match markets to cities/stations correctly | ✅ Built |

---

## Totals
- ✅ Done: 4
- 🟡 Partial: 3
- ❌ Not Done: 25
- **Total: 32 items**

## Build Priority (CEO directed)
1. Polymarket Explorer proxy (1.1–1.6) — CEO needs access from India
2. Intelligence layer (2.1–2.12) — all checks before any trade
3. Improvement loop (3.1–3.9) — learn from mistakes, CEO approves changes
4. Fix scanner (5.1–5.2) — unblocks market data
5. Admin panel (4.1–4.5) — wallet config for live trading
