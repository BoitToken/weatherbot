"""
Edge Monitor — watches open positions for edge decay.
Runs every 5 minutes via scheduler.
Paper mode: informational alerts only.
Live mode (future): will auto-trigger exits.
"""
import logging
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class EdgeMonitor:
    """Monitor open positions for edge decay."""

    GAMMA_BASE = "https://gamma-api.polymarket.com"
    TIMEOUT = 10

    def __init__(self, db_pool):
        self.db_pool = db_pool

    # ------------------------------------------------------------------ #
    # Core: check all open positions
    # ------------------------------------------------------------------ #

    async def check_all_positions(self) -> List[Dict]:
        """
        For each open trade:
        1. Get current Polymarket price (from sports_markets table or Gamma API)
        2. Get current sportsbook consensus (from sportsbook_odds table)
        3. Calculate current edge vs entry edge
        4. If current edge < 2%: flag for exit
        5. If current edge < 0% (underwater): urgent exit flag

        Returns list of position health dicts.
        """
        positions = await self._get_open_positions()
        if not positions:
            return []

        results = []
        for pos in positions:
            try:
                health = await self._evaluate_position(pos)
                results.append(health)
            except Exception as e:
                logger.error(f"Edge check failed for trade #{pos.get('id')}: {e}")
                results.append({
                    "trade_id": pos.get("id"),
                    "market_id": pos.get("market_id"),
                    "market_title": pos.get("market_title", "")[:80],
                    "side": pos.get("side"),
                    "entry_price": float(pos.get("entry_price", 0)),
                    "entry_edge": float(pos.get("edge_at_entry", 0)),
                    "current_price": None,
                    "current_edge": None,
                    "edge_change": None,
                    "recommendation": "CHECK_FAILED",
                    "reason": str(e),
                })

        return results

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_open_positions(self) -> List[Dict]:
        """Fetch all open paper trades."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, market_id, market_title, side, entry_price,
                           edge_at_entry, size_usd, shares, strategy, metadata, entry_at
                    FROM trades
                    WHERE status IN ('paper_open', 'open', 'live_open')
                    ORDER BY entry_at DESC
                    """
                )
                return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Failed to fetch open positions: {e}")
            return []

    async def _evaluate_position(self, pos: Dict) -> Dict:
        """Evaluate a single position's current edge."""
        market_id = pos.get("market_id", "")
        side = pos.get("side", "BUY")
        entry_price = float(pos.get("entry_price", 0))
        entry_edge = float(pos.get("edge_at_entry", 0))
        market_title = pos.get("market_title", "")[:80]

        # 1. Get current Polymarket price
        current_pm_price = await self._get_current_pm_price(market_id)

        # 2. Get current sportsbook consensus
        current_fair_value = await self._get_sportsbook_consensus(market_id, market_title)

        # 3. Calculate current edge
        current_edge = None
        if current_pm_price is not None and current_fair_value is not None:
            if side.upper() in ("BUY", "YES"):
                # We bought YES — edge = fair_value - pm_price
                current_edge = (current_fair_value - current_pm_price) * 100
            else:
                # We sold / bought NO — edge = pm_price - fair_value
                current_edge = (current_pm_price - current_fair_value) * 100
        elif current_pm_price is not None and entry_edge > 0:
            # No sportsbook data; estimate edge from price movement
            if side.upper() in ("BUY", "YES"):
                price_moved = current_pm_price - entry_price
                current_edge = entry_edge - (price_moved * 100)
            else:
                price_moved = entry_price - current_pm_price
                current_edge = entry_edge - (price_moved * 100)

        # 4. Determine recommendation
        recommendation = "HOLD"
        reason = ""
        if current_edge is not None:
            edge_change = current_edge - entry_edge
            if current_edge < 0:
                recommendation = "EXIT_URGENT"
                reason = f"Edge underwater at {current_edge:.1f}%"
            elif current_edge < 2:
                recommendation = "EXIT_EDGE_DECAY"
                reason = f"Edge decayed to {current_edge:.1f}% (was {entry_edge:.1f}%)"
            elif current_edge < 4:
                recommendation = "WATCH"
                reason = f"Edge thinning: {current_edge:.1f}%"
        else:
            edge_change = None
            reason = "Could not determine current edge"

        return {
            "trade_id": pos.get("id"),
            "market_id": market_id,
            "market_title": market_title,
            "side": side,
            "strategy": pos.get("strategy", ""),
            "size_usd": float(pos.get("size_usd", 0)),
            "entry_price": entry_price,
            "entry_edge": entry_edge,
            "current_price": current_pm_price,
            "current_fair_value": current_fair_value,
            "current_edge": round(current_edge, 2) if current_edge is not None else None,
            "edge_change": round(edge_change, 2) if edge_change is not None else None,
            "recommendation": recommendation,
            "reason": reason,
        }

    async def _get_current_pm_price(self, market_id: str) -> Optional[float]:
        """
        Get current Polymarket price for a market.
        1. Try sports_markets table (refreshed every 3 min by scanner).
        2. Fallback: Gamma API.
        """
        # DB first
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT yes_price FROM sports_markets WHERE market_id = $1 LIMIT 1",
                    market_id,
                )
                if row and row.get("yes_price") is not None:
                    return float(row["yes_price"])
        except Exception as e:
            logger.debug(f"DB price lookup failed for {market_id}: {e}")

        # Gamma API fallback
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.get(
                    f"{self.GAMMA_BASE}/markets",
                    params={"id": market_id},
                )
                resp.raise_for_status()
                data = resp.json()
                markets = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                for m in markets:
                    prices_str = m.get("outcomePrices", "")
                    if prices_str:
                        import json
                        try:
                            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                            if prices and len(prices) > 0:
                                return float(prices[0])
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Gamma price lookup failed for {market_id}: {e}")

        return None

    async def _get_sportsbook_consensus(
        self, market_id: str, market_title: str
    ) -> Optional[float]:
        """
        Get sportsbook consensus (average implied probability) for a market.
        Matches by polymarket_id or fuzzy title match.
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Try exact polymarket_id match first
                rows = await conn.fetch(
                    """
                    SELECT implied_probability
                    FROM sportsbook_odds
                    WHERE polymarket_id = $1
                      AND implied_probability IS NOT NULL
                    ORDER BY fetched_at DESC
                    LIMIT 10
                    """,
                    market_id,
                )

                if not rows:
                    # Fuzzy match: extract key words from market_title
                    # e.g. "Will Lakers win vs Celtics?" → search for 'Lakers'
                    words = [
                        w for w in market_title.replace("?", "").split()
                        if len(w) > 3 and w.lower() not in (
                            "will", "the", "win", "game", "match", "over", "under",
                            "series", "their", "this", "next", "does",
                        )
                    ]
                    if words:
                        search_term = words[0]  # first meaningful word
                        rows = await conn.fetch(
                            """
                            SELECT implied_probability
                            FROM sportsbook_odds
                            WHERE outcome ILIKE $1
                              AND implied_probability IS NOT NULL
                              AND fetched_at > NOW() - INTERVAL '6 hours'
                            ORDER BY fetched_at DESC
                            LIMIT 10
                            """,
                            f"%{search_term}%",
                        )

                if rows:
                    probs = [float(r["implied_probability"]) for r in rows if r.get("implied_probability")]
                    if probs:
                        return sum(probs) / len(probs)

        except Exception as e:
            logger.debug(f"Sportsbook consensus lookup failed for {market_id}: {e}")

        return None

    # ------------------------------------------------------------------ #
    # Public convenience
    # ------------------------------------------------------------------ #

    async def get_current_edge(self, market_id: str) -> Optional[float]:
        """Get current edge for a market by comparing PM price to sportsbook odds."""
        pm_price = await self._get_current_pm_price(market_id)
        fair_value = await self._get_sportsbook_consensus(market_id, "")
        if pm_price is not None and fair_value is not None:
            return round((fair_value - pm_price) * 100, 2)
        return None
