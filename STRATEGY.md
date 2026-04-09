# BTC Paper Trading Strategy — WeatherBot
**Last Updated:** 2026-04-09 13:29 IST

## Active Strategy: V3 (Reward:Risk Gated)
**Activated:** 2026-04-09 13:29 IST

### Core Rules
| Rule | Setting | Rationale |
|------|---------|-----------|
| **R:R Floor** | >= 1:1 | Potential profit must cover loss + fee. Entry < 50c. |
| **Timeframe** | 5M only | 15M entries always 85c+ (market too efficient) |
| **Stake Scaling** | <20c=$75, 20-30c=$50, 30-40c=$35, 40-50c=$25 | Biggest bets on best odds |
| **Factor Agreement** | >= 4/7 | At least 4 of 7 signal factors must agree with direction |
| **15M** | SKIP | 80% accuracy but -$150 P&L — payout ratio 1:25 |

### V3 Math: Why 50c Max Entry
| Entry | Win Amount | Loss | R:R | Breakeven WR | Verdict |
|-------|-----------|------|-----|-------------|--------|
| 10c | +$220.50 | -$75 | 2.9x | 25% | ✅ GREAT |
| 20c | +$98.00 | -$75 | 1.3x | 43% | ✅ GREAT |
| 30c | +$57.17 | -$50 | 1.1x | 47% | ✅ GOOD |
| 40c | +$36.75 | -$35 | 1.1x | 49% | ✅ OK |
| 50c | +$24.50 | -$25 | 0.98x | 51% | ⚠️ EDGE |
| 60c | +$16.33 | -$25 | 0.65x | 60% | ❌ BURN |
| 70c | +$10.50 | -$25 | 0.42x | 70% | ❌ BURN |
| 85c | +$4.41 | -$25 | 0.18x | 85% | 💀 SUICIDE |

### V3 Evidence (from 135 V1 trades)
| R:R Bucket | Trades | Wins | P&L | Verdict |
|-----------|--------|------|-----|--------|
| <0.5x (burn) | 113 | 82 (73%) | **-$710** | 💀 |
| 0.5-1x (partial) | 9 | 5 (56%) | +$5 | Breakeven |
| 1-2x (covers loss) | 9 | 7 (78%) | **+$149** | ✅ |
| 2x+ (great) | 4 | 3 (75%) | **+$259** | ✅ |

**84% of trades were structurally guaranteed to lose money regardless of accuracy.**
V3 eliminates them entirely.

---

## Strategy Version History

### V1 (2026-04-09 05:00-12:36): No filters
- All signals, fixed $25, 5M + 15M
- Result: 86W-32L (73%) but **-$202 P&L**
- Problem: 67% of trades at 85c+ entry (win $0.30, lose $25)

### V2 (2026-04-09 12:36-13:29): Entry < 70c
- Max entry 70c, 5M only, scaled stakes
- Improvement: Eliminated worst 85c+ trades
- Problem: Still took 50-70c trades where R:R < 1:1

### V3 (2026-04-09 13:29+): R:R >= 1:1 (CURRENT)
- Entry < 50c (upside covers downside + fee)
- 4/7 factor agreement minimum
- Aggressive scaling on best odds
- Expected: ~5-10 trades/day, each with +EV structure

---

## Signal Factor Weights
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

## Volatility Tracking
- Table: `btc_volatility_hours` (per-hour per-day performance)
- Daily report: 11:30 PM IST (cron)
- Weekly review: After 7 days, recalibrate time slot rules
- Best observed time: 6AM IST (71c avg entry, 88% accuracy)
- Worst observed: After 10AM IST (entries 85c+ as US market opens)

---

## Key Learnings
1. **Entry price > win rate** for profitability
2. **R:R ratio is the #1 filter** — no trade where upside < downside
3. **Confidence trap** — highest confidence = worst P&L (correlates with extreme odds)
4. **15M markets too efficient** — always 85c+ by discovery time
5. **5M has variance** — wider odds = more opportunity for low entries
6. **Factor agreement matters** — 4/7+ aligned = higher accuracy trades
7. **Scale into conviction** — biggest stakes on best R:R trades
