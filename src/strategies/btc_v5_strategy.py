"""
BTC V5 Strategy — Signal Engine Direction + JC Confluence + Risk Gates
CEO Fix 2026-04-14: JC levels are CONFLUENCE, not a gate.

Direction comes from the 7-factor signal engine (price delta, momentum,
volume imbalance, oracle lead, book imbalance, volatility, time decay).
JC levels ADD confluence (+1 or +2) when price is near a level that
agrees with direction. Trades happen WITHOUT JC proximity.

Risk gates are mandatory. Entry price < 50c (R:R >= 1:1).
Paper only until CEO approves live.
"""

import json
import logging
import time
import httpx
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytz

log = logging.getLogger("btc_v5_strategy")

# ── Risk Constants ────────────────────────────────────────────────────────────
MAX_STAKE = 15.0
MIN_BALANCE = 50.0
DAILY_LOSS_LIMIT = 30.0
CONSECUTIVE_LOSS_DAYS = 3
WALLET_15MIN_PCT = 0.10
MAX_TRADES_PER_HOUR = 8
MAX_ENTRY_PRICE = 0.50        # < 50c (V3 rule: R:R >= 1:1)
MIN_SECONDS_REMAINING = 60    # Enter with at least 60s left (was 210 — too restrictive)
PAPER_STARTING_BANKROLL = 10000.0
IST = pytz.timezone("Asia/Calcutta")

# Stake scaling from V3 STRATEGY.md
# <20c=$75, 20-30c=$50, 30-40c=$35, 40-50c=$25
STAKE_TIERS = [
    (0.20, 75),
    (0.30, 50),
    (0.40, 35),
    (0.50, 25),
]

# Telegram config — @ArbitrageBihariBot
TG_BOT_TOKEN = "8610642342:AAEKNxrbvUdJM-djnHs0RKL-82z3MrBVC24"
TG_CHAT_IDS = ["1656605843"]

# ── JC Level Defaults ────────────────────────────────────────────────────────
DEFAULT_JC_LEVELS = [
    {"price": 85500, "label": "SPV resistance", "level_type": "SPV", "direction": "resistance", "strength": 10},
    {"price": 84000, "label": "Current resistance zone", "level_type": "resistance", "direction": "resistance", "strength": 7},
    {"price": 83000, "label": "Support level", "level_type": "support", "direction": "support", "strength": 6},
    {"price": 82000, "label": "Key support", "level_type": "support", "direction": "support", "strength": 8},
    {"price": 80000, "label": "Round number POC", "level_type": "POC", "direction": "support", "strength": 8},
    {"price": 75905, "label": "SPV sweep zone", "level_type": "SPV", "direction": "support", "strength": 5},
    {"price": 74967, "label": "D Level", "level_type": "resistance", "direction": "support", "strength": 5},
    {"price": 73974, "label": "nwPOC (naked weekly)", "level_type": "POC", "direction": "support", "strength": 5},
    {"price": 72829, "label": "SPV of SPV - NY Open", "level_type": "SPV", "direction": "support", "strength": 5},
]


def _tg_send(text: str):
    import urllib.request, urllib.parse
    for chat_id in TG_CHAT_IDS:
        try:
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                data=data, timeout=8)
        except Exception as e:
            log.warning(f"TG send failed: {e}")


async def tg_send(text: str):
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _tg_send, text)


def _get_stake(token_price: float) -> float:
    """V3 stake scaling: bigger bets on better odds."""
    for threshold, stake in STAKE_TIERS:
        if token_price < threshold:
            return stake
    return 0  # > 50c = don't trade


class BTCV5Strategy:
    """
    V5: Signal engine direction + JC confluence + risk gates.
    Direction from 7-factor engine. JC levels = bonus. Paper only.
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool

    # ═════════════════════════════════════════════════════════════════════════
    # RISK GATES — Called before EVERY trade, no exceptions
    # ═════════════════════════════════════════════════════════════════════════

    async def check_risk_gates(self) -> dict:
        try:
            async with self.db_pool.acquire() as conn:
                br = await conn.fetchrow("SELECT balance FROM btc_bankroll WHERE id=1")
                bankroll = float(br['balance']) if br else PAPER_STARTING_BANKROLL

                if bankroll < MIN_BALANCE:
                    return {"ok": False, "reason": f"Bankroll ${bankroll:.2f} < ${MIN_BALANCE}", "bankroll": bankroll}

                row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(simulated_pnl), 0) as total
                    FROM paper_trades
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    AND resolved_at IS NOT NULL AND strategy_version = 'V5'""")
                today_pnl = float(row['total']) if row else 0
                if today_pnl <= -DAILY_LOSS_LIMIT:
                    return {"ok": False, "reason": f"Daily loss ${today_pnl:.2f} hit limit", "bankroll": bankroll}

                rows = await conn.fetch("""
                    SELECT DATE(created_at) as day, SUM(simulated_pnl) as daily_pnl
                    FROM paper_trades WHERE resolved_at IS NOT NULL AND strategy_version = 'V5'
                    GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 3""")
                loss_days = sum(1 for r in rows if float(r['daily_pnl']) < 0)
                if loss_days >= CONSECUTIVE_LOSS_DAYS:
                    return {"ok": False, "reason": f"{loss_days} consecutive losing days", "bankroll": bankroll}

                row3 = await conn.fetchrow("""
                    SELECT COALESCE(SUM(stake_usd), 0) as spent
                    FROM paper_trades WHERE created_at > NOW() - INTERVAL '15 minutes'
                    AND strategy_version = 'V5'""")
                spent_15min = float(row3['spent']) if row3 else 0
                if bankroll > 0 and spent_15min > bankroll * WALLET_15MIN_PCT:
                    return {"ok": False, "reason": f"15min spend cap hit", "bankroll": bankroll}

                row4 = await conn.fetchrow("""
                    SELECT COUNT(*) as cnt FROM paper_trades
                    WHERE created_at > NOW() - INTERVAL '1 hour' AND strategy_version = 'V5'""")
                hourly_count = int(row4['cnt']) if row4 else 0
                if hourly_count >= MAX_TRADES_PER_HOUR:
                    return {"ok": False, "reason": f"Hourly cap {hourly_count}/{MAX_TRADES_PER_HOUR}", "bankroll": bankroll}

                return {"ok": True, "reason": "All risk gates passed", "bankroll": bankroll}

        except Exception as e:
            log.error(f"Risk gate error: {e}")
            return {"ok": False, "reason": f"Risk check failed: {e}", "bankroll": 0}

    # ═════════════════════════════════════════════════════════════════════════
    # EVALUATE — Use signal engine direction + JC confluence
    # ═════════════════════════════════════════════════════════════════════════

    async def evaluate(self, window_id: str, up_price: float, down_price: float,
                       seconds_remaining: int, engine_prediction: str,
                       engine_prob_up: float, engine_confidence: float,
                       engine_factors: dict, btc_price: float) -> dict:
        """
        Decide whether to trade based on:
        1. Signal engine direction (from 7 factors) — MANDATORY
        2. Entry price / R:R — MANDATORY (< 50c)
        3. Timing — MANDATORY (> 210s remaining)
        4. JC level confluence — BONUS (adds confidence)
        
        Returns: {should_trade, direction, stake, token_price, factors, reason}
        """
        factors = {}
        
        # ── Direction from signal engine ──────────────────────────────────
        if engine_prediction == 'SKIP':
            return {"should_trade": False, "reason": "Signal engine: SKIP (no clear direction)",
                    "direction": None, "score": 0, "factors": {"engine": "SKIP"}}
        
        direction = engine_prediction  # 'UP' or 'DOWN'
        token_price = up_price if direction == "UP" else down_price
        
        factors["engine_direction"] = f"{direction} (prob_up={engine_prob_up:.2f}, confidence={engine_confidence:.2f})"
        factors["engine_factors"] = {k: round(v, 3) if isinstance(v, float) else v 
                                      for k, v in engine_factors.items() 
                                      if k.startswith('f_') and not isinstance(v, bool)}
        
        # ── Entry price gate (V3 rule: R:R >= 1:1, max 50c) ─────────────
        if token_price >= MAX_ENTRY_PRICE:
            rr = (1 - token_price) / token_price if token_price > 0 else 0
            return {"should_trade": False, 
                    "reason": f"Entry {token_price*100:.1f}c too expensive (R:R {rr:.1f}:1, need < 50c)",
                    "direction": direction, "score": 0, 
                    "factors": {**factors, "entry": f"{token_price*100:.1f}c REJECTED"}}
        
        rr = (1 - token_price) / token_price
        factors["entry_price"] = f"{token_price*100:.1f}c | R:R {rr:.1f}:1"
        
        # ── Timing gate ──────────────────────────────────────────────────
        if seconds_remaining <= MIN_SECONDS_REMAINING:
            return {"should_trade": False,
                    "reason": f"Too late: {seconds_remaining}s remaining (need >{MIN_SECONDS_REMAINING}s)",
                    "direction": direction, "score": 0, "factors": factors}
        
        factors["timing"] = f"{seconds_remaining}s remaining ✅"
        
        # ── Confidence check (engine must have some conviction) ──────────
        if engine_confidence < 0.15:
            return {"should_trade": False,
                    "reason": f"Low confidence: {engine_confidence:.2f} (need >= 0.15)",
                    "direction": direction, "score": 0, "factors": factors}
        
        factors["confidence"] = f"{engine_confidence:.2f} ✅"
        
        # ── JC Level confluence (BONUS, not required) ────────────────────
        jc = await self._get_nearest_jc_level(btc_price)
        jc_bonus = 0
        jc_label = "none nearby"
        if jc:
            jc_price = float(jc["price"])
            distance_pct = abs(btc_price - jc_price) / btc_price
            jc_direction = "UP" if jc.get("direction") == "support" else "DOWN"
            
            if distance_pct < 0.01:  # Within 1%
                if jc_direction == direction:
                    # JC level agrees with our direction
                    lt = jc.get("level_type", "")
                    if lt in ("SPV", "CDW"):
                        jc_bonus = 2
                        jc_label = f"{jc['label']} ({distance_pct*100:.2f}% away, AGREES, {lt} +2)"
                    else:
                        jc_bonus = 1
                        jc_label = f"{jc['label']} ({distance_pct*100:.2f}% away, agrees +1)"
                else:
                    jc_label = f"{jc['label']} ({distance_pct*100:.2f}% away, DISAGREES — caution)"
            else:
                jc_label = f"{jc['label']} ({distance_pct*100:.1f}% away, no effect)"
        
        factors["jc_confluence"] = jc_label
        
        # ── Stake from V3 tiers ──────────────────────────────────────────
        stake = _get_stake(token_price)
        if stake == 0:
            return {"should_trade": False, "reason": "No stake tier for this price",
                    "direction": direction, "score": 0, "factors": factors}
        
        # Scale stake down if confidence is moderate
        if engine_confidence < 0.5:
            stake = stake * 0.5  # Half stake on lower confidence
            factors["stake_adj"] = "50% (moderate confidence)"
        
        # ── TRADE! ───────────────────────────────────────────────────────
        score = round(engine_confidence * 10) + jc_bonus  # 0-12 scale
        
        return {
            "should_trade": True,
            "direction": direction,
            "score": score,
            "stake": round(stake, 2),
            "token_price": token_price,
            "btc_price": btc_price,
            "jc_level": jc_label,
            "jc_bonus": jc_bonus,
            "rr": round(rr, 1),
            "factors": factors,
            "reason": f"✅ TRADE {direction} | {token_price*100:.1f}c | ${stake} | confidence={engine_confidence:.2f} | JC bonus +{jc_bonus}",
        }

    # ═════════════════════════════════════════════════════════════════════════
    # RESOLVE — Check if paper trade windows have closed, score win/loss
    # ═════════════════════════════════════════════════════════════════════════

    async def resolve_open_trades(self) -> list:
        resolved = []
        try:
            async with self.db_pool.acquire() as conn:
                open_trades = await conn.fetch("""
                    SELECT pt.id, pt.window_id, pt.direction, pt.token_price,
                           pt.stake_usd, pt.confluence_score, pt.factors_json, pt.jc_level,
                           pt.created_at
                    FROM paper_trades pt
                    WHERE pt.resolved_at IS NULL AND pt.strategy_version = 'V5'
                    ORDER BY pt.created_at ASC""")

                if not open_trades:
                    return []

                for trade in open_trades:
                    window = await conn.fetchrow("""
                        SELECT resolution, btc_open, btc_close, close_time
                        FROM btc_windows
                        WHERE window_id = $1 AND resolution IS NOT NULL""",
                        trade['window_id'])

                    if not window:
                        continue

                    actual = window['resolution']
                    direction = trade['direction']
                    token_price = float(trade['token_price'])
                    stake = float(trade['stake_usd'])
                    won = (direction == actual)

                    if won:
                        payout = stake / token_price
                        pnl = payout - stake
                    else:
                        pnl = -stake

                    btc_open = float(window['btc_open'] or 0)
                    btc_close = float(window['btc_close'] or 0)
                    btc_move = btc_close - btc_open

                    await conn.execute("""
                        UPDATE paper_trades
                        SET resolution = $1, won = $2, simulated_pnl = $3, resolved_at = NOW()
                        WHERE id = $4""", actual, won, round(pnl, 2), trade['id'])

                    if won:
                        await conn.execute("""
                            UPDATE btc_bankroll SET
                                balance = balance + $1, available = available + $1,
                                total_won = total_won + $1, total_trades = total_trades + 1,
                                peak_balance = GREATEST(peak_balance, balance + $1),
                                updated_at = NOW()
                            WHERE id = 1""", round(pnl, 2))
                    else:
                        await conn.execute("""
                            UPDATE btc_bankroll SET
                                balance = balance + $1, available = available + $1,
                                total_lost = total_lost + $2, total_trades = total_trades + 1,
                                updated_at = NOW()
                            WHERE id = 1""", round(pnl, 2), round(abs(pnl), 2))

                    result_emoji = "✅" if won else "❌"
                    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"

                    br = await conn.fetchrow("SELECT balance, total_trades FROM btc_bankroll WHERE id=1")
                    new_balance = float(br['balance']) if br else 0

                    stats = await conn.fetchrow("""
                        SELECT COUNT(*) as total,
                               COUNT(*) FILTER (WHERE won = true) as wins,
                               COALESCE(SUM(simulated_pnl), 0) as total_pnl
                        FROM paper_trades
                        WHERE strategy_version = 'V5' AND resolved_at IS NOT NULL""")

                    win_rate = (float(stats['wins']) / float(stats['total']) * 100) if stats and float(stats['total']) > 0 else 0
                    total_pnl = float(stats['total_pnl']) if stats else 0

                    # Parse factors for reason summary
                    factors_data = {}
                    try:
                        if trade['factors_json']:
                            factors_data = json.loads(trade['factors_json']) if isinstance(trade['factors_json'], str) else dict(trade['factors_json'])
                    except: pass
                    reason_lines = []
                    for k, v in factors_data.items():
                        if k not in ('engine_factors',):
                            reason_lines.append(f"  {k}: {v}")
                    reason_str = '\n'.join(reason_lines[:5]) if reason_lines else '  Signal engine confluence'

                    msg = (
                        f"{result_emoji} {'WON' if won else 'LOST'} | {pnl_str}\n"
                        f"{'='*30}\n"
                        f"Position: {'🟢 LONG' if direction=='UP' else '🔴 SHORT'}\n"
                        f"Entry: {token_price*100:.1f}c | Stake: ${stake:.2f}\n"
                        f"BTC: ${btc_open:,.0f} -> ${btc_close:,.0f} ({btc_move:+,.0f})\n"
                        f"Outcome: {actual}\n"
                        f"{'='*30}\n"
                        f"Reason:\n{reason_str}\n"
                        f"{'='*30}\n"
                        f"Bankroll: ${new_balance:,.2f} | P&L: {pnl_str}\n"
                        f"Record: {stats['wins']}W-{int(stats['total'])-int(stats['wins'])}L ({win_rate:.0f}%)\n"
                        f"Total P&L: ${total_pnl:+,.2f}\n"
                        f"PAPER MODE"
                    )
                    await tg_send(msg)

                    resolved.append({
                        "id": trade['id'], "window_id": trade['window_id'],
                        "direction": direction, "actual": actual,
                        "won": won, "pnl": round(pnl, 2), "bankroll": new_balance,
                    })

                    log.info(f"{'✅' if won else '❌'} V5 resolved #{trade['id']}: "
                             f"{direction} vs {actual} | P&L ${pnl:+.2f} | Bankroll ${new_balance:,.2f}")

        except Exception as e:
            log.error(f"V5 resolution error: {e}")

        return resolved

    # ═════════════════════════════════════════════════════════════════════════
    # Helpers
    # ═════════════════════════════════════════════════════════════════════════

    async def _get_nearest_jc_level(self, btc_price: float) -> dict:
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM jc_levels WHERE active=true ORDER BY price")
                if rows:
                    levels = [{k: v for k, v in r.items()} for r in rows]
                    return min(levels, key=lambda l: abs(float(l["price"]) - btc_price))
        except Exception:
            pass
        return min(DEFAULT_JC_LEVELS, key=lambda l: abs(l["price"] - btc_price))
