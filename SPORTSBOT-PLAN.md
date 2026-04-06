# SportsBot — Polymarket Sports Arbitrage Engine
**Status:** Planning Phase  
**Priority:** #1 (Build First)  
**Created:** 2026-04-06  

---

## Why Sports First

1. **0% fees** — Polymarket charges ZERO on sports. Every edge point is pure profit.
2. **Proven at scale** — Swisstony: $3.7M profit, 22K predictions, 5 months. Not theoretical.
3. **Fastest capital cycle** — Games resolve in hours, not days. Money recycles daily.
4. **Strongest data benchmark** — Sportsbook odds represent professional oddsmakers with $B+ at stake. Most reliable "ground truth" on Polymarket.
5. **Multiple edges stack** — odds lag + injury news + line movement = 3 independent alpha sources.

---

## The Three Edges

### Edge 1: Sportsbook Odds Arbitrage (Core Strategy)

Sportsbook odds (DraftKings, Betfair, Pinnacle) are set by professional oddsmakers with sophisticated models. Polymarket is priced by retail traders who guess. When they diverge, the sportsbook is right.

```
DraftKings:  Lakers -200 → 66.7% implied probability
Polymarket:  Lakers @ 61¢ → 61% implied probability
Edge:        5.7% → BUY Lakers on Polymarket

Expected value: For every $100 bet at 61¢, 
  you expect to receive $66.70 back.
  Profit per $100: $5.70 (5.7% edge)
  Annualized over daily trades: massive.
```

**How it works in practice:**
1. Poll DraftKings/Betfair/Pinnacle odds every 60 seconds
2. Convert to implied probability (remove vig)
3. Compare to Polymarket price
4. When gap > 3%: flag. When gap > 5%: auto-trade.

### Edge 2: Line Movement Trading (Speed Edge)

When sportsbooks move their lines (e.g. Lakers from -200 to -300), they've received new information. Polymarket takes **30-60 minutes** to adjust. Bot sees the movement → trades Polymarket instantly.

```
10:00 AM — DraftKings Lakers: -200 (66.7%)
10:15 AM — DraftKings Lakers: -300 (75.0%)  ← LINE MOVED
10:15 AM — Polymarket Lakers: still 62¢      ← HASN'T MOVED
→ BUY at 62¢, true value 75¢, edge 13%

10:45 AM — Polymarket Lakers adjusts to 73¢  
→ SELL at 73¢ for 17.7% profit. No need to wait for game.
```

### Edge 3: Injury/News Alpha (Information Edge)

Key player ruled out → sportsbooks adjust in seconds. Polymarket takes minutes to hours. First to trade wins.

```
3:45 PM — @wojespn tweets: "LeBron James OUT tonight (rest)"
3:45 PM — DraftKings instantly: Lakers from -200 → +120 (45.5%)
3:45 PM — Polymarket: Lakers still at 62¢ ← STALE
→ SELL Lakers immediately at 62¢, true value now ~45¢
→ Lock in 17¢ profit per share
```

**Sources for news speed:**
- Twitter/X API (follow @wojespn, @shaboroian, @raaborteport)
- ESPN push notifications API
- Rotowire lineups API (official injury reports)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        SportsBot                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ODDS INGESTION LAYER                                     │ │
│  │ ├─ Pinnacle API (sharpest book, REST, 30s poll)          │ │
│  │ ├─ DraftKings scraper (odds page, 60s poll)              │ │
│  │ ├─ Betfair Exchange API (real-time, WebSocket)           │ │
│  │ ├─ FanDuel scraper (backup source)                       │ │
│  │ └─ De-vig engine: convert American/Decimal → true prob   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ NEWS INGESTION LAYER                                     │ │
│  │ ├─ Twitter/X stream: injury reporters (Woj, Shams, etc) │ │
│  │ ├─ ESPN API: official injury/lineup updates              │ │
│  │ ├─ Rotowire: confirmed starting lineups                 │ │
│  │ └─ Claude Haiku: parse tweet → extract player/status    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ SIGNAL ENGINE                                            │ │
│  │ ├─ Odds comparison: sportsbook prob vs Polymarket price  │ │
│  │ ├─ Line movement detector: Δ > 3% triggers alert        │ │
│  │ ├─ News impact scorer: player importance → price impact  │ │
│  │ ├─ Min edge filter: 3% value, 5% auto-trade             │ │
│  │ ├─ Confidence weighting: multi-book agreement = higher   │ │
│  │ └─ Output: {market, side, edge%, confidence, size}       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ EXECUTION ENGINE (shared with WeatherBot)                │ │
│  │ ├─ Polymarket CLOB API (py-clob-client)                  │ │
│  │ ├─ Kelly Criterion sizing (¼ Kelly, 5% cap)              │ │
│  │ ├─ Order management: limit orders, cancel stale          │ │
│  │ ├─ Pre-game exit: sell position if edge flips            │ │
│  │ └─ Circuit breaker: halt at -10% daily drawdown          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ LEARNING ENGINE (continuously improves)                   │ │
│  │ ├─ Log every trade: edge, outcome, book source, timing   │ │
│  │ ├─ Win rate by sport, league, edge threshold             │ │
│  │ ├─ Sportsbook accuracy ranking (which book = best ref?)  │ │
│  │ ├─ Optimal entry timing (minutes after line move)        │ │
│  │ ├─ Edge decay analysis (how fast does arb close?)        │ │
│  │ └─ Weekly auto-tune: adjust thresholds from results      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Sports Coverage (Phase 1)

| Sport | League | Games/Week | Polymarket Liquidity | Data Source |
|-------|--------|-----------|---------------------|-------------|
| Basketball | NBA | 14-20 | Very High | DraftKings, ESPN |
| Football | NFL | 16 (season) | Very High | DraftKings, ESPN |
| Soccer | EPL | 10 | High | Betfair, Pinnacle |
| Soccer | Champions League | 8-16 | High | Betfair, Pinnacle |
| MMA | UFC | 12-14/card | Medium | DraftKings, Betfair |
| Golf | PGA/Augusta | 1 tournament | High (see $70M Augusta) | DraftKings |
| F1 | Formula 1 | 1 race/week | High ($84M season) | Betfair |
| Cricket | IPL | 7/week | Medium | Betfair, Dream11 odds |
| Esports | LOL/CS2 | Daily | Medium | Pinnacle, HLTV |
| Tennis | Grand Slams | Varies | Medium | Betfair |

---

## De-Vig Engine (Critical Component)

Sportsbook odds include a "vig" (margin). You must remove it to get true probability.

```python
def devig_american(favorite_odds, underdog_odds):
    """Convert American odds to true implied probability (removing vig)"""
    def implied(odds):
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)
    
    p1 = implied(favorite_odds)
    p2 = implied(underdog_odds)
    total = p1 + p2  # > 1.0 due to vig
    
    # Remove vig proportionally
    return p1 / total, p2 / total

# Example: Lakers -200, Celtics +170
true_lakers, true_celtics = devig_american(-200, 170)
# true_lakers = 0.649 (64.9%), true_celtics = 0.351 (35.1%)
# Sum = 100% (vig removed)
```

**Multi-book consensus:** Average de-vigged probability across 3+ books for highest accuracy.

---

## Build Phases

### Phase 1 — Odds Scraper + Signal Engine (Week 1)

- [ ] Pinnacle API integration (REST, 30s poll, de-vig)
- [ ] DraftKings odds scraper (Playwright/Puppeteer, 60s cycle)
- [ ] Betfair Exchange API integration (WebSocket stream)
- [ ] De-vig engine: American, Decimal, Fractional → true probability
- [ ] Polymarket CLOB scanner: pull all active sports markets
- [ ] Market matcher: link Polymarket markets to sportsbook events (fuzzy match by team + date)
- [ ] Edge calculator: sportsbook_prob - polymarket_price → edge%
- [ ] Signal output: JSON log of all edges > 2%
- [ ] Telegram alert when edge > 5%

**Deliverable:** Bot runs 24/7, logs every edge found, sends Telegram alerts for top signals.

### Phase 2 — News Engine (Week 2)

- [ ] Twitter/X API stream: follow 20 injury/lineup reporters per sport
- [ ] Claude Haiku parser: tweet → structured data (player, team, status, impact score)
- [ ] ESPN injury report API poller (30-min cycle)
- [ ] Rotowire lineups API (pre-game confirmed starters)
- [ ] News impact scorer: starting QB out = -15% team win prob, bench player = -1%
- [ ] Cross-reference: news impact → check if Polymarket has adjusted → flag if not
- [ ] Latency target: news tweet → Polymarket trade < 2 minutes

### Phase 3 — Execution + Paper Trading (Week 2-3)

- [ ] Polymarket CLOB order placement (shared with WeatherBot)
- [ ] Kelly Criterion sizing: edge * confidence / variance
- [ ] Limit order logic: place slightly better than market to ensure fill
- [ ] Position tracking: active bets, unrealized P&L
- [ ] Pre-game exit: if edge flips to negative, sell position early
- [ ] Paper trading mode: log what WOULD have been traded for 1 week
- [ ] Validate: win rate, edge accuracy, fill rate

### Phase 4 — Go Live (Week 3-4)

- [ ] Fund wallet: $1,000-2,000 USDC
- [ ] Start with NBA + NFL only (highest liquidity)
- [ ] Max $50/trade for first 50 trades
- [ ] Daily P&L tracking + edge analysis
- [ ] Scale to $100/trade after 100+ trades with >55% win rate

### Phase 5 — Learning Engine (Month 2)

- [ ] Trade outcome logging: every field (edge, book source, timing, sport, result)
- [ ] Win rate analysis by: sport, league, edge threshold, time to game
- [ ] Sportsbook accuracy ranking: which book's odds are most predictive?
- [ ] Edge decay model: how fast does arbitrage window close?
- [ ] Auto-tune: weekly cron adjusts min edge threshold + position sizing
- [ ] Monthly Claude Sonnet analysis: "Here are this month's 500 trades. What patterns do you see?"

---

## Risk Management

### Position Limits
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max per trade | 5% of bankroll | Survive 20-loss streak |
| Max per game | 10% of bankroll | Don't over-concentrate |
| Max per day | 30% of bankroll | Daily exposure cap |
| Daily loss limit | -10% of bankroll | Circuit breaker |
| Weekly loss limit | -15% of bankroll | Step back, review |

### Exit Rules
- **Pre-game exit:** If edge flips to < -2%, sell position immediately
- **Stale order cancel:** Cancel unfilled orders after 5 minutes
- **No live betting:** Only pre-game positions (live markets are bot-dominated)
- **Cash out:** Take profits at 70%+ of max payout (don't get greedy)

---

## Data Cost

| Source | Cost | Notes |
|--------|------|-------|
| Pinnacle API | Free | Needs Pinnacle account |
| DraftKings | Free (scrape) | Playwright automation |
| Betfair Exchange | Free tier | Needs API key |
| ESPN API | Free | Public endpoints |
| Twitter/X API | $100/mo (Basic) | For streaming injury news |
| Rotowire | $10/mo | Confirmed lineups |
| Claude Haiku | ~$15/mo | News parsing + analysis |
| Claude Sonnet | ~$10/mo | Weekly strategy review |
| **Total** | **~$135/mo** | Paid for by first winning trade |

---

## Expected Performance

### Conservative (Month 1-3)
| Metric | Target |
|--------|--------|
| Trades/week | 20-30 |
| Avg edge | 4-6% |
| Win rate | 55-60% |
| Monthly return | 10-20% |
| Bankroll growth | $2K → $3K (Month 1) |

### Scaled (Month 4+)
| Metric | Target |
|--------|--------|
| Trades/week | 50-100 |
| Avg edge | 5-8% |
| Win rate | 58-65% |
| Monthly return | 20-40% |
| Bankroll growth | $5K → $15K (Month 4-6) |

### Swisstony Benchmark (Aspirational)
| Metric | His Results |
|--------|-----------|
| Total trades | 22,000+ |
| Win rate | ~57% |
| Total profit | $3.7M |
| Time period | 5 months |
| Biggest single win | $290K |

---
