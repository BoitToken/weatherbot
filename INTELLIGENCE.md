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

## Key Files

- `src/execution/settlement.py` — Trade settlement service
- `src/execution/paper_trader.py` — Paper trade execution
- `src/sports/cross_odds_engine.py` — Multi-book price comparison
- `src/sports/sports_signal_loop.py` — Signal generation
- `src/learning/improvement.py` — Learning engine
- `src/alerts/subscriber_bot.py` — Telegram alerts
