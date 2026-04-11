"""
Late Window Scalper — Near-Certain BTC Contract Buyer
Paper trading only. Buys 85-99¢ contracts in final 15-20 seconds of 5M windows.

Strategy:
  - Monitor active 5M BTC Up/Down windows
  - In final 5-20 seconds, check if current BTC > open BTC (UP winning) or < (DOWN winning)
  - If winning side token price >= 0.85 → paper buy $10 stake
  - Skip if BTC delta < $10 (too close to call)
  - Settle pending trades after window closes
"""

import asyncio
import httpx
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BINANCE_API = "https://api.binance.com/api/v3"
TELEGRAM_TOKEN = "8610642342:AAEKNxrbvUdJM-djnHs0RKL-82z3MrBVC24"
TELEGRAM_CHAT_ID = 1656605843

STAKE_USD = 10.0
MIN_ENTRY_PRICE = 0.85  # only buy 85¢+ contracts
MIN_BTC_DELTA = 10.0    # skip if BTC move < $10 (too close to call)
SCALP_WINDOW_MIN = 5    # enter when 5s remaining
SCALP_WINDOW_MAX = 20   # enter when <= 20s remaining


class LateWindowScalper:
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._enabled = True
        self._running = False
        self._traded_windows: set = set()  # epoch -> already traded, avoid double entry
        self._window_open_cache: Dict[int, float] = {}  # epoch -> btc_open_price
        self._binance_price_cache = None
        self._binance_price_ts = None
        
        # Stats for current session
        self._win_streak = 0
        self._today_pnl = 0.0

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------
    async def ensure_tables(self):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS late_window_trades (
                    id SERIAL PRIMARY KEY,
                    window_epoch BIGINT,
                    window_length INT DEFAULT 5,
                    direction TEXT,
                    entry_price NUMERIC(8,4),
                    exit_price NUMERIC(8,4),
                    stake_usd NUMERIC(10,2),
                    pnl_usd NUMERIC(10,2),
                    btc_open_price NUMERIC(12,2),
                    btc_close_price NUMERIC(12,2),
                    btc_current_price NUMERIC(12,2),
                    seconds_remaining INT,
                    oracle_price NUMERIC(12,2),
                    binance_price NUMERIC(12,2),
                    outcome TEXT DEFAULT 'pending',
                    traded_at TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS late_window_stats (
                    id SERIAL PRIMARY KEY,
                    stat_date DATE DEFAULT CURRENT_DATE,
                    trades_total INT DEFAULT 0,
                    trades_won INT DEFAULT 0,
                    trades_lost INT DEFAULT 0,
                    total_pnl NUMERIC(10,2) DEFAULT 0,
                    avg_entry_price NUMERIC(8,4),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(stat_date)
                )
            """)
        logger.info("✅ Late Window Scalper tables ready")

    # ------------------------------------------------------------------
    # BTC price helpers
    # ------------------------------------------------------------------
    async def get_binance_price(self) -> Optional[float]:
        """Get current BTC/USDT price from Binance. Cached for 1 second."""
        now = time.time()
        if self._binance_price_cache and self._binance_price_ts and (now - self._binance_price_ts) < 1:
            return self._binance_price_cache
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{BINANCE_API}/ticker/price", params={"symbol": "BTCUSDT"})
                data = resp.json()
                price = float(data['price'])
                self._binance_price_cache = price
                self._binance_price_ts = now
                return price
        except Exception as e:
            logger.warning(f"⚠️ Binance price failed: {e}")
            return self._binance_price_cache  # return stale if available

    async def get_window_open_price(self, window_epoch: int) -> Optional[float]:
        """Get BTC price at window open (5m candle open). Cached per epoch."""
        if window_epoch in self._window_open_cache:
            return self._window_open_cache[window_epoch]
        
        window_start = window_epoch - 300  # 5m window: start = end - 300s
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"{BINANCE_API}/klines",
                    params={
                        "symbol": "BTCUSDT",
                        "interval": "5m",
                        "startTime": window_start * 1000,
                        "limit": 1,
                    }
                )
                klines = resp.json()
                if klines and len(klines) > 0:
                    open_price = float(klines[0][1])  # index 1 = open price
                    self._window_open_cache[window_epoch] = open_price
                    return open_price
        except Exception as e:
            logger.warning(f"⚠️ get_window_open_price failed for epoch {window_epoch}: {e}")
        return None

    async def get_oracle_price(self) -> Optional[float]:
        """Get BTC price from CoinGecko oracle."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "bitcoin", "vs_currencies": "usd"}
                )
                data = resp.json()
                return float(data['bitcoin']['usd'])
        except Exception as e:
            logger.debug(f"Oracle price failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    def determine_winner(self, btc_open: float, btc_current: float) -> Optional[str]:
        """
        Determine which side is winning.
        Returns 'UP', 'DOWN', or None (too close to call).
        """
        delta = btc_current - btc_open
        if abs(delta) < MIN_BTC_DELTA:
            return None  # too close to call
        return 'UP' if delta > 0 else 'DOWN'

    async def paper_trade(
        self, direction: str, entry_price: float, window_epoch: int,
        btc_open: float, btc_current: float, seconds_remaining: int,
        oracle_price: Optional[float], binance_price: float
    ) -> Optional[int]:
        """Record a paper trade in the DB."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO late_window_trades 
                        (window_epoch, window_length, direction, entry_price, stake_usd,
                         btc_open_price, btc_current_price, seconds_remaining,
                         oracle_price, binance_price, outcome)
                    VALUES ($1, 5, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')
                    RETURNING id
                """, window_epoch, direction, entry_price, STAKE_USD,
                    btc_open, btc_current, seconds_remaining,
                    oracle_price, binance_price)
                return row['id'] if row else None
        except Exception as e:
            logger.error(f"❌ paper_trade failed: {e}")
            return None

    async def settle_pending(self):
        """Settle pending trades whose windows have closed."""
        try:
            now_ts = int(time.time())
            async with self.db_pool.acquire() as conn:
                # Get pending trades where window has ended (epoch <= now)
                pending = await conn.fetch("""
                    SELECT id, window_epoch, direction, entry_price, stake_usd, btc_open_price
                    FROM late_window_trades
                    WHERE outcome = 'pending'
                      AND window_epoch <= $1
                """, now_ts)

            for trade in pending:
                try:
                    trade_id = trade['id']
                    window_epoch = trade['window_epoch']
                    direction = trade['direction']
                    entry_price = float(trade['entry_price'])
                    stake = float(trade['stake_usd'])
                    btc_open = float(trade['btc_open_price'])

                    # Get BTC close price at window resolution
                    btc_close = await self.get_binance_price()
                    if not btc_close:
                        continue

                    # Determine actual winner
                    actual_winner = self.determine_winner(btc_open, btc_close)
                    if actual_winner is None:
                        # Still too close — wait a bit more or default to loss
                        # If window closed more than 60s ago, force settle
                        if now_ts - window_epoch > 60:
                            actual_winner = 'UP'  # default (rare edge case)
                        else:
                            continue

                    won = (direction == actual_winner)
                    if won:
                        # PnL = stake * (1 - entry_price) / entry_price
                        pnl = stake * (1.0 - entry_price) / entry_price
                        exit_price = 1.0
                        outcome = 'won'
                    else:
                        pnl = -stake
                        exit_price = 0.0
                        outcome = 'lost'

                    async with self.db_pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE late_window_trades
                            SET outcome = $1, exit_price = $2, pnl_usd = $3,
                                btc_close_price = $4, resolved_at = NOW()
                            WHERE id = $5
                        """, outcome, exit_price, round(pnl, 2), btc_close, trade_id)

                    # Update today's stats
                    await self._update_daily_stats(won, pnl)
                    
                    # Update session streak
                    if won:
                        self._win_streak += 1
                        self._today_pnl += pnl
                    else:
                        self._win_streak = 0
                        self._today_pnl += pnl

                    logger.info(
                        f"{'✅' if won else '❌'} Late scalp settled: {direction} | "
                        f"Entry={entry_price:.2f} | BTC {btc_open:.0f}→{btc_close:.0f} | "
                        f"PnL: ${pnl:+.2f}"
                    )

                    # Send Telegram notification
                    await self._send_telegram_report(trade, won, pnl, btc_close, actual_winner)

                except Exception as e:
                    logger.error(f"❌ Failed to settle trade {trade['id']}: {e}")

        except Exception as e:
            logger.error(f"❌ settle_pending failed: {e}")

    async def _update_daily_stats(self, won: bool, pnl: float):
        """Update daily aggregate stats."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO late_window_stats (stat_date, trades_total, trades_won, trades_lost, total_pnl)
                    VALUES (CURRENT_DATE, 1, $1, $2, $3)
                    ON CONFLICT (stat_date) DO UPDATE SET
                        trades_total = late_window_stats.trades_total + 1,
                        trades_won = late_window_stats.trades_won + $1,
                        trades_lost = late_window_stats.trades_lost + $2,
                        total_pnl = late_window_stats.total_pnl + $3,
                        updated_at = NOW()
                """, 1 if won else 0, 0 if won else 1, round(pnl, 2))
        except Exception as e:
            logger.warning(f"⚠️ _update_daily_stats failed: {e}")

    async def _send_telegram_report(self, trade, won: bool, pnl: float, btc_close: float, actual_winner: str):
        """Send trade result to Telegram."""
        try:
            btc_open = float(trade['btc_open_price'])
            direction = trade['direction']
            entry_price = float(trade['entry_price'])
            
            # Get today's stats for summary
            stats = await self.get_stats()
            today_pnl = float(stats.get('total_pnl_today', 0))
            win_rate = stats.get('win_rate_today', 0)
            trades_today = stats.get('trades_today', 0)
            
            direction_emoji = "⬆️" if direction == 'UP' else "⬇️"
            winner_str = f"{actual_winner} {'✅' if won else '❌'}"
            outcome_str = f"Won ${pnl:.2f}" if won else f"Lost ${abs(pnl):.2f}"
            
            msg = (
                f"⏱️ LAST MINUTE SCALP\n"
                f"BTC window: ${btc_open:,.0f} → ${btc_close:,.0f} ({winner_str})\n"
                f"Entry: {entry_price*100:.0f}¢ → {outcome_str}\n"
                f"Stake: ${STAKE_USD:.0f} | PnL: ${pnl:+.2f}\n"
                f"Win streak: {self._win_streak} | Today: ${today_pnl:+.2f}"
            )
            
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
                )
            logger.debug(f"📱 Telegram sent for trade {trade['id']}")
        except Exception as e:
            logger.warning(f"⚠️ Telegram report failed: {e}")

    # ------------------------------------------------------------------
    # Main scan loop
    # ------------------------------------------------------------------
    async def scan_and_scalp(self):
        """Main loop — called every 2 seconds."""
        if not self._enabled:
            return
        if self._running:
            return  # prevent concurrent execution
        
        self._running = True
        try:
            from src.strategies.btc_signal_engine import BTCSignalEngine
            engine = BTCSignalEngine(self.db_pool)
            
            # First settle any pending trades
            await self.settle_pending()
            
            # Find active 5M windows
            windows = await engine.find_active_btc_windows()
            five_min_windows = [w for w in windows if w['window_length'] == 5]
            
            for window in five_min_windows:
                window_epoch = window['end_epoch']
                seconds_remaining = window['seconds_remaining']
                
                # Only act in scalp zone: 5 < remaining < 20
                if not (SCALP_WINDOW_MIN < seconds_remaining < SCALP_WINDOW_MAX):
                    continue
                
                # Don't trade same window twice
                if window_epoch in self._traded_windows:
                    continue
                
                # Get BTC open price for this window
                btc_open = await self.get_window_open_price(window_epoch)
                if not btc_open:
                    logger.warning(f"⚠️ No BTC open price for window {window_epoch}")
                    continue
                
                # Get current BTC price
                btc_current = await self.get_binance_price()
                if not btc_current:
                    logger.warning("⚠️ No current BTC price")
                    continue
                
                # Determine winner
                winner_direction = self.determine_winner(btc_open, btc_current)
                if winner_direction is None:
                    logger.info(
                        f"⏭️ Scalp skipped (delta too small): "
                        f"open={btc_open:.0f}, current={btc_current:.0f}, "
                        f"delta={btc_current - btc_open:.0f}"
                    )
                    continue
                
                # Get token price for winning side
                up_price = window.get('up_price', 0.5)
                down_price = window.get('down_price', 0.5)
                entry_price = up_price if winner_direction == 'UP' else down_price
                
                # Only buy if >= 0.85 (near-certain)
                if entry_price < MIN_ENTRY_PRICE:
                    logger.info(
                        f"⏭️ Scalp skipped (price too low): {winner_direction} @ {entry_price:.2f} "
                        f"(need >= {MIN_ENTRY_PRICE})"
                    )
                    continue
                
                # Get oracle price (best-effort)
                oracle_price = await engine.get_oracle_price()
                
                # PAPER TRADE!
                trade_id = await self.paper_trade(
                    direction=winner_direction,
                    entry_price=entry_price,
                    window_epoch=window_epoch,
                    btc_open=btc_open,
                    btc_current=btc_current,
                    seconds_remaining=seconds_remaining,
                    oracle_price=oracle_price,
                    binance_price=btc_current,
                )
                
                if trade_id:
                    self._traded_windows.add(window_epoch)
                    logger.info(
                        f"⏱️ LATE SCALP ENTERED! ID={trade_id} | "
                        f"{winner_direction} @ {entry_price:.2f} | "
                        f"BTC {btc_open:.0f}→{btc_current:.0f} (+{btc_current - btc_open:.0f}) | "
                        f"{seconds_remaining}s remaining"
                    )
                
                # Clean up old epochs from traded_windows (keep last 50)
                if len(self._traded_windows) > 50:
                    sorted_epochs = sorted(self._traded_windows)
                    self._traded_windows = set(sorted_epochs[-50:])

        except Exception as e:
            logger.error(f"❌ scan_and_scalp failed: {e}")
        finally:
            self._running = False

    # ------------------------------------------------------------------
    # Status & data accessors
    # ------------------------------------------------------------------
    async def get_status(self) -> dict:
        """Return current status for API."""
        try:
            now_ts = int(time.time())
            # Next 5M window
            next_5m_epoch = (now_ts // 300 + 1) * 300
            seconds_to_next = next_5m_epoch - now_ts
            seconds_in_scalp_zone = max(0, seconds_to_next - SCALP_WINDOW_MAX)
            
            btc_price = await self.get_binance_price()
            
            # Count pending trades
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM late_window_trades WHERE outcome = 'pending'"
                )
                pending_count = row['cnt'] if row else 0
            
            return {
                'enabled': self._enabled,
                'running': self._running,
                'current_btc_price': btc_price,
                'next_window_epoch': next_5m_epoch,
                'seconds_to_next_window': seconds_to_next,
                'seconds_to_scalp_zone': seconds_in_scalp_zone,
                'in_scalp_zone': seconds_to_next <= SCALP_WINDOW_MAX,
                'pending_trades': pending_count or 0,
                'win_streak': self._win_streak,
                'today_pnl': self._today_pnl,
                'scalp_zone': f"{SCALP_WINDOW_MIN}-{SCALP_WINDOW_MAX}s",
                'min_entry_price': MIN_ENTRY_PRICE,
                'stake_usd': STAKE_USD,
            }
        except Exception as e:
            logger.error(f"❌ get_status failed: {e}")
            return {'enabled': self._enabled, 'error': str(e)}

    async def get_trades(self, limit: int = 50) -> List[dict]:
        """Return recent trades for dashboard."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, window_epoch, window_length, direction,
                           entry_price, exit_price, stake_usd, pnl_usd,
                           btc_open_price, btc_close_price, btc_current_price,
                           seconds_remaining, oracle_price, binance_price,
                           outcome, traded_at, resolved_at
                    FROM late_window_trades
                    ORDER BY traded_at DESC
                    LIMIT $1
                """, limit)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"❌ get_trades failed: {e}")
            return []

    async def get_stats(self) -> dict:
        """Return aggregate stats: win rate, total PnL, avg entry price, trades today."""
        try:
            async with self.db_pool.acquire() as conn:
                # Today's stats
                today_row = await conn.fetchrow("""
                    SELECT trades_total, trades_won, trades_lost, total_pnl
                    FROM late_window_stats
                    WHERE stat_date = CURRENT_DATE
                """)
                
                # All-time stats
                all_time = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
                        SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as lost,
                        SUM(COALESCE(pnl_usd, 0)) as total_pnl,
                        AVG(entry_price) as avg_entry_price,
                        COUNT(CASE WHEN outcome = 'pending' THEN 1 END) as pending
                    FROM late_window_trades
                """)
            
            total = int(all_time['total'] or 0)
            won = int(all_time['won'] or 0)
            lost = int(all_time['lost'] or 0)
            win_rate = (won / total * 100) if total > 0 else 0
            
            today_total = int(today_row['trades_total'] if today_row else 0)
            today_won = int(today_row['trades_won'] if today_row else 0)
            today_pnl = float(today_row['total_pnl'] if today_row else 0)
            today_win_rate = (today_won / today_total * 100) if today_total > 0 else 0
            
            return {
                'total_trades': total,
                'total_won': won,
                'total_lost': lost,
                'win_rate': round(win_rate, 1),
                'total_pnl': round(float(all_time['total_pnl'] or 0), 2),
                'avg_entry_price': round(float(all_time['avg_entry_price'] or 0), 4),
                'pending_trades': int(all_time['pending'] or 0),
                'trades_today': today_total,
                'won_today': today_won,
                'total_pnl_today': round(today_pnl, 2),
                'win_rate_today': round(today_win_rate, 1),
            }
        except Exception as e:
            logger.error(f"❌ get_stats failed: {e}")
            return {
                'total_trades': 0, 'win_rate': 0, 'total_pnl': 0,
                'avg_entry_price': 0, 'trades_today': 0, 'total_pnl_today': 0,
                'win_rate_today': 0,
            }

    def toggle(self) -> bool:
        """Toggle enabled/disabled. Returns new state."""
        self._enabled = not self._enabled
        logger.info(f"⏱️ Late Window Scalper: {'ENABLED' if self._enabled else 'DISABLED'}")
        return self._enabled
