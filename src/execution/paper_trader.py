"""
Paper Trader for WeatherBot — Sports Edition.
Auto-executes qualifying paper trades based on INTELLIGENCE.md criteria.

Schema (trades table):
  id SERIAL, signal_id INT, market_id TEXT, market_title TEXT, side TEXT,
  entry_price NUMERIC, shares NUMERIC, size_usd NUMERIC, edge_at_entry NUMERIC,
  status TEXT, exit_price NUMERIC, pnl_usd NUMERIC, pnl_pct NUMERIC,
  resolved_at TIMESTAMP, entry_at TIMESTAMP, metadata JSONB, strategy VARCHAR
"""
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PaperTrader:
    """Executes paper trades against the trades table using psycopg2 async wrapper."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        # Counters for status endpoint (reset daily via external caller or on first use)
        self.trades_placed_today = 0
        self.signals_evaluated_today = 0
        self.skipped_reasons: list = []  # list of {"market_id": ..., "reason": ...}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def create_trade(
        self,
        market_id: str,
        market_title: str,
        side: str,
        entry_price: float,
        size_usd: float,
        edge_pct: float,
        strategy: str = "cross_odds",
        signal_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        INSERT a new paper trade. Returns the new trade id, or None on failure.
        entry_price should be the Polymarket probability (0-1 range stored as-is).
        shares = size_usd / entry_price (how many shares we get).
        """
        shares = round(size_usd / entry_price, 4) if entry_price > 0 else 0

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO trades (
                        signal_id, market_id, market_title, side,
                        entry_price, shares, size_usd, edge_at_entry,
                        status, entry_at, metadata, strategy
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW(),$10,$11)
                    RETURNING id
                    """,
                    signal_id,
                    market_id,
                    market_title,
                    side,
                    entry_price,
                    shares,
                    size_usd,
                    edge_pct,
                    "paper_open",
                    metadata or {},
                    strategy,
                )
                trade_id = row["id"] if row else None
                logger.info(
                    f"✅ Paper trade #{trade_id}: {side} {market_title[:60]} "
                    f"@ {entry_price:.4f} ${size_usd} edge={edge_pct:.1f}%"
                )
                self.trades_placed_today += 1
                return trade_id
        except Exception as e:
            logger.error(f"❌ Failed to create paper trade: {e}")
            return None

    async def check_duplicate(self, market_id: str) -> bool:
        """Return True if an open trade already exists for this market_id."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM trades WHERE market_id = $1 AND status = 'paper_open' LIMIT 1",
                    market_id,
                )
                return row is not None
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False  # fail-open: allow trade if check errors

    async def get_open_count(self) -> int:
        """Count currently open paper positions."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM trades WHERE status = 'paper_open'"
                )
                return int(row["cnt"]) if row else 0
        except Exception as e:
            logger.error(f"Open count query failed: {e}")
            return 0

    async def get_daily_pnl(self) -> float:
        """Sum today's realized P&L (resolved trades only)."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(pnl_usd), 0) AS total
                    FROM trades
                    WHERE resolved_at::date = CURRENT_DATE
                      AND status IN ('paper_won', 'paper_lost', 'settled_win', 'settled_loss')
                    """
                )
                return float(row["total"]) if row else 0.0
        except Exception as e:
            logger.error(f"Daily P&L query failed: {e}")
            return 0.0

    async def get_today_stats(self) -> Dict[str, Any]:
        """Quick summary for status endpoint."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE entry_at::date = CURRENT_DATE) AS placed_today,
                        COUNT(*) FILTER (WHERE status = 'paper_open') AS open_positions,
                        COALESCE(SUM(pnl_usd) FILTER (
                            WHERE resolved_at::date = CURRENT_DATE
                              AND status IN ('paper_won','paper_lost','settled_win','settled_loss')
                        ), 0) AS daily_pnl
                    FROM trades
                    """
                )
                return {
                    "trades_placed_today": int(row["placed_today"]) if row else 0,
                    "open_positions": int(row["open_positions"]) if row else 0,
                    "daily_pnl_usd": float(row["daily_pnl"]) if row else 0.0,
                }
        except Exception as e:
            logger.error(f"Today stats query failed: {e}")
            return {"trades_placed_today": 0, "open_positions": 0, "daily_pnl_usd": 0.0}
