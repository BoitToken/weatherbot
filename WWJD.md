# WWJD — What Would Jayson Do?
## JC Copy Trader Strategy System
**Version:** 1.0  
**Created:** 2026-04-10  
**Status:** Active — integrated into `jc_copy_trader.py`

---

## 1. Entry Rules (Pre-Trade)

### 1.1 Level Proximity
- Price must be within **0.2% of a JC level** to trigger entry consideration
- At SPV/CDW sweeps: tighten to 0.15% (these are precision levels)
- At Fib/POC levels: keep 0.2% (wider zones)
- **NEVER enter between levels** — must be at an exact JC level

### 1.2 Confluence Requirements
Entry requires **minimum 3 of these factors** agreeing:

| Factor | Weight | Description |
|--------|--------|-------------|
| Level Type | 0.25 | SPV/CDW sweep > POC > Fib > D/W |
| Price Action | 0.20 | Rejection wick, engulfing candle, volume spike at level |
| Market Structure | 0.20 | Trend direction, higher highs/lows, break of structure |
| JC Signal | 0.15 | Explicit signal from Jayson (Discord/chart annotation) |
| R:R Ratio | 0.10 | Minimum 1:1, prefer 3:1+ |
| Time of Day | 0.05 | NY session (18:30-01:30 IST) or London (13:00-21:30 IST) |
| Momentum | 0.05 | RSI not overbought/oversold counter to trade |

### 1.3 Market Structure Check
- **Trend Alignment:** Don't short in a strong uptrend unless at a major resistance (SPV/CDW)
- **Support/Resistance Validity:** Level must have been tested ≤3 times (weakens each touch)
- **Break of Structure (BOS):** If BOS occurred opposite to trade direction, skip unless at major level

### 1.4 Risk Assessment
- **Minimum R:R:** 1:1 (entry to SL vs entry to TP1)
- **Preferred R:R:** 3:1 or better
- **Maximum SL distance:** 0.5% beyond the JC level
- **If R:R < 1:1:** SKIP — no matter how strong the level looks

### 1.5 Position Sizing (Conviction-Based)

| Conviction | Bankroll % | When |
|-----------|-----------|------|
| 🟢 HIGH | 5% | 4+ factors aligned, SPV/CDW level, JC explicit signal |
| 🟡 MEDIUM | 3% | 3 factors, named level (POC/Fib), decent R:R |
| 🔴 LOW/SKIP | 0% | <3 factors, between levels, poor R:R |

---

## 2. Trade Management (Active Position)

### 2.1 Initial Stop Loss
- **Always honor JC's stop** — if Jayson marks a level, SL goes 0.5% beyond it
- **SPV levels:** SL at the sweep wick low/high + 0.3%
- **Fib levels:** SL below/above the next Fib level
- **NEVER widen SL** after entry — only tighten

### 2.2 Partial Profit Taking
- **At TP1 (first opposing JC level):** Close 50% of position
- **At TP2 (second opposing level or +1.5%):** Close remaining 50%
- **If trending >1.5%:** Hold remainder, let it ride to next level

### 2.3 Breakeven Move
- **After TP1 hit:** Move SL to entry price (breakeven)
- **After +1.0% move in favor:** Move SL to breakeven even if TP1 hasn't hit
- **Never move SL before +1.0%** — give the trade room to breathe

### 2.4 Trailing Stop Rules
- **After TP1:** Trail SL to each broken JC level as price moves through
- **Trending market (>1.5%):** Trail SL 0.5% behind price
- **If momentum slows (RSI divergence):** Tighten trail to 0.3%
- **Lock minimum 50% of unrealized profit** after TP1

---

## 3. Stop-Out Response (What JC Does)

### 3.1 Immediate Actions
When a trade hits SL:
1. **Log the stopped level + reason** — was it a fake-out or true invalidation?
2. **Check if level still holds structure** — did price close beyond or wick back?
3. **Assess momentum shift** — is the broader move against us or was it a sweep?
4. **Check Jayson's Discord** — has he posted about it? Updated his view?

### 3.2 Re-Entry Decision Tree

```
STOPPED OUT AT LEVEL
        │
        ├── Level holds on retest (wick beyond, close back)?
        │       ├── YES → Wait 5-15 min for confirmation
        │       │         → Re-enter SAME direction at SAME level
        │       │         → Use SMALLER size (2% vs 3%)
        │       │         → Tighter SL (below wick low)
        │       └── NO → Level invalidated
        │
        ├── Level invalidated (clean break + close)?
        │       ├── Move to NEXT major level in hierarchy
        │       │   (e.g., if $72,829 broke, watch $73,974)
        │       └── Wait for price to reach next level before trading
        │
        ├── Momentum flipped (BOS in opposite direction)?
        │       ├── Consider OPPOSITE bias at next key level
        │       │   (e.g., was long at support, now short at resistance)
        │       └── Wait for JC's explicit new signal
        │
        └── Wait for JC's signal (ALWAYS)
                ├── No revenge trades
                ├── No doubling down
                └── Patience > action
```

### 3.3 Re-Entry Timing
- **Minimum wait:** 5 minutes after stop-out (no revenge)
- **Ideal wait:** Until next candle close confirms level holds
- **Maximum wait:** Until JC posts new signal or 30 minutes
- **If 3 consecutive stops at same level:** That level is broken, skip it

### 3.4 What NOT to Do
- ❌ **Revenge trade immediately** — emotions are high, wait
- ❌ **Double down without confirmation** — "it'll come back" is hope, not strategy
- ❌ **Hope and hold losers** — SL is SL, honor it always
- ❌ **Enter between levels** — must be at exact JC level
- ❌ **Increase size after a loss** — reduce to 2% until next win
- ❌ **Trade counter to JC's bias** — if he's bearish, don't go long
- ❌ **Overtrade** — max 2 concurrent, max 6 trades/day

---

## 4. Win Management

### 4.1 Partial Taking
1. **TP1 hit (first opposing level):**
   - Close 50% of position
   - Move SL to breakeven
   - Book the partial P&L
   
2. **Remainder management:**
   - If trending: trail to next JC level
   - If ranging: close at TP2 or +1.5%
   - If momentum dying: close at current price

### 4.2 Trailing Winners
- After TP1: SL trails 0.5% behind price
- At each new JC level broken: move SL to that level
- **"Let the rest sizzle"** — Jayson's phrase for letting winners run
- Only close remainder at: TP2, next JC level, or trail stop

### 4.3 Maximum Hold Time
- **Scalps (at minor levels):** Max 4 hours
- **Swings (at major levels):** Max 24 hours
- **If still open after max hold:** Evaluate and close unless strongly trending

---

## 5. Level Hierarchy (JC's Key Levels)

### 5.1 Resistance Levels (Sell/Short Zones)

| Price | Label | Type | Confidence | Leverage |
|-------|-------|------|-----------|---------|
| $75,905 | SPV? | Stop sweep zone | HIGH | 50x |
| $74,967 | D Level | Daily level | MEDIUM | 35x |
| $73,974 | nwPOC | Naked weekly POC | HIGH | 45x |
| $72,829 | SPV of SPV | NY Open P&D | HIGHEST | 50x |

### 5.2 Support Levels (Buy/Long Zones)

| Price | Label | Type | Confidence | Leverage |
|-------|-------|------|-----------|---------|
| $71,215 | SPV? | Potential sweep → reversal | HIGH | 50x |
| $70,623 | KEY / SPs Filled | Key level, SPs filled | HIGH | 45x |
| $69,578 | 0.918 Fib | Fibonacci extension | MEDIUM | 40x |
| $68,517 | 0.786 Fib | Golden Pocket | HIGH | 40x |
| $68,424 | ndPOC | Naked daily POC | HIGH | 45x |
| $67,361 | nfPOC | Naked monthly POC | HIGH | 40x |
| $65,931 | W (Weekly) | Weekly level | MEDIUM | 35x |

### 5.3 Level Type Explanations
- **SPV (Single Print Value):** One-time volume nodes — price tends to sweep and reverse
- **CDW (Chart Drawn Wicks):** Price wicked but didn't close — unfinished business
- **nwPOC/ndPOC/nfPOC:** Naked Point of Control — untested magnet level (weekly/daily/monthly)
- **POI (Point of Interest):** Marked by Jayson as significant
- **NY Open P&D (Push & Dump):** Levels set during NY session open volatility
- **Fib Levels:** Fibonacci retracements — 0.786 (Golden Pocket) is highest conviction
- **KEY:** Jayson's marked key levels with multiple confluence points
- **D/W Levels:** Daily/Weekly timeframe levels

---

## 6. Signal Classification

### 🟢 HIGH CONVICTION — Enter at 5% risk
**Requirements (4+ factors must agree):**
- At a major JC level (SPV, CDW, Golden Pocket, nPOC)
- Price action confirms (rejection wick, volume spike)
- Market structure aligned (trending in trade direction)
- R:R ≥ 3:1
- Jayson's explicit signal or chart annotation matches
- NY or London session active

**Conviction Score: 80-100**

### 🟡 MEDIUM — Enter at 3% risk  
**Requirements (3 factors agree):**
- At a named JC level (Fib, D Level, W Level)
- Decent price action (some confirmation)
- R:R ≥ 1.5:1
- No JC signal contradicting

**Conviction Score: 50-79**

### 🔴 SKIP — Do Not Trade
**Any of these:**
- Fewer than 3 factors agreeing
- R:R < 1:1
- Between levels (not at an exact JC level)
- Counter to JC's stated bias
- 3+ recent stops at this level
- Late night / low liquidity session

**Conviction Score: 0-49**

---

## 7. Bankroll Management

### 7.1 Per-Trade Sizing

| Setup Quality | % of Bankroll | At $10K | Max Leverage |
|--------------|--------------|---------|-------------|
| 🟢 HIGH conviction | 5% | $500 | 50x |
| 🟡 MEDIUM conviction | 3% | $300 | 40x |
| 🔴 After stop-out | 2% | $200 | 30x |

### 7.2 Portfolio Rules
- **Max 2 concurrent positions** (any direction)
- **Max 10% total exposure** at any time
- **After 3 consecutive losses:** Reduce to 2% per trade until next win
- **After max drawdown (15%):** Pause trading for 24 hours, review strategy

### 7.3 Scaling Rules
- **Balance grows:** Position sizes scale automatically (% based)
- **Balance drops >10%:** Auto-reduce to 2% per trade
- **Balance drops >15%:** Auto-pause, require manual restart
- **Win streak (5+):** Don't increase above 5% — overconfidence kills

### 7.4 Fee Accounting
- Entry fee: ~0.02% (Bybit maker)
- Exit fee: ~0.02% (Bybit maker)
- Funding rate: variable (8h)
- **All P&L calculations include fees** — no gross-only delusions

---

## Conviction Scoring Algorithm

```
Score = Σ(factor_weight × factor_score)

Factors:
  level_type_score    × 0.25  →  SPV=10, CDW=10, nPOC=8, KEY=7, Fib=6, D/W=4
  price_action_score  × 0.20  →  Rejection wick=10, volume spike=8, engulfing=7
  market_structure    × 0.20  →  Trend aligned=10, ranging=5, counter-trend=2
  jc_signal           × 0.15  →  Explicit entry=10, chart match=7, no signal=3
  risk_reward         × 0.10  →  >3:1=10, 2-3:1=7, 1.5-2:1=5, 1-1.5:1=3
  session_quality     × 0.05  →  NY=10, London=8, Asian=4, dead=2
  momentum            × 0.05  →  Aligned RSI=10, neutral=5, divergence=2

If score >= 80: HIGH conviction → 5% risk
If score >= 50: MEDIUM → 3% risk
If score < 50:  SKIP → no trade
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────┐
│          WWJD — QUICK REFERENCE             │
├─────────────────────────────────────────────┤
│ BEFORE ENTRY:                               │
│  ✓ At exact JC level (within 0.2%)?        │
│  ✓ 3+ confluence factors agree?             │
│  ✓ R:R ≥ 1:1 (prefer 3:1)?               │
│  ✓ Max 2 open positions?                    │
│  ✓ Not counter to JC's bias?               │
├─────────────────────────────────────────────┤
│ DURING TRADE:                               │
│  • SL = 0.5% beyond level (NEVER widen)    │
│  • +1.0% → breakeven                       │
│  • TP1 (opposing level) → close 50%        │
│  • Trail remainder → TP2 or next level     │
├─────────────────────────────────────────────┤
│ AFTER STOP-OUT:                             │
│  • Wait minimum 5 minutes                   │
│  • Level holds? → re-enter at 2% size      │
│  • Level broke? → move to next level        │
│  • Wait for JC's signal                     │
│  • NEVER revenge trade                      │
├─────────────────────────────────────────────┤
│ SIZING:                                     │
│  🟢 HIGH (4+ factors):  5% / 50x           │
│  🟡 MED  (3 factors):   3% / 40x           │
│  🔴 SKIP (<3 factors):  NO TRADE           │
│  ⚠️  After loss:         2% / 30x           │
└─────────────────────────────────────────────┘
```

---

*"The market will always be there tomorrow. Your capital won't if you're reckless today."*  
— Jayson Casper approach, systematized for copy trading.
