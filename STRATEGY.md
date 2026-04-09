# BTC Paper Trading Strategy — WeatherBot
**Last Updated:** 2026-04-09 12:36 IST

## Active Strategy: V2 (Entry-Price Gated)

### Core Rules
| Rule | Setting | Rationale |
|------|---------|-----------|
| **Max Entry** | 70c | Above 70c = negative EV even at 80% accuracy |
| **Timeframe** | 5M only | 15M entries always 85c+ (market too efficient) |
| **Stake Scaling** | <30c=$50, 30-50c=$35, 50-70c=$25 | Larger bets on better odds |
| **15M** | SKIP | 80% accuracy but -$150 P&L — payout ratio 1:25 |

### Why These Rules?
Based on 118 paper trades over 7 hours (2026-04-09):
- **<30c entries:** 77% accuracy, +$209 P&L — avg win $28.45
- **30-50c entries:** 86% accuracy, +$143 P&L — avg win $28.01
- **50-70c entries:** 40% accuracy, -$68 P&L — avg win $20.49
- **70-85c entries:** 78% accuracy, -$3 P&L — avg win $6.74
- **85c+ entries:** 74% accuracy, -$507 P&L — avg win $0.30 💀

**The math:** At 85c entry, win = $0.30, loss = -$25.00. Need 99% win rate to break even. We hit 74%. Impossible.

### Confidence Trap (CRITICAL LEARNING)
- "Ultra 80%+" confidence: 74 trades, 71.6% accuracy, **-$425 P&L**
  - Why: Avg entry 92c. Confidence correlates with extreme odds, not profit.
- "High 60-80%" confidence: 43 trades, 74.4% accuracy, **+$199 P&L**
  - Why: Avg entry 63c. Better odds = better payout.
- **Lesson:** NEVER use confidence score for position sizing. Entry price is the ONLY sizing signal.

---

## V1 Performance (Baseline — 2026-04-09 05:00–12:20 IST)

| Metric | Value |
|--------|-------|
| Total Trades | 118 |
| Win Rate | 73% (86W-32L) |
| Net P&L | -$202.39 |
| Gross Profit | +$597.61 |
| Gross Loss | -$800.00 |
| Best Trade | +$133.56 |
| Fees | $12.20 |
| Total Risked | $2,950 |

### Hourly V1 Performance
| Hour | W-L | Win% | P&L | Avg Entry | Notes |
|------|-----|------|-----|-----------|-------|
| 5AM | 11-4 | 73% | +$57 | 79c | Session start |
| 6AM | 14-2 | 88% | +$151 | 71c | **Peak** — best entries |
| 7AM | 11-5 | 69% | -$97 | 87c | Entry jumped |
| 8AM | 12-4 | 75% | -$66 | 80c | Bleeding |
| 9AM | 12-4 | 75% | -$41 | 76c | Slight improvement |
| 10AM | 10-6 | 63% | -$114 | 78c | Worst accuracy |
| 11AM | 10-6 | 63% | -$68 | 86c | Continued bleed |
| 12PM | 6-2 | 75% | -$48 | 94c | Worst entries |

**Pattern:** 6AM had best entries (71c avg) AND best accuracy (88%). After 7AM, entries crept up as US market opened.

### By Timeframe (V1)
| Window | Trades | Accuracy | P&L | Avg Entry | Verdict |
|--------|--------|----------|-----|-----------|---------|
| 5M | 88 | 74% | +$121 | 73c | ✅ Profitable |
| 15M | 30 | 80% | -$150 | 92c | ❌ Money losing |

---

## Volatility Tracking

### Purpose
Track hourly time slots to find when BTC markets have favorable odds (low entry prices, high volume, high volatility). After 1 week, identify:
- Best hours to trade (highest P&L per trade)
- Worst hours to avoid
- Volatility patterns by day-of-week
- Correlation between BTC price range and entry odds

### Data Storage
Table: `btc_volatility_hours`
Columns: date, hour_ist, window_length, trades_taken, trades_won, trades_lost, net_pnl, avg_entry, btc_price_range_pct, best_trade, session_tag

### V2 Hypothesis
- **Early hours (5-7AM IST / 11:30PM-1:30AM ET):** Lower volume → wider odds → better entries
- **US market hours (7PM-2AM IST / 9:30AM-4PM ET):** Higher volume → tighter odds → worse entries
- **Volatile days:** Large BTC price swings → wider odds → better trading conditions

### Review Schedule
- **Daily:** Automated strategy report at 11:30 PM IST (to all subscribers)
- **Weekly:** Manual review of accumulated volatility data
- **Adjustments:** After 7 days of V2 data, recalibrate rules

---

## Projected V2 Impact
Based on retroactive analysis of today's 118 trades:
- Would have taken ~30 trades (not 118) — 75% reduction
- 24 wins × avg +$20 = +$480
- 6 losses × avg -$35 = -$210
- **Projected net: +$270** (vs actual -$202)

---

## Evolution Plan

### Week 1 (Current)
- [x] V2 rules implemented (max 70c, 5M only, scaled stakes)
- [x] Volatility tracking per hour
- [x] Hourly financial reports
- [x] Daily strategy report at 11:30 PM

### Week 2 (After data review)
- [ ] Identify optimal trading hours
- [ ] Adjust entry threshold per time slot
- [ ] Add exit signals (edge decay, take-profit)
- [ ] Consider Kelly criterion sizing

### Week 3+
- [ ] Live trading evaluation
- [ ] Multi-day pattern detection
- [ ] Automated strategy parameter tuning
- [ ] Portfolio allocation across strategies

---

## Signal Factor Weights (Current)
| Factor | Weight | Description |
|--------|--------|-------------|
| Price Delta | 0.25 | BTC price vs window open |
| Momentum | 0.20 | Short-term trend direction |
| Volume Imbalance | 0.15 | Buy/sell pressure |
| Oracle Lead | 0.15 | Binance vs Chainlink spread |
| Book Imbalance | 0.10 | Orderbook depth ratio |
| Volatility | 0.10 | Realized vs implied vol |
| Time Decay | 0.05 | Seconds remaining in window |

---

**Strategy Version History:**
- V1 (2026-04-09 05:00): All signals, fixed $25, 5M + 15M → -$202
- V2 (2026-04-09 12:36): Entry < 70c, 5M only, scaled stakes → active
