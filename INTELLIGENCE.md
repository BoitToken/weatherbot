# INTELLIGENCE.md — Trading Bot Philosophy & Priority

**Last Updated:** 2026-04-08 20:23 IST
**Status:** ACTIVE — This document drives all bot development decisions

## Core Mandate (CEO Directive)

**The bot auto-executes ALL qualifying trades. No limit on volume.**
**The ONLY priority of post-trade intelligence is: make the qualifying criteria more accurate.**

## Philosophy

1. **Volume is unlimited** — Pull as many trades as pass the filter. 100/day is better than 5/day if accuracy holds.
2. **Accuracy is everything** — Every resolved trade feeds back into qualifying criteria. Win rate > 55% = keep going. Win rate < 50% = strategy gets disabled.
3. **Paper first, live second** — No strategy goes live until it's paper-tested with statistical significance (min 30 trades, win rate > 55%, positive expected value).
4. **No human in the loop for paper** — Bot decides, bot executes, bot settles, bot learns.
5. **CEO approval gate for live only** — When a strategy passes paper testing, CEO gets a report + approval request before real money flows.

## Qualifying Criteria (v1 — will evolve via learning engine)

A trade qualifies when ALL of these pass:
- Edge ≥ 7% (sportsbook consensus vs Polymarket price)
- 3+ sportsbooks agree on direction
- Market has ≥ $10K liquidity on Polymarket
- Match starts within 48 hours (no stale lines)
- Strategy has not been disabled by learning engine
- Daily loss circuit breaker not tripped (-$200/day paper, TBD live)

## Strategies (tracked independently)

| Strategy | Description | Status |
|----------|-------------|--------|
| ARBITRAGE | Pure price gap: PM price vs sportsbook consensus | Active |
| MOMENTUM | Live score change → market hasn't adjusted yet | Planned |
| CLV (Closing Line Value) | Bet early when line will move our way | Planned |
| CONTRARIAN | Fade public favorites when books disagree | Planned |

## Learning Loop

After every resolved trade:
1. Log: predicted edge vs actual outcome
2. Was the qualifying criteria correct? (edge > 7% → did we win?)
3. Per-strategy win rate (rolling 30-trade window)
4. Per-sport win rate
5. Edge threshold optimization: if 7% edge wins 60% but 12% edge wins 75%, raise the bar
6. Auto-disable: any strategy with <48% win rate over 30+ trades gets paused
7. Weekly report to CEO via Telegram

## Risk Limits

- **Paper mode:** $25 default position, $50 max per trade, $500 max deployed at once
- **Daily loss limit:** -$200 (circuit breaker — no new trades until next day)
- **Max concurrent positions:** 50
- **No single sport > 40% of deployed capital**

## Path to Live Execution

1. ✅ Paper trading pipeline (Sprint 1)
2. ✅ Auto-settlement + P&L tracking (Sprint 2)
3. ✅ Learning engine with strategy scorecards (Sprint 3)
4. 🔲 Strategy passes paper test (30+ trades, >55% win rate, +EV)
5. 🔲 CEO reviews performance report + approves live
6. 🔲 Polymarket wallet funded + execution keys configured
7. 🔲 Live execution with $100 bankroll test
8. 🔲 Scale based on results

## Data Sources

- **The Odds API** (61418768679376886c592ce0b8cf540f) — 22 sportsbooks, 88 sports
- **ESPN Cricket API** (league 8048) — IPL live scores
- **Polymarket CLOB API** — market prices, order books, resolution
- **Open-Meteo** — weather data (original use case)

## Execution Protocols (Fed to bot at every scan cycle)

### Protocol 1: Internal Arbitrage (RISK-FREE)
**Trigger:** YES + NO < $1.00 on same Polymarket market
**Process:**
1. Scan all active markets for YES + NO < $1.00
2. Calculate raw profit: `(1.0 - combined_cost) / combined_cost * 100`
3. Subtract 2% Polymarket fee on winnings
4. If net profit > 0.5% → EXECUTE (buy both YES and NO)
5. Log: market_id, prices, profit %, stake, timestamp
6. Auto-resolve immediately (profit is guaranteed at entry)
7. Broadcast to all subscribers on Telegram
**Risk:** Near zero. Only risk is Polymarket settlement delay (capital lock-up)
**Priority:** HIGHEST — run every 2 minutes, 24/7

### Protocol 2: Cross-Market Arbitrage (Sportsbook vs Polymarket)
**Trigger:** Sportsbook consensus price differs from Polymarket by > 7% (5% after fees)
**Process:**
1. Fetch odds from 22 sportsbooks via Odds API
2. Calculate consensus implied probability
3. Compare to Polymarket YES price
4. Calculate fee-adjusted edge: `raw_edge - 2%`
5. Require 3+ sportsbooks agreeing on direction
6. Check orderbook depth (if available): depth must be > 2x position size
7. If all pass → EXECUTE paper trade
8. Log: strategy, sport, edge (raw + fee-adjusted), book count, depth info
9. Broadcast HIGH confidence signals to subscribers
**Risk:** Directional — sportsbooks can be wrong. This is why accuracy tracking matters.
**Priority:** HIGH — run every 3 minutes

### Protocol 3: Edge Decay Monitoring
**Trigger:** Open position where current edge < 2% (was higher at entry)
**Process:**
1. For each open trade, fetch current Polymarket price
2. Fetch current sportsbook consensus
3. Calculate current edge vs entry edge
4. If edge < 2% → flag EXIT_EDGE_DECAY
5. If edge < 0% (underwater) → flag EXIT_URGENT
6. Alert admin on Telegram with entry vs current edge
7. In paper mode: informational. In live mode: auto-exit.
**Risk:** Holding a position whose edge has evaporated = gambling, not trading
**Priority:** MEDIUM — check every 5 minutes

### Protocol 4: Line Movement Detection
**Trigger:** Sportsbook odds moved > 3% in last 2 hours, Polymarket hasn't adjusted
**Process:**
1. Compare current sportsbook odds to odds from 2 hours ago
2. If movement > 3% AND Polymarket price hasn't moved proportionally
3. This means smart money moved the sportsbook line but Polymarket is lagging
4. Fee-adjust the edge, check depth, then EXECUTE
5. These are often the highest-conviction trades
**Risk:** Line could move back. But historically, sharp money is right 55-60% of the time.
**Priority:** HIGH — checked during every signal scan

### Protocol 5: Settlement & Learning (Post-Trade)
**Trigger:** Match/event completes
**Process:**
1. Check Odds API + ESPN for completed events (every 5 min)
2. Match completed event to open trades (strict: both teams in title + sport alignment)
3. Calculate P&L: won = shares * (1.0 - entry_price), lost = -size_usd
4. Update trade record (status, pnl_usd, resolved_at)
5. Feed to learning engine:
   a. Was our predicted edge accurate? (edge_at_entry vs actual outcome)
   b. Update per-strategy win rate (rolling 30 trades)
   c. Update per-sport performance
   d. Check if qualifying thresholds need adjustment
   e. Auto-disable strategy if win rate < 48% over 30+ trades
6. Broadcast result to all subscribers
7. Weekly: generate strategy report for CEO
**Priority:** CRITICAL — this is how the bot gets smarter

### Protocol 6: Risk Management (Always Active)
**Rules enforced before every trade:**
- Daily loss circuit breaker: -$200 → no new trades until next day
- Max concurrent positions: 50
- No single sport > 40% of deployed capital
- Position sizing via half-Kelly (min $10, max $50)
- No duplicate trades on same market_id
- For live mode (future): CEO approval gate required

## Key Files

- `src/execution/settlement.py` — Trade settlement service
- `src/execution/paper_trader.py` — Paper trade execution
- `src/sports/cross_odds_engine.py` — Multi-book price comparison
- `src/sports/sports_signal_loop.py` — Signal generation
- `src/learning/improvement.py` — Learning engine
- `src/alerts/subscriber_bot.py` — Telegram alerts
