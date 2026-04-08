"""
Orderbook Depth Checker — Polymarket CLOB API.
Checks orderbook depth before trade execution.
Paper mode: best-effort (don't block on failures).
Live mode: depth check MANDATORY (enforced by caller).
"""
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class OrderbookChecker:
    """Check Polymarket CLOB orderbook depth before executing trades."""

    CLOB_BASE = "https://clob.polymarket.com"
    GAMMA_BASE = "https://gamma-api.polymarket.com"
    TIMEOUT = 10  # seconds

    # ------------------------------------------------------------------ #
    # Low-level API helpers
    # ------------------------------------------------------------------ #

    async def get_orderbook(self, token_id: str) -> Dict:
        """
        GET {CLOB_BASE}/book?token_id={token_id}
        Returns raw bids/asks with price levels and sizes.
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.get(
                    f"{self.CLOB_BASE}/book",
                    params={"token_id": token_id},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Orderbook fetch failed for {token_id}: {e}")
            return {}

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """
        GET {CLOB_BASE}/midpoint?token_id={token_id}
        Returns current midpoint price.
        """
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.get(
                    f"{self.CLOB_BASE}/midpoint",
                    params={"token_id": token_id},
                )
                resp.raise_for_status()
                data = resp.json()
                return float(data.get("mid", 0)) if data else None
        except Exception as e:
            logger.warning(f"Midpoint fetch failed for {token_id}: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Token-id resolution (best-effort for paper mode)
    # ------------------------------------------------------------------ #

    async def _resolve_token_id(
        self, market_id: str, db_pool=None
    ) -> Optional[str]:
        """
        Try to resolve a Polymarket token_id for a given market_id.
        1. Check sports_markets.metadata JSONB for stored token ids.
        2. Fallback: query Gamma API by slug/condition_id.
        3. If all fail, return None.
        """
        # Attempt 1: DB metadata lookup
        if db_pool is not None:
            try:
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT metadata FROM sports_markets WHERE market_id = $1 LIMIT 1",
                        market_id,
                    )
                    if row and row.get("metadata"):
                        meta = row["metadata"]
                        if isinstance(meta, dict):
                            # Check common keys
                            for key in ("clob_token_ids", "clobTokenIds", "token_id", "tokens"):
                                val = meta.get(key)
                                if val:
                                    if isinstance(val, list) and val:
                                        return str(val[0].get("token_id", val[0])) if isinstance(val[0], dict) else str(val[0])
                                    elif isinstance(val, str):
                                        return val
            except Exception as e:
                logger.debug(f"DB token_id lookup failed for {market_id}: {e}")

        # Attempt 2: Gamma API by condition_id / slug
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
                    clob_ids = m.get("clobTokenIds")
                    if clob_ids:
                        try:
                            import json
                            ids = json.loads(clob_ids) if isinstance(clob_ids, str) else clob_ids
                            if ids and isinstance(ids, list):
                                return str(ids[0])
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Gamma token_id lookup failed for {market_id}: {e}")

        return None

    # ------------------------------------------------------------------ #
    # Main depth check
    # ------------------------------------------------------------------ #

    async def check_depth(
        self,
        token_id: Optional[str],
        side: str,
        size_usd: float,
        market_id: Optional[str] = None,
        db_pool=None,
    ) -> Dict:
        """
        Check if orderbook has enough depth to fill our order.

        Parameters
        ----------
        token_id : str or None
            CLOB token id. If None, will attempt resolution via market_id.
        side : str
            'BUY' or 'SELL' (maps to asks or bids).
        size_usd : float
            Desired trade size in USD.
        market_id : str, optional
            Used for token_id resolution if token_id is None.
        db_pool : optional
            Async DB pool for metadata lookup.

        Returns
        -------
        dict with keys:
            has_depth       : bool or None (None = unknown/couldn't check)
            depth_checked   : bool
            available_depth_usd : float
            best_price      : float or None
            slippage_pct    : float
            recommended_size: float
        """
        # Resolve token_id if needed
        if not token_id and market_id:
            token_id = await self._resolve_token_id(market_id, db_pool)

        if not token_id:
            logger.info(f"No token_id for market {market_id} — depth unknown")
            return {
                "has_depth": None,
                "depth_checked": False,
                "available_depth_usd": 0,
                "best_price": None,
                "slippage_pct": 0,
                "recommended_size": size_usd,
            }

        try:
            book = await self.get_orderbook(token_id)
            if not book:
                return {
                    "has_depth": None,
                    "depth_checked": False,
                    "available_depth_usd": 0,
                    "best_price": None,
                    "slippage_pct": 0,
                    "recommended_size": size_usd,
                }

            # BUY → we consume asks (we pay ask prices)
            # SELL → we consume bids (we receive bid prices)
            levels = book.get("asks", []) if side.upper() == "BUY" else book.get("bids", [])

            if not levels:
                return {
                    "has_depth": False,
                    "depth_checked": True,
                    "available_depth_usd": 0,
                    "best_price": None,
                    "slippage_pct": 100,
                    "recommended_size": 0,
                }

            # Calculate cumulative depth
            total_depth_usd = 0.0
            best_price = None
            weighted_price_sum = 0.0
            for level in levels:
                price = float(level.get("price", level.get("p", 0)))
                # Size may be in shares; approximate USD = shares * price
                size = float(level.get("size", level.get("s", 0)))
                level_usd = size * price if price > 0 else size
                if best_price is None:
                    best_price = price
                total_depth_usd += level_usd
                weighted_price_sum += price * level_usd

            # Slippage: difference between best price and volume-weighted average
            if total_depth_usd > 0 and best_price and best_price > 0:
                vwap = weighted_price_sum / total_depth_usd
                slippage_pct = abs(vwap - best_price) / best_price * 100
            else:
                slippage_pct = 0

            has_depth = total_depth_usd >= (2 * size_usd)
            recommended_size = size_usd if has_depth else min(size_usd, total_depth_usd * 0.5)

            return {
                "has_depth": has_depth,
                "depth_checked": True,
                "available_depth_usd": round(total_depth_usd, 2),
                "best_price": best_price,
                "slippage_pct": round(slippage_pct, 4),
                "recommended_size": round(recommended_size, 2),
            }

        except Exception as e:
            logger.warning(f"Depth check failed for token {token_id}: {e}")
            return {
                "has_depth": None,
                "depth_checked": False,
                "available_depth_usd": 0,
                "best_price": None,
                "slippage_pct": 0,
                "recommended_size": size_usd,
            }
