# BUILD PLAN: Live Autonomous Trading Bot
**Date:** 2026-04-11 04:53 IST
**Status:** APPROVED — CEO authorized all work
**Focus:** BTC 5M/15M Polymarket + JC Copy Trading Desk
**Budget:** 3 agents on Sonnet 4.6

---

## Context

Live trading pipeline PROVEN working (manual trades placed through proxy wallet).
Now: wire the automated signal loop → live execution so the bot trades autonomously.

### Wallet Config (CONFIRMED)
- EOA: `0xb9BEa5FDe7957709D0f8d2064188B1603b74D5Ca`
- Proxy: `0x8A110d95c48662147f8772C48d73A87ec23909d8` (Polymarket UI wallet)
- Signature Type: 2 (POLY_PROXY)
- CLOB API: configured in `.env`
- Balance: ~$987 USDC.e on proxy
- All exchange approvals: ✅ confirmed on-chain

---

## Agent 1: BTC 5M Market Discovery & Auto-Execution Pipeline

**Goal:** Make the bot autonomously discover live 5M/15M BTC windows and execute trades through the proxy wallet.

### Tasks:
1. **Fix market discovery** — Replace broken Gamma API `accepting_orders` check with epoch-based window discovery:
   - 5M windows: `btc-updown-5m-{epoch}` where epoch = end of 300s window
   - Calculate current/next windows from `time.time()`
   - Query CLOB order book directly to verify market is live (has bids+asks)
   - Fall back to Gamma slug lookup if CLOB fails

2. **Fix token ID resolution** — Build `get_5m_tokens(window_epoch)`:
   - Fetch from Gamma API: `events?slug=btc-updown-5m-{epoch}`
   - Extract `clobTokenIds` for Up/Down outcomes
   - Cache token IDs per window (they don't change)
   - Store in `btc_windows` table

3. **Wire signal loop → live execution via proxy wallet**:
   - In `scheduled_btc_signal_scan()`, after V4.1 rules pass:
   - Initialize `PolymarketLiveTrader` with proxy wallet config
   - Call `execute_live_trade()` with discovered token_id
   - Ensure `PROXY_WALLET` and `SIGNATURE_TYPE=2` are read from env

4. **Dynamic bankroll sizing**:
   - Read proxy wallet USDC balance from CLOB API on startup + every 5 min
   - Replace fixed `$25` with: `min(bankroll * 0.03, $25)` for normal, `min(bankroll * 0.05, $50)` for 4x conviction
   - Hard cap: never more than 10% of bankroll on one trade
   - Circuit breaker: stop trading if daily loss > 5% of bankroll

5. **Fix 15M markets** (re-enable with proper entry gate):
   - V3 skipped ALL 15M because entries were always 85c+
   - With maker orders (Agent 2), we can get better entries
   - For now: enable 15M only if entry < 30c (rare but happens pre-market)

### Files to modify:
- `src/strategies/btc_signal_engine.py` — `run_scan()` method, market discovery
- `src/main.py` — `scheduled_btc_signal_scan()`, live execution wiring
- `src/polymarket_live.py` — ensure proxy wallet init works
- `src/config.py` — add PROXY_WALLET, SIGNATURE_TYPE

### Success criteria:
- Bot autonomously detects next 5M window opening
- Places trade through proxy wallet when V4.1 rules pass
- Trade visible in Polymarket UI under logged-in profile
- Telegram alert fires on trade open + resolution

---

## Agent 2: Maker Orders & Spread Capture

**Goal:** Transform from taker-only to maker-first strategy for 2-5x more profit per window.

### Tasks:
1. **Build `MakerEngine` class** (`src/execution/maker_engine.py`):
   - Compute fair value from 7-factor signal engine
   - Post limit orders on BOTH sides (Up + Down) with 3-5¢ spread around fair value
   - Manage order lifecycle: post → monitor → cancel/replace → settle
   - Use GTC orders, cancel when window enters final 30 seconds

2. **Spread quoting logic**:
   - Default spread: 3¢ each side of fair value (e.g., fair=50c → bid 47c, ask 53c)
   - Skew toward predicted winner as confidence grows
   - In final 30s: tighten on predicted side, widen on other
   - Min spread: 2¢ (below this, fees eat the edge)

3. **Toxic flow protection**:
   - Monitor BTC price via Binance websocket
   - If price moves > 0.5σ (trailing 60s realized vol) within 500ms → cancel ALL resting orders
   - Log every cancel: timestamp, σ, BTC move, cancelled orders
   - Re-quote after 2 seconds of stability

4. **Order management**:
   - Track all open maker orders in `maker_orders` DB table
   - Cancel all orders when window closes (cleanup)
   - Handle partial fills — adjust remaining quantity
   - Max 2 orders per side per window

5. **Integrate with scheduler**:
   - New job: `scheduled_maker_quote` running every 5 seconds during active windows
   - Detect window open → start quoting → window close → cancel all → settle

### Files to create/modify:
- `src/execution/maker_engine.py` — NEW
- `src/main.py` — add `scheduled_maker_quote` job
- `schema.sql` — add `maker_orders` table

### Success criteria:
- Bot posts limit orders on both sides of 5M markets
- Orders fill when market moves through our price
- Toxic flow cancels fire within 100ms of detection
- Net maker P&L positive after 1 day of trading

---

## Agent 3: JC Copy Trading Desk — Live Bybit Execution

**Goal:** Wire Jayson Casper signal parser to live Bybit futures execution.

### Tasks:
1. **Audit current JC pipeline** (`src/` JC-related files):
   - Ghost bot watches JC Discord → parses signals → stores in DB
   - Dashboard shows signals + BTC price
   - WWJD strategy computes entries from JC's support/resistance levels
   - Bybit API keys configured but execution is paper-only

2. **Wire Bybit live execution**:
   - When JC posts a signal that matches our WWJD entry rules:
   - Open Bybit futures position (BTC/USDT perpetual)
   - Use configured leverage (check current setting)
   - Set TP/SL from JC's levels
   - Track in `jc_trades` table

3. **Position management**:
   - Monitor open positions every 10s
   - Trailing stop: move SL to breakeven after 1R profit
   - Manual override: respect dashboard TP/SL/kill controls
   - Max 1 position at a time (no pyramiding without CEO approval)

4. **Risk controls**:
   - Max position size: $100 (start conservative)
   - Max daily loss: $50 → pause trading
   - Only trade when JC explicitly posts a setup (not general commentary)
   - Require minimum 2 confirmation factors from WWJD

5. **Telegram integration**:
   - @BTCJaysonCasperBot already forwards JC signals
   - Add trade execution alerts: "🟢 Opened LONG BTC @ $72,800 | TP: $74,200 | SL: $72,000"
   - Add close alerts with P&L

### Files to audit/modify:
- Ghost bot signal parser (wherever JC signals are stored)
- `src/main.py` — `run_jc_copy_trader` job (already scheduled every 10s)
- Bybit execution module
- JC dashboard components

### Success criteria:
- JC posts a BTC long signal → bot opens Bybit long within 30s
- TP/SL set from JC's levels
- Position visible in dashboard
- Telegram alert fires on open + close
- Paper mode toggle works (can switch back if needed)

---

## Shared Rules (ALL AGENTS)

1. **Read `.env` for ALL secrets** — never hardcode keys
2. **Use `load_dotenv('/data/.openclaw/workspace/projects/weatherbot/.env', override=True)`**
3. **Proxy wallet for Polymarket:** `PROXY_WALLET=0x8A110d95c48662147f8772C48d73A87ec23909d8`, `SIGNATURE_TYPE=2`
4. **Telegram bot:** token `8610642342:AAE...`, chat_id `1656605843`
5. **All trades must be logged to DB** — no silent execution
6. **`npm run build` equivalent:** code must import cleanly, no syntax errors
7. **Test with a $1 trade first** before enabling full sizing
8. **Git commit when done** with descriptive message

---

## Timeline
- **Agent 1 (Discovery + Execution):** ~2 hours — HIGHEST PRIORITY
- **Agent 2 (Maker Engine):** ~3 hours
- **Agent 3 (JC Copy Desk):** ~2 hours
- **Total:** All 3 running in parallel, expect completion by ~7 AM IST

---

## Post-Build Verification
1. Bot detects live 5M window ✅
2. Places trade through proxy wallet ✅
3. Trade visible in Polymarket UI ✅
4. Telegram alert fires ✅
5. Maker orders posted on both sides ✅
6. JC signal → Bybit execution ✅
7. All trades logged to DB ✅
8. Daily P&L report at 11:30 PM ✅
