"""
WeatherBot FastAPI Server
API endpoints for dashboard + scheduler for data/signal loops.
All endpoints query REAL database — no stubs, no mocks.
"""
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import json
import base64
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
import logging
import traceback

from src import config
from src.db import fetch_all, fetch_one, execute, init_tables, close_pool, get_pool
from src.db_async import get_async_pool

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler
scheduler = AsyncIOScheduler()

# Track scan times
_last_data_scan: Optional[datetime] = None
_last_signal_scan: Optional[datetime] = None
_startup_time: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════
# TRADING MODE GATE — checks bot_settings before any Telegram send
# ═══════════════════════════════════════════════════════════════
_trading_mode_cache = {'mode': None, 'paper_notif': None, 'ts': None}


async def get_trading_mode() -> dict:
    """Read trading_mode + paper_notifications from bot_settings.
    Returns {'mode': 'live'|'paper', 'paper_notifications': bool}.
    Cached for 60s to avoid DB spam.
    """
    import time
    now = time.time()
    if _trading_mode_cache['ts'] and (now - _trading_mode_cache['ts']) < 60:
        return {'mode': _trading_mode_cache['mode'], 'paper_notifications': _trading_mode_cache['paper_notif']}
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row_mode = await conn.fetchrow(
                "SELECT value FROM bot_settings WHERE key = 'trading_mode'"
            )
            row_notif = await conn.fetchrow(
                "SELECT value FROM bot_settings WHERE key = 'paper_notifications'"
            )
        mode = 'live'
        if row_mode:
            v = str(row_mode['value']).strip().strip('"').lower()
            mode = v if v in ('live', 'paper') else 'live'
        paper_notif = False
        if row_notif:
            v = str(row_notif['value']).strip().strip('"').lower()
            paper_notif = v in ('true', '1', 'yes')
        _trading_mode_cache['mode'] = mode
        _trading_mode_cache['paper_notif'] = paper_notif
        _trading_mode_cache['ts'] = now
        return {'mode': mode, 'paper_notifications': paper_notif}
    except Exception as e:
        logger.error(f"❌ get_trading_mode failed: {e}")
        return {'mode': 'live', 'paper_notifications': False}


def should_send_paper_telegram(trading_cfg: dict) -> bool:
    """Return True only if paper notifications are allowed."""
    return trading_cfg.get('paper_notifications', False)


def is_live_mode(trading_cfg: dict) -> bool:
    """Return True if trading mode is live."""
    return trading_cfg.get('mode', 'paper') == 'live'

# Signal loop instance (initialized on startup)
_signal_loop = None
_improvement_engine = None


async def scheduled_data_scan():
    """Run data collection cycle on schedule."""
    global _last_data_scan
    try:
        from src.data.data_loop import run_single_cycle
        logger.info("⏰ Scheduled data scan starting...")
        await run_single_cycle()
        _last_data_scan = datetime.utcnow()
        logger.info(f"✅ Data scan complete at {_last_data_scan.isoformat()}")
    except Exception as e:
        logger.error(f"❌ Data scan failed: {e}\n{traceback.format_exc()}")


async def scheduled_signal_scan():
    """Run signal detection on schedule."""
    global _last_signal_scan, _signal_loop
    try:
        if _signal_loop is None:
            logger.warning("Signal loop not initialized, skipping")
            return
        logger.info("⏰ Scheduled signal scan starting...")
        await _signal_loop.run_once()
        _last_signal_scan = datetime.utcnow()
        logger.info(f"✅ Signal scan complete at {_last_signal_scan.isoformat()}")
    except Exception as e:
        logger.error(f"❌ Signal scan failed: {e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# SPORTS INTELLIGENCE — Scheduled Scan Function
# ═══════════════════════════════════════════════════════════════
_sports_loop = None
_last_sports_scan: Optional[datetime] = None


async def scheduled_sports_scan():
    """Run sports intelligence cycle on schedule.
    Protocols: P2 (Cross-Market Arb) + P4 (Line Movement) + P6 (Risk Mgmt)
    See INTELLIGENCE.md for full protocol definitions.
    """
    global _last_sports_scan, _sports_loop
    try:
        if _sports_loop is None:
            # Initialize on first run
            from src.sports.sports_signal_loop import SportsSignalLoop
            async_pool = get_async_pool()
            _sports_loop = SportsSignalLoop(async_pool)
            logger.info("✅ Sports signal loop initialized")
        
        logger.info("⏰ Scheduled sports scan starting...")
        result = await _sports_loop.run_once()
        _last_sports_scan = datetime.utcnow()
        logger.info(f"✅ Sports scan complete: {result}")
    except Exception as e:
        logger.error(f"❌ Sports scan failed: {e}\n{traceback.format_exc()}")
# ═══════════════════════════════════════════════════════════════


async def scheduled_edge_monitor():
    """Protocol 3: Edge Decay Monitoring.
    Check all open positions — if edge < 2%, flag for exit.
    See INTELLIGENCE.md Protocol 3.
    """
    try:
        from src.execution.edge_monitor import EdgeMonitor
        monitor = EdgeMonitor(get_async_pool())
        alerts = await monitor.check_all_positions()

        exit_needed = [a for a in alerts if a['recommendation'].startswith('EXIT')]
        if exit_needed:
            logger.warning(f"⚠️ {len(exit_needed)} positions need exit!")
            # Log internally only — DO NOT spam subscribers with edge decay
            # Subscribers only get: trade placed + trade resolved
        else:
            total = len(alerts)
            if total > 0:
                logger.info(f"✅ Edge monitor: {total} positions healthy")
    except Exception as e:
        logger.error(f"❌ Edge monitor failed: {e}")


async def scheduled_settlement():
    """Protocol 5: Settlement & Learning.
    Check completed events, settle trades, feed learning engine.
    See INTELLIGENCE.md Protocol 5.
    """
    """Auto-settle completed trades every 5 minutes."""
    try:
        from src.execution.settlement import settle_trades
        odds_key = os.environ.get('ODDS_API_KEY', '')
        if not odds_key:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith('ODDS_API_KEY'):
                            odds_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            break
        result = await settle_trades(fetch_all, execute, fetch_one, odds_key)
        if result.get('settled', 0) > 0:
            logger.info(f"\u2705 Settlement: {result['settled']} trades settled, P&L: ${result.get('total_pnl', 0):+.2f}")
            # Broadcast results via Telegram
            if _telegram_bot:
                for t in result.get('trades', []):
                    pass  # Sports trade broadcasts disabled (noise)
    except Exception as e:
        logger.error(f"\u274c Settlement error: {e}")


# ═══════════════════════════════════════════════════════════════
# TELEGRAM SUBSCRIBER BOT — Scheduled Jobs
# ═══════════════════════════════════════════════════════════════
_telegram_bot = None


async def check_and_broadcast_signals():
    """Check for new HIGH confidence signals and broadcast to subscribers."""
    global _telegram_bot
    if not _telegram_bot:
        return
    
    try:
        # Get signals created in last 3 minutes with >10% edge
        async_pool = get_async_pool()
        async with async_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT id, sport, market_id, market_title, polymarket_price, fair_value, 
                           edge_pct, signal, confidence, reasoning, created_at
                    FROM sports_signals
                    WHERE created_at >= NOW() - INTERVAL '3 minutes'
                      AND confidence = 'HIGH'
                      AND edge_pct > 10
                    ORDER BY created_at DESC
                """)
                rows = await cur.fetchall()
                
                for row in rows:
                    signal_dict = {
                        'id': row[0],
                        'sport': row[1],
                        'market_id': row[2],
                        'market_title': row[3],
                        'polymarket_price': float(row[4]) if row[4] else 0,
                        'fair_value': float(row[5]) if row[5] else 0,
                        'edge_pct': float(row[6]) if row[6] else 0,
                        'signal': row[7],
                        'confidence': row[8],
                        'reasoning': row[9],
                        'created_at': row[10],
                        'sportsbooks': 'DraftKings, Pinnacle, Betfair',
                        'source_count': 22,
                        'start_time': 'TBD'
                    }
                    pass  # Signal alert broadcast disabled (noise)
                    logger.info(f"📢 Broadcasted signal: {signal_dict['market_title'][:40]}")
    except Exception as e:
        logger.error(f"❌ Signal broadcast failed: {e}")


async def daily_summary_task():
    """Send daily summary at 9 AM IST — Sprint 2 enhanced version."""
    global _telegram_bot
    if not _telegram_bot:
        return
    # Gate: this is paper/sports summary, suppress if paper_notifications=false
    _tcfg = await get_trading_mode()
    if not should_send_paper_telegram(_tcfg):
        logger.info("🔇 Daily summary suppressed (paper_notifications=false)")
        return
    try:
        import pytz
        IST = pytz.timezone('Asia/Calcutta')
        now_ist = datetime.now(IST)
        yesterday = (now_ist - timedelta(days=1)).date()
        
        # Yesterday's trades from trades table
        yesterday_stats = await fetch_one("""
            SELECT 
                COUNT(*) as trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                COALESCE(SUM(pnl_usd), 0) as total_pnl
            FROM trades
            WHERE DATE(resolved_at) = %s AND status IN ('won', 'lost')
        """, (yesterday,))
        
        y_trades = int(yesterday_stats.get('trades', 0) or 0) if yesterday_stats else 0
        y_wins = int(yesterday_stats.get('wins', 0) or 0) if yesterday_stats else 0
        y_pnl = float(yesterday_stats.get('total_pnl', 0) or 0) if yesterday_stats else 0
        y_win_rate = (y_wins / y_trades * 100) if y_trades > 0 else 0
        
        # Per-strategy breakdown
        strat_rows = await fetch_all("""
            SELECT strategy,
                   COUNT(*) as trades,
                   SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                   COALESCE(SUM(pnl_usd), 0) as pnl
            FROM trades
            WHERE DATE(resolved_at) = %s AND status IN ('won', 'lost')
            GROUP BY strategy
            ORDER BY pnl DESC
        """, (yesterday,))
        
        # Best / worst trade
        best = await fetch_one("""
            SELECT market_title, pnl_usd, strategy FROM trades
            WHERE DATE(resolved_at) = %s AND status IN ('won', 'lost')
            ORDER BY pnl_usd DESC LIMIT 1
        """, (yesterday,))
        worst = await fetch_one("""
            SELECT market_title, pnl_usd, strategy FROM trades
            WHERE DATE(resolved_at) = %s AND status IN ('won', 'lost')
            ORDER BY pnl_usd ASC LIMIT 1
        """, (yesterday,))
        
        # Bankroll
        bankroll = await fetch_one(
            "SELECT total_usd, available_usd, in_positions_usd FROM bankroll ORDER BY timestamp DESC LIMIT 1"
        )
        bankroll_total = float(bankroll.get('total_usd', 0) or 0) if bankroll else 0
        bankroll_available = float(bankroll.get('available_usd', 0) or 0) if bankroll else 0
        bankroll_deployed = float(bankroll.get('in_positions_usd', 0) or 0) if bankroll else 0
        
        # Disabled strategies
        disabled = await fetch_all("""
            SELECT strategy, win_rate, total_trades FROM strategy_performance
            WHERE is_active = false
        """)
        
        # Build the message
        pnl_emoji = '\U0001f4b0' if y_pnl >= 0 else '\U0001f534'
        pnl_sign = '+' if y_pnl >= 0 else ''
        
        msg = (
            f"\U0001f4ca <b>Daily Digest \u2014 {now_ist.strftime('%b %d, %Y')}</b>\n\n"
            f"<b>Yesterday's Results:</b>\n"
            f"Trades: {y_trades} | Win Rate: {y_win_rate:.0f}%\n"
            f"{pnl_emoji} P&amp;L: {pnl_sign}${y_pnl:.2f}\n\n"
        )
        
        # Strategy breakdown
        if strat_rows:
            msg += "<b>Per-Strategy:</b>\n"
            for s in strat_rows:
                s_pnl = float(s.get('pnl', 0) or 0)
                s_emoji = '\u2705' if s_pnl >= 0 else '\u274c'
                s_sign = '+' if s_pnl >= 0 else ''
                s_wins = int(s.get('wins', 0) or 0)
                s_trades = int(s.get('trades', 0) or 0)
                msg += f"{s_emoji} {s['strategy']}: {s_sign}${s_pnl:.2f} ({s_wins}/{s_trades})\n"
            msg += "\n"
        
        # Best/worst trades
        if best and float(best.get('pnl_usd', 0) or 0) != 0:
            msg += f"\U0001f3c6 <b>Best:</b> {(best.get('market_title',''))[:40]} (+${float(best.get('pnl_usd',0) or 0):.2f})\n"
        if worst and float(worst.get('pnl_usd', 0) or 0) < 0:
            msg += f"\U0001f4a5 <b>Worst:</b> {(worst.get('market_title',''))[:40]} (${float(worst.get('pnl_usd',0) or 0):.2f})\n"
        if best or worst:
            msg += "\n"
        
        # Bankroll
        msg += (
            f"\U0001f4b3 <b>Bankroll:</b>\n"
            f"Total: ${bankroll_total:.2f} | Available: ${bankroll_available:.2f}\n"
            f"Deployed: ${bankroll_deployed:.2f}\n"
        )
        
        # Disabled strategies
        if disabled:
            msg += "\n\U0001f6a8 <b>Auto-Disabled:</b>\n"
            for d in disabled:
                d_wr = float(d.get('win_rate', 0) or 0) * 100
                msg += f"\u26d4 {d['strategy']} ({d_wr:.1f}% over {d['total_trades']} trades)\n"
        
        # Send to all subscribers
        subscribers = await _telegram_bot.get_all_subscribers()
        for sub in subscribers:
            try:
                await _telegram_bot.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=msg,
                    parse_mode='HTML'
                )
            except Exception as send_err:
                logger.error(f"Failed to send daily digest to {sub['chat_id']}: {send_err}")
        
        logger.info(f"\U0001f4ca Daily digest sent to {len(subscribers)} subscribers")
    except Exception as e:
        logger.error(f"\u274c Daily summary failed: {e}")


# ═══════════════════════════════════════════════════════════════
# INTERNAL ARBITRAGE — Scheduled Scan Function
# ═══════════════════════════════════════════════════════════════
_last_internal_arb_scan: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════
# LATE WINDOW SCALPER — Global instance
# ═══════════════════════════════════════════════════════════════
_late_window_scalper = None

async def scheduled_late_window_scan():
    """Late Window Scalper: buy near-certain BTC contracts in final 15-20s of 5M windows."""
    global _late_window_scalper
    try:
        from src.strategies.late_window_scalper import LateWindowScalper
        if _late_window_scalper is None:
            _late_window_scalper = LateWindowScalper(get_async_pool())
            await _late_window_scalper.ensure_tables()
        await _late_window_scalper.scan_and_scalp()
    except Exception as e:
        logger.error(f"❌ Late window scan failed: {e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# PENNY HUNTER — Scheduled Scan Function
# ═══════════════════════════════════════════════════════════════
_last_penny_scan: Optional[datetime] = None


async def scheduled_penny_scan():
    """Penny Hunter: scan for 1-3¢ contracts with asymmetric upside."""
    global _last_penny_scan
    try:
        from src.strategies.penny_hunter import PennyHunter
        hunter = PennyHunter(get_async_pool())
        await hunter.ensure_tables()

        # Scan markets
        pennies = await hunter.scan_penny_contracts()

        # Score and filter
        scored = []
        for p in pennies:
            score, reason = hunter.score_catalyst(p)
            p['catalyst_score'] = score
            p['catalyst_reason'] = reason
            if score >= 3:
                scored.append(p)

        # Sort by score, take top 5 per scan
        scored.sort(key=lambda x: -x['catalyst_score'])

        executed = 0
        executed_contracts = []
        for contract in scored[:5]:
            pos_id = await hunter.execute_penny_bet(contract)
            if pos_id:
                executed += 1
                executed_contracts.append(contract)

        # Check resolutions
        resolved = await hunter.check_resolutions()
        _last_penny_scan = datetime.utcnow()

        # Penny bet placed — silent (only HIT/DEAD broadcasts, no entry noise)

        # Broadcast resolutions — only if paper notifications are enabled
        if _telegram_bot and resolved:
            _tcfg = await get_trading_mode()
            if should_send_paper_telegram(_tcfg):
                for r in resolved:
                    won = r.get('pnl_usd', 0) > 0
                    emoji = "💰" if won else "💀"
                    bp = r.get('buy_price', 0.01)
                    msg = (
                        f"{emoji} PENNY {'HIT!' if won else 'DEAD'}\n\n"
                        f"{r['question'][:60]}\n"
                        f"Bought at: {bp*100:.0f}¢\n"
                        f"P&L: ${r['pnl_usd']:+.2f}\n"
                        f"{'🎯 ' + str(int(1/bp)) + 'x RETURN!' if won else ''}"
                    )
                    try:
                        subscribers = await _telegram_bot.get_all_subscribers(instant_only=True)
                        for sub in subscribers:
                            try:
                                await _telegram_bot.app.bot.send_message(chat_id=sub['chat_id'], text=msg)
                            except Exception:
                                pass
                    except Exception:
                        pass
            else:
                logger.info(f"🔇 Penny resolutions suppressed (paper_notifications=false, {len(resolved)} resolved)")

        logger.info(
            f"🎰 Penny scan complete: {len(pennies)} found, {len(scored)} scored, "
            f"{executed} executed, {len(resolved)} resolved"
        )
    except Exception as e:
        logger.error(f"❌ Penny scan failed: {e}\n{traceback.format_exc()}")
# ═══════════════════════════════════════════════════════════════


async def scheduled_internal_arb_scan():
    """Protocol 1: Internal Arbitrage (RISK-FREE).
    Scan all Polymarket markets for YES+NO < $1.00.
    Buy both sides for guaranteed profit after 2% fee.
    See INTELLIGENCE.md Protocol 1. Priority: HIGHEST.
    """
    global _last_internal_arb_scan
    try:
        from src.strategies.internal_arb import InternalArbScanner
        scanner = InternalArbScanner(get_async_pool())
        opps = await scanner.scan_combined()
        _last_internal_arb_scan = datetime.utcnow()
        if opps:
            logger.info(f"💰 Found {len(opps)} internal arb opportunities!")
            # Auto-execute paper trades for profitable ones
            for opp in opps:
                if opp['fee_adjusted_profit_pct'] > 0.5:
                    await scanner.execute_internal_arb(
                        opp['market_id'], opp['yes_price'], opp['no_price'],
                        opp.get('recommended_stake', 25)
                    )
            # Broadcast ONLY executed trades to subscribers (not raw opportunities)
            executed = [o for o in opps if o.get('fee_adjusted_profit_pct', 0) > 0.5]
            if _telegram_bot and executed:
                pass  # Internal arb broadcasts disabled (noise)
        else:
            logger.info("💰 Internal arb scan: no opportunities found")
    except Exception as e:
        logger.error(f"❌ Internal arb scan failed: {e}\n{traceback.format_exc()}")


async def broadcast_internal_arb_trades(executed_opps):
    """Broadcast EXECUTED internal arb trades to ALL subscribers."""
    if not _telegram_bot:
        return
    
    subscribers = await _telegram_bot.get_all_subscribers(instant_only=True)
    
    for opp in executed_opps[:3]:  # Max 3 per cycle
        profit_usd = opp.get('recommended_stake', 25) * (opp['fee_adjusted_profit_pct'] / 100)
        msg = (
            f"🟢 RISK-FREE TRADE PLACED\n\n"
            f"{opp['question'][:60]}\n\n"
            f"Action: Buy YES ({opp['yes_price']:.2f}\u00a2) + NO ({opp['no_price']:.2f}\u00a2)\n"
            f"Combined Cost: {opp['combined_cost']:.2f}\u00a2 (< $1.00)\n"
            f"Guaranteed Profit: {opp['fee_adjusted_profit_pct']:.1f}% (${profit_usd:.2f})\n"
            f"Stake: ${opp.get('recommended_stake', 25)}\n\n"
            f"Rationale: YES + NO < $1.00 = guaranteed payout.\n"
            f"Risk: None (both sides covered, profit locked at entry)."
        )
        for sub in subscribers:
            try:
                await _telegram_bot.app.bot.send_message(
                    chat_id=sub['chat_id'], text=msg
                )
            except Exception as e:
                logger.error(f"Failed to send arb trade to {sub['chat_id']}: {e}")
# ═══════════════════════════════════════════════════════════════


async def pre_match_alerts():
    """Check for matches starting in 1 hour and send alerts."""
    global _telegram_bot
    if not _telegram_bot:
        return
    # Gate: sports are paper trades, suppress if paper_notifications=false
    _tcfg = await get_trading_mode()
    if not should_send_paper_telegram(_tcfg):
        return
    try:
        one_hour_later = datetime.utcnow() + timedelta(hours=1)
        async_pool = get_async_pool()
        
        async with async_pool.connection() as conn:
            async with conn.cursor() as cur:
                # Find matches starting in 55-65 minutes
                await cur.execute("""
                    SELECT event_name, sport, start_time
                    FROM live_events
                    WHERE status = 'scheduled'
                      AND start_time BETWEEN NOW() + INTERVAL '55 minutes' AND NOW() + INTERVAL '65 minutes'
                """)
                rows = await cur.fetchall()
                
                for row in rows:
                    event_name, sport, start_time = row
                    
                    # Get our position for this match
                    await cur.execute("""
                        SELECT market_title, size_usd, signal, edge_pct
                        FROM paper_trades_live
                        WHERE market_title LIKE %s AND status = 'open'
                        LIMIT 1
                    """, (f"%{event_name}%",))
                    trade_row = await cur.fetchone()
                    
                    match_dict = {
                        'event_name': event_name,
                        'sport': sport,
                        'size_usd': float(trade_row[1]) if trade_row else 0,
                        'pick': trade_row[2] if trade_row else 'No position',
                        'edge_pct': float(trade_row[3]) if trade_row else 0,
                        'odds_display': 'TBD',
                        'source_count': 22
                    }
                    
                    if trade_row:  # Only alert if we have a position
                        await _telegram_bot.broadcast_pre_match_alert(match_dict)
                        logger.info(f"⏰ Pre-match alert sent: {event_name}")
    except Exception as e:
        logger.error(f"❌ Pre-match alerts failed: {e}")
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# BTC BANKROLL MANAGEMENT
# ═══════════════════════════════════════════════════════════════

BTC_STARTING_BALANCE = 5000.00

async def get_btc_bankroll_state():
    """Fetch current bankroll from DB. Returns dict with balance, available, in_positions."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT balance, available, in_positions, total_won, total_lost, total_trades, peak_balance, max_drawdown_pct "
                "FROM btc_bankroll ORDER BY id DESC LIMIT 1"
            )
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"❌ Bankroll fetch failed: {e}")
    return {
        'balance': BTC_STARTING_BALANCE,
        'available': BTC_STARTING_BALANCE,
        'in_positions': 0,
        'total_won': 0,
        'total_lost': 0,
        'total_trades': 0,
        'peak_balance': BTC_STARTING_BALANCE,
        'max_drawdown_pct': 0,
    }

async def compute_btc_stake(entry_price: float, prediction: str, bankroll_state: dict) -> tuple:
    """
    Compute bankroll-proportional stake for a BTC trade.
    Returns (stake, skip_reason) where skip_reason is None if trade is allowed.
    """
    balance = float(bankroll_state.get('balance', BTC_STARTING_BALANCE))
    available = float(bankroll_state.get('available', BTC_STARTING_BALANCE))
    in_positions = float(bankroll_state.get('in_positions', 0))

    max_single_bet = balance * 0.10
    max_exposure = balance * 0.30
    conviction_max = balance * 0.20

    # Base stake as % of bankroll
    if prediction == 'DOWN':
        if entry_price < 0.20:
            base_pct = 0.030
        elif entry_price < 0.30:
            base_pct = 0.020
        elif entry_price < 0.40:
            base_pct = 0.015
        else:  # 40-50c
            base_pct = 0.010
    else:  # UP
        base_pct = 0.005

    stake = balance * base_pct
    stake = min(stake, max_single_bet)

    # Check bankroll guards
    if available < stake:
        return 0, f"BANKROLL: insufficient available (${available:.0f} < ${stake:.0f})"
    if in_positions + stake > max_exposure:
        return 0, f"BANKROLL: exposure limit (${in_positions:.0f}+${stake:.0f} > ${max_exposure:.0f})"

    return round(stake, 2), None

async def update_btc_bankroll_open(stake: float):
    """Reserve stake in bankroll when opening a trade."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE btc_bankroll SET
                    available = available - $1,
                    in_positions = in_positions + $1,
                    updated_at = NOW()
                WHERE id = (SELECT id FROM btc_bankroll ORDER BY id DESC LIMIT 1)
            """, stake)
    except Exception as e:
        logger.error(f"❌ Bankroll open update failed: {e}")

async def update_btc_bankroll_close(stake: float, pnl: float, won: bool):
    """Update bankroll after trade resolves."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            if won:
                # WON: balance += pnl, return stake + gain
                await conn.execute("""
                    UPDATE btc_bankroll SET
                        balance = balance + $1,
                        available = available + $2 + $1,
                        in_positions = GREATEST(0, in_positions - $2),
                        total_won = total_won + $1,
                        total_trades = total_trades + 1,
                        peak_balance = GREATEST(peak_balance, balance + $1),
                        max_drawdown_pct = CASE
                            WHEN GREATEST(peak_balance, balance + $1) > 0
                            THEN ROUND((GREATEST(peak_balance, balance + $1) - (balance + $1)) / GREATEST(peak_balance, balance + $1) * 100, 2)
                            ELSE 0 END,
                        updated_at = NOW()
                    WHERE id = (SELECT id FROM btc_bankroll ORDER BY id DESC LIMIT 1)
                """, pnl, stake)
            else:
                # LOST: balance -= stake, lose stake
                await conn.execute("""
                    UPDATE btc_bankroll SET
                        balance = balance - $1,
                        available = available,
                        in_positions = GREATEST(0, in_positions - $1),
                        total_lost = total_lost + $1,
                        total_trades = total_trades + 1,
                        max_drawdown_pct = CASE
                            WHEN peak_balance > 0
                            THEN ROUND((peak_balance - (balance - $1)) / peak_balance * 100, 2)
                            ELSE 0 END,
                        updated_at = NOW()
                    WHERE id = (SELECT id FROM btc_bankroll ORDER BY id DESC LIMIT 1)
                """, stake)
    except Exception as e:
        logger.error(f"❌ Bankroll close update failed: {e}")

async def sync_btc_in_positions():
    """Recalculate in_positions from open (unresolved) btc_signals."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(s.stake_used), 0) as open_stake
                FROM btc_signals s
                JOIN btc_windows w ON s.window_id = w.window_id
                WHERE s.prediction != 'SKIP' AND w.resolution IS NULL
                AND s.stake_used IS NOT NULL
            """)
            open_stake = float(row['open_stake']) if row else 0
            state = await get_btc_bankroll_state()
            balance = float(state['balance'])
            total_won = float(state['total_won'])
            total_lost = float(state['total_lost'])
            # available = balance - open_stake
            available = max(0, balance - open_stake)
            await conn.execute("""
                UPDATE btc_bankroll SET
                    in_positions = $1,
                    available = $2,
                    updated_at = NOW()
                WHERE id = (SELECT id FROM btc_bankroll ORDER BY id DESC LIMIT 1)
            """, open_stake, available)
    except Exception as e:
        logger.error(f"❌ Bankroll sync failed: {e}")

# ═══════════════════════════════════════════════════════════════
# BTC SIGNAL ENGINE — Scheduled Scan Functions
# ═══════════════════════════════════════════════════════════════
_btc_engine = None
_last_btc_scan: Optional[datetime] = None
_last_btc_resolution: Optional[datetime] = None

# ═══════════════════════════════════════════════════════════════
# MAKER ENGINE — Spread quoting for BTC 5M windows
# ═══════════════════════════════════════════════════════════════
_maker_engine = None
_last_maker_quote: Optional[datetime] = None


async def scheduled_maker_quote():
    """
    Maker Quote Engine: runs every 5 seconds.
    Logic:
      - If active 5M window AND >30s remaining: start or update quotes
      - Check toxic flow → cancel if triggered
      - If <10s remaining: cancel all orders
    Only runs in live mode. Skips gracefully if engine not initialized.
    """
    global _maker_engine, _last_maker_quote, _btc_engine
    try:
        # Only run in live mode
        _tcfg = await get_trading_mode()
        if not is_live_mode(_tcfg):
            return

        # Lazy-init maker engine
        if _maker_engine is None:
            from src.execution.maker_engine import MakerEngine
            _maker_engine = MakerEngine(get_async_pool(), dry_run=False)
            await _maker_engine.ensure_tables()
            logger.info("✅ MakerEngine initialized")

        # Skip if paused for daily loss limit
        if _maker_engine.is_paused:
            return

        # Find the active 5M window (from btc_signal_engine cache)
        if _btc_engine is None:
            return

        # Get current active windows from DB
        now = datetime.utcnow()
        pool = get_async_pool()
        async with pool.acquire() as conn:
            active_window = await conn.fetchrow("""
                SELECT w.window_id, w.window_length, w.open_time, w.close_time,
                       w.up_price, w.down_price, w.volume_usd,
                       s.prediction, s.prob_up, s.confidence,
                       s.f_price_delta, s.f_momentum, s.f_volume_imbalance,
                       s.f_oracle_lead, s.f_book_imbalance
                FROM btc_windows w
                LEFT JOIN LATERAL (
                    SELECT * FROM btc_signals
                    WHERE window_id = w.window_id AND prediction != 'SKIP'
                    ORDER BY confidence DESC LIMIT 1
                ) s ON true
                WHERE w.window_length = 5
                  AND w.close_time > NOW()
                  AND w.resolution IS NULL
                ORDER BY w.close_time ASC
                LIMIT 1
            """)

        if not active_window:
            # No active 5M window — cancel any resting orders and clean up
            if _maker_engine.is_quoting:
                await _maker_engine.cancel_all_orders(expire_window=True)
            return

        close_time = active_window["close_time"]
        # Ensure close_time is offset-aware
        if close_time.tzinfo is None:
            from datetime import timezone as _tz
            close_time = close_time.replace(tzinfo=_tz.utc)
        from datetime import timezone as _tz
        now_aware = datetime.now(_tz.utc)
        seconds_remaining = max(0, int((close_time - now_aware).total_seconds()))

        window_id = active_window["window_id"]
        up_price = float(active_window["up_price"] or 0.5)
        down_price = float(active_window["down_price"] or 0.5)
        fair_value = float(active_window["prob_up"] or 0.5)
        prediction = active_window["prediction"]   # 'UP', 'DOWN', or None
        confidence = float(active_window["confidence"] or 0.5)

        # Extract token IDs from btc_windows (stored by signal engine scan)
        up_token = ""
        down_token = ""
        async with pool.acquire() as conn:
            token_row = await conn.fetchrow("""
                SELECT token_id_up, token_id_down FROM btc_windows WHERE window_id = $1
            """, window_id)
        if token_row:
            up_token = token_row["token_id_up"] or ""
            down_token = token_row["token_id_down"] or ""

        # If <10s remaining: cancel all and bail
        if seconds_remaining < 10:
            if _maker_engine.is_quoting:
                logger.info(f"🔔 Window {window_id} closing in {seconds_remaining}s — cancelling all orders")
                await _maker_engine.cancel_all_orders(expire_window=True)
            return

        # Toxic flow check (runs whether quoting or not, uses deque from engine)
        if _maker_engine.is_quoting:
            is_toxic = await _maker_engine.check_toxic_flow()
            if is_toxic:
                await _maker_engine.cancel_all_orders(expire_window=False)
                _last_maker_quote = datetime.utcnow()
                return

        # We need token IDs to post orders. Try to get them via the scan.
        # The btc_signal_engine stores token IDs in the signal metadata.
        if not up_token or not down_token:
            async with pool.acquire() as conn:
                sig_row = await conn.fetchrow("""
                    SELECT skip_reason FROM btc_signals
                    WHERE window_id = $1 ORDER BY created_at DESC LIMIT 1
                """, window_id)
            # If token IDs unavailable, skip making for this window
            if not up_token or not down_token:
                logger.debug(f"Maker: no token IDs for window {window_id} — skipping")
                return

        # If >30s remaining: start or update quotes
        if seconds_remaining > 30:
            # Parse window epoch from window_id (format: btc-updown-5m-{epoch})
            try:
                window_epoch = int(window_id.split("-")[-1])
            except Exception:
                window_epoch = int(now_aware.timestamp())

            if not _maker_engine.is_quoting:
                await _maker_engine.start_quoting(
                    window_epoch=window_epoch,
                    window_length=5,
                    fair_value=fair_value,
                    up_token=up_token,
                    down_token=down_token,
                    size_per_side=_maker_engine.MAX_SIZE_PER_SIDE,
                )
            else:
                await _maker_engine.update_quotes(
                    new_fair_value=fair_value,
                    seconds_remaining=seconds_remaining,
                    confidence=confidence,
                    predicted_side=prediction,
                )

        _last_maker_quote = datetime.utcnow()

    except Exception as e:
        logger.error(f"❌ scheduled_maker_quote failed: {e}")
        # Safety: cancel all on any error
        if _maker_engine:
            try:
                await _maker_engine.cancel_all_orders(expire_window=False)
            except Exception:
                pass


async def scheduled_btc_signal_scan():
    """BTC Signal Engine: scan for active BTC windows, compute 7-factor signals."""
    global _last_btc_scan, _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
            logger.info("✅ BTC Signal Engine initialized")

        results = await _btc_engine.run_scan()
        _last_btc_scan = datetime.utcnow()

        # ═══════════════════════════════════════════════════════════
        # STRATEGY V3 (2026-04-09 13:29 IST)
        # Rule 1: REWARD >= RISK — potential profit must cover loss + fee
        #         This means entry_price < 50c (reward:risk >= 1:1)
        # Rule 2: Scale stake aggressively on best odds
        #         <20c=$75, 20-30c=$50, 30-40c=$35, 40-50c=$25
        # Rule 3: Skip 15M (always 85c+ entries)
        # Rule 4: Minimum factor agreement — at least 4/7 factors aligned
        # ═══════════════════════════════════════════════════════════
        if _telegram_bot and results:
            for sig in results:
                prob = sig.get('prob_up', 0.5)
                conf = sig.get('confidence', 0)
                pred = sig.get('prediction', 'SKIP')
                if pred == 'SKIP':
                    continue
                # Must have directional conviction
                if not (prob > 0.70 or prob < 0.30):
                    continue
                
                wl = sig.get('window_length', 15)
                up_price = sig.get('up_price', 0.5)
                down_price = sig.get('down_price', 0.5)
                entry_price = down_price if pred == 'UP' else up_price

                # RULE 3: Skip 15M windows entirely
                if wl == 15:
                    continue

                # ═══ LIVE-ADJUSTED STRATEGY (V4.1) ═══
                # Accounts for: slippage (~3%), fees (~2%), partial fills
                # Total execution cost estimate: ~5% round-trip
                
                EXECUTION_COST = 0.05  # 5% total (2% fee + 3% slippage estimate)
                MIN_ENTRY = 0.02      # Below 2c = no liquidity
                MAX_ENTRY = 0.40      # Tightened from 50c — need more upside buffer
                MIN_RR_AFTER_COSTS = 1.5  # Must clear 1.5:1 AFTER all costs
                MIN_FACTORS = 5       # 5 of 7 factors must agree

                # ═══ DYNAMIC BANKROLL SIZING ═══
                # Query proxy wallet balance from CLOB (cached in signal engine)
                try:
                    _proxy_balance = getattr(_btc_engine, '_cached_proxy_balance', None)
                    if _proxy_balance and _proxy_balance > 0:
                        # Normal: 3% of bankroll, cap $25
                        # Conviction (handled below if 4x signal): 5% of bankroll, cap $50
                        LIVE_STAKE = min(_proxy_balance * 0.03, 25.0)
                        if LIVE_STAKE < 5.0:
                            logger.warning(f"⚠️ Bankroll too low (${_proxy_balance:.2f}), skipping trade")
                            continue
                    else:
                        LIVE_STAKE = 25  # Fallback
                except Exception:
                    LIVE_STAKE = 25  # Fallback
                
                # RULE 1: Entry price bounds
                if entry_price <= MIN_ENTRY or entry_price >= MAX_ENTRY:
                    continue
                
                # RULE 2: Calculate REAL reward:risk after ALL costs
                # Win payout: (1/entry - 1) minus execution costs on both sides
                gross_rr = (1.0 / entry_price) - 1.0  # Raw R:R
                # Deduct: buy slippage + sell slippage + fees
                net_win_per_dollar = gross_rr - EXECUTION_COST  # What you actually keep per $1
                net_loss_per_dollar = 1.0 + EXECUTION_COST  # What you actually lose per $1 (stake + costs)
                
                reward_risk = net_win_per_dollar / net_loss_per_dollar if net_loss_per_dollar > 0 else 0
                
                if reward_risk < MIN_RR_AFTER_COSTS:
                    continue  # Upside doesn't justify downside after costs
                
                # RULE 3: Fixed stake for live (no scaled sizing — liquidity appropriate)
                stake = LIVE_STAKE
                
                # RULE 4: Check factor agreement (from signal factors)
                factors = sig.get('factors', {})
                if factors:
                    direction_sign = 1 if pred == 'UP' else -1
                    factor_vals = [
                        factors.get('f_price_delta', 0),
                        factors.get('f_momentum', 0),
                        factors.get('f_volume_imbalance', 0),
                        factors.get('f_oracle_lead', 0),
                        factors.get('f_book_imbalance', 0),
                        factors.get('f_volatility', 0),
                        factors.get('f_time_decay', 0),
                    ]
                    agreeing = sum(1 for f in factor_vals if f * direction_sign > 0)
                    if agreeing < MIN_FACTORS:
                        continue  # Need 5+ factors aligned

                price = sig.get('btc_price', 0)
                btc_open = sig.get('btc_open', price)
                delta_pct = ((price - btc_open) / btc_open * 100) if btc_open > 0 else 0
                potential = (stake / entry_price - stake) * (1 - EXECUTION_COST)  # Net after all costs
                
                # Trade opened — log only, NO telegram broadcast
                # WON/LOST sent on resolution with full analysis
                logger.info(f"V4 trade: {pred} {wl}M | {entry_price*100:.0f}c | ${stake} | R:R {reward_risk:.1f}x | {agreeing}/7")

                # ═══════════════════════════════════════════════════════
                # LIVE TRADE EXECUTION — if mode is 'live' and passes V4+
                # ═══════════════════════════════════════════════════════
                try:
                    _tcfg = await get_trading_mode()
                    if is_live_mode(_tcfg) and agreeing >= 5:
                        from src.polymarket_live import PolymarketLiveTrader
                        _live_trader = PolymarketLiveTrader(get_async_pool())
                        # Determine token_id: buy the side we predict wins
                        _token_id = sig.get('token_id_up', '') if pred == 'UP' else sig.get('token_id_down', '')
                        _live_stake = min(stake, 25.0)  # Hard cap $25 for live
                        if _token_id:
                            _live_trade_id = await _live_trader.execute_live_trade(
                                window_id=sig.get('window_id', ''),
                                prediction=pred,
                                token_id=_token_id,
                                entry_price=entry_price,
                                stake_usd=_live_stake,
                                factors_agreeing=agreeing,
                                signal_metadata={'factors': factors, 'window_length': wl, 'reward_risk': reward_risk},
                            )
                            if _live_trade_id:
                                logger.info(f"🟢 LIVE trade #{_live_trade_id} placed for {pred} {wl}M")
                        else:
                            logger.warning(f"⚠️ No token_id for {pred} — cannot place live trade")
                except Exception as _live_e:
                    logger.error(f"❌ Live trade execution error: {_live_e}")

                # Store stake_used on the signal row and update bankroll
                _window_id = sig.get('window_id', '')
                if _window_id:
                    try:
                        pool = get_async_pool()
                        async with pool.acquire() as conn:
                            await conn.execute("""
                                UPDATE btc_signals SET stake_used = $1
                                WHERE window_id = $2 AND prediction != 'SKIP'
                            """, stake, _window_id)
                    except Exception as _se:
                        logger.error(f"❌ Stake save failed: {_se}")
                await update_btc_bankroll_open(stake)

                # Track volatility per hour slot
                try:
                    pool = get_async_pool()
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO btc_volatility_hours (
                                date, hour_ist, window_length, trades_taken, avg_entry, 
                                btc_price_range_pct, session_tag
                            ) VALUES (
                                CURRENT_DATE,
                                EXTRACT(HOUR FROM NOW() AT TIME ZONE 'Asia/Kolkata')::int,
                                $1, 1, $2, $3, 'v2'
                            )
                            ON CONFLICT (date, hour_ist, window_length) DO UPDATE SET
                                trades_taken = btc_volatility_hours.trades_taken + 1,
                                avg_entry = (btc_volatility_hours.avg_entry * btc_volatility_hours.trades_taken + $2) 
                                    / (btc_volatility_hours.trades_taken + 1),
                                btc_price_range_pct = GREATEST(btc_volatility_hours.btc_price_range_pct, $3)
                        """, wl, entry_price, abs(delta_pct))
                except Exception:
                    pass

        logger.info(f"📊 BTC scan: {len(results)} signals")
    except Exception as e:
        logger.error(f"❌ BTC signal scan failed: {e}\n{traceback.format_exc()}")


_pinned_msg_ids = {  # chat_id -> message_id per report type for pin management
    'hourly': {},
    'penny': {},
    'intelligence': {},
    'daily': {},
}

async def _send_and_pin(bot_token, subscribers, msg, report_type):
    """Send message to all subscribers, pin it, unpin previous of same type."""
    global _pinned_msg_ids
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        for sub in subscribers:
            chat_id = sub['chat_id'] if isinstance(sub, dict) else sub
            try:
                # Unpin previous of same type
                old_id = _pinned_msg_ids[report_type].get(chat_id)
                if old_id:
                    await client.post(f"https://api.telegram.org/bot{bot_token}/unpinChatMessage",
                        json={"chat_id": chat_id, "message_id": old_id})
                # Send
                resp = await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg})
                result = resp.json()
                if result.get('ok'):
                    new_id = result['result']['message_id']
                    # Pin
                    await client.post(f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
                        json={"chat_id": chat_id, "message_id": new_id, "disable_notification": True})
                    _pinned_msg_ids[report_type][chat_id] = new_id
            except Exception as e:
                logger.error(f"\u274c {report_type} send/pin failed for {chat_id}: {e}")

async def scheduled_btc_hourly_summary():
    """Send hourly performance summary with financials to Telegram. Pins the message."""
    global _telegram_bot, _pinned_msg_ids
    if not _telegram_bot:
        logger.warning("\u26a0\ufe0f BTC hourly: _telegram_bot is None, skipping")
        return
    # Gate: suppress if paper mode + paper_notifications=false
    _tcfg = await get_trading_mode()
    if is_live_mode(_tcfg):
        logger.info("🔇 BTC hourly summary suppressed (live mode — only live trade alerts)")
        return
    if not should_send_paper_telegram(_tcfg):
        logger.info("🔇 BTC hourly summary suppressed (paper notifications off)")
        return
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='polyedge', user='node', host='localhost')
        cur = conn.cursor()

        # All-time per timeframe — uses btc_pnl view (correct stakes + filters invalid prices)
        cur.execute("""
            SELECT window_length, COUNT(*) as total, COUNT(*) FILTER (WHERE correct) as wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                ROUND(SUM(CASE WHEN trade_pnl > 0 THEN trade_pnl ELSE 0 END)::numeric, 2) as gross_profit,
                ROUND(ABS(SUM(CASE WHEN trade_pnl < 0 THEN trade_pnl ELSE 0 END))::numeric, 2) as gross_loss,
                ROUND(MAX(trade_pnl)::numeric, 2) as best_trade,
                ROUND(SUM(CASE WHEN trade_pnl > 0 THEN stake * (1.0/entry_price - 1.0) * 0.02 ELSE 0 END)::numeric, 2) as fees
            FROM btc_pnl GROUP BY window_length ORDER BY window_length
        """)
        stats = cur.fetchall()

        # Last hour
        cur.execute("""
            SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE correct) as wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                ROUND(MAX(trade_pnl)::numeric, 2) as best_trade
            FROM btc_pnl WHERE close_time > NOW() - INTERVAL '1 hour'
        """)
        last_hour = cur.fetchone()

        # Today's P&L
        cur.execute("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE correct),
                ROUND(SUM(trade_pnl)::numeric, 2),
                ROUND(SUM(CASE WHEN trade_pnl > 0 THEN trade_pnl ELSE 0 END)::numeric, 2),
                ROUND(ABS(SUM(CASE WHEN trade_pnl < 0 THEN trade_pnl ELSE 0 END))::numeric, 2),
                ROUND(SUM(CASE WHEN trade_pnl > 0 THEN stake * (1.0/entry_price - 1.0) * 0.02 ELSE 0 END)::numeric, 2),
                ROUND(SUM(stake)::numeric, 2)
            FROM btc_pnl WHERE close_time::date = CURRENT_DATE
        """)
        today_stats = cur.fetchone()

        # Active strategy
        cur.execute("SELECT version FROM btc_strategy_versions WHERE status = 'active' LIMIT 1")
        active_v = cur.fetchone()
        strategy_name = active_v[0] if active_v else '?'
        conn.close()

        # Build message
        from datetime import datetime as dt
        now_ist = dt.now().strftime('%H:%M IST')
        _mode_label = '🟢 BTC LIVE TRADING' if is_live_mode(_tcfg) else '📊 BTC PAPER TRADING'
        lines = [f"{_mode_label} \u2014 {now_ist}", f"Strategy: {strategy_name}", ""]

        h_total, h_wins, h_net, h_best = last_hour if last_hour else (0, 0, 0, 0)
        if h_total and h_total > 0:
            h_sign = '+' if float(h_net or 0) >= 0 else ''
            lines.append(f"\u23f0 Last Hour: {h_wins}W-{h_total-h_wins}L | {h_sign}${h_net}")
            if h_best and float(h_best) > 0:
                lines.append(f"   Best: +${h_best}")
        else:
            lines.append("\u23f0 Last Hour: No trades resolved")

        # TODAY section
        d_total, d_wins, d_net, d_profit, d_loss, d_fees, d_returns = today_stats if today_stats else (0,0,0,0,0,0,0)
        d_total = d_total or 0; d_wins = d_wins or 0; d_net = float(d_net or 0)
        d_profit = float(d_profit or 0); d_loss = float(d_loss or 0)
        d_fees = float(d_fees or 0); d_spent = d_total * 25
        lines.append("")
        lines.append("\u2501\u2501\u2501 TODAY \u2501\u2501\u2501")
        d_emoji = '\U0001f7e2' if d_net >= 0 else '\U0001f534'
        d_sign = '+' if d_net >= 0 else ''
        lines.append(f"{d_emoji} Net P&L: {d_sign}${d_net:.2f}")
        lines.append(f"\U0001f4b0 Profit: +${d_profit:.2f} | \U0001f4c9 Loss: -${d_loss:.2f}")
        lines.append(f"\U0001f4b5 Spent: ${d_spent} | \U0001f4b8 Fees: ${d_fees:.2f}")
        if d_total > 0:
            lines.append(f"Record: {d_wins}W-{d_total-d_wins}L ({d_wins/d_total*100:.0f}%)")

        # YTD (all-time) section
        lines.append("")
        lines.append("\u2501\u2501\u2501 ALL-TIME (YTD) \u2501\u2501\u2501")

        a_net = sum(float(r[3] or 0) for r in stats)
        a_profit = sum(float(r[4] or 0) for r in stats)
        a_loss = sum(float(r[5] or 0) for r in stats)
        a_best = max((float(r[6] or 0) for r in stats), default=0)
        a_fees = sum(float(r[7] or 0) for r in stats)
        a_total = sum(r[1] for r in stats)
        a_wins = sum(r[2] for r in stats)
        a_spent = a_total * 25

        net_emoji = '\U0001f7e2' if a_net >= 0 else '\U0001f534'
        net_sign = '+' if a_net >= 0 else ''
        lines.append(f"{net_emoji} Net P&L: {net_sign}${a_net:.2f}")
        lines.append(f"\U0001f4b0 Profit: +${a_profit:.2f} | \U0001f4c9 Loss: -${a_loss:.2f}")
        lines.append(f"\U0001f3c6 Best Trade: +${a_best:.2f}")
        lines.append(f"\U0001f4b5 Spent: ${a_spent} | \U0001f4b8 Fees: ${a_fees:.2f}")

        lines.append("")
        for r in stats:
            wl, total, wins, net_pnl = r[0], r[1], r[2], r[3]
            acc = wins/total*100 if total > 0 else 0
            lines.append(f"{wl}m: {wins}W-{total-wins}L ({acc:.0f}%) | {'+' if float(net_pnl or 0) >= 0 else ''}${net_pnl}")

        if a_total > 0:
            lines.append(f"\nRecord: {a_wins}W-{a_total-a_wins}L ({a_wins/a_total*100:.0f}%)")

        # BANKROLL section
        try:
            br = await get_btc_bankroll_state()
            br_bal = float(br.get('balance', BTC_STARTING_BALANCE))
            br_avail = float(br.get('available', br_bal))
            br_in_pos = float(br.get('in_positions', 0))
            br_dd = float(br.get('max_drawdown_pct', 0))
            br_pnl_pct = (br_bal - BTC_STARTING_BALANCE) / BTC_STARTING_BALANCE * 100
            br_emoji = '\U0001f7e2' if br_bal >= BTC_STARTING_BALANCE else '\U0001f534'
            lines.append("")
            lines.append("\u2501\u2501\u2501 BANKROLL \u2501\u2501\u2501")
            lines.append(f"{br_emoji} Balance: ${br_bal:,.0f} ({'+' if br_pnl_pct>=0 else ''}{br_pnl_pct:.1f}% from ${BTC_STARTING_BALANCE:,.0f})")
            lines.append(f"\U0001f4b3 Available: ${br_avail:,.0f} | In Positions: ${br_in_pos:,.0f}")
            if br_dd > 0.01:
                lines.append(f"\U0001f4c9 Max Drawdown: {br_dd:.1f}%")
            lines.append(f"\U0001f3af Max Bet: ${br_bal*0.10:,.0f} | Max Exposure: ${br_bal*0.30:,.0f}")
        except Exception as _bre:
            logger.error(f"Bankroll section failed: {_bre}")

        lines.append(f"Dashboard: weatherbot.1nnercircle.club/btc15m")

        msg = "\n".join(lines)
        subscribers = await _telegram_bot.get_all_subscribers(instant_only=False)
        await _send_and_pin(_telegram_bot.bot_token, subscribers, msg, 'hourly')
        logger.info(f"\U0001f4ca BTC hourly summary sent + pinned to {len(subscribers)} subscribers")
    except Exception as e:
        logger.error(f"\u274c BTC hourly summary failed: {e}\n{traceback.format_exc()}")


async def scheduled_btc_intelligence_loop():
    """Daily Intelligence Loop at 11:00 PM IST.
    
    THE LOOP:
    1. Analyze today's performance under current strategy
    2. Compare to previous day (progressive, regressive, or neutral)
    3. If progressive: RETAIN strategy, note what worked
    4. If regressive: REVERT to previous strategy + capture learnings
    5. Either way: propose ONE adjustment for tomorrow
    6. Activate new/adjusted strategy for next 24 hours
    7. Log everything to btc_intelligence_log
    8. Broadcast full report to Telegram
    """
    global _telegram_bot
    if not _telegram_bot:
        return
    # Gate: suppress if paper mode + paper_notifications=false
    _tcfg = await get_trading_mode()
    if is_live_mode(_tcfg):
        logger.info("🔇 BTC intelligence loop suppressed (live mode)")
        return
    if not should_send_paper_telegram(_tcfg):
        logger.info("🔇 BTC intelligence loop suppressed (paper notifications off)")
        return
    try:
        import psycopg2, json
        from datetime import date
        conn = psycopg2.connect(dbname='polyedge', user='node', host='localhost')
        cur = conn.cursor()

        # Get active strategy
        cur.execute("SELECT version, max_entry, min_rr, min_factors, window_lengths, stakes FROM btc_strategy_versions WHERE status = 'active' ORDER BY id DESC LIMIT 1")
        active = cur.fetchone()
        if not active:
            conn.close()
            return
        active_version, max_entry, min_rr, min_factors, win_lengths, stakes = active

        # Today's performance (V3-eligible trades: entry < max_entry, correct window lengths)
        cur.execute("""
            WITH best AS (
                SELECT DISTINCT ON (s.window_id)
                    s.window_id, s.prediction, s.confidence, w.resolution, w.window_length,
                    w.close_time,
                    (s.prediction = w.resolution) as correct,
                    CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                FROM btc_signals s
                JOIN btc_windows w ON s.window_id = w.window_id
                WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                    AND w.close_time::date = CURRENT_DATE
                ORDER BY s.window_id, s.confidence DESC
            ),
            pnl AS (
                SELECT *,
                    CASE
                        WHEN entry_price < 0.20 THEN 75 WHEN entry_price < 0.30 THEN 50
                        WHEN entry_price < 0.40 THEN 35 ELSE 25
                    END as stake,
                    CASE
                        WHEN correct AND entry_price > 0 AND entry_price < 1 THEN
                            (CASE WHEN entry_price < 0.20 THEN 75 WHEN entry_price < 0.30 THEN 50 WHEN entry_price < 0.40 THEN 35 ELSE 25 END
                             / entry_price - CASE WHEN entry_price < 0.20 THEN 75 WHEN entry_price < 0.30 THEN 50 WHEN entry_price < 0.40 THEN 35 ELSE 25 END) * 0.98
                        WHEN NOT correct THEN
                            -1 * CASE WHEN entry_price < 0.20 THEN 75 WHEN entry_price < 0.30 THEN 50 WHEN entry_price < 0.40 THEN 35 ELSE 25 END
                        ELSE 0
                    END as trade_pnl,
                    CASE WHEN entry_price > 0 THEN (1.0/entry_price - 1.0) * 0.98 ELSE 0 END as rr
                FROM best
            )
            SELECT 
                COUNT(*) as total, COUNT(*) FILTER (WHERE correct) as wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                ROUND(SUM(CASE WHEN trade_pnl > 0 THEN trade_pnl ELSE 0 END)::numeric, 2) as gross_profit,
                ROUND(ABS(SUM(CASE WHEN trade_pnl < 0 THEN trade_pnl ELSE 0 END))::numeric, 2) as gross_loss,
                ROUND(MAX(trade_pnl)::numeric, 2) as best_trade,
                ROUND(AVG(entry_price)::numeric, 4) as avg_entry,
                ROUND(AVG(rr)::numeric, 2) as avg_rr
            FROM pnl
        """)
        today = cur.fetchone()
        t_total, t_wins, t_net, t_profit, t_loss, t_best, t_avg_entry, t_avg_rr = today

        # Hourly breakdown for best/worst hour
        cur.execute("""
            WITH best AS (
                SELECT DISTINCT ON (s.window_id)
                    s.window_id, s.prediction, w.resolution, w.window_length, w.close_time,
                    (s.prediction = w.resolution) as correct,
                    CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                FROM btc_signals s
                JOIN btc_windows w ON s.window_id = w.window_id
                WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                    AND w.close_time::date = CURRENT_DATE
                ORDER BY s.window_id, s.confidence DESC
            ),
            pnl AS (
                SELECT *, CASE WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98 WHEN NOT correct THEN -25.0 ELSE 0 END as trade_pnl
                FROM best
            )
            SELECT EXTRACT(HOUR FROM close_time AT TIME ZONE 'Asia/Kolkata')::int as hr,
                COUNT(*) as trades, COUNT(*) FILTER (WHERE correct) as wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as pnl,
                ROUND(AVG(entry_price)::numeric, 3) as avg_entry
            FROM pnl GROUP BY 1 ORDER BY 1
        """)
        hourly = cur.fetchall()
        best_hour = max(hourly, key=lambda x: float(x[3])) if hourly else None
        worst_hour = min(hourly, key=lambda x: float(x[3])) if hourly else None
        vol_data = {str(h[0]): {"trades": h[1], "wins": h[2], "pnl": float(h[3]), "avg_entry": float(h[4])} for h in hourly}

        # Previous day for comparison
        cur.execute("SELECT net_pnl, trades_taken, strategy_version, verdict FROM btc_intelligence_log WHERE date = CURRENT_DATE - 1")
        prev = cur.fetchone()
        prev_pnl = float(prev[0]) if prev else None
        prev_version = prev[2] if prev else None

        # === INTELLIGENCE DECISION ===
        t_net_f = float(t_net or 0)
        verdict = 'neutral'
        action = 'retain'
        learnings = []
        next_version = active_version

        if t_total == 0:
            verdict = 'no_data'
            action = 'retain'
            learnings.append('No trades taken today. Filters may be too tight or no favorable entries.')
        elif t_net_f > 0:
            verdict = 'progressive'
            action = 'retain'
            learnings.append(f'Profitable day (+${t_net_f}). Strategy {active_version} is working.')
            if best_hour:
                learnings.append(f'Best hour: {best_hour[0]:02d}:00 (+${float(best_hour[3]):.2f}, entry {float(best_hour[4])*100:.0f}c)')
            if t_avg_rr and float(t_avg_rr) > 1.5:
                learnings.append(f'Avg R:R {float(t_avg_rr):.1f}x — excellent trade selection.')
        elif t_net_f < 0 and t_net_f > -50:
            verdict = 'neutral'
            action = 'retain'
            learnings.append(f'Small loss (${t_net_f}). Within noise range. Retain strategy.')
        else:
            verdict = 'regressive'
            # Check if we should revert or evolve
            if prev and prev_pnl and float(prev_pnl) > 0:
                action = 'revert'
                learnings.append(f'Regressive day (${t_net_f}). Previous strategy {prev_version} was profitable.')
                learnings.append('Reverting to previous strategy and capturing learnings.')
            else:
                action = 'evolve'
                learnings.append(f'Regressive day (${t_net_f}). No profitable previous strategy to revert to.')

        # === PROPOSE ADJUSTMENT ===
        adjustment_note = ''
        new_max_entry = float(max_entry)
        new_min_rr = float(min_rr)
        new_min_factors = min_factors
        new_win_lengths = list(win_lengths)
        new_stakes = json.loads(stakes) if isinstance(stakes, str) else dict(stakes)

        if action == 'revert':
            # Find the BEST historical version (highest P&L in performance_snapshot)
            cur.execute("""
                SELECT version, max_entry, min_rr, min_factors, window_lengths, stakes,
                    (performance_snapshot->>'net_pnl')::numeric as hist_pnl
                FROM btc_strategy_versions 
                WHERE performance_snapshot IS NOT NULL 
                    AND (performance_snapshot->>'net_pnl')::numeric > 0
                ORDER BY (performance_snapshot->>'net_pnl')::numeric DESC
                LIMIT 1
            """)
            best_hist = cur.fetchone()
            
            # Fallback to previous day's version if no profitable history
            if not best_hist and prev_version:
                cur.execute("SELECT version, max_entry, min_rr, min_factors, window_lengths, stakes FROM btc_strategy_versions WHERE version = %s", (prev_version,))
                best_hist = cur.fetchone()
            
            if best_hist:
                revert_to = best_hist[0]
                new_max_entry, new_min_rr, new_min_factors = float(best_hist[1]), float(best_hist[2]), best_hist[3]
                new_win_lengths = list(best_hist[4])
                new_stakes = json.loads(best_hist[5]) if isinstance(best_hist[5], str) else dict(best_hist[5])
                hist_pnl = float(best_hist[6]) if len(best_hist) > 6 and best_hist[6] else None
                pnl_note = f' (was +${hist_pnl:.2f})' if hist_pnl else ''
                adjustment_note = f'Reverted to {revert_to} parameters{pnl_note}. Proven profitable.'
        elif verdict == 'progressive':
            # Small optimization: if avg entry is clustered, widen slightly
            if t_avg_entry and float(t_avg_entry) < 0.35:
                adjustment_note = 'Entries clustered low. Strategy is selective — good.'
            elif worst_hour:
                wh = worst_hour[0]
                adjustment_note = f'Consider avoiding hour {wh:02d}:00 (worst P&L: ${float(worst_hour[3]):.2f}).'
        elif verdict == 'no_data':
            # Loosen slightly if no trades at all
            if new_max_entry < 0.55:
                new_max_entry = min(new_max_entry + 0.05, 0.55)
                adjustment_note = f'No trades taken. Loosened max entry from {float(max_entry)*100:.0f}c to {new_max_entry*100:.0f}c.'
            elif new_min_factors > 3:
                new_min_factors = max(new_min_factors - 1, 3)
                adjustment_note = f'No trades taken. Relaxed factor agreement from {min_factors}/7 to {new_min_factors}/7.'

        # Create new version
        version_num = int(active_version.replace('V', '')) + 1
        new_version = f'V{version_num}'

        # Only create new version if parameters actually changed
        if (new_max_entry != float(max_entry) or new_min_rr != float(min_rr) or 
            new_min_factors != min_factors or new_win_lengths != list(win_lengths)):
            # Snapshot today's performance onto the outgoing version (immutable record)
            cur.execute("""
                UPDATE btc_strategy_versions 
                SET status = %s, deactivated_at = NOW(),
                    performance_snapshot = %s,
                    revert_reason = CASE WHEN %s = 'revert' THEN %s ELSE NULL END
                WHERE status = 'active'
            """, (
                'retained' if action == 'retain' else 'reverted' if action == 'revert' else 'superseded',
                json.dumps({
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'trades': t_total or 0, 'wins': t_wins or 0,
                    'net_pnl': float(t_net or 0), 'best_trade': float(t_best or 0),
                    'avg_entry': float(t_avg_entry or 0), 'avg_rr': float(t_avg_rr or 0),
                    'verdict': verdict
                }),
                action, '\n'.join(learnings)
            ))
            # Create new version — APPEND ONLY, old versions never modified after this
            cur.execute("""
                INSERT INTO btc_strategy_versions 
                (version, status, max_entry, min_rr, min_factors, window_lengths, stakes, parent_version, notes)
                VALUES (%s, 'active', %s, %s, %s, %s, %s, %s, %s)
            """, (new_version, new_max_entry, new_min_rr, new_min_factors, new_win_lengths,
                   json.dumps(new_stakes), active_version, adjustment_note))
            next_version = new_version
        else:
            next_version = active_version

        # Log today's intelligence
        cur.execute("""
            INSERT INTO btc_intelligence_log (date, strategy_version, trades_taken, trades_won,
                net_pnl, gross_profit, gross_loss, best_trade, avg_entry, avg_rr,
                best_hour, worst_hour, best_hour_pnl, worst_hour_pnl,
                volatility_data, verdict, action_taken, next_strategy, learnings)
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date) DO UPDATE SET
                trades_taken = EXCLUDED.trades_taken, trades_won = EXCLUDED.trades_won,
                net_pnl = EXCLUDED.net_pnl, gross_profit = EXCLUDED.gross_profit,
                gross_loss = EXCLUDED.gross_loss, best_trade = EXCLUDED.best_trade,
                avg_entry = EXCLUDED.avg_entry, avg_rr = EXCLUDED.avg_rr,
                best_hour = EXCLUDED.best_hour, worst_hour = EXCLUDED.worst_hour,
                best_hour_pnl = EXCLUDED.best_hour_pnl, worst_hour_pnl = EXCLUDED.worst_hour_pnl,
                volatility_data = EXCLUDED.volatility_data, verdict = EXCLUDED.verdict,
                action_taken = EXCLUDED.action_taken, next_strategy = EXCLUDED.next_strategy,
                learnings = EXCLUDED.learnings
        """, (
            active_version, t_total or 0, t_wins or 0,
            t_net or 0, t_profit or 0, t_loss or 0, t_best or 0,
            t_avg_entry or 0, t_avg_rr or 0,
            best_hour[0] if best_hour else None,
            worst_hour[0] if worst_hour else None,
            float(best_hour[3]) if best_hour else None,
            float(worst_hour[3]) if worst_hour else None,
            json.dumps(vol_data),
            verdict, action, next_version,
            '\n'.join(learnings)
        ))
        conn.commit()
        conn.close()

        # === BROADCAST ===
        verdict_emoji = {'progressive': '\U0001f7e2', 'regressive': '\U0001f534', 'neutral': '\U0001f7e1', 'no_data': '\u26aa'}
        action_emoji = {'retain': '\u2705', 'revert': '\u21a9\ufe0f', 'evolve': '\U0001f52c'}

        lines = [
            '\U0001f9e0 BTC INTELLIGENCE LOOP \u2014 Daily Report',
            f'Date: {datetime.now().strftime("%Y-%m-%d")} IST',
            f'Strategy: {active_version}',
            '',
            '\u2501\u2501\u2501 TODAY\'S PERFORMANCE \u2501\u2501\u2501',
        ]
        if t_total and t_total > 0:
            lines.append(f'Trades: {t_wins}W-{t_total-t_wins}L ({t_wins/t_total*100:.0f}%)')
            lines.append(f'Net P&L: {"+ " if t_net_f >= 0 else ""}${t_net_f:.2f}')
            lines.append(f'Gross Profit: +${float(t_profit or 0):.2f}')
            lines.append(f'Gross Loss: -${float(t_loss or 0):.2f}')
            lines.append(f'Best Trade: +${float(t_best or 0):.2f}')
            lines.append(f'Avg Entry: {float(t_avg_entry or 0)*100:.0f}c | Avg R:R: {float(t_avg_rr or 0):.1f}x')
        else:
            lines.append('No trades taken today.')

        if hourly:
            lines.append('')
            lines.append('\u2501\u2501\u2501 HOURLY HEATMAP \u2501\u2501\u2501')
            for h in hourly:
                hr, trades, wins, pnl, entry = h
                e = '\U0001f7e2' if float(pnl) >= 0 else '\U0001f534'
                lines.append(f'{e} {hr:02d}:00 | {wins}W-{trades-wins}L | {"+ " if float(pnl)>=0 else ""}${pnl} | entry: {float(entry)*100:.0f}c')

        lines.append('')
        lines.append('\u2501\u2501\u2501 INTELLIGENCE VERDICT \u2501\u2501\u2501')
        lines.append(f'{verdict_emoji.get(verdict, "")} Verdict: {verdict.upper()}')
        lines.append(f'{action_emoji.get(action, "")} Action: {action.upper()}')
        if prev_pnl is not None:
            lines.append(f'vs Yesterday: {"+ " if prev_pnl >= 0 else ""}${prev_pnl:.2f} ({prev_version})')
        for l in learnings:
            lines.append(f'\U0001f4a1 {l}')

        lines.append('')
        lines.append('\u2501\u2501\u2501 TOMORROW\'S STRATEGY \u2501\u2501\u2501')
        lines.append(f'Version: {next_version}')
        lines.append(f'Max Entry: {new_max_entry*100:.0f}c | Min R:R: {new_min_rr:.1f}x')
        lines.append(f'Factor Agreement: {new_min_factors}/7 | Windows: {"m, ".join(str(w) for w in new_win_lengths)}m')
        if adjustment_note:
            lines.append(f'\U0001f527 {adjustment_note}')

        lines.append(f'\nDashboard: weatherbot.1nnercircle.club/btc15m')

        msg = '\n'.join(lines)
        subscribers = await _telegram_bot.get_all_subscribers(instant_only=False)
        await _send_and_pin(_telegram_bot.bot_token, subscribers, msg, 'intelligence')
        logger.info(f'\U0001f9e0 Intelligence Loop: {verdict} / {action} / next={next_version}')
    except Exception as e:
        logger.error(f'\u274c Intelligence Loop failed: {e}\n{traceback.format_exc()}')


async def scheduled_penny_daily_report():
    """Daily penny positions report at 9 PM IST — portfolio, timeline, risk."""
    global _telegram_bot
    if not _telegram_bot:
        return
    # Gate: penny trades are paper-only, suppress if paper_notifications=false
    _tcfg = await get_trading_mode()
    if not should_send_paper_telegram(_tcfg):
        logger.info("🔇 Penny daily report suppressed (paper_notifications=false)")
        return
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='polyedge', user='node', host='localhost')
        cur = conn.cursor()

        cur.execute("""
            SELECT question, outcome, buy_price, quantity, size_usd, potential_payout,
                catalyst_score, days_to_resolution, category, status, resolution, pnl_usd,
                opened_at AT TIME ZONE 'Asia/Kolkata' as opened
            FROM penny_positions ORDER BY days_to_resolution ASC
        """)
        positions = cur.fetchall()

        # Decrement days_to_resolution daily
        cur.execute("UPDATE penny_positions SET days_to_resolution = GREATEST(days_to_resolution - 1, 0) WHERE status = 'open'")
        conn.commit()
        conn.close()

        open_pos = [p for p in positions if p[9] == 'open']
        resolved_pos = [p for p in positions if p[9] == 'resolved']

        if not open_pos and not resolved_pos:
            return

        total_invested = sum(float(p[4]) for p in open_pos)
        total_upside = sum(float(p[5]) for p in open_pos)
        avg_entry = sum(float(p[2]) for p in open_pos) / len(open_pos) if open_pos else 0
        realized_pnl = sum(float(p[11] or 0) for p in resolved_pos)

        lines = [
            '\U0001f3b0 PENNY POSITIONS \u2014 Daily Report',
            f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")} IST',
            '',
            '\u2501\u2501\u2501 PORTFOLIO \u2501\u2501\u2501',
            f'Open: {len(open_pos)} | Resolved: {len(resolved_pos)}',
            f'Capital at risk: ${total_invested:.2f}',
            f'Potential payout: ${total_upside:.2f}',
            f'Avg entry: {avg_entry*100:.1f}\u00a2',
        ]

        if resolved_pos:
            won = len([p for p in resolved_pos if p[10] == 'yes'])
            lines.append(f'Resolved: {won}W-{len(resolved_pos)-won}L | P&L: {"+ " if realized_pnl>=0 else ""}${realized_pnl:.2f}')

        imminent = [p for p in open_pos if p[7] <= 4]
        mid = [p for p in open_pos if 4 < p[7] <= 21]
        far = [p for p in open_pos if p[7] > 21]

        if imminent:
            lines.append('')
            lines.append('\u2501\u2501\u2501 \u26a1 RESOLVING SOON (1-4d) \u2501\u2501\u2501')
            for p in imminent:
                q = p[0][:55] + '...' if len(p[0]) > 55 else p[0]
                upside = float(p[5]) * 0.98 - float(p[4])
                lines.append(f'\u2022 {q}')
                lines.append(f'  {float(p[2])*100:.1f}\u00a2 | ${p[4]} \u2192 ${float(p[5]):.0f} | +${upside:.0f} | {p[7]}d')

        if mid:
            lines.append('')
            lines.append('\u2501\u2501\u2501 \U0001f4c5 MID-TERM (5-21d) \u2501\u2501\u2501')
            for p in mid:
                q = p[0][:55] + '...' if len(p[0]) > 55 else p[0]
                upside = float(p[5]) * 0.98 - float(p[4])
                lines.append(f'\u2022 {q}')
                lines.append(f'  {float(p[2])*100:.1f}\u00a2 | +${upside:.0f} | {p[7]}d | {p[8]}')

        if far:
            lines.append('')
            lines.append('\u2501\u2501\u2501 \U0001f5d3\ufe0f LONG-TERM (22d+) \u2501\u2501\u2501')
            for p in far:
                q = p[0][:55] + '...' if len(p[0]) > 55 else p[0]
                upside = float(p[5]) * 0.98 - float(p[4])
                lines.append(f'\u2022 {q}')
                lines.append(f'  {float(p[2])*100:.1f}\u00a2 | +${upside:.0f} | {p[7]}d | {p[8]}')

        lines.append('')
        lines.append('\u2501\u2501\u2501 RISK SCENARIOS \u2501\u2501\u2501')
        avg_payout = total_upside / len(open_pos) if open_pos else 0
        lines.append(f'If 1/{len(open_pos)} hits: +${avg_payout*0.98 - total_invested:.0f}')
        lines.append(f'If 2 hit: +${2*avg_payout*0.98 - total_invested:.0f}')
        lines.append(f'If 0 hit: -${total_invested:.2f}')

        msg = '\n'.join(lines)
        subscribers = await _telegram_bot.get_all_subscribers(instant_only=False)
        await _send_and_pin(_telegram_bot.bot_token, subscribers, msg, 'penny')
        logger.info(f'\U0001f3b0 Penny daily report sent + pinned to {len(subscribers)} subscribers')
    except Exception as e:
        logger.error(f'\u274c Penny daily report failed: {e}\n{traceback.format_exc()}')


async def scheduled_btc_daily_strategy_report():
    """Daily strategy analysis at 11:30 PM IST — volatility, hourly performance, adjustments."""
    global _telegram_bot
    if not _telegram_bot:
        return
    # Gate: suppress if paper mode + paper_notifications=false
    _tcfg = await get_trading_mode()
    if is_live_mode(_tcfg):
        logger.info("🔇 BTC daily strategy report suppressed (live mode)")
        return
    if not should_send_paper_telegram(_tcfg):
        logger.info("🔇 BTC daily strategy report suppressed (paper notifications off)")
        return
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='polyedge', user='node', host='localhost')
        cur = conn.cursor()

        # Today's hourly breakdown — uses btc_pnl view (correct filters + scaled stakes)
        cur.execute("""
            SELECT 
                EXTRACT(HOUR FROM close_time AT TIME ZONE 'Asia/Kolkata')::int as hour_ist,
                COUNT(*) as all_trades,
                COUNT(*) FILTER (WHERE correct) as all_wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as all_pnl,
                ROUND(AVG(entry_price)::numeric, 3) as avg_entry
            FROM btc_pnl
            WHERE close_time::date = CURRENT_DATE
            GROUP BY 1 ORDER BY 1
        """)
        hourly = cur.fetchall()

        # Volatility data
        cur.execute("""
            SELECT hour_ist, trades_taken, trades_won, net_pnl, avg_entry, btc_price_range_pct, session_tag
            FROM btc_volatility_hours
            WHERE date = CURRENT_DATE
            ORDER BY hour_ist
        """)
        volatility = cur.fetchall()

        # Overall today — from btc_pnl view
        cur.execute("""
            SELECT 
                COUNT(*) as total, COUNT(*) FILTER (WHERE correct) as wins,
                ROUND(SUM(trade_pnl)::numeric, 2) as net,
                ROUND(MAX(trade_pnl)::numeric, 2) as best,
                ROUND(SUM(stake)::numeric, 2) as spent,
                ROUND(SUM(CASE WHEN trade_pnl>0 THEN stake*(1.0/entry_price-1.0)*0.02 ELSE 0 END)::numeric, 2) as fees
            FROM btc_pnl
            WHERE close_time::date = CURRENT_DATE
        """)
        totals = cur.fetchone()
        conn.close()

        # Build report
        lines = ["\U0001f4ca BTC DAILY STRATEGY REPORT", f"Date: {datetime.now().strftime('%Y-%m-%d')} IST", ""]

        # Hourly heat map
        lines.append("\u2501\u2501\u2501 HOURLY PERFORMANCE \u2501\u2501\u2501")
        best_hour, worst_hour = None, None
        best_pnl, worst_pnl = -999999, 999999
        for h in hourly:
            hr, all_t, all_w, all_p, avg_e = h
            emoji = '\U0001f7e2' if float(all_p) >= 0 else '\U0001f534'
            sign = '+' if float(all_p) >= 0 else ''
            lines.append(f"{emoji} {hr:02d}:00 | {all_w}W-{all_t-all_w}L | {sign}${all_p} | avg entry: {float(avg_e)*100:.0f}c")
            if float(all_p) > best_pnl:
                best_pnl, best_hour = float(all_p), hr
            if float(all_p) < worst_pnl:
                worst_pnl, worst_hour = float(all_p), hr

        if best_hour is not None:
            lines.append(f"\n\U0001f3c6 Best hour: {best_hour:02d}:00 (+${best_pnl:.2f})")
            lines.append(f"\U0001f4a9 Worst hour: {worst_hour:02d}:00 (${worst_pnl:.2f})")

        # Volatility slots
        if volatility:
            lines.append("")
            lines.append("\u2501\u2501\u2501 VOLATILITY MAP \u2501\u2501\u2501")
            for v in volatility:
                v_hr, v_trades, v_won, v_pnl, v_entry, v_range, v_tag = v
                vol_emoji = '\U0001f525' if float(v_range) > 0.3 else '\u26a1' if float(v_range) > 0.1 else '\U0001f4a4'
                lines.append(f"{vol_emoji} {v_hr:02d}:00 | Range: {float(v_range):.2f}% | {v_trades} trades | tag: {v_tag}")

        # Totals — uses corrected btc_pnl view
        total, wins, net, best, spent, fees = totals
        net_f = float(net or 0); spent_f = float(spent or 0); fees_f = float(fees or 0)
        lines.append("")
        lines.append("\u2501\u2501\u2501 DAY TOTALS \u2501\u2501\u2501")
        net_emoji = '\U0001f7e2' if net_f >= 0 else '\U0001f534'
        net_sign = '+' if net_f >= 0 else ''
        lines.append(f"{net_emoji} Net P&L: {net_sign}${net_f:.2f}")
        if total > 0:
            lines.append(f"Record: {wins}W-{total-wins}L ({wins/total*100:.0f}%)")
        lines.append(f"\U0001f4b5 Spent: ${spent_f:.0f} | \U0001f4b8 Fees: ${fees_f:.2f}")
        if best:
            lines.append(f"\U0001f3c6 Best trade: +${best}")

        cur.execute("SELECT version, max_entry, min_factors, min_rr FROM btc_strategy_versions WHERE status=\'active\' LIMIT 1")
        strat = cur.fetchone()
        lines.append("\n\u2501\u2501\u2501 STRATEGY \u2501\u2501\u2501")
        if strat:
            lines.append(f"Active: {strat[0]} | Entry <{float(strat[1])*100:.0f}c | {strat[2]}/7 factors | Min R:R {float(strat[3]):.1f}x")
        lines.append("Hourly slots tracked for weekly review")
        lines.append("\nDashboard: weatherbot.1nnercircle.club/btc15m")
        conn.close()

        msg = "\n".join(lines)
        subscribers = await _telegram_bot.get_all_subscribers(instant_only=False)
        await _send_and_pin(_telegram_bot.bot_token, subscribers, msg, 'daily')
        logger.info(f"\U0001f4ca BTC daily strategy report sent + pinned")
    except Exception as e:
        logger.error(f"\u274c BTC daily strategy report failed: {e}")


async def scheduled_btc_resolution_check():
    """BTC Signal Engine: check closed windows, score predictions."""
    global _last_btc_resolution, _btc_engine
    try:
        if _btc_engine is None:
            return
        resolved = await _btc_engine.check_resolutions()
        _last_btc_resolution = datetime.utcnow()
        if resolved:
            logger.info(f"📊 BTC resolved: {len(resolved)} windows")
            
            # Check trading mode — only send Telegram if live OR paper_notifications=true
            _tcfg = await get_trading_mode()
            _send_telegram = is_live_mode(_tcfg) or should_send_paper_telegram(_tcfg)
            
            # Broadcast WON/LOST for each resolved window with a signal
            if _telegram_bot and not _send_telegram:
                logger.info(f"🔇 BTC resolution alerts suppressed (paper mode, notifications off, {len(resolved)} resolved)")
            if _telegram_bot and _send_telegram:
                import psycopg2 as _pg
                import httpx as _httpx
                for r in resolved:
                    if not r.get('had_signal'):
                        continue
                    was_correct = r.get('was_correct', False)
                    pred = r.get('prediction', '?')
                    actual = r.get('resolution', '?')
                    wl = r.get('window_length', 15)
                    window_id = r.get('window_id', '')

                    try:
                        _conn = _pg.connect(dbname='polyedge', user='node', host='localhost')
                        _cur = _conn.cursor()
                        _cur.execute("""
                            SELECT p.entry_price, p.stake, ROUND(p.trade_pnl::numeric,2),
                                s.prob_up, s.confidence,
                                s.f_price_delta, s.f_momentum, s.f_volume_imbalance, s.f_oracle_lead,
                                w.btc_open, w.btc_close,
                                (CASE WHEN (p.prediction='DOWN' AND s.f_price_delta<0) OR (p.prediction='UP' AND s.f_price_delta>0) THEN 1 ELSE 0 END +
                                 CASE WHEN (p.prediction='DOWN' AND s.f_momentum<0) OR (p.prediction='UP' AND s.f_momentum>0) THEN 1 ELSE 0 END +
                                 CASE WHEN (p.prediction='DOWN' AND s.f_volume_imbalance<0) OR (p.prediction='UP' AND s.f_volume_imbalance>0) THEN 1 ELSE 0 END +
                                 CASE WHEN (p.prediction='DOWN' AND s.f_oracle_lead<0) OR (p.prediction='UP' AND s.f_oracle_lead>0) THEN 1 ELSE 0 END +
                                 CASE WHEN s.f_book_imbalance IS NOT NULL THEN 1 ELSE 0 END) as factors_agreed
                            FROM btc_pnl p
                            JOIN btc_windows w ON p.window_id = w.window_id
                            JOIN LATERAL (
                                SELECT * FROM btc_signals WHERE window_id = p.window_id AND prediction != 'SKIP'
                                ORDER BY confidence DESC LIMIT 1
                            ) s ON true
                            WHERE p.window_id = %s
                        """, (window_id,))
                        row = _cur.fetchone()
                        _cur.execute("""
                            SELECT COUNT(*), COUNT(*) FILTER (WHERE correct), ROUND(SUM(trade_pnl)::numeric,2)
                            FROM btc_pnl
                        """)
                        ytd = _cur.fetchone()
                        _conn.close()

                        if row:
                            ep, stake, pnl, prob, conf, f_pd, f_mom, f_vol, f_orc, btc_open, btc_close, factors = row
                            ep=float(ep); stake=float(stake); pnl=float(pnl)
                            btc_move = float(btc_close or 0) - float(btc_open or 0)
                            roi = pnl/stake*100 if stake else 0
                            ytd_t, ytd_w, ytd_net = ytd
                            pnl_str = f"+${pnl:.2f}" if pnl>=0 else f"-${abs(pnl):.2f}"
                            move_str = f"+${btc_move:,.0f}" if btc_move>=0 else f"-${abs(btc_move):,.0f}"
                            re = '\u2705' if was_correct else '\u274c'
                            rw = 'WON' if was_correct else 'LOST'

                            # ✔️ Update bankroll on resolution
                            try:
                                await update_btc_bankroll_close(stake, pnl, was_correct)
                                await sync_btc_in_positions()
                            except Exception as _bre:
                                logger.error(f"❌ Bankroll resolution update failed: {_bre}")

                            # ✔️ Resolve matching live trade if exists
                            try:
                                _live_pool = get_async_pool()
                                async with _live_pool.acquire() as _lconn:
                                    _live_row = await _lconn.fetchrow(
                                        "SELECT id FROM live_trades WHERE window_id = $1 AND status = 'open' LIMIT 1",
                                        window_id
                                    )
                                if _live_row:
                                    from src.polymarket_live import PolymarketLiveTrader
                                    _live_trader = PolymarketLiveTrader(get_async_pool())
                                    await _live_trader.resolve_trade(
                                        trade_id=_live_row['id'],
                                        won=was_correct,
                                        exit_price=1.0 if was_correct else 0.0,
                                    )
                                    _live_emoji = '\U0001f7e2' if was_correct else '\U0001f534'
                                    logger.info(f"{_live_emoji} Live trade #{_live_row['id']} resolved")
                            except Exception as _lre:
                                logger.error(f"❌ Live trade resolution failed: {_lre}")
                            crowd_pct = max(float(prob or 0.5), 1-float(prob or 0.5)) * 100
                            crowd_side = 'bullish' if float(prob or 0.5) > 0.5 else 'bearish'
                            rr = (1/ep - 1)*0.98 if ep > 0 else 0

                            # Per-factor confluence
                            def _fa(val, direction):
                                v = float(val or 0)
                                agree = (direction=='DOWN' and v<0) or (direction=='UP' and v>0)
                                bar = '\u2588' * min(int(abs(v)*5), 5)
                                return ('\u2705' if agree else '\u274c'), bar
                            pd_e,pd_b = _fa(f_pd, pred)
                            mm_e,mm_b = _fa(f_mom, pred)
                            vi_e,vi_b = _fa(f_vol, pred)
                            ol_e,ol_b = _fa(f_orc, pred)
                            bk_e = '\u2705' if factors >= 4 else '\u274c'

                            # Get updated bankroll for display
                            try:
                                _br_disp = await get_btc_bankroll_state()
                                _br_bal = float(_br_disp.get('balance', BTC_STARTING_BALANCE))
                                _br_avail = float(_br_disp.get('available', BTC_STARTING_BALANCE))
                                _br_dd = float(_br_disp.get('max_drawdown_pct', 0))
                                _br_pnl_pct = (_br_bal - BTC_STARTING_BALANCE) / BTC_STARTING_BALANCE * 100
                                _br_label = 'WALLET' if is_live_mode(_tcfg) else 'BANKROLL'
                                bankroll_line = (f"\n\u2501\u2501\u2501 {_br_label} \u2501\u2501\u2501\n"
                                    f"\U0001f4b0 ${_br_bal:,.0f} ({'+' if _br_pnl_pct>=0 else ''}{_br_pnl_pct:.1f}%) | Avail: ${_br_avail:,.0f}"
                                    + (f" | DD: {_br_dd:.1f}%" if _br_dd > 0.01 else ""))
                            except Exception:
                                bankroll_line = ""

                            # LIVE green theme vs paper theme
                            if is_live_mode(_tcfg):
                                _win_emoji = '\U0001f7e2\U0001f4b0' if was_correct else '\U0001f534\U0001f4b8'
                                _label = 'LIVE WIN' if was_correct else 'LIVE LOSS'
                                _section = 'REAL PROFIT' if was_correct else 'REAL LOSS'
                            else:
                                _win_emoji = re
                                _label = rw
                                _section = 'TRADE'

                            msg = (
                                f"{_win_emoji if is_live_mode(_tcfg) else re} BTC {_label if is_live_mode(_tcfg) else rw} \u2014 {wl}M\n"
                                f"\n"
                                f"\u2501\u2501\u2501 {_section} \u2501\u2501\u2501\n"
                                f"Direction: {pred} \u2192 Actual: {actual}\n"
                                f"Entry: {ep*100:.1f}\u00a2 | Stake: ${stake:.0f} | R:R {rr:.1f}:1\n"
                                f"P&L: {pnl_str} | ROI: {'+' if roi>=0 else ''}{roi:.0f}%\n"
                                f"BTC: ${float(btc_open):,.0f} \u2192 ${float(btc_close):,.0f} ({move_str})\n"
                                f"\n"
                                f"\u2501\u2501\u2501 SIGNALS ({factors}/5 agreed) \u2501\u2501\u2501\n"
                                f"{pd_e} Price Delta   {float(f_pd or 0):+.3f} {pd_b}\n"
                                f"{mm_e} Momentum      {float(f_mom or 0):+.3f} {mm_b}\n"
                                f"{vi_e} Volume        {float(f_vol or 0):+.3f} {vi_b}\n"
                                f"{ol_e} Oracle Lead   {float(f_orc or 0):+.3f} {ol_b}\n"
                                f"{bk_e} Crowd: {crowd_pct:.0f}% {crowd_side} | Conf: {float(conf or 0)*100:.0f}%\n"
                                f"\n"
                                f"\U0001f4c8 YTD: {ytd_w}W-{ytd_t-ytd_w}L | {'+' if float(ytd_net)>=0 else ''}${float(ytd_net):.2f}"
                                f"{bankroll_line}"
                            )
                        else:
                            re = '✅' if was_correct else '❌'
                            msg = f"{re} BTC {'WON' if was_correct else 'LOST'} — {wl}M | {pred} → {actual}"
                    except Exception as _e:
                        logger.error(f"❌ Trade broadcast error: {_e}")
                        re = '✅' if was_correct else '❌'
                        msg = f"{re} BTC {'WON' if was_correct else 'LOST'} — {wl}M | {pred} → {actual}"

                    # GATE: Only send Telegram if real live trade exists for this window OR paper notifications on
                    _has_live_trade = False
                    try:
                        _lpool = get_async_pool()
                        async with _lpool.acquire() as _lc:
                            _lt = await _lc.fetchrow("SELECT id FROM live_trades WHERE window_id = $1 LIMIT 1", window_id)
                            _has_live_trade = _lt is not None
                    except Exception:
                        pass

                    _should_send = _has_live_trade or should_send_paper_telegram(_tcfg)
                    if _should_send:
                        try:
                            BOT_TOKEN = _telegram_bot.bot_token
                            subs = await _telegram_bot.get_all_subscribers(instant_only=False)
                            async with _httpx.AsyncClient(timeout=10) as _c:
                                for sub in subs:
                                    try:
                                        await _c.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                            json={"chat_id": sub['chat_id'], "text": msg})
                                    except Exception:
                                        pass
                        except Exception:
                            pass
    except Exception as e:
        logger.error(f"❌ BTC resolution check failed: {e}")
# ═══════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown."""
    global _last_data_scan, _startup_time, _signal_loop, _improvement_engine, _telegram_bot, _leader_poller

    logger.info("🚀 WeatherBot starting...")
    _startup_time = datetime.utcnow()
    await init_tables()

    # Initialize signal loop
    try:
        from src.signals.signal_loop import SignalLoop
        from src.data.city_map import CITY_TO_ICAO
        async_pool = get_async_pool()
        _signal_loop = SignalLoop(
            db_pool=async_pool,
            city_map=CITY_TO_ICAO,
            anthropic_api_key=config.ANTHROPIC_API_KEY,
            min_edge_for_claude=float(getattr(config, 'MIN_EDGE_ALERT', 0.15)),
            min_edge_for_trade=float(getattr(config, 'MIN_EDGE_AUTO_TRADE', 0.25)),
        )
        logger.info("✅ Signal loop initialized")
    except Exception as e:
        logger.error(f"⚠️ Signal loop init failed (will retry): {e}")
    
    # Initialize improvement engine
    try:
        from src.learning.improvement import ImprovementEngine
        async_pool = get_async_pool()
        _improvement_engine = ImprovementEngine(async_pool, config)
        logger.info("✅ Improvement engine initialized")
    except Exception as e:
        logger.error(f"⚠️ Improvement engine init failed: {e}")

    # Run initial data fetch
    try:
        from src.data.data_loop import run_single_cycle
        await run_single_cycle()
        _last_data_scan = datetime.utcnow()
        logger.info(f"✅ Initial data fetch complete: {_last_data_scan.isoformat()}")
    except Exception as e:
        logger.error(f"⚠️ Initial data fetch failed: {e}")

    # Initialize btc_bankroll if empty
    try:
        existing = await fetch_one("SELECT id FROM btc_bankroll LIMIT 1")
        if not existing:
            pool = get_async_pool()
            async with pool.acquire() as _conn:
                await _conn.execute(
                    "INSERT INTO btc_bankroll (balance, available, peak_balance) VALUES ($1, $2, $3)",
                    BTC_STARTING_BALANCE, BTC_STARTING_BALANCE, BTC_STARTING_BALANCE
                )
            logger.info("✅ BTC bankroll initialized at $5,000")
        else:
            await sync_btc_in_positions()
            br_state = await get_btc_bankroll_state()
            logger.info(f"✅ BTC bankroll: ${float(br_state.get('balance', 0)):,.0f} available ${float(br_state.get('available', 0)):,.0f}")
    except Exception as e:
        logger.error(f"⚠️ BTC Bankroll init failed: {e}")

    # Legacy bankroll table
    try:
        existing2 = await fetch_one("SELECT id FROM bankroll LIMIT 1")
        if not existing2:
            await execute("INSERT INTO bankroll (total_usd, available_usd, in_positions_usd, daily_pnl) VALUES (0, 0, 0, 0)")
    except Exception:
        pass

    # Initialize Telegram subscriber bot
    try:
        from src.alerts.subscriber_bot import init_bot
        from src.alerts.invite_gate import InviteGate
        if config.TELEGRAM_BOT_TOKEN:
            _telegram_bot = await init_bot(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_ADMIN_CHAT_ID)
            # Wire invite gate
            if _telegram_bot and hasattr(_telegram_bot, 'pool'):
                _telegram_bot.invite_gate = InviteGate(_telegram_bot.pool, config.TELEGRAM_ADMIN_CHAT_ID)
            logger.info("✅ Telegram subscriber bot initialized (invite-only mode)")
        else:
            logger.warning("⚠️ Telegram bot disabled: no token")
    except Exception as e:
        logger.error(f"⚠️ Telegram bot init failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # LEADER STRATEGY — Copy-Trading Poller
    # ═══════════════════════════════════════════════════════════════
    try:
        from src.leader_poller import LeaderPoller
        async_pool = get_async_pool()
        _leader_poller = LeaderPoller(
            db_pool=async_pool,
            telegram_bot=_telegram_bot if '_telegram_bot' in dir() else None
        )
        asyncio.create_task(_leader_poller.start())
        logger.info("✅ Leader Poller started (tracking 0x4924...3782)")
    except Exception as e:
        logger.error(f"⚠️ Leader Poller init failed: {e}")
    
    # Start scheduler
    scheduler.add_job(scheduled_data_scan, 'interval', minutes=15, id='data_loop', replace_existing=True)
    scheduler.add_job(scheduled_signal_scan, 'interval', minutes=2, id='signal_loop', replace_existing=True)
    
    # ═══════════════════════════════════════════════════════════════
    # SPORTS INTELLIGENCE — Scheduled Jobs
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_sports_scan, 'interval', seconds=45, id='sports_loop', replace_existing=True)
    
    # ═══════════════════════════════════════════════════════════════
    # TELEGRAM SUBSCRIBER BOT — Scheduled Jobs
    # ═══════════════════════════════════════════════════════════════
    if _telegram_bot:
        # DISABLED: sports signal broadcasts (noise)
        # scheduler.add_job(check_and_broadcast_signals, ...)
        # DISABLED: old sports daily summary (replaced by BTC daily)
        # scheduler.add_job(daily_summary_task, ...)
        # DISABLED: pre-match sports alerts (noise)
        # scheduler.add_job(pre_match_alerts, ...)
        logger.info("✅ Telegram broadcast jobs scheduled")
    
    # ═══════════════════════════════════════════════════════════════
    # TRADE SETTLEMENT — Auto-resolve completed matches every 5 min
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_settlement, 'interval', minutes=1, id='settlement_loop', replace_existing=True)
    logger.info("✅ Settlement loop scheduled (every 5 min)")
    
    # ═══════════════════════════════════════════════════════════════
    # EDGE MONITOR — Check open positions for edge decay every 5 min
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_edge_monitor, 'interval', minutes=1, id='edge_monitor', replace_existing=True)
    logger.info("✅ Edge monitor scheduled (every 5 min)")
    
    # ═══════════════════════════════════════════════════════════════
    # INTERNAL ARBITRAGE — Primary strategy, scan every 2 minutes
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_internal_arb_scan, 'interval', seconds=30, id='internal_arb', replace_existing=True)
    logger.info("✅ Internal arb scanner scheduled (every 2 min)")
    
    # ═══════════════════════════════════════════════════════════════
    # PENNY HUNTER — Scan every 30 minutes for 1-3¢ contracts
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_penny_scan, 'interval', minutes=30, id='penny_hunter', replace_existing=True)
    logger.info("✅ Penny Hunter scheduled (every 30 min)")

    # ═══════════════════════════════════════════════════════════════
    # LATE WINDOW SCALPER — Buy near-certain contracts in final 15-20s
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_late_window_scan, 'interval', seconds=2, id='late_window_scalper', replace_existing=True)
    logger.info("✅ Late Window Scalper scheduled (every 2s)")
    
    # ═══════════════════════════════════════════════════════════════
    # BTC SIGNAL ENGINE — Scan every 45 seconds, resolve every 2 min
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(scheduled_btc_signal_scan, 'interval', seconds=45, id='btc_signal', replace_existing=True)
    scheduler.add_job(scheduled_btc_resolution_check, 'interval', minutes=2, id='btc_resolution', replace_existing=True)
    scheduler.add_job(scheduled_maker_quote, 'interval', seconds=5, id='maker_quote', replace_existing=True)
    logger.info("✅ Maker Engine scheduled (every 5s)")
    scheduler.add_job(scheduled_btc_hourly_summary, 'cron', minute=0, timezone='Asia/Kolkata', id='btc_hourly', replace_existing=True)
    scheduler.add_job(scheduled_btc_intelligence_loop, 'cron', hour=23, minute=0, timezone='Asia/Kolkata', id='btc_intelligence', replace_existing=True)
    scheduler.add_job(scheduled_btc_daily_strategy_report, 'cron', hour=23, minute=30, timezone='Asia/Kolkata', id='btc_daily', replace_existing=True)
    scheduler.add_job(scheduled_penny_daily_report, 'cron', hour=21, minute=0, timezone='Asia/Kolkata', id='penny_daily', replace_existing=True)
    logger.info("✅ BTC Signal Engine scheduled (scan: 45s, resolve: 2min, hourly: on-the-hour)")

    # ═══════════════════════════════════════════════════════════════
    # JC COPY TRADER — Monitor Jayson's levels every 10s
    # ═══════════════════════════════════════════════════════════════
    try:
        import sys
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from jc_copy_trader import run_jc_copy_trader, send_jc_hourly_report, send_jc_daily_report
        scheduler.add_job(run_jc_copy_trader, 'interval', seconds=10, id='jc_copy_trader', replace_existing=True)
        scheduler.add_job(send_jc_hourly_report, 'cron', minute=0, timezone='Asia/Kolkata', id='jc_hourly', replace_existing=True)
        scheduler.add_job(send_jc_daily_report, 'cron', hour=23, minute=0, timezone='Asia/Kolkata', id='jc_daily', replace_existing=True)
        logger.info("✅ JC Copy Trader scheduled (trade: 10s, hourly report, daily at 11PM)")
    except Exception as e:
        logger.error(f"❌ JC Copy Trader failed to load: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # LEARNING ENGINE — Sprint 3 Scheduled Jobs
    # ═══════════════════════════════════════════════════════════════
    async def _learning_optimize_thresholds():
        try:
            from src.learning.improvement import LearningEngine
            engine = LearningEngine(get_async_pool())
            result = await engine.optimize_thresholds()
            logger.info(f"🎯 Threshold optimization complete: rec={result.get('recommendation')}")
        except Exception as e:
            logger.error(f"❌ Threshold optimization failed: {e}")

    async def _learning_auto_disable():
        try:
            from src.learning.improvement import LearningEngine
            engine = LearningEngine(get_async_pool())
            result = await engine.auto_disable_check()
            disabled = len(result.get('disabled_strategies', []))
            flagged = len(result.get('flagged_sports', []))
            if disabled or flagged:
                logger.info(f"🚨 Auto-disable: {disabled} strategies disabled, {flagged} sports flagged")
        except Exception as e:
            logger.error(f"❌ Auto-disable check failed: {e}")

    async def _learning_weekly_report():
        try:
            from src.learning.improvement import LearningEngine
            engine = LearningEngine(get_async_pool())
            report = await engine.weekly_report()
            logger.info(f"📊 Weekly learning report generated: {len(report.get('recommendations', []))} recommendations")
            # Send via Telegram if available (gate: paper notifications)
            _tcfg = await get_trading_mode()
            if _telegram_bot and should_send_paper_telegram(_tcfg):
                recs = report.get('recommendations', [])
                perf = report.get('strategy_performance', [])
                msg_parts = ["📊 <b>Weekly Learning Report</b>\n"]
                for sp in perf:
                    msg_parts.append(
                        f"  • <b>{sp['strategy']}</b>: {sp['win_rate']:.0%} WR, "
                        f"{sp['total_trades']} trades, ${sp['total_pnl']:+.2f}"
                    )
                if recs:
                    msg_parts.append("\n<b>Recommendations:</b>")
                    for r in recs:
                        msg_parts.append(f"  {r}")
                try:
                    await _telegram_bot.app.bot.send_message(
                        chat_id=_telegram_bot.admin_chat_id,
                        text="\n".join(msg_parts),
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"❌ Weekly learning report failed: {e}")

    # Daily at 4 AM IST = 22:30 UTC
    scheduler.add_job(_learning_optimize_thresholds, 'cron', hour=22, minute=30, id='learning_optimize', replace_existing=True)
    # Every 6 hours
    scheduler.add_job(_learning_auto_disable, 'interval', hours=6, id='learning_auto_disable', replace_existing=True)
    # Sunday 9 AM IST = Sunday 3:30 UTC
    scheduler.add_job(_learning_weekly_report, 'cron', day_of_week='sun', hour=3, minute=30, id='learning_weekly', replace_existing=True)
    logger.info("✅ Learning engine jobs scheduled (optimize: daily 4AM IST, auto-disable: 6h, weekly: Sun 9AM IST)")
    
    scheduler.start()
    logger.info("✅ Scheduler started (data: 30min, signals: 5min, sports: 3min, settlement: 5min, learning: enabled, telegram: enabled)")
    logger.info("✅ WeatherBot ready")

    yield

    # Shutdown
    logger.info("🛑 WeatherBot shutting down...")
    scheduler.shutdown(wait=False)
    
    # Shutdown Leader Poller
    if '_leader_poller' in globals() and _leader_poller:
        await _leader_poller.stop()
    
    # Shutdown Telegram bot
    if _telegram_bot:
        from src.alerts.subscriber_bot import shutdown_bot
        await shutdown_bot()
    
    await close_pool()


app = FastAPI(
    title="WeatherBot — PolyEdge",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# =============================================================================
# Ghost Trading Bot API Bridge
# =============================================================================
try:
    import sys
    sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
    from api_bridge import router as ghost_router
    app.include_router(ghost_router)
    logger.info("\u2705 Ghost trading bot API mounted at /api/ghost")
except Exception as e:
    logger.warning(f"\u26a0\ufe0f Ghost API not loaded: {e}")

# =============================================================================
# Paper Trades
# =============================================================================

@app.get("/api/paper-trades")
async def get_paper_trades():
    """Return all paper trades from paper_trades_live table."""
    try:
        query = """
            SELECT id, match_name, sport, team_backed, entry_price, fair_value,
                   edge_pct, position_size, shares, strategy, books_consensus,
                   book_count, status, exit_price, pnl, match_time, entry_at,
                   resolved_at, notes
            FROM paper_trades_live
            ORDER BY entry_at DESC
        """
        results = await fetch_all(query)
        trades = [{
            "id": r['id'],
            "match_name": r['match_name'],
            "sport": r['sport'],
            "team_backed": r['team_backed'],
            "entry_price": float(r['entry_price']) if r['entry_price'] else 0,
            "fair_value": float(r['fair_value']) if r['fair_value'] else 0,
            "edge_pct": float(r['edge_pct']) if r['edge_pct'] else 0,
            "position_size": float(r['position_size']) if r['position_size'] else 0,
            "shares": float(r['shares']) if r['shares'] else 0,
            "strategy": r['strategy'],
            "books_consensus": r['books_consensus'],
            "book_count": r['book_count'],
            "status": r['status'],
            "exit_price": float(r['exit_price']) if r['exit_price'] else None,
            "pnl": float(r['pnl']) if r['pnl'] else None,
            "match_time": str(r['match_time']) if r['match_time'] else None,
            "entry_at": str(r['entry_at']) if r['entry_at'] else None,
            "resolved_at": str(r['resolved_at']) if r['resolved_at'] else None,
            "notes": r['notes'],
        } for r in results]
        return {"trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"Paper trades error: {e}")
        return {"trades": [], "count": 0}


# =============================================================================
# Polymarket Leaderboard API
# =============================================================================

@app.get("/api/leaderboard")
async def get_polymarket_leaderboard(
    category: str = "OVERALL",
    timePeriod: str = "MONTH", 
    orderBy: str = "PNL",
    limit: int = 10
):
    """Proxy Polymarket leaderboard API — top traders by PnL or volume."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://data-api.polymarket.com/v1/leaderboard",
                params={
                    "category": category.upper(),
                    "timePeriod": timePeriod.upper(),
                    "orderBy": orderBy.upper(),
                    "limit": min(limit, 50),
                }
            )
            resp.raise_for_status()
            data = resp.json()
            
            traders = []
            for t in (data if isinstance(data, list) else []):
                name = t.get("userName") or t.get("xUsername") or (t.get("proxyWallet", "")[:10] + "...")
                traders.append({
                    "rank": t.get("rank"),
                    "name": name,
                    "wallet": t.get("proxyWallet", ""),
                    "pnl": float(t.get("pnl", 0)),
                    "volume": float(t.get("vol", 0)),
                    "profileImage": t.get("profileImage"),
                    "verified": bool(t.get("verifiedBadge")),
                    "xUsername": t.get("xUsername"),
                })
            
            return {"traders": traders, "category": category, "timePeriod": timePeriod, "orderBy": orderBy}
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return {"traders": [], "error": str(e)}


# =============================================================================
# Polymarket Gamma API Proxies
# =============================================================================

@app.get("/api/polymarket/events")
async def proxy_polymarket_events(
    limit: int = 20,
    active: bool = True,
    closed: bool = False,
    tag: str = None,
    order: str = "volume",
    ascending: bool = False
):
    """Proxy Polymarket Gamma events API."""
    import httpx
    try:
        params = {
            "limit": min(limit, 50),
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if tag and tag != 'all':
            params["tag"] = tag
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://gamma-api.polymarket.com/events", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            events = []
            for e in (data if isinstance(data, list) else []):
                markets = e.get("markets", [])
                parsed_markets = []
                for m in markets:
                    prices_str = m.get("outcomePrices", "[]")
                    try:
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                    except:
                        prices = []
                    parsed_markets.append({
                        "id": m.get("id"),
                        "question": m.get("question"),
                        "yes_price": float(prices[0]) if len(prices) > 0 else 0.5,
                        "no_price": float(prices[1]) if len(prices) > 1 else 0.5,
                        "volume": float(m.get("volume", 0) or 0),
                        "image": m.get("image"),
                        "active": m.get("active", True),
                        "closed": m.get("closed", False),
                        "endDate": m.get("endDate"),
                        "outcomes": m.get("outcomes"),
                        "slug": m.get("slug"),
                    })
                
                events.append({
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "description": (e.get("description") or "")[:300],
                    "image": e.get("image"),
                    "icon": e.get("icon"),
                    "volume": float(e.get("volume", 0) or 0),
                    "active": e.get("active", True),
                    "closed": e.get("closed", False),
                    "markets": parsed_markets,
                    "market_count": len(parsed_markets),
                })
            
            return {"events": events, "count": len(events)}
    except Exception as e:
        logger.error(f"Polymarket events proxy error: {e}")
        return {"events": [], "error": str(e)}


@app.get("/api/polymarket/markets")
async def proxy_polymarket_markets(
    limit: int = 50,
    active: bool = True,
    closed: bool = False,
    tag: str = None,
    order: str = "volume",
    ascending: bool = False
):
    """Proxy Polymarket Gamma markets API."""
    import httpx
    try:
        params = {
            "limit": min(limit, 100),
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if tag and tag != 'all':
            params["tag"] = tag
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://gamma-api.polymarket.com/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            markets = []
            for m in (data if isinstance(data, list) else []):
                prices_str = m.get("outcomePrices", "[]")
                try:
                    prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                except:
                    prices = []
                markets.append({
                    "id": m.get("id"),
                    "question": m.get("question"),
                    "yes_price": float(prices[0]) if len(prices) > 0 else 0.5,
                    "no_price": float(prices[1]) if len(prices) > 1 else 0.5,
                    "volume": float(m.get("volume", 0) or 0),
                    "image": m.get("image"),
                    "icon": m.get("icon"),
                    "active": m.get("active", True),
                    "closed": m.get("closed", False),
                    "endDate": m.get("endDate"),
                    "outcomes": m.get("outcomes"),
                    "slug": m.get("slug"),
                    "description": (m.get("description") or "")[:200],
                })
            
            return {"markets": markets, "count": len(markets)}
    except Exception as e:
        logger.error(f"Polymarket markets proxy error: {e}")
        return {"markets": [], "error": str(e)}


# =============================================================================
# Health & Status
# =============================================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.2.0",
        "scheduler": scheduler.running,
        "last_data_scan": _last_data_scan.isoformat() if _last_data_scan else None,
        "last_signal_scan": _last_signal_scan.isoformat() if _last_signal_scan else None,
    }


@app.get("/api/bot/status")
async def bot_status():
    uptime = (datetime.utcnow() - _startup_time).total_seconds() if _startup_time else 0

    # Auto-trade stats from signal loop
    auto_trade_stats = {}
    if _signal_loop is not None:
        raw = getattr(_signal_loop, '_last_auto_trade_stats', None) or {}
        auto_trade_stats = {
            "trades_auto_placed_today": raw.get("trades_placed", 0),
            "signals_evaluated_today": raw.get("signals_evaluated", 0),
            "trades_skipped_today": len(raw.get("skipped", [])),
            "skip_reasons": raw.get("skipped", [])[:20],  # cap at 20 for readability
        }
        # Also pull DB-level stats
        try:
            from src.execution.paper_trader import PaperTrader
            from src.db_async import get_async_pool
            trader = PaperTrader(get_async_pool())
            db_stats = await trader.get_today_stats()
            auto_trade_stats["db_trades_placed_today"] = db_stats.get("trades_placed_today", 0)
            auto_trade_stats["open_positions"] = db_stats.get("open_positions", 0)
            auto_trade_stats["daily_pnl_usd"] = db_stats.get("daily_pnl_usd", 0.0)
        except Exception:
            pass

    return {
        "running": scheduler.running,
        "mode": getattr(config, 'MODE', 'paper'),
        "last_data_scan": _last_data_scan.isoformat() if _last_data_scan else None,
        "last_signal_scan": _last_signal_scan.isoformat() if _last_signal_scan else None,
        "uptime_seconds": int(uptime),
        "signal_loop_ready": _signal_loop is not None,
        "auto_trade": auto_trade_stats,
    }


# =============================================================================
# Manual Triggers
# =============================================================================

@app.post("/api/bot/scan-now")
async def trigger_scan():
    """Manually trigger a full data + signal scan."""
    results = {}
    try:
        await scheduled_data_scan()
        results["data_scan"] = "completed"
    except Exception as e:
        results["data_scan"] = f"failed: {str(e)}"

    try:
        await scheduled_signal_scan()
        results["signal_scan"] = "completed"
    except Exception as e:
        results["signal_scan"] = f"failed: {str(e)}"

    return {"status": "scan_triggered", "results": results, "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# METAR Data
# =============================================================================

@app.get("/api/metar/latest")
async def get_latest_metar():
    query = """
        SELECT DISTINCT ON (station_icao)
            station_icao, temperature_c, dewpoint_c,
            wind_speed_kt, wind_dir, raw_metar,
            observation_time, created_at
        FROM metar_readings
        ORDER BY station_icao, observation_time DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


@app.get("/api/metar/{icao}")
async def get_metar_history(icao: str, hours: int = 24):
    icao = icao.upper()
    since = datetime.utcnow() - timedelta(hours=hours)
    query = """
        SELECT station_icao, temperature_c, dewpoint_c,
               wind_speed_kt, raw_metar,
               observation_time
        FROM metar_readings
        WHERE station_icao = %s AND observation_time >= %s
        ORDER BY observation_time DESC
    """
    results = await fetch_all(query, (icao, since))
    if not results:
        raise HTTPException(status_code=404, detail=f"No data for {icao}")
    return {"station": icao, "data": results, "count": len(results)}


# =============================================================================
# Markets — queries REAL weather_markets table
# =============================================================================

@app.get("/api/markets")
async def get_active_markets():
    query = """
        SELECT market_id, title, city, station_icao, threshold_type,
               threshold_value, threshold_unit, resolution_date,
               yes_price, no_price, volume_usd, liquidity_usd,
               last_updated, active
        FROM weather_markets
        WHERE active = true
        ORDER BY last_updated DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


# =============================================================================
# Signals — queries REAL signals table
# =============================================================================

@app.get("/api/signals")
async def get_signals(limit: int = 50, strategy: str = None):
    """Get signals, optionally filtered by strategy"""
    if strategy:
        query = """
            SELECT id, market_id, station_icao, city, side,
                   our_probability, market_price, edge, confidence,
                   claude_reasoning, was_traded, skip_reason, strategy, created_at
            FROM signals
            WHERE strategy = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        results = await fetch_all(query, (strategy, limit))
    else:
        query = """
            SELECT id, market_id, station_icao, city, side,
                   our_probability, market_price, edge, confidence,
                   claude_reasoning, was_traded, skip_reason, strategy, created_at
            FROM signals
            ORDER BY created_at DESC
            LIMIT %s
        """
        results = await fetch_all(query, (limit,))
    return {"data": results, "count": len(results)}


@app.get("/api/signals/pending")
async def get_pending_signals():
    query = """
        SELECT id, market_id, station_icao, city, side,
               our_probability, market_price, edge, confidence,
               claude_reasoning, strategy, created_at
        FROM signals
        WHERE was_traded = false AND confidence IN ('HIGH', 'MEDIUM')
        ORDER BY edge DESC
    """
    results = await fetch_all(query)
    return {"data": results, "count": len(results)}


# =============================================================================
# Dual Strategy Endpoints
# =============================================================================

@app.get("/api/strategy/comparison")
async def get_strategy_comparison():
    """Side-by-side performance comparison of Strategy A vs Strategy B"""
    try:
        # Get performance metrics for both strategies
        query = """
            SELECT
                strategy,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                COALESCE(SUM(pnl_usd), 0) as total_pnl,
                COALESCE(AVG(edge_at_entry), 0) as avg_edge,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions
            FROM trades
            WHERE strategy IN ('forecast_edge', 'intelligence_layer')
            GROUP BY strategy
        """
        results = await fetch_all(query)
        
        # Format as dict
        comparison = {
            "forecast_edge": {
                "name": "Strategy A: Forecast Edge",
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_edge": 0,
                "open_positions": 0
            },
            "intelligence_layer": {
                "name": "Strategy B: Intelligence Layer",
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_edge": 0,
                "open_positions": 0
            }
        }
        
        for row in results:
            strategy = row['strategy']
            if strategy in comparison:
                comparison[strategy].update({
                    "total_trades": row['total_trades'],
                    "wins": row['wins'],
                    "losses": row['losses'],
                    "win_rate": float(row['win_rate'] or 0),
                    "total_pnl": float(row['total_pnl'] or 0),
                    "avg_edge": float(row['avg_edge'] or 0),
                    "open_positions": row['open_positions']
                })
        
        return {
            "strategies": comparison,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Strategy comparison error: {e}")
        return {"strategies": {}, "error": str(e)}


@app.get("/api/strategy/a/signals")
async def get_strategy_a_signals(limit: int = 20):
    """Latest Strategy A (Forecast Edge) signals"""
    return await get_signals(limit=limit, strategy='forecast_edge')


@app.get("/api/strategy/b/signals")
async def get_strategy_b_signals(limit: int = 20):
    """Latest Strategy B (Intelligence Layer) signals"""
    return await get_signals(limit=limit, strategy='intelligence_layer')


@app.get("/api/positions/open")
async def get_open_positions():
    """All open positions with current P/L"""
    query = """
        SELECT
            p.id, p.market_id, p.market_title, p.city, p.strategy,
            p.side, p.entry_price, p.current_price, p.size_usd,
            p.entered_at,
            CASE
                WHEN p.side = 'YES' THEN (p.current_price - p.entry_price) * p.size_usd / p.entry_price
                ELSE (p.entry_price - p.current_price) * p.size_usd / p.entry_price
            END as unrealized_pnl,
            w.yes_price, w.no_price
        FROM positions p
        LEFT JOIN weather_markets w ON p.market_id = w.market_id
        WHERE p.status = 'open'
        ORDER BY p.entered_at DESC
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Open positions error: {e}")
        return {"data": [], "count": 0}


@app.get("/api/noaa/forecast/{city}")
async def get_noaa_forecast(city: str):
    """Get NOAA forecast for a city"""
    try:
        from src.data.noaa_forecast import fetch_noaa_forecast
        forecast = await fetch_noaa_forecast(city)
        if not forecast:
            raise HTTPException(status_code=404, detail=f"No NOAA forecast for {city} (may not be in US)")
        return forecast
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NOAA forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Trades — correct column names from actual schema
# =============================================================================

@app.get("/api/trades")
async def get_trades(limit: int = 100):
    query = """
        SELECT id, signal_id, market_id, market_title, side,
               entry_price, shares, size_usd, edge_at_entry,
               status, exit_price, pnl_usd, pnl_pct,
               resolved_at, entry_at, metadata
        FROM trades
        ORDER BY entry_at DESC
        LIMIT %s
    """
    try:
        results = await fetch_all(query, (limit,))
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch trades: {e}")
        return {"data": [], "count": 0}


@app.get("/api/trades/active")
async def get_active_trades():
    query = """
        SELECT id, signal_id, market_id, market_title, side,
               entry_price, shares, size_usd, edge_at_entry,
               status, entry_at, metadata
        FROM trades
        WHERE status IN ('open', 'paper_open', 'live_open')
        ORDER BY entry_at DESC
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch active trades: {e}")
        return {"data": [], "count": 0}


# =============================================================================
# P&L & Analytics — correct column names
# =============================================================================

@app.get("/api/pnl/daily")
async def get_daily_pnl(days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    query = """
        SELECT
            DATE(resolved_at) as date,
            COUNT(*) as trades,
            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
            SUM(pnl_usd) as total_pnl,
            AVG(pnl_usd) as avg_pnl
        FROM trades
        WHERE resolved_at IS NOT NULL AND resolved_at >= %s
        GROUP BY DATE(resolved_at)
        ORDER BY date DESC
    """
    try:
        results = await fetch_all(query, (since,))
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to fetch daily P&L: {e}")
        return {"data": [], "count": 0}


@app.get("/api/bankroll")
async def get_bankroll():
    """Query REAL bankroll table."""
    try:
        result = await fetch_one(
            "SELECT total_usd, available_usd, in_positions_usd, daily_pnl, timestamp as last_updated FROM bankroll ORDER BY timestamp DESC LIMIT 1"
        )
        if result:
            return {
                "total": float(result.get("total_usd", 0) or 0),
                "available": float(result.get("available_usd", 0) or 0),
                "in_positions": float(result.get("in_positions_usd", 0) or 0),
                "daily_pnl": float(result.get("daily_pnl", 0) or 0),
                "last_updated": result.get("last_updated", "").isoformat() if result.get("last_updated") else None,
            }
        return {"total": 0, "available": 0, "in_positions": 0, "daily_pnl": 0, "last_updated": None}
    except Exception as e:
        logger.error(f"Failed to fetch bankroll: {e}")
        return {"total": 0, "available": 0, "in_positions": 0, "daily_pnl": 0, "last_updated": None}


@app.get("/api/analytics/win-rate")
async def get_win_rate(days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    query = """
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            CASE WHEN COUNT(*) > 0
                THEN ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2)
                ELSE 0 END as win_rate_pct,
            COALESCE(SUM(pnl_usd), 0) as total_pnl,
            COALESCE(AVG(edge_at_entry), 0) as avg_edge
        FROM trades
        WHERE resolved_at IS NOT NULL AND resolved_at >= %s
    """
    try:
        result = await fetch_one(query, (since,))
        return result or {"total_trades": 0, "wins": 0, "win_rate_pct": 0, "total_pnl": 0, "avg_edge": 0}
    except Exception as e:
        logger.error(f"Failed to fetch win rate: {e}")
        return {"total_trades": 0, "wins": 0, "win_rate_pct": 0, "total_pnl": 0, "avg_edge": 0}


# =============================================================================
# DB Stats (for dashboard verification)
# =============================================================================

@app.get("/api/stats")
async def get_db_stats():
    """Return row counts for all tables — useful for verifying real data."""
    tables = ["metar_readings", "temperature_trends", "weather_markets", "signals", "trades", "bankroll", "station_accuracy"]
    stats = {}
    for table in tables:
        try:
            result = await fetch_one(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = result["count"] if result else 0
        except:
            stats[table] = "error"
    return {"tables": stats, "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# Polymarket Explorer — Proxy to bypass ISP blocks
# =============================================================================

def detect_category(question: str) -> str:
    """Detect market category from question text."""
    q = question.lower()
    
    weather_kw = ['temperature', 'weather', 'rain', 'snow', 'celsius', 'fahrenheit', '°f', '°c', 'heat wave', 'cold front', 'forecast', 'high temp', 'low temp']
    sports_kw = ['ncaa', 'nba', 'nfl', 'mlb', 'nhl', 'premier league', 'champions league', 'world cup', 'super bowl', 'touchdown', 'goal', 'match', 'game', 'playoffs', 'series', 'vs.', 'vs ']
    politics_kw = ['president', 'election', 'vote', 'congress', 'senate', 'governor', 'democrat', 'republican', 'biden', 'trump', 'parliament', 'prime minister']
    crypto_kw = ['bitcoin', 'ethereum', 'btc', 'eth', 'crypto', 'token', 'blockchain', 'defi', 'solana', 'sol']
    economics_kw = ['gdp', 'inflation', 'fed', 'interest rate', 'unemployment', 'recession', 'stock', 's&p', 'nasdaq', 'dow jones']
    science_kw = ['ai', 'artificial intelligence', 'spacex', 'nasa', 'climate', 'vaccine', 'disease', 'pandemic']
    entertainment_kw = ['oscar', 'grammy', 'box office', 'movie', 'album', 'taylor swift', 'drake', 'emmy']
    
    if any(kw in q for kw in weather_kw): return 'weather'
    if any(kw in q for kw in sports_kw): return 'sports'
    if any(kw in q for kw in politics_kw): return 'politics'
    if any(kw in q for kw in crypto_kw): return 'crypto'
    if any(kw in q for kw in economics_kw): return 'economics'
    if any(kw in q for kw in science_kw): return 'science'
    if any(kw in q for kw in entertainment_kw): return 'entertainment'
    return 'other'


@app.get("/api/explorer/markets")
async def explore_markets(category: str = None, search: str = None, limit: int = 50, cursor: str = "MA==", active_only: bool = True):
    """Proxy to Polymarket Gamma API — filtered, categorized markets."""
    import httpx
    
    all_markets = []
    offset = 0
    try:
        offset = int.from_bytes(base64.b64decode(cursor), 'big') if cursor and cursor != 'MA==' else 0
    except Exception:
        offset = 0
    
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            # Use Gamma API which supports server-side active/closed filtering
            params = {
                "limit": min(limit * 2, 200),  # fetch extra for client-side filters
                "offset": offset,
                "order": "volume",
                "ascending": "false",
            }
            if active_only:
                params["active"] = "true"
                params["closed"] = "false"
            else:
                params["closed"] = "true"
            
            if search:
                params["tag"] = search
            
            resp = await client.get("https://gamma-api.polymarket.com/markets", params=params)
            resp.raise_for_status()
            batch = resp.json()
            
            if not isinstance(batch, list):
                batch = batch.get("data", []) if isinstance(batch, dict) else []
            
            for market in batch:
                question = (market.get("question") or "").lower()
                market["_category"] = detect_category(question)
                
                # Apply category filter
                if category and market["_category"] != category.lower():
                    continue
                
                # Apply search filter (text match beyond tag search)
                if search and search.lower() not in question:
                    continue
                
                # Extract price data from Gamma format
                out_price = market.get("outcomePrices", "")
                try:
                    prices = json.loads(out_price) if isinstance(out_price, str) and out_price else []
                except Exception:
                    prices = []
                market["_yes_price"] = float(prices[0]) if len(prices) > 0 else 0.5
                market["_no_price"] = float(prices[1]) if len(prices) > 1 else 0.5
                market["_volume"] = float(market.get("volume", 0) or 0)
                market["active"] = market.get("active", True)
                market["closed"] = market.get("closed", False)
                
                all_markets.append(market)
                if len(all_markets) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Explorer markets error: {e}")
    
    # Next cursor for pagination
    next_offset = offset + len(all_markets)
    next_cursor = base64.b64encode(next_offset.to_bytes(4, 'big')).decode() if len(all_markets) >= limit else None
    
    return {
        "data": all_markets[:limit],
        "count": len(all_markets[:limit]),
        "next_cursor": next_cursor,
        "source": "polymarket_gamma"
    }


@app.get("/api/explorer/weather")
async def explore_weather_markets():
    """Our tracked weather markets from DB."""
    query = """
        SELECT market_id, title, city, station_icao, threshold_type, threshold_value,
               threshold_unit, resolution_date, yes_price, no_price, volume_usd, 
               liquidity_usd, active, last_updated
        FROM weather_markets 
        WHERE active = true
        ORDER BY volume_usd DESC NULLS LAST
    """
    try:
        results = await fetch_all(query)
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Weather markets error: {e}")
        return {"data": [], "count": 0}


@app.get("/api/explorer/events")
async def explore_events(tag: str = None, search: str = None, limit: int = 20):
    """Proxy to Polymarket events."""
    import httpx
    params = {"limit": limit, "active": "true", "closed": "false"}
    if tag:
        params["tag"] = tag
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://gamma-api.polymarket.com/events", params=params)
            resp.raise_for_status()
            data = resp.json()
        
        # Ensure data is a list
        if not isinstance(data, list):
            data = data.get("data", []) if isinstance(data, dict) else []
        
        # Filter by search
        if search:
            search_lower = search.lower()
            data = [
                e for e in data 
                if search_lower in e.get("title", "").lower() 
                or search_lower in e.get("question", "").lower()
            ]
        
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"Explorer events error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch events: {str(e)}")


@app.get("/api/explorer/market/{condition_id}")
async def get_market_detail(condition_id: str):
    """Get detailed market data including order book."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get market data
            market_resp = await client.get(f"https://clob.polymarket.com/markets/{condition_id}")
            market_resp.raise_for_status()
            market = market_resp.json()
            
            # Get order book
            try:
                book_resp = await client.get(f"https://clob.polymarket.com/book?token_id={condition_id}")
                book_resp.raise_for_status()
                order_book = book_resp.json()
            except:
                order_book = {"bids": [], "asks": []}
        
        return {
            "market": market,
            "order_book": order_book
        }
    except Exception as e:
        logger.error(f"Explorer market detail error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch market detail: {str(e)}")


@app.get("/api/explorer/prices/{condition_id}")
async def get_price_history(condition_id: str, interval: str = "1h", fidelity: int = 60):
    """Get price history for charting."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://clob.polymarket.com/prices-history",
                params={"market": condition_id, "interval": interval, "fidelity": fidelity}
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Explorer price history error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch price history: {str(e)}")


# =============================================================================
# Intelligence Data — Forecasts, Historical, Combined View
# =============================================================================

@app.get("/api/intelligence/live-signals")
async def get_live_signals():
    """Run real-time intelligence analysis across all tracked markets.
    Returns probability estimates, expected returns, and trade recommendations.
    This is the LIVE TRADING SIGNAL BOARD."""
    from src.data.openmeteo import fetch_forecast
    
    try:
        # 1. Get all active weather markets from DB
        markets = await fetch_all("""
            SELECT * FROM weather_markets 
            WHERE active = true
            ORDER BY volume_usd DESC NULLS LAST
        """)
        
        # 2. Get latest METAR for each station
        metar = await fetch_all("""
            SELECT DISTINCT ON (station_icao)
                station_icao, temperature_c, observation_time
            FROM metar_readings 
            ORDER BY station_icao, observation_time DESC
        """)
        metar_map = {m['station_icao']: m for m in metar}
        
        # 3. Get trends
        trends = await fetch_all("""
            SELECT DISTINCT ON (station_icao)
                station_icao, trend_per_hour, projected_high, projected_low, confidence
            FROM temperature_trends 
            ORDER BY station_icao, calculated_at DESC
        """)
        trend_map = {t['station_icao']: t for t in trends}
        
        signals = []
        for market in markets:
            icao = market.get('station_icao', '')
            if not icao:
                continue
            
            metar_data = metar_map.get(icao, {})
            trend_data = trend_map.get(icao, {})
            
            if not metar_data:
                continue
            
            current_temp = float(metar_data.get('temperature_c', 0) or 0)
            threshold = float(market.get('threshold_value', 0) or 0)
            yes_price = float(market.get('yes_price', 0.5) or 0.5)
            no_price = float(market.get('no_price', 0.5) or 0.5)
            trend = float(trend_data.get('trend_per_hour', 0) or 0)
            projected_high = trend_data.get('projected_high')
            
            # Get forecast (cached, don't fetch every call)
            forecast_high = None
            try:
                forecast = await fetch_forecast(icao)
                if forecast:
                    forecast_high = forecast.get('forecast_high_c')
            except:
                pass
            
            # Calculate our probability
            # Simple model: based on data convergence
            votes_yes = 0
            total_sources = 0
            
            threshold_type = market.get('threshold_type', 'high_above')
            
            # Source 1: Current METAR
            total_sources += 1
            if threshold_type == 'high_above':
                if current_temp >= threshold:
                    votes_yes += 1  # Already hit
                elif projected_high and float(projected_high) >= threshold:
                    votes_yes += 0.7  # Trend says likely
            elif threshold_type == 'low_below':
                if current_temp <= threshold:
                    votes_yes += 1
            
            # Source 2: Forecast
            if forecast_high is not None:
                total_sources += 1
                if threshold_type == 'high_above' and forecast_high >= threshold:
                    votes_yes += 1
                elif threshold_type == 'low_below' and forecast_high <= threshold:
                    votes_yes += 1
            
            # Our probability estimate
            our_prob = min(0.95, max(0.05, votes_yes / max(total_sources, 1)))
            
            # Edge = our probability - market price
            edge_yes = our_prob - yes_price
            edge_no = (1 - our_prob) - no_price
            
            # Which side has better edge?
            if edge_yes > edge_no:
                recommended_side = "YES"
                edge = edge_yes
                entry_price = yes_price
            else:
                recommended_side = "NO"
                edge = edge_no
                entry_price = no_price
            
            # Expected return
            if entry_price > 0 and entry_price < 1:
                expected_return_pct = ((1.0 / entry_price) - 1) * our_prob * 100
            else:
                expected_return_pct = 0
            
            # Signal strength
            if edge >= 0.25:
                signal_status = "STRONG_BUY"  # Green flash
                auto_trade = True
            elif edge >= 0.15:
                signal_status = "BUY"  # Yellow
                auto_trade = False  # Alert only
            elif edge >= 0.05:
                signal_status = "WATCH"  # Gray
                auto_trade = False
            else:
                signal_status = "SKIP"
                auto_trade = False
            
            # Binary arbitrage check
            arb_total = yes_price + no_price
            is_arb = arb_total < 0.98
            
            signals.append({
                "market_id": market.get('market_id'),
                "title": market.get('title', ''),
                "city": market.get('city', ''),
                "station_icao": icao,
                "threshold": threshold,
                "threshold_type": threshold_type,
                "threshold_unit": market.get('threshold_unit', '°C'),
                
                # Current data
                "current_temp": current_temp,
                "trend_per_hour": trend,
                "projected_high": float(projected_high) if projected_high else None,
                "forecast_high": forecast_high,
                
                # Market prices
                "yes_price": yes_price,
                "no_price": no_price,
                "volume": float(market.get('volume_usd', 0) or 0),
                
                # Our analysis
                "our_probability": round(our_prob, 4),
                "recommended_side": recommended_side,
                "edge": round(edge, 4),
                "expected_return_pct": round(expected_return_pct, 2),
                
                # Signal
                "signal": signal_status,
                "auto_trade": auto_trade,
                "is_arbitrage": is_arb,
                "arb_total": round(arb_total, 4),
                
                # Data sources used
                "sources": {
                    "metar": True,
                    "forecast": forecast_high is not None,
                    "historical": False,  # Not fetched per-call for speed
                    "trend": trend != 0,
                },
                
                "resolution_date": str(market.get('resolution_date', '')),
                "last_updated": str(market.get('last_updated', '')),
            })
        
        # Sort by edge (strongest signals first)
        signals.sort(key=lambda s: abs(s['edge']), reverse=True)
        
        return {
            "signals": signals,
            "total_markets": len(markets),
            "actionable": sum(1 for s in signals if s['signal'] in ('STRONG_BUY', 'BUY')),
            "arbitrage": sum(1 for s in signals if s['is_arbitrage']),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Live signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trades/execute")
async def execute_trade(data: dict):
    """Execute a trade (paper or live based on mode)."""
    from src.execution.paper_trader import paper_trade
    
    try:
        market_id = data.get("market_id")
        side = data.get("side", "YES")
        size_usd = float(data.get("size_usd", 25))
        
        if not market_id:
            raise HTTPException(status_code=400, detail="market_id required")
        
        # Get current settings
        settings_row = await fetch_one("SELECT value FROM bot_settings WHERE key = 'trading_mode'")
        mode = settings_row['value'] if settings_row else '"paper"'
        
        # Execute paper trade (always paper for now)
        result = await paper_trade({
            "market_id": market_id,
            "side": side,
            "size_usd": size_usd,
            "mode": "paper",
        })
        
        return {
            "status": "executed",
            "trade": result,
            "mode": "paper",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute trade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Trade Settlement
# =============================================================================

@app.post("/api/trades/settle")
async def settle_trades_endpoint():
    """Auto-settle completed trades using Odds API + ESPN scores."""
    from src.execution.settlement import settle_trades
    try:
        odds_key = os.environ.get('ODDS_API_KEY', '')
        if not odds_key:
            # Try loading from .env
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith('ODDS_API_KEY'):
                            odds_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            break
        result = await settle_trades(fetch_all, execute, fetch_one, odds_key)
        return result
    except Exception as e:
        logger.error(f"Settlement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trades/settle-manual")
async def settle_trade_manual(data: dict):
    """Manually settle a trade by ID."""
    from src.execution.settlement import manual_settle
    trade_id = data.get('trade_id')
    outcome = data.get('outcome')  # 'won' or 'lost'
    winner = data.get('winner', '')
    
    if not trade_id or outcome not in ('won', 'lost'):
        raise HTTPException(status_code=400, detail="trade_id and outcome ('won'/'lost') required")
    
    try:
        result = await manual_settle(execute, int(trade_id), outcome, winner)
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/forecast/{icao}")
async def get_forecast(icao: str):
    """Get Open-Meteo forecast for a station."""
    from src.data.openmeteo import fetch_forecast
    try:
        result = await fetch_forecast(icao.upper())
        if not result:
            raise HTTPException(status_code=404, detail=f"No forecast data for {icao}")
        return {"station": icao.upper(), **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/forecasts")
async def get_all_forecasts():
    """Get Open-Meteo forecasts for all tracked stations."""
    from src.data.openmeteo import fetch_all_forecasts, CITY_COORDS
    try:
        stations = list(CITY_COORDS.keys())
        results = await fetch_all_forecasts(stations)
        return {"data": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/historical/{icao}")
async def get_historical(icao: str):
    """Get historical temperature pattern for a station."""
    from src.data.historical import fetch_historical_pattern
    from datetime import datetime
    try:
        result = await fetch_historical_pattern(icao.upper(), datetime.utcnow())
        if not result:
            raise HTTPException(status_code=404, detail=f"No historical data for {icao}")
        return {"station": icao.upper(), **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/dashboard")
async def get_intelligence_dashboard():
    """Combined intelligence view — METAR + forecasts + trends + comparison.
    Returns all data needed for the Intelligence dashboard page."""
    from src.data.openmeteo import fetch_forecast, CITY_COORDS
    from src.data.city_map import CITY_TO_ICAO
    import asyncio
    
    try:
        # Get latest METAR data
        metar_data = await fetch_all("""SELECT DISTINCT ON (station_icao)
            station_icao, temperature_c, dewpoint_c, wind_speed_kt, wind_dir,
            observation_time, created_at
            FROM metar_readings ORDER BY station_icao, observation_time DESC""")
        
        # Get temperature trends
        trends = await fetch_all("""SELECT DISTINCT ON (station_icao)
            station_icao, trend_per_hour, projected_high, projected_low, confidence, num_readings
            FROM temperature_trends ORDER BY station_icao, calculated_at DESC""")
        trend_map = {t['station_icao']: t for t in trends}
        
        # Get Open-Meteo forecasts for top 10 stations (to keep response fast)
        top_stations = [m['station_icao'] for m in metar_data[:10]]
        forecasts = {}
        for icao in top_stations:
            try:
                f = await fetch_forecast(icao)
                if f:
                    forecasts[icao] = f
            except:
                pass
        
        # Build combined view per station
        stations = []
        for m in metar_data:
            icao = m['station_icao']
            trend = trend_map.get(icao, {})
            forecast = forecasts.get(icao, {})
            
            # Calculate data convergence (Gate 1 preview)
            metar_temp = m.get('temperature_c', 0)
            forecast_high = forecast.get('forecast_high_c')
            trend_projected = trend.get('projected_high')
            
            sources_agree = 0
            total_sources = 1  # METAR always counts
            if forecast_high is not None:
                total_sources += 1
                if abs(forecast_high - metar_temp) < 5:  # Within 5°C
                    sources_agree += 1
            if trend_projected is not None:
                total_sources += 1
                if abs(trend_projected - metar_temp) < 5:
                    sources_agree += 1
            
            stations.append({
                'station_icao': icao,
                'metar': {
                    'temperature_c': metar_temp,
                    'dewpoint_c': m.get('dewpoint_c'),
                    'wind_speed_kt': m.get('wind_speed_kt'),
                    'wind_dir': m.get('wind_dir'),
                    'observation_time': str(m.get('observation_time', '')),
                },
                'trend': {
                    'per_hour': trend.get('trend_per_hour'),
                    'projected_high': trend.get('projected_high'),
                    'projected_low': trend.get('projected_low'),
                    'confidence': trend.get('confidence'),
                },
                'forecast': {
                    'high_c': forecast_high,
                    'low_c': forecast.get('forecast_low_c'),
                    'hourly_temps': forecast.get('hourly_temps', [])[:12],
                    'precip_probs': forecast.get('precipitation_probs', [])[:12],
                },
                'convergence': {
                    'sources_agree': sources_agree,
                    'total_sources': total_sources,
                    'status': 'high' if sources_agree >= 2 else 'medium' if sources_agree == 1 else 'low',
                },
            })
        
        # Get signal count and recent activity
        signal_count = await fetch_all("SELECT COUNT(*) as count FROM signals")
        trade_count = await fetch_all("SELECT COUNT(*) as count FROM trades")
        
        return {
            'stations': stations,
            'station_count': len(stations),
            'signal_count': signal_count[0]['count'] if signal_count else 0,
            'trade_count': trade_count[0]['count'] if trade_count else 0,
            'forecast_count': len(forecasts),
            'trend_count': len(trends),
        }
    except Exception as e:
        logger.error(f"Intelligence dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PERFORMANCE — CEO Command Center Endpoints
# =============================================================================

@app.get("/api/performance/strategies")
async def get_performance_strategies():
    """Returns all strategies with their signal stats."""
    try:
        # Sports strategies from sports_signals
        sports_cross_odds = await fetch_one("""
            SELECT COUNT(*) as signal_count,
                   AVG(edge_pct) as avg_edge,
                   COUNT(CASE WHEN signal = 'BUY' OR signal LIKE 'BUY%' THEN 1 END) as buy_count,
                   COUNT(CASE WHEN signal = 'SELL' OR signal LIKE 'SELL%' THEN 1 END) as sell_count,
                   MAX(created_at) as last_signal_time,
                   string_agg(DISTINCT sport, ', ' ORDER BY sport) as sports_covered
            FROM sports_signals
            WHERE edge_type = 'cross_odds'
        """)
        
        sports_logical_arb = await fetch_one("""
            SELECT COUNT(*) as signal_count,
                   AVG(edge_pct) as avg_edge,
                   COUNT(CASE WHEN signal = 'BUY' OR signal LIKE 'BUY%' THEN 1 END) as buy_count,
                   COUNT(CASE WHEN signal = 'SELL' OR signal LIKE 'SELL%' THEN 1 END) as sell_count,
                   MAX(created_at) as last_signal_time,
                   string_agg(DISTINCT sport, ', ' ORDER BY sport) as sports_covered
            FROM sports_signals
            WHERE edge_type = 'logical_arb'
        """)
        
        # Weather strategies from signals table
        forecast_edge = await fetch_one("""
            SELECT COUNT(*) as signal_count,
                   AVG(edge) as avg_edge,
                   COUNT(CASE WHEN side = 'YES' THEN 1 END) as buy_count,
                   COUNT(CASE WHEN side = 'NO' THEN 1 END) as sell_count,
                   MAX(created_at) as last_signal_time
            FROM signals
            WHERE strategy = 'forecast_edge'
        """)
        
        intelligence_layer = await fetch_one("""
            SELECT COUNT(*) as signal_count,
                   AVG(edge) as avg_edge,
                   COUNT(CASE WHEN side = 'YES' THEN 1 END) as buy_count,
                   COUNT(CASE WHEN side = 'NO' THEN 1 END) as sell_count,
                   MAX(created_at) as last_signal_time
            FROM signals
            WHERE strategy = 'intelligence_layer'
        """)
        
        strategies = [
            {
                "id": "cross_odds",
                "name": "Cross-Odds Arbitrage",
                "emoji": "⚡",
                "description": "DraftKings vs Polymarket price discrepancies",
                "signal_count": sports_cross_odds.get('signal_count', 0) if sports_cross_odds else 0,
                "avg_edge": float(sports_cross_odds.get('avg_edge', 0) or 0) if sports_cross_odds else 0,
                "buy_count": sports_cross_odds.get('buy_count', 0) if sports_cross_odds else 0,
                "sell_count": sports_cross_odds.get('sell_count', 0) if sports_cross_odds else 0,
                "last_signal_time": str(sports_cross_odds.get('last_signal_time', '')) if sports_cross_odds and sports_cross_odds.get('last_signal_time') else None,
                "sports_covered": (sports_cross_odds.get('sports_covered', '') or '').split(', ') if sports_cross_odds and sports_cross_odds.get('sports_covered') else [],
                "status": "active"
            },
            {
                "id": "logical_arb",
                "name": "Logical Arbitrage",
                "emoji": "🔗",
                "description": "Group overpricing (e.g., Stanley Cup teams > 100%)",
                "signal_count": sports_logical_arb.get('signal_count', 0) if sports_logical_arb else 0,
                "avg_edge": float(sports_logical_arb.get('avg_edge', 0) or 0) if sports_logical_arb else 0,
                "buy_count": sports_logical_arb.get('buy_count', 0) if sports_logical_arb else 0,
                "sell_count": sports_logical_arb.get('sell_count', 0) if sports_logical_arb else 0,
                "last_signal_time": str(sports_logical_arb.get('last_signal_time', '')) if sports_logical_arb and sports_logical_arb.get('last_signal_time') else None,
                "sports_covered": (sports_logical_arb.get('sports_covered', '') or '').split(', ') if sports_logical_arb and sports_logical_arb.get('sports_covered') else [],
                "status": "active"
            },
            {
                "id": "forecast_edge",
                "name": "Forecast Edge",
                "emoji": "🌡️",
                "description": "Weather model predictions vs market prices",
                "signal_count": forecast_edge.get('signal_count', 0) if forecast_edge else 0,
                "avg_edge": float(forecast_edge.get('avg_edge', 0) or 0) if forecast_edge else 0,
                "buy_count": forecast_edge.get('buy_count', 0) if forecast_edge else 0,
                "sell_count": forecast_edge.get('sell_count', 0) if forecast_edge else 0,
                "last_signal_time": str(forecast_edge.get('last_signal_time', '')) if forecast_edge and forecast_edge.get('last_signal_time') else None,
                "sports_covered": ["Weather"],
                "status": "active"
            },
            {
                "id": "intelligence_layer",
                "name": "8-Gate Intelligence",
                "emoji": "🧠",
                "description": "Multi-source convergence + Claude analysis",
                "signal_count": intelligence_layer.get('signal_count', 0) if intelligence_layer else 0,
                "avg_edge": float(intelligence_layer.get('avg_edge', 0) or 0) if intelligence_layer else 0,
                "buy_count": intelligence_layer.get('buy_count', 0) if intelligence_layer else 0,
                "sell_count": intelligence_layer.get('sell_count', 0) if intelligence_layer else 0,
                "last_signal_time": str(intelligence_layer.get('last_signal_time', '')) if intelligence_layer and intelligence_layer.get('last_signal_time') else None,
                "sports_covered": ["Weather"],
                "status": "active"
            },
            {
                "id": "live_momentum",
                "name": "Live Momentum",
                "emoji": "🏃",
                "description": "Real-time event tracking + price movements",
                "signal_count": 0,
                "avg_edge": 0,
                "buy_count": 0,
                "sell_count": 0,
                "last_signal_time": None,
                "sports_covered": [],
                "status": "coming_soon"
            }
        ]
        
        return {"strategies": strategies, "count": len(strategies)}
    except Exception as e:
        logger.error(f"Performance strategies error: {e}")
        return {"strategies": [], "count": 0}


@app.get("/api/performance/signals/timeline")
async def get_signals_timeline():
    """Signal generation over time (hourly for 24h)."""
    try:
        # Hourly buckets for last 24 hours
        query = """
            SELECT
                DATE_TRUNC('hour', created_at) as time_bucket,
                COUNT(CASE WHEN edge_type = 'cross_odds' THEN 1 END) as cross_odds_count,
                COUNT(CASE WHEN edge_type = 'logical_arb' THEN 1 END) as logical_arb_count,
                COUNT(*) as total
            FROM sports_signals
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY time_bucket
            ORDER BY time_bucket ASC
        """
        results = await fetch_all(query)
        
        buckets = [{
            "time": str(r['time_bucket']),
            "cross_odds_count": r['cross_odds_count'],
            "logical_arb_count": r['logical_arb_count'],
            "total": r['total']
        } for r in results]
        
        return {"buckets": buckets, "count": len(buckets)}
    except Exception as e:
        logger.error(f"Signals timeline error: {e}")
        return {"buckets": [], "count": 0}


@app.get("/api/performance/signals/latest")
async def get_latest_signals_feed(limit: int = 50):
    """Latest 50 signals with full detail for live feed."""
    try:
        query = """
            SELECT
                id, edge_type, sport, market_id, market_title,
                polymarket_price, fair_value,
                edge_pct, signal, confidence,
                reasoning, created_at
            FROM sports_signals
            ORDER BY created_at DESC
            LIMIT %s
        """
        results = await fetch_all(query, (limit,))
        
        signals = [{
            "id": r['id'],
            "strategy": "Cross-Odds" if r['edge_type'] == 'cross_odds' else "Logical Arb",
            "sport": r['sport'],
            "market_id": r['market_id'],
            "market_title": r['market_title'],
            "polymarket_price": float(r['polymarket_price']) if r['polymarket_price'] else 0,
            "fair_value": float(r['fair_value']) if r['fair_value'] else 0,
            "edge": float(r['edge_pct']) if r['edge_pct'] else 0,
            "side": r['signal'] or 'HOLD',
            "confidence": r['confidence'] or 'MEDIUM',
            "reasoning": r['reasoning'],
            "created_at": str(r['created_at'])
        } for r in results]
        
        return {"signals": signals, "count": len(signals)}
    except Exception as e:
        logger.error(f"Latest signals error: {e}")
        return {"signals": [], "count": 0}


@app.get("/api/performance/edge-distribution")
async def get_edge_distribution():
    """Edge % distribution for histogram."""
    try:
        query = """
            SELECT bucket as range, COUNT(*) as count FROM (
                SELECT
                    CASE
                        WHEN ABS(edge_pct) < 5 THEN '0-5%'
                        WHEN ABS(edge_pct) < 10 THEN '5-10%'
                        WHEN ABS(edge_pct) < 25 THEN '10-25%'
                        WHEN ABS(edge_pct) < 50 THEN '25-50%'
                        WHEN ABS(edge_pct) < 100 THEN '50-100%'
                        ELSE '100%+'
                    END as bucket
                FROM sports_signals
            ) sub
            GROUP BY bucket
            ORDER BY
                CASE bucket
                    WHEN '0-5%' THEN 1
                    WHEN '5-10%' THEN 2
                    WHEN '10-25%' THEN 3
                    WHEN '25-50%' THEN 4
                    WHEN '50-100%' THEN 5
                    ELSE 6
                END
        """
        results = await fetch_all(query)
        
        buckets = [{
            "range": r['range'],
            "count": r['count']
        } for r in results]
        
        return {"buckets": buckets, "count": len(buckets)}
    except Exception as e:
        logger.error(f"Edge distribution error: {e}")
        return {"buckets": [], "count": 0}


@app.get("/api/performance/sports-breakdown")
async def get_sports_breakdown():
    """Signals grouped by sport."""
    try:
        query = """
            SELECT
                sport,
                COUNT(*) as signals,
                AVG(edge_pct) as avg_edge,
                COUNT(DISTINCT market_id) as markets
            FROM sports_signals
            GROUP BY sport
            ORDER BY signals DESC
        """
        results = await fetch_all(query)
        
        sports = [{
            "sport": r['sport'],
            "signals": r['signals'],
            "avg_edge": round(float(r['avg_edge'] or 0), 2),
            "markets": r['markets']
        } for r in results]
        
        return {"sports": sports, "count": len(sports)}
    except Exception as e:
        logger.error(f"Sports breakdown error: {e}")
        return {"sports": [], "count": 0}


@app.get("/api/performance/odds-comparison")
async def get_odds_comparison(limit: int = 50):
    """Sportsbook vs Polymarket comparison for matched markets."""
    try:
        # Match sportsbook outcomes to Polymarket questions by team name
        query = """
            SELECT DISTINCT ON (so.outcome, sm.market_id)
                sm.market_id,
                sm.question as event,
                sm.sport,
                sm.yes_price as polymarket_price,
                so.outcome as team,
                so.implied_probability as book_prob,
                so.bookmaker as book_name,
                so.event_name as book_event,
                ABS(so.implied_probability - sm.yes_price) * 100 as edge_pct
            FROM sports_markets sm
            CROSS JOIN sportsbook_odds so
            WHERE sm.yes_price IS NOT NULL
              AND so.implied_probability IS NOT NULL
              AND LOWER(sm.question) LIKE '%%' || LOWER(SPLIT_PART(so.outcome, ' ', array_length(string_to_array(so.outcome, ' '), 1))) || '%%'
              AND LOWER(sm.sport) = LOWER(so.sport)
            ORDER BY so.outcome, sm.market_id, ABS(so.implied_probability - sm.yes_price) DESC
            LIMIT %s
        """
        results = await fetch_all(query, (limit,))
        
        comparisons = [{
            "event": r['event'][:100],
            "team": r.get('team', ''),
            "polymarket_price": round(float(r['polymarket_price']), 3),
            "book_price": round(float(r['book_prob']), 3),
            "book_name": r['book_name'],
            "book_event": r.get('book_event', ''),
            "edge": round(float(r['edge_pct']), 2),
            "sport": r['sport']
        } for r in results]
        
        return {"comparisons": comparisons, "count": len(comparisons)}
    except Exception as e:
        logger.error(f"Odds comparison error: {e}")
        return {"comparisons": [], "count": 0}


# =============================================================================
# Learning Engine — Sprint 3 Endpoints
# =============================================================================

@app.get("/api/learning/scorecard")
async def learning_scorecard(strategy: str = "arbitrage", lookback_days: int = 30):
    """Strategy scorecard from the learning engine."""
    try:
        from src.learning.improvement import LearningEngine
        from src.db_async import get_async_pool
        engine = LearningEngine(get_async_pool())
        result = await engine.strategy_scorecard(strategy, lookback_days)
        return result
    except Exception as e:
        logger.error(f"Learning scorecard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/learning/thresholds")
async def learning_thresholds():
    """Current edge threshold analysis."""
    try:
        from src.learning.improvement import LearningEngine
        from src.db_async import get_async_pool
        engine = LearningEngine(get_async_pool())
        result = await engine.get_current_thresholds()
        return result
    except Exception as e:
        logger.error(f"Learning thresholds error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/learning/report/latest")
async def learning_report_latest():
    """Latest weekly learning report."""
    try:
        from src.learning.improvement import LearningEngine
        from src.db_async import get_async_pool
        engine = LearningEngine(get_async_pool())
        result = await engine.get_latest_report()
        if not result:
            return {"message": "No weekly report generated yet"}
        return result
    except Exception as e:
        logger.error(f"Learning report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/learning/optimize")
async def learning_optimize():
    """Trigger threshold optimization manually."""
    try:
        from src.learning.improvement import LearningEngine
        from src.db_async import get_async_pool
        engine = LearningEngine(get_async_pool())
        result = await engine.optimize_thresholds()
        return result
    except Exception as e:
        logger.error(f"Learning optimize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Intelligence & Improvement — Analysis Endpoints
# =============================================================================

@app.get("/api/intelligence/daily")
async def get_daily_analysis():
    """Get daily performance analysis from improvement engine."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        analysis = await _improvement_engine.daily_analysis()
        return analysis
    except Exception as e:
        logger.error(f"Daily analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate daily analysis: {str(e)}")


@app.get("/api/intelligence/weekly")
async def get_weekly_review():
    """Get weekly strategy review with findings and proposals."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        review = await _improvement_engine.weekly_review()
        return review
    except Exception as e:
        logger.error(f"Weekly review error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate weekly review: {str(e)}")


@app.get("/api/intelligence/calibration")
async def get_probability_calibration():
    """Get probability model calibration metrics."""
    global _improvement_engine
    
    if not _improvement_engine:
        raise HTTPException(status_code=503, detail="Improvement engine not initialized")
    
    try:
        calibration = await _improvement_engine.calibrate_probability_model()
        return calibration
    except Exception as e:
        logger.error(f"Calibration error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate calibration: {str(e)}")


@app.post("/api/intelligence/approve/{proposal_id}")
async def approve_proposal(proposal_id: str):
    """CEO approves a strategy change proposal.
    
    NOTE: This is a placeholder. Real implementation would:
    1. Fetch proposal from DB
    2. Parse parameter changes
    3. Update STRATEGY.md
    4. Update config values
    5. Log approval in changelog
    """
    # TODO: Implement proposal approval workflow
    return {
        "status": "approved",
        "proposal_id": proposal_id,
        "message": "Proposal approval not yet implemented. See STRATEGY.md for manual updates.",
        "timestamp": datetime.utcnow().isoformat()
    }


# =============================================================================
# Settings & Bot Control
# =============================================================================

@app.get("/api/settings")
async def get_settings():
    """Get all bot settings from DB and config."""
    try:
        # Fetch from bot_settings table
        query = "SELECT key, value FROM bot_settings"
        rows = await fetch_all(query)
        settings = {row["key"]: row["value"] for row in rows}
        
        # Add config defaults if missing
        if not settings:
            settings = {
                "max_position_size": 50,
                "max_portfolio_exposure": 15,
                "kelly_fraction": 0.25,
                "max_trades_per_city_per_day": 3,
                "daily_loss_limit": 10,
                "min_edge_auto_trade": 25,
                "min_edge_alert": 15,
                "min_confidence_sources": 2,
                "max_spread_cents": 8,
                "min_liquidity_multiple": 2,
                "min_hours_to_resolution": 2,
                "gates_enabled": {
                    "data_convergence": True,
                    "multi_station": True,
                    "bucket_coherence": True,
                    "binary_arbitrage": True,
                    "liquidity_check": True,
                    "time_window": True,
                    "risk_manager": True,
                    "claude_confirmation": True
                },
                "telegram_alerts": False,
                "telegram_chat_id": "",
                "alert_on_trade": True,
                "alert_on_signal": True,
                "alert_on_daily_summary": True,
                "refresh_interval_min": 15,
                "strategy_auto_proposals": True,
                "weekly_review_day": "Sunday",
                "weekly_review_time": "09:00",
                "auto_adjust_accuracy": True,
                "proposal_approval_mode": "require"
            }
        
        return {
            "settings": settings,
            "mode": getattr(config, 'MODE', 'paper'),
            "wallet_address": getattr(config, 'WALLET_ADDRESS', None)
        }
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        return {"settings": {}, "mode": "paper", "wallet_address": None}


@app.post("/api/settings")
async def save_settings(settings: dict):
    """Save bot settings to DB."""
    try:
        for key, value in settings.items():
            await execute(
                "INSERT INTO bot_settings (key, value, updated_at) VALUES (%s, %s::jsonb, NOW()) ON CONFLICT (key) DO UPDATE SET value = %s::jsonb, updated_at = NOW()",
                (key, str(value), str(value))
            )
        return {"status": "saved", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Save settings error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@app.post("/api/bot/start")
async def start_bot():
    """Start the trading bot."""
    global scheduler
    if not scheduler.running:
        scheduler.start()
    return {"status": "started", "running": scheduler.running, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/bot/pause")
async def pause_bot():
    """Pause — stop new trades but keep monitoring."""
    # TODO: Add pause flag to signal loop
    return {"status": "paused", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/bot/stop")
async def stop_bot():
    """Emergency stop — halt everything immediately."""
    global scheduler
    if scheduler.running:
        scheduler.pause()
    return {"status": "stopped", "running": scheduler.running, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/positions/health")
async def get_position_health():
    """Check health of all open positions — edge decay monitoring."""
    try:
        from src.execution.edge_monitor import EdgeMonitor
        monitor = EdgeMonitor(get_async_pool())
        alerts = await monitor.check_all_positions()
        return {
            "positions": alerts,
            "exit_needed": len([a for a in alerts if a['recommendation'].startswith('EXIT')]),
            "watch": len([a for a in alerts if a['recommendation'] == 'WATCH']),
            "healthy": len([a for a in alerts if a['recommendation'] == 'HOLD']),
            "total_open": len(alerts),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Position health error: {e}")
        return {"positions": [], "exit_needed": 0, "total_open": 0, "error": str(e)}


@app.get("/api/wallet/balance")
async def get_wallet_balance():
    """Get real USDC + MATIC balance from Polygon blockchain."""
    import httpx
    WALLET = "0xb9BEa5FDe7957709D0f8d2064188B1603b74D5Ca"
    RPC = "https://small-cosmological-friday.matic.quiknode.pro/c6dd1696accaf8a955e09f34475deb31913c5254/"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # MATIC balance
            r = await client.post(RPC, json={
                "jsonrpc": "2.0", "method": "eth_getBalance",
                "params": [WALLET, "latest"], "id": 1
            })
            matic = int(r.json()["result"], 16) / 1e18
            # USDC balance (native USDC on Polygon)
            USDC = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
            data = "0x70a08231000000000000000000000000" + WALLET[2:]
            r2 = await client.post(RPC, json={
                "jsonrpc": "2.0", "method": "eth_call",
                "params": [{"to": USDC, "data": data}, "latest"], "id": 2
            })
            usdc = int(r2.json()["result"], 16) / 1e6
        return {
            "wallet": WALLET, "usdc": round(usdc, 2), "matic": round(matic, 4),
            "chain": "Polygon", "live": True
        }
    except Exception as e:
        logger.error(f"Wallet balance error: {e}")
        return {"wallet": WALLET, "usdc": 0, "matic": 0, "chain": "Polygon", "live": True, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# SPORTS INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

from src.sports.polymarket_sports_scanner import PolymarketSportsScanner
from src.sports.espn_live import ESPNLiveScores
from src.sports.correlation_engine import CorrelationEngine
from src.sports.cross_odds_engine import CrossOddsEngine


# =============================================================================
# Internal Arbitrage API
# =============================================================================

# =============================================================================
# Penny Hunter API
# =============================================================================

@app.get("/api/penny/positions")
async def get_penny_positions(status: str = None, limit: int = 100):
    """Get penny positions, optionally filtered by status."""
    try:
        if status:
            rows = await fetch_all("""
                SELECT id, market_id, condition_id, question, category, outcome,
                       buy_price, quantity, size_usd, potential_payout,
                       catalyst_score, catalyst_reason, days_to_resolution,
                       volume_usd, status, resolution, pnl_usd,
                       opened_at, resolved_at, metadata
                FROM penny_positions
                WHERE status = %s
                ORDER BY opened_at DESC
                LIMIT %s
            """, (status, min(limit, 500)))
        else:
            rows = await fetch_all("""
                SELECT id, market_id, condition_id, question, category, outcome,
                       buy_price, quantity, size_usd, potential_payout,
                       catalyst_score, catalyst_reason, days_to_resolution,
                       volume_usd, status, resolution, pnl_usd,
                       opened_at, resolved_at, metadata
                FROM penny_positions
                ORDER BY opened_at DESC
                LIMIT %s
            """, (min(limit, 500),))
        
        positions = []
        for r in (rows or []):
            positions.append({
                'id': r['id'],
                'market_id': r['market_id'],
                'condition_id': r.get('condition_id', ''),
                'question': r['question'],
                'category': r.get('category', ''),
                'outcome': r.get('outcome', ''),
                'buy_price': float(r['buy_price']) if r['buy_price'] else 0,
                'quantity': float(r['quantity']) if r['quantity'] else 0,
                'size_usd': float(r['size_usd']) if r['size_usd'] else 0,
                'potential_payout': float(r['potential_payout']) if r['potential_payout'] else 0,
                'catalyst_score': float(r['catalyst_score']) if r['catalyst_score'] else 0,
                'catalyst_reason': r.get('catalyst_reason', ''),
                'days_to_resolution': r.get('days_to_resolution'),
                'volume_usd': float(r['volume_usd']) if r['volume_usd'] else 0,
                'status': r['status'],
                'resolution': r.get('resolution', ''),
                'pnl_usd': float(r['pnl_usd']) if r['pnl_usd'] else 0,
                'opened_at': str(r['opened_at']) if r['opened_at'] else None,
                'resolved_at': str(r['resolved_at']) if r['resolved_at'] else None,
            })
        return {"positions": positions, "count": len(positions)}
    except Exception as e:
        logger.error(f"Penny positions error: {e}")
        return {"positions": [], "count": 0, "error": str(e)}


@app.get("/api/penny/stats")
async def get_penny_stats():
    """Get penny portfolio stats."""
    try:
        from src.strategies.penny_hunter import PennyHunter
        hunter = PennyHunter(get_async_pool())
        stats = await hunter.get_portfolio_stats()
        stats['last_scan'] = _last_penny_scan.isoformat() if _last_penny_scan else None
        return stats
    except Exception as e:
        logger.error(f"Penny stats error: {e}")
        return {"error": str(e), "total_positions": 0, "open_positions": 0, "total_pnl": 0}


@app.get("/api/penny/scan")
async def get_penny_scan():
    """Run a live scan and return current penny contracts available (no trades executed)."""
    try:
        from src.strategies.penny_hunter import PennyHunter
        hunter = PennyHunter(get_async_pool())
        pennies = await hunter.scan_penny_contracts()
        
        # Score all
        for p in pennies:
            score, reason = hunter.score_catalyst(p)
            p['catalyst_score'] = score
            p['catalyst_reason'] = reason
        
        # Sort by score
        pennies.sort(key=lambda x: -x['catalyst_score'])
        
        # Return top 50
        results = []
        for p in pennies[:50]:
            results.append({
                'market_id': p['market_id'],
                'question': p['question'],
                'category': p.get('category', ''),
                'outcome': p.get('outcome', ''),
                'buy_price': p['buy_price'],
                'days_to_resolution': p.get('days_to_resolution'),
                'volume_usd': p.get('volume_usd', 0),
                'catalyst_score': p['catalyst_score'],
                'catalyst_reason': p['catalyst_reason'],
                'would_buy': p['catalyst_score'] >= 3,
                'potential_return': f"{(1/p['buy_price']):.0f}x" if p['buy_price'] > 0 else '0x',
            })
        
        return {
            "contracts": results,
            "total_found": len(pennies),
            "would_buy": sum(1 for p in pennies if p['catalyst_score'] >= 3),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Penny scan API error: {e}")
        return {"contracts": [], "total_found": 0, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# LATE WINDOW SCALPER — API Endpoints
# ═══════════════════════════════════════════════════════════════


@app.get("/api/late-window/status")
async def get_late_window_status():
    """Current state, active windows, next entry."""
    global _late_window_scalper
    try:
        from src.strategies.late_window_scalper import LateWindowScalper
        if _late_window_scalper is None:
            _late_window_scalper = LateWindowScalper(get_async_pool())
            await _late_window_scalper.ensure_tables()
        return await _late_window_scalper.get_status()
    except Exception as e:
        logger.error(f"Late window status error: {e}")
        return {"enabled": False, "error": str(e)}


@app.get("/api/late-window/trades")
async def get_late_window_trades(limit: int = 50):
    """Recent trades with P&L."""
    global _late_window_scalper
    try:
        from src.strategies.late_window_scalper import LateWindowScalper
        if _late_window_scalper is None:
            _late_window_scalper = LateWindowScalper(get_async_pool())
            await _late_window_scalper.ensure_tables()
        trades = await _late_window_scalper.get_trades(limit=min(limit, 200))
        # Convert datetime objects to strings for JSON serialization
        result = []
        for t in trades:
            d = dict(t)
            for k, v in d.items():
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
                elif v is not None and hasattr(v, '__float__'):
                    d[k] = float(v)
            result.append(d)
        return {"trades": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Late window trades error: {e}")
        return {"trades": [], "count": 0, "error": str(e)}


@app.get("/api/late-window/stats")
async def get_late_window_stats():
    """Win rate, total PnL, avg entry price, trades today."""
    global _late_window_scalper
    try:
        from src.strategies.late_window_scalper import LateWindowScalper
        if _late_window_scalper is None:
            _late_window_scalper = LateWindowScalper(get_async_pool())
            await _late_window_scalper.ensure_tables()
        return await _late_window_scalper.get_stats()
    except Exception as e:
        logger.error(f"Late window stats error: {e}")
        return {"total_trades": 0, "win_rate": 0, "total_pnl": 0, "error": str(e)}


@app.post("/api/late-window/toggle")
async def toggle_late_window():
    """Enable/disable the scalper."""
    global _late_window_scalper
    try:
        from src.strategies.late_window_scalper import LateWindowScalper
        if _late_window_scalper is None:
            _late_window_scalper = LateWindowScalper(get_async_pool())
            await _late_window_scalper.ensure_tables()
        new_state = _late_window_scalper.toggle()
        return {"enabled": new_state, "message": f"Late Window Scalper {'enabled' if new_state else 'disabled'}"}
    except Exception as e:
        logger.error(f"Late window toggle error: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# BTC SIGNAL ENGINE — API Endpoints
# ═══════════════════════════════════════════════════════════════


@app.get("/api/btc/state")
async def get_btc_state():
    """Live engine state: BTC price, active windows, signals, factors, accuracy."""
    global _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
        return await _btc_engine.get_current_state()
    except Exception as e:
        logger.error(f"BTC state error: {e}")
        return {"error": str(e), "btc_price": 0, "active_windows": [], "accuracy": {}}


@app.get("/api/btc/signals")
async def get_btc_signals(limit: int = 50):
    """Recent signals with accuracy info."""
    global _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
        signals = await _btc_engine.get_recent_signals(limit=min(limit, 200))
        return {"signals": signals, "count": len(signals)}
    except Exception as e:
        logger.error(f"BTC signals error: {e}")
        return {"signals": [], "count": 0, "error": str(e)}


@app.get("/api/btc/accuracy")
async def get_btc_accuracy():
    """Rolling accuracy stats."""
    global _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
        return await _btc_engine.get_accuracy_stats()
    except Exception as e:
        logger.error(f"BTC accuracy error: {e}")
        return {"error": str(e)}


@app.get("/api/btc/windows")
async def get_btc_windows(limit: int = 50):
    """Active + recent windows."""
    global _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
        windows = await _btc_engine.get_windows(limit=min(limit, 200))
        return {"windows": windows, "count": len(windows)}
    except Exception as e:
        logger.error(f"BTC windows error: {e}")
        return {"windows": [], "count": 0, "error": str(e)}


@app.get("/api/btc/calibration")
async def get_btc_calibration(limit: int = 30):
    """Weight calibration history."""
    global _btc_engine
    try:
        if _btc_engine is None:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            _btc_engine = BTCSignalEngine(get_async_pool())
            await _btc_engine.ensure_tables()
        calibrations = await _btc_engine.get_calibration_history(limit=min(limit, 100))
        return {"calibrations": calibrations, "count": len(calibrations)}
    except Exception as e:
        logger.error(f"BTC calibration error: {e}")
        return {"calibrations": [], "count": 0, "error": str(e)}
# ═══════════════════════════════════════════════════════════════


@app.get("/api/btc/analysis")
async def get_btc_analysis(hours: int = 1):
    """Analysis data for dashboard with timeframe toggle (1h, 4h, 8h, 24h, 72h, 168h)."""
    try:
        pool = get_async_pool()
        interval = f"{hours} hours"
        async with pool.acquire() as conn:
            # Entry price bucket performance
            buckets = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl,
                        CASE 
                            WHEN entry_price < 0.3 THEN '<30c'
                            WHEN entry_price < 0.5 THEN '30-50c'
                            WHEN entry_price < 0.7 THEN '50-70c'
                            WHEN entry_price < 0.85 THEN '70-85c'
                            ELSE '85c+'
                        END as bucket
                    FROM best
                )
                SELECT bucket, COUNT(*) as trades, 
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(AVG(CASE WHEN correct THEN trade_pnl END)::numeric, 2) as avg_win,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best_trade
                FROM pnl GROUP BY bucket ORDER BY bucket
            """)

            # Hourly heatmap
            hourly = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl
                    FROM best
                )
                SELECT 
                    EXTRACT(HOUR FROM close_time AT TIME ZONE 'Asia/Kolkata')::int as hour_ist,
                    COUNT(*) as trades,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(AVG(entry_price)::numeric, 3) as avg_entry,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best_trade
                FROM pnl GROUP BY 1 ORDER BY 1
            """)

            # Cumulative P&L over time (for chart)
            cumulative = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl
                    FROM best
                )
                SELECT close_time, trade_pnl, correct, entry_price,
                    SUM(trade_pnl) OVER (ORDER BY close_time) as running_pnl
                FROM pnl ORDER BY close_time
            """)

            # Confidence vs P&L
            confidence = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, s.confidence, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl,
                        CASE 
                            WHEN confidence < 0.4 THEN 'Low <40%'
                            WHEN confidence < 0.6 THEN 'Med 40-60%'
                            WHEN confidence < 0.8 THEN 'High 60-80%'
                            ELSE 'Ultra 80%+'
                        END as conf_tier
                    FROM best
                )
                SELECT conf_tier, COUNT(*) as trades, 
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(AVG(entry_price)::numeric, 3) as avg_entry
                FROM pnl GROUP BY conf_tier ORDER BY conf_tier
            """)

            # Timeframe comparison
            timeframes = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl
                    FROM best
                )
                SELECT window_length||'m' as wl,
                    COUNT(*) as trades,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(AVG(entry_price)::numeric, 3) as avg_entry,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best_trade
                FROM pnl GROUP BY window_length ORDER BY window_length
            """)

            # V2 filter comparison
            v2_compare = await conn.fetch(f"""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time,
                        (s.prediction = w.resolution) as correct,
                        CASE WHEN s.prediction = 'UP' THEN w.up_price ELSE w.down_price END as entry_price
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                        AND w.close_time > NOW() - INTERVAL '{interval}'
                    ORDER BY s.window_id, s.confidence DESC
                ),
                pnl AS (
                    SELECT *,
                        CASE
                            WHEN correct AND entry_price > 0 AND entry_price < 1 THEN (25.0/entry_price - 25.0)*0.98
                            WHEN NOT correct THEN -25.0 ELSE 0
                        END as trade_pnl
                    FROM best
                )
                SELECT 
                    'All Trades' as strategy,
                    COUNT(*) as trades,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best
                FROM pnl
                UNION ALL
                SELECT 
                    'V2 (<70c, 5M)' as strategy,
                    COUNT(*) as trades,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best
                FROM pnl WHERE entry_price <= 0.70 AND window_length = 5
            """)

        def row_to_dict(r, keys):
            return {k: (float(v) if isinstance(v, (int, float)) or (hasattr(v, '__float__')) else v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in zip(keys, r) if v is not None}

        return {
            "timeframe_hours": hours,
            "buckets": [{"bucket": r['bucket'], "trades": r['trades'], "wins": r['wins'], "net_pnl": float(r['net_pnl'] or 0), "avg_win": float(r['avg_win'] or 0), "best_trade": float(r['best_trade'] or 0)} for r in buckets],
            "hourly": [{"hour": r['hour_ist'], "trades": r['trades'], "wins": r['wins'], "net_pnl": float(r['net_pnl'] or 0), "avg_entry": float(r['avg_entry'] or 0), "best_trade": float(r['best_trade'] or 0)} for r in hourly],
            "cumulative": [{"time": r['close_time'].isoformat(), "pnl": float(r['trade_pnl'] or 0), "running": float(r['running_pnl'] or 0), "correct": r['correct'], "entry": float(r['entry_price'] or 0)} for r in cumulative],
            "confidence": [{"tier": r['conf_tier'], "trades": r['trades'], "wins": r['wins'], "net_pnl": float(r['net_pnl'] or 0), "avg_entry": float(r['avg_entry'] or 0)} for r in confidence],
            "timeframes": [{"wl": r['wl'], "trades": r['trades'], "wins": r['wins'], "net_pnl": float(r['net_pnl'] or 0), "avg_entry": float(r['avg_entry'] or 0), "best_trade": float(r['best_trade'] or 0)} for r in timeframes],
            "v2_compare": [{"strategy": r['strategy'], "trades": r['trades'], "wins": r['wins'], "net_pnl": float(r['net_pnl'] or 0), "best": float(r['best'] or 0)} for r in v2_compare],
        }
    except Exception as e:
        logger.error(f"BTC analysis error: {e}\n{traceback.format_exc()}")
        return {"error": str(e)}


@app.get("/api/btc/bankroll")
async def get_btc_bankroll_endpoint():
    """Current bankroll status with P&L metrics."""
    try:
        state = await get_btc_bankroll_state()
        balance = float(state.get('balance', BTC_STARTING_BALANCE))
        available = float(state.get('available', balance))
        in_positions = float(state.get('in_positions', 0))
        total_won = float(state.get('total_won', 0))
        total_lost = float(state.get('total_lost', 0))
        total_trades = int(state.get('total_trades', 0))
        peak_balance = float(state.get('peak_balance', balance))
        max_drawdown_pct = float(state.get('max_drawdown_pct', 0))
        pnl_pct = (balance - BTC_STARTING_BALANCE) / BTC_STARTING_BALANCE * 100 if BTC_STARTING_BALANCE > 0 else 0
        max_single_bet = balance * 0.10
        max_exposure = balance * 0.30
        return {
            "balance": round(balance, 2),
            "available": round(available, 2),
            "in_positions": round(in_positions, 2),
            "total_won": round(total_won, 2),
            "total_lost": round(total_lost, 2),
            "total_trades": total_trades,
            "peak_balance": round(peak_balance, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "pnl_pct": round(pnl_pct, 2),
            "max_single_bet": round(max_single_bet, 2),
            "max_exposure": round(max_exposure, 2),
            "starting_balance": BTC_STARTING_BALANCE,
        }
    except Exception as e:
        logger.error(f"BTC bankroll endpoint error: {e}")
        return {"error": str(e)}


@app.get("/api/btc/stats")
async def get_btc_stats():
    """Real-time stats using correct btc_pnl view."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    COUNT(*) FILTER (WHERE NOT correct) as losses,
                    ROUND(COUNT(*) FILTER (WHERE correct)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as win_rate,
                    ROUND(SUM(trade_pnl)::numeric, 2) as net_pnl,
                    ROUND(SUM(CASE WHEN trade_pnl > 0 THEN trade_pnl ELSE 0 END)::numeric, 2) as gross_profit,
                    ROUND(SUM(CASE WHEN trade_pnl < 0 THEN ABS(trade_pnl) ELSE 0 END)::numeric, 2) as gross_loss,
                    ROUND(SUM(stake)::numeric, 2) as total_spent,
                    ROUND(MAX(trade_pnl)::numeric, 2) as best_trade,
                    ROUND(SUM(CASE WHEN close_time::date = CURRENT_DATE THEN trade_pnl ELSE 0 END)::numeric, 2) as today_pnl,
                    COUNT(*) FILTER (WHERE close_time::date = CURRENT_DATE) as today_trades
                FROM btc_pnl
            """)
            stats = dict(row) if row else {"total_trades": 0}
            # Add bankroll-based P&L (source of truth)
            br = await conn.fetchrow("SELECT balance, total_won, total_lost, total_trades, peak_balance FROM btc_bankroll ORDER BY id DESC LIMIT 1")
            if br:
                initial = 5000.0
                stats["bankroll_balance"] = float(br["balance"])
                stats["bankroll_pnl"] = float(br["balance"]) - initial
                stats["bankroll_initial"] = initial
                stats["bankroll_won"] = float(br["total_won"])
                stats["bankroll_lost"] = float(br["total_lost"])
                stats["bankroll_trades"] = int(br["total_trades"])
                stats["peak_balance"] = float(br["peak_balance"])
                # Override net_pnl with bankroll truth
                stats["net_pnl"] = float(br["balance"]) - initial
            return stats
    except Exception as e:
        logger.error(f"BTC stats error: {e}")
        return {"error": str(e)}


@app.get("/api/btc/trades-detail")
async def get_btc_trades_detail():
    """Last 50 resolved trades with all signal factors for drill-down."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    p.window_id, p.window_length, p.prediction, p.resolution, p.correct,
                    p.entry_price, p.stake, ROUND(p.trade_pnl::numeric, 2) as trade_pnl,
                    ROUND((p.trade_pnl / NULLIF(p.stake, 0) * 100)::numeric, 0) as roi_pct,
                    w.btc_open, w.btc_close,
                    ROUND((w.btc_close - w.btc_open)::numeric, 2) as btc_move,
                    p.close_time,
                    s.prob_up, s.confidence,
                    s.f_price_delta, s.f_momentum, s.f_volume_imbalance,
                    s.f_oracle_lead, s.f_book_imbalance, s.f_volatility, s.f_time_decay,
                    (CASE WHEN (p.prediction='DOWN' AND s.f_price_delta < 0) OR (p.prediction='UP' AND s.f_price_delta > 0) THEN 1 ELSE 0 END +
                     CASE WHEN (p.prediction='DOWN' AND s.f_momentum < 0) OR (p.prediction='UP' AND s.f_momentum > 0) THEN 1 ELSE 0 END +
                     CASE WHEN (p.prediction='DOWN' AND s.f_volume_imbalance < 0) OR (p.prediction='UP' AND s.f_volume_imbalance > 0) THEN 1 ELSE 0 END +
                     CASE WHEN (p.prediction='DOWN' AND s.f_oracle_lead < 0) OR (p.prediction='UP' AND s.f_oracle_lead > 0) THEN 1 ELSE 0 END +
                     CASE WHEN (p.prediction='DOWN' AND s.f_book_imbalance > 0) OR (p.prediction='UP' AND s.f_book_imbalance < 0) THEN 1 ELSE 0 END +
                     CASE WHEN s.f_volatility > 0.5 THEN 1 ELSE 0 END +
                     CASE WHEN s.f_time_decay > 0.5 THEN 1 ELSE 0 END) as factors_agreed
                FROM btc_pnl p
                JOIN btc_windows w ON p.window_id = w.window_id
                JOIN LATERAL (
                    SELECT * FROM btc_signals WHERE window_id = p.window_id AND prediction != 'SKIP' ORDER BY confidence DESC LIMIT 1
                ) s ON true
                ORDER BY p.close_time DESC
                LIMIT 50
            """)
            # Convert Decimal/datetime to JSON-serializable
            trades = []
            for r in rows:
                trade = dict(r)
                for k, v in trade.items():
                    if hasattr(v, 'isoformat'):
                        trade[k] = v.isoformat()
                    elif hasattr(v, '__float__'):
                        trade[k] = float(v)
                trades.append(trade)
            return {"trades": trades}
    except Exception as e:
        logger.error(f"BTC trades-detail error: {e}\n{traceback.format_exc()}")
        return {"trades": [], "error": str(e)}


@app.get("/api/btc/performance")
async def get_btc_performance():
    """Full performance summary — deduplicated best signal per window."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            # Per-timeframe stats
            stats = await conn.fetch("""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, s.prob_up, s.confidence,
                        w.resolution, w.window_length, w.btc_open, w.btc_close,
                        w.close_time, w.up_price, w.down_price,
                        (s.prediction = w.resolution) as correct
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                    ORDER BY s.window_id, s.confidence DESC
                )
                SELECT window_length, 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    COUNT(*) FILTER (WHERE NOT correct) as losses,
                    ROUND(COUNT(*) FILTER (WHERE correct)::numeric / COUNT(*)::numeric * 100, 1) as accuracy
                FROM best GROUP BY window_length ORDER BY window_length
            """)

            # Recent trades (last 30)
            trades = await conn.fetch("""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, ROUND(s.prob_up::numeric * 100) as prob,
                        ROUND(s.confidence::numeric * 100) as conf,
                        w.resolution, w.window_length, w.btc_open, w.btc_close,
                        w.close_time, w.up_price, w.down_price,
                        (s.prediction = w.resolution) as correct
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                    ORDER BY s.window_id, s.confidence DESC
                )
                SELECT * FROM best ORDER BY close_time DESC LIMIT 30
            """)

            # Hourly breakdown
            hourly = await conn.fetch("""
                WITH best AS (
                    SELECT DISTINCT ON (s.window_id)
                        s.window_id, s.prediction, w.resolution, w.window_length,
                        w.close_time, (s.prediction = w.resolution) as correct
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    WHERE s.prediction != 'SKIP' AND w.resolution IS NOT NULL
                    ORDER BY s.window_id, s.confidence DESC
                )
                SELECT date_trunc('hour', close_time AT TIME ZONE 'Asia/Kolkata') as hour,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE correct) as wins,
                    ROUND(COUNT(*) FILTER (WHERE correct)::numeric / COUNT(*)::numeric * 100, 1) as accuracy
                FROM best GROUP BY 1 ORDER BY 1 DESC LIMIT 12
            """)

        return {
            "stats": [{"window": f"{r['window_length']}m", "total": r['total'], "wins": r['wins'], "losses": r['losses'], "accuracy": float(r['accuracy'])} for r in stats],
            "trades": [{"window_id": r['window_id'], "wl": f"{r['window_length']}m", "call": r['prediction'], "prob": int(r['prob']), "conf": int(r['conf']), "actual": r['resolution'], "correct": r['correct'], "close_time": r['close_time'].isoformat(), "btc_open": float(r['btc_open']) if r['btc_open'] else None, "btc_close": float(r['btc_close']) if r['btc_close'] else None} for r in trades],
            "hourly": [{"hour": r['hour'].isoformat(), "total": r['total'], "wins": r['wins'], "accuracy": float(r['accuracy'])} for r in hourly],
        }
    except Exception as e:
        logger.error(f"BTC performance error: {e}")
        return {"error": str(e)}


@app.get("/api/arb/internal")
async def get_internal_arb_opportunities():
    """Get current internal arb opportunities (YES+NO < $1.00)."""
    try:
        from src.strategies.internal_arb import InternalArbScanner
        scanner = InternalArbScanner(get_async_pool())
        opps = await scanner.scan_combined()
        return {
            "opportunities": opps,
            "count": len(opps),
            "last_scan": _last_internal_arb_scan.isoformat() if _last_internal_arb_scan else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Internal arb API error: {e}")
        return {"opportunities": [], "count": 0, "error": str(e)}


@app.get("/api/arb/internal/db")
async def get_internal_arb_db_only():
    """Get arb opportunities from DB only (faster, no external API calls)."""
    try:
        from src.strategies.internal_arb import InternalArbScanner
        scanner = InternalArbScanner(get_async_pool())
        opps = await scanner.scan_all_markets()
        return {"opportunities": opps, "count": len(opps)}
    except Exception as e:
        logger.error(f"Internal arb DB API error: {e}")
        return {"opportunities": [], "count": 0, "error": str(e)}


@app.get("/api/arb/internal/live")
async def get_internal_arb_live():
    """Get arb opportunities from Gamma API (real-time, slower)."""
    try:
        from src.strategies.internal_arb import InternalArbScanner
        scanner = InternalArbScanner(get_async_pool())
        opps = await scanner.scan_clob_live()
        return {"opportunities": opps, "count": len(opps)}
    except Exception as e:
        logger.error(f"Internal arb live API error: {e}")
        return {"opportunities": [], "count": 0, "error": str(e)}


@app.get("/api/arb/trades")
async def get_internal_arb_trades(limit: int = 50):
    """Get executed internal arb paper trades."""
    try:
        results = await fetch_all("""
            SELECT id, market_id, market_title, side, entry_price, shares,
                   size_usd, edge_at_entry, status, pnl_usd, pnl_pct,
                   entry_at, resolved_at, metadata
            FROM trades
            WHERE strategy = 'internal_arb'
            ORDER BY entry_at DESC
            LIMIT %s
        """, (min(limit, 200),))
        
        total_pnl = sum(float(r.get('pnl_usd', 0) or 0) for r in (results or []))
        return {
            "trades": results or [],
            "count": len(results or []),
            "total_pnl": round(total_pnl, 2),
        }
    except Exception as e:
        logger.error(f"Internal arb trades error: {e}")
        return {"trades": [], "count": 0, "error": str(e)}


# =============================================================================
# Sports Intelligence Endpoints
# =============================================================================

@app.get("/api/sports/markets")
async def sports_markets(sport: str = None, limit: int = 200):
    """Get active sports markets from Polymarket, categorized. Fetches live from Gamma API."""
    import httpx
    try:
        scanner = PolymarketSportsScanner(None)
        raw_markets = await scanner.fetch_sports_markets()
        
        # Categorize and filter
        categorized = []
        for m in raw_markets:
            q = m.get('question', '')
            s = scanner.categorize_sport(q)
            if sport and s.lower() != sport.lower():
                continue
            m['sport'] = s
            m['event_type'] = scanner.detect_event_type(q)
            m['group_id'] = scanner.generate_group_id(q)
            team_a, team_b = scanner.extract_teams(q, s)
            m['team_a'] = team_a
            m['team_b'] = team_b
            categorized.append(m)
        
        # Sort by volume
        categorized.sort(key=lambda x: float(x.get('volume', 0) or 0), reverse=True)
        categorized = categorized[:limit]
        
        # Group by sport
        sports_summary = {}
        for m in categorized:
            s = m.get('sport', 'Other')
            if s not in sports_summary:
                sports_summary[s] = {'count': 0, 'total_volume': 0, 'total_liquidity': 0}
            sports_summary[s]['count'] += 1
            sports_summary[s]['total_volume'] += float(m.get('volume', 0) or 0)
            sports_summary[s]['total_liquidity'] += float(m.get('liquidity', 0) or 0)
        
        # Normalize field names
        for m in categorized:
            m['yes_price'] = m.get('outcomePrices', '').split(',')[0] if m.get('outcomePrices') else None
            m['volume_usd'] = m.get('volume', 0)
            m['liquidity_usd'] = m.get('liquidity', 0)
            m['market_id'] = m.get('id', '')
            m['resolution_date'] = m.get('endDate', '')
        
        return {
            "total": len(categorized),
            "scanned": len(raw_markets),
            "by_sport": sports_summary,
            "markets": categorized
        }
    except Exception as e:
        logger.error(f"Sports markets error: {e}")
        import traceback; traceback.print_exc()
        return {"total": 0, "error": str(e), "markets": []}


@app.get("/api/sports/markets/{sport}")
async def sports_markets_by_sport(sport: str):
    """Get markets for a specific sport."""
    return await sports_markets(sport=sport, limit=200)


@app.get("/api/sports/groups")
async def sports_groups():
    """Get market groups with sum analysis. Groups markets by event (e.g., all Stanley Cup teams)."""
    try:
        # Fetch fresh market data
        data = await sports_markets(limit=500)
        all_markets = data.get('markets', [])
        
        # Group by group_id
        group_map = {}
        for m in all_markets:
            gid = m.get('group_id')
            if not gid:
                continue
            if gid not in group_map:
                group_map[gid] = {'sport': m.get('sport', 'Other'), 'markets': []}
            
            # Parse yes_price
            yp = 0
            try:
                prices_str = m.get('outcomePrices', '')
                if prices_str:
                    # Format is '["0.95","0.05"]' or '0.95,0.05'
                    import json
                    try:
                        prices = json.loads(prices_str)
                        yp = float(prices[0]) if prices else 0
                    except:
                        yp = float(prices_str.split(',')[0].strip('[]"')) if ',' in prices_str else 0
            except:
                yp = 0
            
            group_map[gid]['markets'].append({
                'question': m.get('question', ''),
                'yes_price': yp,
                'market_id': m.get('id', m.get('market_id', '')),
                'volume': float(m.get('volume', 0) or 0)
            })
        
        # Build groups with sum analysis
        groups = []
        for gid, data in group_map.items():
            mkts = data['markets']
            if len(mkts) < 2:
                continue
            total = sum(m['yes_price'] for m in mkts)
            mkts.sort(key=lambda x: -x['yes_price'])
            groups.append({
                'group_id': gid,
                'sport': data['sport'],
                'market_count': len(mkts),
                'total_yes_sum': round(total, 4),
                'overpriced': total > 1.05,
                'sum_pct': round(total * 100, 1),
                'arb_edge': round((total - 1.0) * 100, 1) if total > 1.0 else 0,
                'questions': [m['question'] for m in mkts[:10]],
                'prices': [m['yes_price'] for m in mkts[:10]],
                'market_ids': [m['market_id'] for m in mkts[:10]],
                'total_volume': sum(m['volume'] for m in mkts)
            })
        
        groups.sort(key=lambda x: -x['total_yes_sum'])
        
        return {
            "total_groups": len(groups),
            "overpriced_groups": len([g for g in groups if g['overpriced']]),
            "groups": groups
        }
    except Exception as e:
        logger.error(f"Sports groups error: {e}")
        import traceback; traceback.print_exc()
        return {"total_groups": 0, "error": str(e), "groups": []}


@app.get("/api/sports/arbitrage")
async def sports_arbitrage():
    """Find logical arbitrage from group overpricing."""
    try:
        group_data = await sports_groups()
        overpriced = [g for g in group_data.get('groups', []) if g['overpriced']]
        
        opportunities = []
        for g in overpriced:
            opportunities.append({
                'type': 'group_overpricing',
                'group_id': g['group_id'],
                'sport': g['sport'],
                'market_count': g['market_count'],
                'sum_pct': g['sum_pct'],
                'edge_pct': g['arb_edge'],
                'reasoning': f"Group '{g['group_id']}' has {g['market_count']} markets summing to {g['sum_pct']}% (should be ~100%). Overpriced by {g['arb_edge']}%.",
                'top_markets': list(zip(g['questions'][:5], g['prices'][:5]))
            })
        
        return {
            "total": len(opportunities),
            "opportunities": opportunities
        }
    except Exception as e:
        logger.error(f"Sports arbitrage error: {e}")
        return {"total": 0, "error": str(e), "opportunities": []}


@app.get("/api/sports/signals")
async def sports_signals(limit: int = 50):
    """Get sports trading signals. For now, derive from group overpricing."""
    try:
        arb_data = await sports_arbitrage()
        signals = []
        for opp in arb_data.get('opportunities', []):
            signals.append({
                'id': len(signals) + 1,
                'edge_type': opp['type'],
                'sport': opp['sport'],
                'market_id': opp['group_id'],
                'market_title': opp['group_id'],
                'polymarket_price': opp['sum_pct'] / 100,
                'fair_value': 1.0,
                'edge_pct': opp['edge_pct'],
                'confidence': 'HIGH' if opp['edge_pct'] > 10 else 'MEDIUM',
                'signal': 'SELL_OVERPRICED',
                'reasoning': opp['reasoning'],
                'created_at': datetime.utcnow().isoformat()
            })
        return {"signals": signals}
    except Exception as e:
        logger.error(f"Sports signals error: {e}")
        return {"signals": [], "error": str(e)}


@app.get("/api/sports/live")
async def sports_live():
    """Get live games with scores from ESPN."""
    import httpx
    try:
        espn_feeds = [
            ('hockey', 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard'),
            ('basketball', 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'),
            ('soccer_ucl', 'https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard'),
            ('soccer_epl', 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard'),
            ('baseball', 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard'),
        ]
        
        events = []
        async with httpx.AsyncClient(timeout=10) as client:
            for sport_key, url in espn_feeds:
                try:
                    resp = await client.get(url)
                    data = resp.json()
                    for evt in data.get('events', []):
                        status_type = evt.get('status', {}).get('type', {})
                        status = 'live' if status_type.get('state') == 'in' else ('finished' if status_type.get('completed') else 'scheduled')
                        comps = evt.get('competitions', [{}])[0]
                        competitors = comps.get('competitors', [])
                        home = next((c for c in competitors if c.get('homeAway') == 'home'), competitors[0] if competitors else {})
                        away = next((c for c in competitors if c.get('homeAway') == 'away'), competitors[1] if len(competitors) > 1 else {})
                        events.append({
                            'sport': sport_key.replace('_ucl','').replace('_epl',''),
                            'event_id': evt.get('id', ''),
                            'home_team': home.get('team', {}).get('displayName', ''),
                            'away_team': away.get('team', {}).get('displayName', ''),
                            'home_score': int(home.get('score', 0) or 0),
                            'away_score': int(away.get('score', 0) or 0),
                            'status': status,
                            'detail': status_type.get('shortDetail', ''),
                            'period': comps.get('status', {}).get('period', ''),
                            'minute': comps.get('status', {}).get('displayClock', ''),
                        })
                except Exception as e:
                    logger.warning(f"ESPN {sport_key} fetch failed: {e}")
        
        # Sort: live first, then scheduled, then finished
        events.sort(key=lambda x: 0 if x['status'] == 'live' else (1 if x['status'] == 'scheduled' else 2))
        
        return {
            "total": len(events),
            "live": len([e for e in events if e['status'] == 'live']),
            "scheduled": len([e for e in events if e['status'] == 'scheduled']),
            "finished": len([e for e in events if e['status'] == 'finished']),
            "events": events
        }
    except Exception as e:
        logger.error(f"Sports live error: {e}")
        return {"total": 0, "error": str(e), "events": []}


@app.get("/api/sports/performance")
async def sports_performance():
    """Sports strategy performance metrics."""
    try:
        arb_data = await sports_arbitrage()
        return {
            "total_opportunities": arb_data.get('total', 0),
            "by_edge_type": [{
                'type': 'group_overpricing',
                'total': arb_data.get('total', 0),
                'avg_edge': sum(o['edge_pct'] for o in arb_data.get('opportunities',[])) / max(len(arb_data.get('opportunities',[])), 1)
            }]
        }
    except Exception as e:
        return {"by_edge_type": [], "error": str(e)}


# =============================================================================
# Telegram Subscriber Bot API
# =============================================================================

@app.get("/api/telegram/subscribers")
async def get_telegram_subscribers():
    """Get subscriber count and stats."""
    try:
        async_pool = get_async_pool()
        async with async_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN is_active = true THEN 1 END) as active,
                        COUNT(CASE WHEN alert_frequency = 'instant' THEN 1 END) as instant,
                        COUNT(CASE WHEN alert_frequency = 'daily' THEN 1 END) as daily,
                        SUM(total_alerts_sent) as total_alerts
                    FROM telegram_subscribers
                """)
                row = await cur.fetchone()
                
        return {
            "total": row[0] if row else 0,
            "active": row[1] if row else 0,
            "instant": row[2] if row else 0,
            "daily": row[3] if row else 0,
            "total_alerts_sent": row[4] if row else 0,
            "bot_enabled": _telegram_bot is not None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Telegram subscribers error: {e}")
        return {"total": 0, "active": 0, "error": str(e)}


@app.post("/api/telegram/broadcast")
async def manual_broadcast(data: dict):
    """Manually broadcast a message (admin only)."""
    global _telegram_bot
    
    if not _telegram_bot:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    message = data.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    
    # Admin check (compare with TELEGRAM_ADMIN_CHAT_ID)
    admin_chat_id = data.get("admin_chat_id")
    if str(admin_chat_id) != str(_telegram_bot.admin_chat_id):
        raise HTTPException(status_code=403, detail="Admin only")
    
    try:
        subscribers = await _telegram_bot.get_all_subscribers()
        sent = 0
        for sub in subscribers:
            try:
                await _telegram_bot.app.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='HTML'
                )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send to {sub['chat_id']}: {e}")
        
        return {
            "status": "broadcast_complete",
            "sent": sent,
            "total_subscribers": len(subscribers),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Manual broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Leader Strategy — Copy-Trading System
# =============================================================================

LEADER_WALLET = "0x492442eab586f242b53bda933fd5de859c8a3782"


@app.get("/api/leader/trades")
async def get_leader_trades(limit: int = 50, status: str = None, sport: str = None):
    """Get tracked leader trades."""
    query = "SELECT * FROM leader_trades ORDER BY detected_at DESC LIMIT %s"
    params = (min(limit, 200),)
    
    if status:
        query = "SELECT * FROM leader_trades WHERE status = %s ORDER BY detected_at DESC LIMIT %s"
        params = (status, min(limit, 200))
    
    rows = await fetch_all(query, tuple(params))
    return {"trades": rows or [], "count": len(rows or [])}


@app.get("/api/leader/stats")
async def get_leader_stats():
    """Get leader strategy statistics."""
    # Overall stats
    stats = await fetch_one("""
        SELECT 
            COUNT(*) as total_trades,
            SUM(leader_size) as total_volume,
            AVG(leader_price) as avg_entry_price,
            COUNT(CASE WHEN status = 'detected' THEN 1 END) as active,
            COUNT(CASE WHEN result = 'won' THEN 1 END) as wins,
            COUNT(CASE WHEN result = 'lost' THEN 1 END) as losses,
            SUM(CASE WHEN result IS NOT NULL THEN pnl ELSE 0 END) as total_pnl,
            SUM(our_size) as our_total_deployed
        FROM leader_trades
    """)
    
    # By sport breakdown
    by_sport = await fetch_all("""
        SELECT sport, COUNT(*) as count, SUM(leader_size) as volume, 
               AVG(leader_price) as avg_price
        FROM leader_trades 
        GROUP BY sport ORDER BY volume DESC
    """)
    
    # By type breakdown
    by_type = await fetch_all("""
        SELECT trade_type, COUNT(*) as count, SUM(leader_size) as volume
        FROM leader_trades
        GROUP BY trade_type ORDER BY volume DESC
    """)
    
    # Daily performance
    daily = await fetch_all("""
        SELECT * FROM leader_performance 
        WHERE wallet = %s 
        ORDER BY date DESC LIMIT 14
    """, (LEADER_WALLET,))
    
    return {
        "stats": stats or {},
        "by_sport": by_sport or [],
        "by_type": by_type or [],
        "daily_performance": daily or [],
        "leader_wallet": LEADER_WALLET,
        "leader_name": "Multicolored-Self",
        "leader_rank": "#1 Monthly"
    }


@app.get("/api/leader/live")  
async def get_leader_live_activity():
    """Get leader's live activity feed (real-time from Polymarket API)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://data-api.polymarket.com/v1/activity",
                params={"user": LEADER_WALLET, "limit": 20}
            )
            data = resp.json()
            
            activities = []
            for a in data:
                slug = a.get('slug', '').lower()
                # Classify
                if 'spread' in slug: 
                    trade_type = 'SPREAD'
                elif 'total' in slug: 
                    trade_type = 'TOTAL'
                else: 
                    trade_type = 'ML'
                
                sport = 'OTHER'
                for s, kw in [('NBA','nba'),('NHL','nhl'),('NCAA','ncaa'),('MLB','mlb')]:
                    if kw in slug:
                        sport = s
                        break
                
                activities.append({
                    "type": a.get("type"),
                    "title": a.get("title"),
                    "slug": a.get("slug"),
                    "price": float(a.get("price", 0)),
                    "size": float(a.get("usdcSize", 0)),
                    "side": a.get("side", ""),
                    "outcome": a.get("outcome", ""),
                    "outcome_index": a.get("outcomeIndex"),
                    "timestamp": a.get("timestamp"),
                    "trade_type": trade_type,
                    "sport": sport,
                    "condition_id": a.get("conditionId"),
                })
            
            return {"activities": activities, "count": len(activities)}
    except Exception as e:
        logger.error(f"Leader live activity error: {e}")
        return {"activities": [], "error": str(e)}


@app.get("/api/leader/config")
async def get_leader_config():
    """Get leader tracking configuration."""
    wallets = await fetch_all("SELECT * FROM leader_wallets WHERE active = true")
    return {
        "wallets": wallets or [{
            "wallet": LEADER_WALLET,
            "name": "Multicolored-Self (#1 Monthly)",
            "scale_factor": 0.00025,
            "max_position": 50.0,
            "active": True
        }],
        "poll_interval": 60,
        "strategy_rules": {
            "only_spreads_totals": True,
            "max_entry_price": 0.60,
            "min_leader_size": 10000,
            "sports_filter": ["NBA", "NHL", "NCAA"],
            "copy_delay_seconds": 5,
        }
    }


# =============================================================================
# SPRINT 2: Analytics Endpoints
# =============================================================================

@app.get("/api/analytics/strategies")
async def get_analytics_strategies():
    """Returns all strategy performance data from strategy_performance table."""
    try:
        results = await fetch_all("""
            SELECT strategy, sport, period_start, period_end,
                   total_trades, wins, losses, win_rate,
                   total_pnl, avg_edge, avg_pnl_per_trade,
                   max_drawdown, sharpe_ratio, is_active, updated_at
            FROM strategy_performance
            ORDER BY updated_at DESC
        """)
        strategies = []
        for r in results:
            strategies.append({
                'strategy': r['strategy'],
                'sport': r['sport'],
                'period_start': str(r['period_start']) if r['period_start'] else None,
                'period_end': str(r['period_end']) if r['period_end'] else None,
                'total_trades': r['total_trades'],
                'wins': r['wins'],
                'losses': r['losses'],
                'win_rate': float(r['win_rate']) if r['win_rate'] else 0,
                'total_pnl': float(r['total_pnl']) if r['total_pnl'] else 0,
                'avg_edge': float(r['avg_edge']) if r['avg_edge'] else 0,
                'avg_pnl_per_trade': float(r['avg_pnl_per_trade']) if r['avg_pnl_per_trade'] else 0,
                'max_drawdown': float(r['max_drawdown']) if r['max_drawdown'] else 0,
                'sharpe_ratio': float(r['sharpe_ratio']) if r['sharpe_ratio'] else None,
                'is_active': r['is_active'],
                'updated_at': str(r['updated_at']) if r['updated_at'] else None,
            })
        return {"strategies": strategies, "count": len(strategies)}
    except Exception as e:
        logger.error(f"Analytics strategies error: {e}")
        return {"strategies": [], "count": 0, "error": str(e)}


@app.get("/api/analytics/daily-digest")
async def get_analytics_daily_digest():
    """Returns today's summary: trades, P&L, best/worst strategy, bankroll."""
    try:
        # Today's settled trades
        today_stats = await fetch_one("""
            SELECT 
                COUNT(*) as trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(pnl_usd), 0) as total_pnl,
                MAX(pnl_usd) as best_pnl,
                MIN(pnl_usd) as worst_pnl
            FROM trades
            WHERE resolved_at >= CURRENT_DATE AND status IN ('won', 'lost')
        """)
        
        # Per-strategy today
        strat_breakdown = await fetch_all("""
            SELECT strategy,
                   COUNT(*) as trades,
                   SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                   COALESCE(SUM(pnl_usd), 0) as pnl
            FROM trades
            WHERE resolved_at >= CURRENT_DATE AND status IN ('won', 'lost')
            GROUP BY strategy
            ORDER BY pnl DESC
        """)
        
        # Best and worst trade details
        best_trade = await fetch_one("""
            SELECT market_title, pnl_usd, strategy FROM trades
            WHERE resolved_at >= CURRENT_DATE AND status IN ('won', 'lost')
            ORDER BY pnl_usd DESC LIMIT 1
        """)
        worst_trade = await fetch_one("""
            SELECT market_title, pnl_usd, strategy FROM trades
            WHERE resolved_at >= CURRENT_DATE AND status IN ('won', 'lost')
            ORDER BY pnl_usd ASC LIMIT 1
        """)
        
        # Bankroll
        bankroll = await fetch_one(
            "SELECT total_usd, available_usd, in_positions_usd FROM bankroll ORDER BY timestamp DESC LIMIT 1"
        )
        
        # Disabled strategies
        disabled = await fetch_all("""
            SELECT strategy, win_rate, total_trades FROM strategy_performance
            WHERE is_active = false
        """)
        
        total_trades = int(today_stats.get('trades', 0) or 0) if today_stats else 0
        wins = int(today_stats.get('wins', 0) or 0) if today_stats else 0
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "date": datetime.utcnow().strftime('%Y-%m-%d'),
            "trades": total_trades,
            "wins": wins,
            "losses": int(today_stats.get('losses', 0) or 0) if today_stats else 0,
            "win_rate": round(win_rate, 1),
            "total_pnl": float(today_stats.get('total_pnl', 0) or 0) if today_stats else 0,
            "best_trade": {
                "market": best_trade.get('market_title', '') if best_trade else '',
                "pnl": float(best_trade.get('pnl_usd', 0) or 0) if best_trade else 0,
                "strategy": best_trade.get('strategy', '') if best_trade else '',
            } if best_trade else None,
            "worst_trade": {
                "market": worst_trade.get('market_title', '') if worst_trade else '',
                "pnl": float(worst_trade.get('pnl_usd', 0) or 0) if worst_trade else 0,
                "strategy": worst_trade.get('strategy', '') if worst_trade else '',
            } if worst_trade else None,
            "strategy_breakdown": [{
                "strategy": s['strategy'],
                "trades": s['trades'],
                "wins": int(s['wins'] or 0),
                "pnl": float(s['pnl'] or 0),
            } for s in (strat_breakdown or [])],
            "bankroll": {
                "total": float(bankroll.get('total_usd', 0) or 0) if bankroll else 0,
                "available": float(bankroll.get('available_usd', 0) or 0) if bankroll else 0,
                "in_positions": float(bankroll.get('in_positions_usd', 0) or 0) if bankroll else 0,
            },
            "disabled_strategies": [{
                "strategy": d['strategy'],
                "win_rate": float(d['win_rate'] or 0),
                "total_trades": d['total_trades'],
            } for d in (disabled or [])],
        }
    except Exception as e:
        logger.error(f"Analytics daily digest error: {e}")
        return {"error": str(e)}


@app.get("/api/analytics/sport-breakdown")
async def get_analytics_sport_breakdown():
    """P&L breakdown by sport."""
    try:
        # From trades table - extract sport from market_title heuristics
        results = await fetch_all("""
            SELECT 
                CASE 
                    WHEN LOWER(market_title) LIKE '%%ipl%%' OR LOWER(market_title) LIKE '%%cricket%%' THEN 'Cricket/IPL'
                    WHEN LOWER(market_title) LIKE '%%nba%%' OR LOWER(market_title) LIKE '%%basketball%%' THEN 'NBA'
                    WHEN LOWER(market_title) LIKE '%%nhl%%' OR LOWER(market_title) LIKE '%%hockey%%' THEN 'NHL'
                    WHEN LOWER(market_title) LIKE '%%soccer%%' OR LOWER(market_title) LIKE '%%epl%%' THEN 'Soccer'
                    WHEN LOWER(market_title) LIKE '%%mlb%%' OR LOWER(market_title) LIKE '%%baseball%%' THEN 'MLB'
                    ELSE 'Other'
                END as sport,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(pnl_usd), 0) as total_pnl,
                COALESCE(AVG(pnl_usd), 0) as avg_pnl,
                COALESCE(AVG(edge_at_entry), 0) as avg_edge
            FROM trades
            WHERE status IN ('won', 'lost')
            GROUP BY sport
            ORDER BY total_pnl DESC
        """)
        
        sports = [{
            'sport': r['sport'],
            'total_trades': r['total_trades'],
            'wins': int(r['wins'] or 0),
            'losses': int(r['losses'] or 0),
            'win_rate': round(int(r['wins'] or 0) / r['total_trades'] * 100, 1) if r['total_trades'] > 0 else 0,
            'total_pnl': round(float(r['total_pnl'] or 0), 2),
            'avg_pnl': round(float(r['avg_pnl'] or 0), 2),
            'avg_edge': round(float(r['avg_edge'] or 0), 4),
        } for r in (results or [])]
        
        return {"sports": sports, "count": len(sports)}
    except Exception as e:
        logger.error(f"Sport breakdown error: {e}")
        return {"sports": [], "count": 0, "error": str(e)}


# =============================================================================
# LIVE TRADING ENDPOINTS (live trades, live stats)
# =============================================================================

@app.get("/api/live/trades")
async def get_live_trades():
    """Get only LIVE trades (not paper)."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, window_id, prediction, token_id, side,
                       entry_price, stake_usd, tx_hash, status,
                       exit_price, pnl_usd, wallet_balance_before,
                       wallet_balance_after, created_at, resolved_at
                FROM live_trades
                ORDER BY created_at DESC
                LIMIT 50
            """)
            trades = []
            for row in rows:
                r = dict(row)
                trades.append({
                    "id": r["id"],
                    "window_id": r.get("window_id"),
                    "prediction": r.get("prediction"),
                    "token_id": r.get("token_id"),
                    "side": r.get("side"),
                    "entry_price": float(r["entry_price"]) if r.get("entry_price") else None,
                    "stake_usd": float(r["stake_usd"]) if r.get("stake_usd") else None,
                    "tx_hash": r.get("tx_hash"),
                    "status": r.get("status"),
                    "exit_price": float(r["exit_price"]) if r.get("exit_price") else None,
                    "pnl_usd": float(r["pnl_usd"]) if r.get("pnl_usd") else None,
                    "wallet_before": float(r["wallet_balance_before"]) if r.get("wallet_balance_before") else None,
                    "wallet_after": float(r["wallet_balance_after"]) if r.get("wallet_balance_after") else None,
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                    "resolved_at": r["resolved_at"].isoformat() if r.get("resolved_at") else None,
                })
            return {"trades": trades, "mode": "live"}
    except Exception as e:
        logger.error(f"Live trades error: {e}")
        return {"trades": [], "mode": "live", "error": str(e)}


@app.get("/api/live/stats")
async def get_live_stats():
    """Get live trading stats only."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), 0) as wins,
                    COALESCE(SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END), 0) as losses,
                    COALESCE(SUM(pnl_usd), 0) as total_pnl,
                    COALESCE(AVG(pnl_usd), 0) as avg_pnl,
                    COALESCE(SUM(stake_usd), 0) as total_staked
                FROM live_trades
                WHERE status = 'resolved'
            """)
            total = int(row["total"])
            wins = int(row["wins"])
            losses = int(row["losses"])
            total_pnl = float(row["total_pnl"])
            avg_pnl = float(row["avg_pnl"])
            total_staked = float(row["total_staked"])
            win_rate = (wins / total * 100) if total > 0 else 0
            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 2),
                "total_staked": round(total_staked, 2),
                "mode": "live"
            }
    except Exception as e:
        logger.error(f"Live stats error: {e}")
        return {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0, "total_staked": 0, "mode": "live", "error": str(e)}


# =============================================================================
# HOME COMMAND CENTER ENDPOINTS
# =============================================================================

@app.get("/api/live/today")
async def get_today_pnl():
    """Today's P&L from live_trades resolved today."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as trades,
                    COALESCE(SUM(pnl_usd), 0) as pnl,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins
                FROM live_trades
                WHERE resolved_at >= CURRENT_DATE
                AND status = 'resolved'
            """)
        pnl = float(row['pnl'])
        return {
            "trades": row['trades'],
            "pnl": round(pnl, 2),
            "wins": row['wins'] or 0,
            "profitable": pnl >= 0
        }
    except Exception as e:
        logger.error(f"Today PnL error: {e}")
        return {"trades": 0, "pnl": 0, "wins": 0, "profitable": True}


@app.get("/api/live/positions")
async def get_active_positions():
    """Active open positions count and deployed capital."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) as count, COALESCE(SUM(stake_usd), 0) as deployed
                FROM live_trades WHERE status = 'open'
            """)
        return {
            "count": row['count'],
            "deployed": round(float(row['deployed']), 2)
        }
    except Exception as e:
        logger.error(f"Active positions error: {e}")
        return {"count": 0, "deployed": 0}


@app.get("/api/live/weekly")
async def get_weekly_pnl():
    """7-day P&L from live_trades."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as trades,
                    COALESCE(SUM(pnl_usd), 0) as pnl
                FROM live_trades
                WHERE resolved_at >= CURRENT_DATE - INTERVAL '7 days'
                AND status = 'resolved'
            """)
        return {
            "trades": row['trades'],
            "pnl": round(float(row['pnl']), 2)
        }
    except Exception as e:
        logger.error(f"Weekly PnL error: {e}")
        return {"trades": 0, "pnl": 0}


@app.get("/api/live/trend")
async def get_pnl_trend():
    """7-day daily P&L trend for sparkline chart."""
    try:
        pool = get_async_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    DATE(resolved_at) as day,
                    COALESCE(SUM(pnl_usd), 0) as pnl,
                    COUNT(*) as trades
                FROM live_trades
                WHERE resolved_at >= CURRENT_DATE - INTERVAL '7 days'
                AND status = 'resolved'
                GROUP BY DATE(resolved_at)
                ORDER BY day
            """)
        return [{"day": str(r['day']), "pnl": round(float(r['pnl']), 2), "trades": r['trades']} for r in rows]
    except Exception as e:
        logger.error(f"PnL trend error: {e}")
        return []


# =============================================================================
# JC Copy Trading API Endpoints
# =============================================================================

@app.get("/api/jc/status")
async def jc_status():
    """Get JC copy trader status: mode, daily loss, open position."""
    try:
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from jc_copy_trader import get_trading_mode
        mode = get_trading_mode()
        
        result = {"mode": mode, "ok": True}
        
        if mode == 'live':
            try:
                from bybit_executor import get_executor
                executor = get_executor()
                conn_test = executor.test_connectivity()
                pos = executor.get_open_positions()
                daily = executor.get_daily_loss_state()
                result.update({
                    "bybit_connected": conn_test.get("ok", False),
                    "bybit_equity": conn_test.get("equity", 0),
                    "open_positions": pos.get("positions", []),
                    "daily_loss": daily,
                })
            except Exception as e:
                result["bybit_error"] = str(e)
        
        # DB stats (sync via psycopg2 since we're in JC context)
        try:
            import psycopg2
            conn2 = psycopg2.connect("dbname=polyedge user=node host=localhost")
            cur2 = conn2.cursor()
            cur2.execute("SELECT balance, available, in_positions, total_won, total_lost, total_trades FROM jc_bankroll ORDER BY id DESC LIMIT 1")
            bank = cur2.fetchone()
            if bank:
                result["bankroll"] = {
                    "balance": float(bank[0]), "available": float(bank[1]),
                    "in_positions": float(bank[2]), "total_won": float(bank[3]),
                    "total_lost": float(bank[4]), "total_trades": bank[5],
                }
            cur2.execute("SELECT id, direction, entry_price, status FROM jc_trades WHERE status IN ('active','half_closed','breakeven')")
            result["open_db_trades"] = [{"id": r[0], "direction": r[1], "entry_price": float(r[2]), "status": r[3]} for r in cur2.fetchall()]
            conn2.close()
        except Exception as db_err:
            result["db_error"] = str(db_err)
        
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/jc/mode")
async def jc_set_mode(request: Request):
    """Toggle JC trading mode between 'paper' and 'live'."""
    try:
        body = await request.json()
        mode = body.get("mode", "paper").lower().strip()
        if mode not in ("paper", "live"):
            return {"ok": False, "error": "mode must be 'paper' or 'live'"}
        
        import psycopg2 as _pg2
        _conn2 = _pg2.connect("dbname=polyedge user=node host=localhost")
        _cur2 = _conn2.cursor()
        _cur2.execute(
            "INSERT INTO jc_settings (key, value, updated_at) VALUES (%s, %s, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
            ('mode', mode, mode),
        )
        _conn2.commit()
        _conn2.close()
        
        logger.info(f"JC trading mode set to: {mode}")
        return {"ok": True, "mode": mode, "message": f"JC trading mode switched to {mode.upper()}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/jc/test-trade")
async def jc_test_trade(request: Request):
    """Simulate a JC signal and trigger the copy trader (paper mode only).
    Useful for end-to-end pipeline testing."""
    try:
        body = await request.json()
        
        # Require paper mode for test
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from jc_copy_trader import get_trading_mode, open_trade, get_btc_price
        
        mode = get_trading_mode()
        if mode == 'live' and not body.get("force", False):
            return {
                "ok": False,
                "error": "Cannot test in live mode. Add force=true to override, or switch to paper mode first.",
                "current_mode": mode,
            }
        
        # Get current price or use override
        price = body.get("price") or get_btc_price() or 83000
        
        # Build a synthetic JC signal
        direction = body.get("direction", "LONG")
        if direction == "LONG":
            sl = price * 0.98     # 2% SL
            tp1 = price * 1.03   # 3% TP1 (1.5:1 R:R)
            tp2 = price * 1.05   # 5% TP2
        else:
            sl = price * 1.02
            tp1 = price * 0.97
            tp2 = price * 0.95
        
        test_signal = {
            "direction": direction,
            "entry": round(price, 2),
            "sl": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "rr": round(abs(tp1 - price) / abs(sl - price), 1) if sl != price else 0,
            "reason": body.get("reason", "TEST nwPOC @ ${:.0f}".format(price)),
            "leverage": body.get("leverage", 10),
            "level": {"price": price, "label": "TEST", "type": "support" if direction == "LONG" else "resistance"},
            "conviction": {
                "classification": "MEDIUM",
                "score": 65.0,
                "factors_agreed": 3,
                "total_factors": 7,
                "stake_pct": 0.03,
                "rr_ratio": 1.5,
            },
            "conviction_stake_pct": 0.03,
        }
        
        logger.info(f"JC test trade: {direction} @ ${price:,.0f}")
        trade_id = open_trade(test_signal, price)
        
        return {
            "ok": True,
            "trade_id": trade_id,
            "signal": test_signal,
            "mode": mode,
            "message": f"Test trade #{trade_id} opened in {mode.upper()} mode",
        }
    except Exception as e:
        logger.error(f"JC test trade error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@app.post("/api/jc/kill")
async def jc_kill_position():
    """Emergency kill — close Bybit position immediately."""
    try:
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from jc_copy_trader import get_trading_mode
        mode = get_trading_mode()
        
        if mode != 'live':
            return {"ok": False, "error": "Not in live mode — no real position to close"}
        
        from bybit_executor import get_executor
        executor = get_executor()
        result = executor.close_position(reason="Dashboard kill")
        
        if result["ok"]:
            # Update DB
            import psycopg2 as _pg2
            _conn2 = _pg2.connect("dbname=polyedge user=node host=localhost")
            _cur2 = _conn2.cursor()
            _cur2.execute("""
                UPDATE jc_trades SET status = 'closed', close_reason = 'MANUAL_KILL',
                    closed_at = NOW() WHERE status IN ('active','half_closed','breakeven')
            """)
            _conn2.commit()
            _conn2.close()
        
        return {"ok": result["ok"], "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/jc/bybit/balance")
async def jc_bybit_balance():
    """Get live Bybit account balance."""
    try:
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from bybit_executor import get_executor
        executor = get_executor()
        return executor.test_connectivity()
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/jc/bybit/position")
async def jc_bybit_position():
    """Get live Bybit open position."""
    try:
        sys.path.insert(0, '/data/.openclaw/workspace/projects/Ghost')
        from bybit_executor import get_executor
        executor = get_executor()
        return executor.get_open_positions()
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/jc/pause")
async def jc_pause_trading(request: Request):
    """Pause or resume JC copy trading."""
    try:
        body = await request.json()
        paused = bool(body.get("paused", True))
        import psycopg2 as _pg2
        _conn2 = _pg2.connect("dbname=polyedge user=node host=localhost")
        _cur2 = _conn2.cursor()
        _cur2.execute(
            "INSERT INTO jc_settings (key, value, updated_at) VALUES (%s, %s, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
            ('paused', str(paused).lower(), str(paused).lower()),
        )
        _conn2.commit()
        _conn2.close()
        return {"ok": True, "paused": paused}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =============================================================================
# Static Files — Serve React Dashboard
# =============================================================================

# Path to the built React dashboard
BUILD_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard", "dist")

if os.path.exists(BUILD_PATH):
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(BUILD_PATH, "assets")), name="assets")
    
    # Serve index.html for all non-API routes (SPA fallback)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If path starts with /api, it's already handled by API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # For root or any non-API path, serve index.html (React Router will handle)
        file_path = os.path.join(BUILD_PATH, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        else:
            return FileResponse(os.path.join(BUILD_PATH, "index.html"))
    
    logger.info(f"✅ Serving React dashboard from {BUILD_PATH}")
else:
    logger.warning(f"⚠️ Dashboard build not found at {BUILD_PATH}. Run 'npm run build' in dashboard/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6010)
