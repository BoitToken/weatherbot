"""
BTC V4 Strategy — 10-Point Confluence System
CEO Mandate 2026-04-13: Paper test first, live only after CEO approval.

10 factors, need 6/10 to trade.
Direction set by nearest JC level (support=UP, resistance=DOWN).
"""

import logging
import httpx
from datetime import datetime, timezone
import pytz

log = logging.getLogger("btc_v4_strategy")

# ── Risk Constants (DO NOT CHANGE WITHOUT CEO APPROVAL) ──────────────────────
MAX_STAKE = 15.0              # Max $15 per trade
MIN_BALANCE = 50.0            # Don't trade if wallet < $50
DAILY_LOSS_LIMIT = 30.0       # Stop trading today if -$30
CONSECUTIVE_LOSS_DAYS = 3     # Auto-stop bot after 3 losing days in a row
WALLET_15MIN_PCT = 0.10       # Alert + halt if >10% wallet spent in 15 min
MIN_CONFLUENCE = 6            # Need 6/10 factors to trade
MAX_ENTRY_PRICE = 0.40        # Token must be < 40¢
MIN_SECONDS_REMAINING = 210   # Enter only in first 90s of 300s window
IST = pytz.timezone("Asia/Calcutta")

# ── JC Level Defaults (bootstrap — updated daily from Ghost Discord) ──────────
DEFAULT_JC_LEVELS = [
    {"price": 85500, "label": "SPV resistance", "level_type": "SPV", "direction": "resistance", "strength": 10},
    {"price": 84000, "label": "Current resistance zone", "level_type": "resistance", "direction": "resistance", "strength": 7},
    {"price": 83000, "label": "Support level", "level_type": "support", "direction": "support", "strength": 6},
    {"price": 82000, "label": "Key support", "level_type": "support", "direction": "support", "strength": 8},
    {"price": 80000, "label": "Round number POC", "level_type": "POC", "direction": "support", "strength": 8},
]


class BTCV4Strategy:
    """
    10-point confluence BTC 5M Polymarket strategy.
    PAPER MODE only until CEO approves live trading.
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._btc_cache = None
        self._btc_cache_ts = 0
        self._candles_cache = None
        self._candles_cache_ts = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Main evaluation
    # ─────────────────────────────────────────────────────────────────────────

    async def evaluate(self, window_id: str, up_price: float, down_price: float,
                       seconds_remaining: int, btc_price: float = None) -> dict:
        """
        Evaluate whether to trade this window.
        Returns dict with: should_trade, direction, score, stake, factors, reason
        """
        score = 0
        factors = {}

        # Get current BTC price
        if btc_price is None:
            btc_price = await self._get_btc_price()
        if not btc_price:
            return {"should_trade": False, "reason": "Cannot get BTC price"}

        # ── Factor 1+2: JC Level proximity + type ────────────────────────────
        jc = await self._get_nearest_jc_level(btc_price)
        if not jc:
            return {"should_trade": False, "reason": "No JC levels in DB"}

        distance_pct = abs(btc_price - float(jc["price"])) / btc_price
        if distance_pct > 0.003:  # Must be within 0.3%
            return {"should_trade": False, "reason": f"No JC level nearby (nearest {jc['label']} is {distance_pct*100:.2f}% away)"}

        score += 1  # Factor 1: near JC level
        direction = "UP" if jc["direction"] == "support" else "DOWN"
        factors["jc_level"] = f"{jc['label']} ({jc['level_type']}, {distance_pct*100:.2f}% away)"

        # Factor 2: level type bonus (SPV/CDW strongest)
        if jc["level_type"] in ("SPV", "CDW"):
            score += 2
            factors["level_strength"] = "SPV/CDW (max strength)"
        elif jc["level_type"] in ("POC", "nwPOC", "ndPOC"):
            score += 1
            factors["level_strength"] = "POC"
        else:
            factors["level_strength"] = f"{jc['level_type']} (standard)"

        # ── Factor 3: 3-candle momentum ───────────────────────────────────────
        candles = await self._get_candles(4)
        if candles and len(candles) >= 3:
            last3 = candles[-3:]
            closes = [c["close"] for c in last3]
            if direction == "UP" and closes[-1] > closes[-2] > closes[-3]:
                score += 1
                factors["momentum"] = f"3 green candles ↑"
            elif direction == "DOWN" and closes[-1] < closes[-2] < closes[-3]:
                score += 1
                factors["momentum"] = f"3 red candles ↓"
            else:
                factors["momentum"] = "momentum not aligned"
        
        # ── Factor 4: Volume spike ─────────────────────────────────────────────
        if candles and len(candles) >= 4:
            recent_vol = candles[-1]["volume"]
            avg_vol = sum(c["volume"] for c in candles[:-1]) / len(candles[:-1])
            if avg_vol > 0 and recent_vol > avg_vol * 1.5:
                score += 1
                factors["volume"] = f"spike {recent_vol/avg_vol:.1f}x avg"
            else:
                factors["volume"] = "no volume spike"

        # ── Factor 5: Market structure (basic HH/HL or LL/LH) ────────────────
        if candles and len(candles) >= 4:
            highs = [c["high"] for c in candles]
            lows = [c["low"] for c in candles]
            if direction == "UP" and highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                score += 1
                factors["structure"] = "HH+HL (bullish structure)"
            elif direction == "DOWN" and highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                score += 1
                factors["structure"] = "LL+LH (bearish structure)"
            else:
                factors["structure"] = "structure not confirmed"

        # ── Factor 6: RSI not counter-directional ─────────────────────────────
        rsi = self._calc_rsi(candles) if candles else 50
        if direction == "UP" and rsi < 70:
            score += 1
            factors["rsi"] = f"RSI {rsi:.0f} (not overbought)"
        elif direction == "DOWN" and rsi > 30:
            score += 1
            factors["rsi"] = f"RSI {rsi:.0f} (not oversold)"
        else:
            factors["rsi"] = f"RSI {rsi:.0f} (counter-directional — skip)"

        # ── Factor 7: Token price < 40¢ ───────────────────────────────────────
        token_price = up_price if direction == "UP" else down_price
        if token_price < MAX_ENTRY_PRICE:
            score += 1
            factors["entry_price"] = f"{token_price*100:.1f}¢ (valid R:R)"
        else:
            factors["entry_price"] = f"{token_price*100:.1f}¢ (too expensive)"

        # ── Factor 8: Oracle agreement (price direction) ──────────────────────
        if candles and len(candles) >= 2:
            price_change = candles[-1]["close"] - candles[-2]["close"]
            if (direction == "UP" and price_change > 0) or (direction == "DOWN" and price_change < 0):
                score += 1
                factors["oracle"] = f"price delta agrees ({price_change:+.1f})"
            else:
                factors["oracle"] = f"price delta disagrees ({price_change:+.1f})"

        # ── Factor 9: Entry timing (first 90s of window) ──────────────────────
        if seconds_remaining > MIN_SECONDS_REMAINING:
            score += 1
            factors["timing"] = f"{seconds_remaining}s remaining (early entry)"
        else:
            factors["timing"] = f"{seconds_remaining}s remaining (too late)"

        # ── Factor 10: Trading session (London or NY) ─────────────────────────
        if self._in_trading_session():
            score += 1
            factors["session"] = "active session (London/NY)"
        else:
            factors["session"] = "outside optimal hours"

        # ── Decision ──────────────────────────────────────────────────────────
        should_trade = score >= MIN_CONFLUENCE and token_price < MAX_ENTRY_PRICE and seconds_remaining > MIN_SECONDS_REMAINING

        # Stake: scale by score
        if score >= 8:
            stake = MAX_STAKE       # $15 — high conviction
        elif score >= 6:
            stake = MAX_STAKE * 0.67  # $10 — medium conviction
        else:
            stake = 0

        return {
            "should_trade": should_trade,
            "direction": direction,
            "score": score,
            "max_score": 10,
            "stake": stake,
            "token_price": token_price,
            "jc_level": jc,
            "factors": factors,
            "reason": f"Score {score}/10 {'✅ TRADE' if should_trade else '❌ SKIP'}: {jc['label']} ({direction})",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Risk checks
    # ─────────────────────────────────────────────────────────────────────────

    async def check_risk_gates(self, wallet_balance: float) -> dict:
        """Check all risk rules before trading. Returns {ok: bool, reason: str}"""
        if wallet_balance < MIN_BALANCE:
            return {"ok": False, "reason": f"Balance ${wallet_balance:.2f} < ${MIN_BALANCE} minimum"}

        # Daily loss check
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT COALESCE(SUM(simulated_pnl), 0) as total FROM paper_trades
                       WHERE created_at > NOW() - INTERVAL '24 hours' AND resolution IS NOT NULL""")
                today_pnl = float(row['total']) if row else 0
                if today_pnl <= -DAILY_LOSS_LIMIT:
                    return {"ok": False, "reason": f"Daily loss limit hit (${today_pnl:.2f})"}

                # Consecutive loss days check
                row2 = await conn.fetchrow(
                    """SELECT COUNT(*) as cnt FROM (
                         SELECT DATE(created_at) as day, SUM(simulated_pnl) as daily_pnl
                         FROM paper_trades WHERE resolution IS NOT NULL
                         GROUP BY day ORDER BY day DESC LIMIT 3
                       ) x WHERE daily_pnl < 0""")
                loss_days = int(row2['cnt']) if row2 else 0
                if loss_days >= CONSECUTIVE_LOSS_DAYS:
                    return {"ok": False, "reason": f"Auto-stopped: {loss_days} consecutive losing days"}

                # 15-minute wallet spend check — covers BOTH paper and live trades
                row3 = await conn.fetchrow(
                    """SELECT
                         COALESCE((SELECT SUM(stake_usd) FROM paper_trades WHERE created_at > NOW() - INTERVAL '15 minutes'), 0) +
                         COALESCE((SELECT SUM(stake_usd) FROM live_trades WHERE created_at > NOW() - INTERVAL '15 minutes'), 0)
                         AS spent""")
                spent_15min = float(row3['spent']) if row3 else 0
                if spent_15min and wallet_balance > 0 and spent_15min > wallet_balance * WALLET_15MIN_PCT:
                    return {"ok": False, "reason": f"ALERT: ${spent_15min:.2f} spent in 15min (>{WALLET_15MIN_PCT*100:.0f}% of wallet) — HALTED"}
        except Exception as e:
            log.warning(f"Risk check DB error: {e}")

        return {"ok": True, "reason": "All risk gates passed"}

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _get_nearest_jc_level(self, btc_price: float) -> dict:
        """Get nearest JC level from DB, fallback to defaults."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM jc_levels WHERE active=true ORDER BY price")
                if rows:
                    levels = [{k: v for k,v in r.items()} for r in rows]
                    return min(levels, key=lambda l: abs(float(l["price"]) - btc_price))
        except Exception:
            pass
        # Fallback to defaults
        if DEFAULT_JC_LEVELS:
            return min(DEFAULT_JC_LEVELS, key=lambda l: abs(l["price"] - btc_price))
        return None

    async def _get_btc_price(self) -> float:
        import time
        now = time.time()
        if self._btc_cache and now - self._btc_cache_ts < 10:
            return self._btc_cache
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
                price = float(r.json()["price"])
                self._btc_cache = price
                self._btc_cache_ts = now
                return price
        except Exception as e:
            log.warning(f"BTC price fetch failed: {e}")
            return None

    async def _get_candles(self, limit: int = 5) -> list:
        import time
        now = time.time()
        if self._candles_cache and now - self._candles_cache_ts < 30:
            return self._candles_cache
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit={limit}")
                candles = [{"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                            "close": float(c[4]), "volume": float(c[5])} for c in r.json()]
                self._candles_cache = candles
                self._candles_cache_ts = now
                return candles
        except Exception as e:
            log.warning(f"Candle fetch failed: {e}")
            return []

    def _calc_rsi(self, candles: list, period: int = 14) -> float:
        if not candles or len(candles) < 2:
            return 50
        closes = [c["close"] for c in candles]
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        if not gains:
            return 50
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _in_trading_session(self) -> bool:
        """London (13:00-21:30 IST) or NY (18:30-01:30 IST)."""
        now_ist = datetime.now(IST)
        hour = now_ist.hour + now_ist.minute / 60
        london = 13.0 <= hour <= 21.5
        ny = hour >= 18.5 or hour <= 1.5
        return london or ny
