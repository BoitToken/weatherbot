"""
MakerEngine — Spread Quoting & Capture for BTC 5M Polymarket Windows

Strategy:
  - Post limit orders on both sides (Up + Down) around fair_value to earn spread + rebates
  - Default spread: 4¢ (2¢ each side)
  - Skew toward predicted winner as conviction grows
  - In final 30s: tighten on predicted side, widen on loser
  - Toxic flow detection: cancel on sharp BTC price move (>0.5σ in 500ms)

Safety:
  - Max $20 per side per window ($40 total exposure)
  - Never post spread < 2¢ (fees eat it)
  - Max 2 active orders per side
  - Daily maker P&L < -$50 → pause for the day
  - Cancel ALL on any error

ClobClient: signature_type=2 (POLY_PROXY) for proxy wallet.
"""

import asyncio
import httpx
import logging
import math
import os
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CLOB Client factory — lazy init to avoid import-time env reads
# ─────────────────────────────────────────────────────────────────────────────

def _build_clob_client():
    """Build ClobClient for live proxy-wallet trading."""
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds

    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY", "")
    api_key = os.environ.get("CLOB_API_KEY", "")
    api_secret = os.environ.get("CLOB_API_SECRET", "")
    api_passphrase = os.environ.get("CLOB_PASSPHRASE", "")
    proxy_wallet = os.environ.get("PROXY_WALLET", "")
    host = os.environ.get("CLOB_HOST", "https://clob.polymarket.com")

    client = ClobClient(
        host=host,
        chain_id=137,
        key=private_key,
        creds=ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        ),
        signature_type=2,          # POLY_PROXY (proxy wallet)
        funder=proxy_wallet,
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# DB table schema (migrated on ensure_tables())
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_MAKER_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS maker_orders (
    id SERIAL PRIMARY KEY,
    window_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    side TEXT NOT NULL,           -- 'BUY_UP' or 'BUY_DOWN'
    token_id TEXT NOT NULL,
    price NUMERIC(6,4),
    size NUMERIC(10,2),
    status TEXT DEFAULT 'open',   -- open, filled, partial, cancelled, expired
    filled_size NUMERIC(10,2) DEFAULT 0,
    pnl_usd NUMERIC(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_MAKER_ORDERS_IDX = """
CREATE INDEX IF NOT EXISTS idx_maker_orders_window ON maker_orders(window_id);
CREATE INDEX IF NOT EXISTS idx_maker_orders_status ON maker_orders(status);
"""

_CREATE_MAKER_PNL_TABLE = """
CREATE TABLE IF NOT EXISTS maker_daily_pnl (
    date DATE PRIMARY KEY DEFAULT CURRENT_DATE,
    gross_pnl NUMERIC(10,2) DEFAULT 0,
    trades_filled INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""


# ─────────────────────────────────────────────────────────────────────────────
# MakerEngine
# ─────────────────────────────────────────────────────────────────────────────

class MakerEngine:
    """
    Maker-first strategy for BTC 5M Polymarket windows.
    Posts limit orders on both sides (Up + Down) to capture spread.

    Lifecycle per window:
      1. start_quoting()  — open window, post initial resting orders
      2. update_quotes()  — called every 5s; reprices orders
      3. cancel_all_orders() — called on window close or toxic flow
    """

    # Safety limits
    MAX_SIZE_PER_SIDE = 20.0        # $20 max per side
    MAX_DAILY_LOSS = -50.0          # pause if maker P&L < -$50 today
    MIN_SPREAD = 0.02               # never post tighter than 2¢ total half-spread
    DEFAULT_HALF_SPREAD = 0.02      # 2¢ each side (4¢ total)
    MAX_ORDERS_PER_SIDE = 2
    BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

    def __init__(self, db_pool, dry_run: bool = False):
        """
        Args:
            db_pool: asyncpg connection pool
            dry_run: if True, log orders but do NOT hit the CLOB API
        """
        self.db_pool = db_pool
        self.dry_run = dry_run

        # Active window state
        self._window_id: Optional[str] = None
        self._window_epoch: Optional[int] = None
        self._window_length: Optional[int] = None
        self._up_token: Optional[str] = None
        self._down_token: Optional[str] = None
        self._fair_value: float = 0.50
        self._is_quoting: bool = False

        # Order tracking: order_id → {side, price, size, token_id}
        self._active_orders: Dict[str, Dict] = {}

        # BTC price deque for volatility (500ms resolution)
        self._btc_prices: deque = deque(maxlen=240)  # 2 min @ 500ms = 240 samples
        self._last_btc_poll: Optional[float] = None

        # Paused state (reset at midnight)
        self._paused: bool = False
        self._pause_reason: Optional[str] = None

        # Lazy CLOB client
        self._clob = None

    # ─────────────────────────────────────────────────────────────────────
    # DB helpers
    # ─────────────────────────────────────────────────────────────────────

    async def ensure_tables(self):
        """Create DB tables if they don't exist."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(_CREATE_MAKER_ORDERS_TABLE)
            await conn.execute(_CREATE_MAKER_ORDERS_IDX)
            await conn.execute(_CREATE_MAKER_PNL_TABLE)
        logger.info("✅ MakerEngine tables ready")

    async def _record_order(self, window_id: str, order_id: str, side: str,
                             token_id: str, price: float, size: float):
        """Insert a new resting order into maker_orders."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO maker_orders
                        (window_id, order_id, side, token_id, price, size, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'open')
                """, window_id, order_id, side, token_id, price, size)
        except Exception as e:
            logger.error(f"❌ _record_order DB error: {e}")

    async def _update_order_status(self, order_id: str, status: str,
                                    filled_size: float = 0.0, pnl_usd: Optional[float] = None):
        """Update an order's status/fill in DB."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE maker_orders
                    SET status = $1, filled_size = $2, pnl_usd = $3, updated_at = NOW()
                    WHERE order_id = $4
                """, status, filled_size, pnl_usd, order_id)
        except Exception as e:
            logger.error(f"❌ _update_order_status DB error: {e}")

    async def _get_daily_pnl(self) -> float:
        """Return today's maker gross P&L."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT gross_pnl FROM maker_daily_pnl WHERE date = CURRENT_DATE"
                )
                return float(row["gross_pnl"]) if row else 0.0
        except Exception as e:
            logger.error(f"❌ _get_daily_pnl error: {e}")
            return 0.0

    async def _add_daily_pnl(self, amount: float):
        """Accumulate maker P&L for today."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO maker_daily_pnl (date, gross_pnl, trades_filled)
                    VALUES (CURRENT_DATE, $1, 1)
                    ON CONFLICT (date) DO UPDATE SET
                        gross_pnl = maker_daily_pnl.gross_pnl + $1,
                        trades_filled = maker_daily_pnl.trades_filled + 1,
                        updated_at = NOW()
                """, amount)
        except Exception as e:
            logger.error(f"❌ _add_daily_pnl error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # CLOB helpers
    # ─────────────────────────────────────────────────────────────────────

    def _get_clob(self):
        """Lazy-init CLOB client."""
        if self._clob is None:
            self._clob = _build_clob_client()
        return self._clob

    def _post_limit_order(self, token_id: str, price: float, size: float) -> Optional[str]:
        """
        Post a GTC limit buy order.
        Returns order_id string or None on failure.
        """
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        try:
            client = self._get_clob()
            order_args = OrderArgs(
                price=round(price, 4),
                size=round(size, 2),
                side=BUY,
                token_id=token_id,
            )
            signed = client.create_order(order_args)
            result = client.post_order(signed, OrderType.GTC)
            order_id = result.get("orderID") or result.get("order_id") or result.get("id")
            logger.info(f"📋 Order posted: {order_id} | token={token_id[:12]}… | {price:.4f} × ${size:.2f}")
            return order_id
        except Exception as e:
            logger.error(f"❌ _post_limit_order failed: {e}")
            return None

    def _cancel_order(self, order_id: str) -> bool:
        """Cancel a single order by ID. Returns True if successful."""
        try:
            client = self._get_clob()
            client.cancel(order_id=order_id)
            logger.info(f"🗑️  Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ _cancel_order {order_id} failed: {e}")
            return False

    def _cancel_all_clob(self) -> bool:
        """Cancel ALL resting orders for the proxy wallet."""
        try:
            client = self._get_clob()
            client.cancel_all()
            logger.info("🗑️  cancel_all() sent to CLOB")
            return True
        except Exception as e:
            logger.error(f"❌ _cancel_all_clob failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # BTC price feed
    # ─────────────────────────────────────────────────────────────────────

    async def _fetch_btc_price(self) -> Optional[float]:
        """Fetch BTC/USDT price from Binance REST (no auth required)."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self.BINANCE_URL)
                data = resp.json()
                return float(data["price"])
        except Exception as e:
            logger.warning(f"⚠️ BTC price fetch failed: {e}")
            return None

    async def poll_btc_price(self):
        """
        Poll BTC price every 500ms during active quoting.
        Stores in deque; check_toxic_flow() uses the deque.
        """
        while self._is_quoting:
            price = await self._fetch_btc_price()
            if price is not None:
                ts = datetime.now(timezone.utc).timestamp()
                self._btc_prices.append((ts, price))
            await asyncio.sleep(0.5)

    # ─────────────────────────────────────────────────────────────────────
    # Toxic flow detection
    # ─────────────────────────────────────────────────────────────────────

    async def check_toxic_flow(self, btc_price_history: Optional[list] = None) -> bool:
        """
        Detect toxic flow: price moved > 0.5σ in last 500ms.

        Args:
            btc_price_history: optional external list of (timestamp, price) tuples.
                               Falls back to self._btc_prices if None.

        Returns:
            True  → cancel all orders now
            False → safe to continue
        """
        prices_data = btc_price_history if btc_price_history is not None else list(self._btc_prices)

        if len(prices_data) < 10:
            return False  # Not enough data yet

        prices = [p for _, p in prices_data]

        # Trailing 60-second realized volatility
        now_ts = datetime.now(timezone.utc).timestamp()
        prices_60s = [p for ts, p in prices_data if (now_ts - ts) <= 60.0]
        if len(prices_60s) < 5:
            return False

        returns_60s = []
        for i in range(1, len(prices_60s)):
            if prices_60s[i - 1] > 0:
                returns_60s.append((prices_60s[i] - prices_60s[i - 1]) / prices_60s[i - 1])

        if not returns_60s:
            return False

        mean_ret = sum(returns_60s) / len(returns_60s)
        variance = sum((r - mean_ret) ** 2 for r in returns_60s) / len(returns_60s)
        sigma = math.sqrt(variance) if variance > 0 else 1e-10

        # Last 500ms move
        ts_500ms_ago = now_ts - 0.5
        recent = [p for ts, p in prices_data if ts >= ts_500ms_ago]
        if len(recent) < 2:
            return False

        move_pct = abs((recent[-1] - recent[0]) / recent[0]) if recent[0] > 0 else 0

        # Threshold: 0.5σ
        threshold = 0.5 * sigma

        if move_pct > threshold:
            logger.warning(
                f"🚨 TOXIC FLOW detected! Move={move_pct*100:.4f}% > threshold={threshold*100:.4f}% "
                f"(0.5σ) | sigma={sigma*100:.4f}% | cancelling all orders"
            )
            return True

        return False

    # ─────────────────────────────────────────────────────────────────────
    # Safety check
    # ─────────────────────────────────────────────────────────────────────

    async def _check_daily_loss_limit(self) -> bool:
        """Returns True if maker is paused (daily P&L < MAX_DAILY_LOSS)."""
        if self._paused:
            return True
        pnl = await self._get_daily_pnl()
        if pnl < self.MAX_DAILY_LOSS:
            self._paused = True
            self._pause_reason = f"Daily maker P&L ${pnl:.2f} < ${self.MAX_DAILY_LOSS}"
            logger.warning(f"⛔ Maker paused for the day: {self._pause_reason}")
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Core quoting logic
    # ─────────────────────────────────────────────────────────────────────

    def _compute_quotes(
        self,
        fair_value: float,
        half_spread: float,
        size_per_side: float,
        up_token: str,
        down_token: str,
        skew: float = 0.0,
    ) -> List[Dict]:
        """
        Compute bid prices for both Up and Down outcomes.

        fair_value: probability that BTC goes UP (0–1)
        half_spread: half-spread in decimal (e.g. 0.02 for 2¢)
        skew: positive → favor Up side (tighten bid, widen Down)

        Returns list of order dicts: {side, token_id, price, size}
        """
        quotes = []

        # Up outcome bid: market probability of UP
        up_bid = fair_value - half_spread + skew
        up_bid = round(max(0.01, min(0.99, up_bid)), 4)

        # Down outcome bid: market probability of DOWN = (1 - fair_value)
        down_fair = 1.0 - fair_value
        down_bid = down_fair - half_spread - skew
        down_bid = round(max(0.01, min(0.99, down_bid)), 4)

        # Enforce minimum half-spread
        if abs(up_bid - fair_value) < self.MIN_SPREAD / 2:
            up_bid = round(fair_value - self.MIN_SPREAD / 2, 4)
        if abs(down_bid - down_fair) < self.MIN_SPREAD / 2:
            down_bid = round(down_fair - self.MIN_SPREAD / 2, 4)

        quotes.append({
            "side": "BUY_UP",
            "token_id": up_token,
            "price": up_bid,
            "size": round(min(size_per_side, self.MAX_SIZE_PER_SIDE), 2),
        })
        quotes.append({
            "side": "BUY_DOWN",
            "token_id": down_token,
            "price": down_bid,
            "size": round(min(size_per_side, self.MAX_SIZE_PER_SIDE), 2),
        })

        return quotes

    async def start_quoting(
        self,
        window_epoch: int,
        window_length: int,
        fair_value: float,
        up_token: str,
        down_token: str,
        size_per_side: float = 10.0,
        half_spread: float = None,
    ):
        """
        Begin market-making for a new BTC 5M window.

        Posts BUY limit orders on both Up and Down outcomes.
        Starts background BTC price polling for toxic flow detection.

        Args:
            window_epoch:   Unix timestamp of window start (used as window_id base)
            window_length:  Window length in minutes (typically 5)
            fair_value:     Our estimate of Pr(BTC goes UP in this window), 0–1
            up_token:       CLOB token ID for the UP outcome
            down_token:     CLOB token ID for the DOWN outcome
            size_per_side:  USD size per side (capped at MAX_SIZE_PER_SIDE=$20)
            half_spread:    Half-spread in decimal cents (default: DEFAULT_HALF_SPREAD=0.02)
        """
        if await self._check_daily_loss_limit():
            logger.warning("⛔ Maker paused — skipping start_quoting")
            return

        if self._is_quoting:
            logger.warning("⚠️ Already quoting — call cancel_all_orders() before start_quoting()")
            return

        if not up_token or not down_token:
            logger.error("❌ start_quoting: missing token IDs")
            return

        half_spread = half_spread or self.DEFAULT_HALF_SPREAD
        size_per_side = min(size_per_side, self.MAX_SIZE_PER_SIDE)

        window_id = f"btc-updown-{window_length}m-{window_epoch}"
        self._window_id = window_id
        self._window_epoch = window_epoch
        self._window_length = window_length
        self._up_token = up_token
        self._down_token = down_token
        self._fair_value = fair_value
        self._active_orders.clear()
        self._btc_prices.clear()

        logger.info(
            f"📐 start_quoting | window={window_id} | fv={fair_value:.4f} "
            f"| half_spread={half_spread:.4f} | size=${size_per_side:.2f}/side"
        )

        quotes = self._compute_quotes(fair_value, half_spread, size_per_side, up_token, down_token)

        for q in quotes:
            if self.dry_run:
                fake_id = f"dry_{q['side']}_{window_epoch}"
                self._active_orders[fake_id] = q
                logger.info(f"[DRY-RUN] Would post {q['side']}: {q['price']:.4f} × ${q['size']:.2f}")
                await self._record_order(window_id, fake_id, q["side"], q["token_id"], q["price"], q["size"])
            else:
                try:
                    order_id = self._post_limit_order(q["token_id"], q["price"], q["size"])
                    if order_id:
                        self._active_orders[order_id] = q
                        await self._record_order(window_id, order_id, q["side"], q["token_id"], q["price"], q["size"])
                except Exception as e:
                    logger.error(f"❌ Failed to post {q['side']} order: {e}")
                    await self.cancel_all_orders()
                    return

        self._is_quoting = True

        # Start BTC price polling in background
        asyncio.create_task(self.poll_btc_price())

        logger.info(f"✅ Quoting started: {len(self._active_orders)} orders resting")

    async def update_quotes(
        self,
        new_fair_value: float,
        seconds_remaining: int,
        confidence: float = 0.5,
        predicted_side: Optional[str] = None,
    ):
        """
        Reprice orders based on updated fair_value.

        As seconds_remaining → 30: skew toward predicted winner.
        In final 30s: tighten on predicted side, widen on loser.

        Args:
            new_fair_value:   Updated Pr(UP)
            seconds_remaining: Seconds until window closes
            confidence:       Signal confidence 0–1 (from BTC engine)
            predicted_side:   'UP' or 'DOWN' from signal engine (or None)
        """
        if not self._is_quoting:
            return

        if await self._check_daily_loss_limit():
            await self.cancel_all_orders()
            return

        self._fair_value = new_fair_value

        # Compute skew
        skew = 0.0
        half_spread = self.DEFAULT_HALF_SPREAD

        if predicted_side and confidence > 0.6:
            # Skew: tighten toward predicted winner (better bid → more likely to get filled)
            conviction = (confidence - 0.6) / 0.4  # 0 → 1 as confidence goes 60% → 100%
            max_skew = 0.01  # 1¢ max skew
            raw_skew = conviction * max_skew

            if predicted_side == "UP":
                skew = raw_skew     # tighten Up bid, widen Down bid
            else:
                skew = -raw_skew    # tighten Down bid, widen Up bid

        if seconds_remaining <= 30:
            # Final 30s: aggressive skew toward predicted side, widen loser
            if predicted_side == "UP":
                half_spread_up = max(self.MIN_SPREAD / 2, self.DEFAULT_HALF_SPREAD / 2)
                half_spread_down = self.DEFAULT_HALF_SPREAD * 2
            elif predicted_side == "DOWN":
                half_spread_up = self.DEFAULT_HALF_SPREAD * 2
                half_spread_down = max(self.MIN_SPREAD / 2, self.DEFAULT_HALF_SPREAD / 2)
            else:
                # No conviction — widen both to reduce fill risk near close
                half_spread_up = half_spread_down = self.DEFAULT_HALF_SPREAD * 1.5
        else:
            half_spread_up = half_spread_down = half_spread

        up_token = self._up_token or ""
        down_token = self._down_token or ""
        if not up_token or not down_token:
            return

        # Cancel existing orders first, then repost
        await self.cancel_all_orders(expire_window=False)
        self._is_quoting = True  # re-enable after cancel_all_orders clears it

        size = self.MAX_SIZE_PER_SIDE

        new_quotes = [
            {
                "side": "BUY_UP",
                "token_id": up_token,
                "price": round(max(0.01, min(0.99, new_fair_value - half_spread_up + skew)), 4),
                "size": round(size, 2),
            },
            {
                "side": "BUY_DOWN",
                "token_id": down_token,
                "price": round(max(0.01, min(0.99, (1.0 - new_fair_value) - half_spread_down - skew)), 4),
                "size": round(size, 2),
            },
        ]

        for q in new_quotes:
            if self.dry_run:
                fake_id = f"dry_{q['side']}_{self._window_epoch}_{seconds_remaining}"
                self._active_orders[fake_id] = q
                logger.info(f"[DRY-RUN] Reposted {q['side']}: {q['price']:.4f} × ${q['size']:.2f}")
                await self._record_order(self._window_id, fake_id, q["side"], q["token_id"], q["price"], q["size"])
            else:
                try:
                    order_id = self._post_limit_order(q["token_id"], q["price"], q["size"])
                    if order_id:
                        self._active_orders[order_id] = q
                        await self._record_order(self._window_id, order_id, q["side"], q["token_id"], q["price"], q["size"])
                except Exception as e:
                    logger.error(f"❌ update_quotes failed posting {q['side']}: {e}")
                    await self.cancel_all_orders()
                    return

        logger.info(
            f"🔄 Quotes updated | fv={new_fair_value:.4f} | skew={skew:.4f} "
            f"| {seconds_remaining}s remaining | {len(self._active_orders)} orders"
        )

    async def cancel_all_orders(self, expire_window: bool = True):
        """
        Cancel all resting orders for the current window.

        Called on:
          - Window close (expire_window=True)
          - Toxic flow detected (expire_window=False — window stays active)
          - Any error

        Uses cancel_all() for efficiency; falls back to per-order cancels.
        """
        if not self._active_orders and not self._is_quoting:
            return

        order_ids = list(self._active_orders.keys())
        logger.info(f"🗑️  cancel_all_orders | {len(order_ids)} orders | expire_window={expire_window}")

        cancelled_count = 0
        if not self.dry_run:
            # Try bulk cancel first
            bulk_ok = self._cancel_all_clob()
            if bulk_ok:
                cancelled_count = len(order_ids)
            else:
                # Fall back to individual cancels
                for oid in order_ids:
                    if self._cancel_order(oid):
                        cancelled_count += 1

        # Update DB
        final_status = "expired" if expire_window else "cancelled"
        for oid in order_ids:
            await self._update_order_status(oid, final_status)

        self._active_orders.clear()
        self._is_quoting = False

        if expire_window:
            self._window_id = None
            self._window_epoch = None
            self._window_length = None
            self._up_token = None
            self._down_token = None
            logger.info(f"✅ Window closed: {cancelled_count} orders cancelled/expired")
        else:
            logger.info(f"✅ Orders cancelled (toxic flow): {cancelled_count} orders cleared")

    # ─────────────────────────────────────────────────────────────────────
    # Fill processing
    # ─────────────────────────────────────────────────────────────────────

    async def on_fill(self, order_id: str, filled_size: float, fill_price: float):
        """
        Called when a maker order is (partially) filled.

        P&L = size × (1 - fill_price) - fees
        Maker rebate: Polymarket pays ~0.1% on each filled maker order.

        Args:
            order_id:    The filled order's ID
            filled_size: USD amount filled
            fill_price:  Price at which filled
        """
        order = self._active_orders.get(order_id)
        if not order:
            logger.warning(f"⚠️ on_fill: unknown order {order_id}")
            return

        # P&L: we bought at fill_price, outcome resolves at 0 or 1
        # Expected value at fill = 0.5 (we hold both sides, so E[resolution] ≈ fair_value)
        # Immediate spread captured = (ask - fill_price) × filled_size if matched by taker
        # Conservative: credit is (DEFAULT_HALF_SPREAD × 2) × filled_size
        spread_earned = self.DEFAULT_HALF_SPREAD * 2 * filled_size
        maker_rebate = 0.001 * filled_size   # ~0.1% Polymarket maker rebate
        fee = 0.002 * filled_size            # 0.2% taker fee on the other side (hedge)
        pnl_estimate = spread_earned + maker_rebate - fee

        logger.info(
            f"💰 FILL: {order['side']} | {filled_size:.2f} @ {fill_price:.4f} "
            f"| est. P&L: ${pnl_estimate:.4f}"
        )

        # Determine fill status
        original_size = order.get("size", filled_size)
        status = "filled" if filled_size >= original_size * 0.99 else "partial"

        await self._update_order_status(order_id, status, filled_size=filled_size, pnl_usd=pnl_estimate)
        await self._add_daily_pnl(pnl_estimate)

        # Remove from active if fully filled
        if status == "filled":
            del self._active_orders[order_id]

    # ─────────────────────────────────────────────────────────────────────
    # Status helpers
    # ─────────────────────────────────────────────────────────────────────

    @property
    def is_quoting(self) -> bool:
        return self._is_quoting

    @property
    def is_paused(self) -> bool:
        return self._paused

    async def get_status(self) -> Dict:
        """Return current engine status for logging/dashboard."""
        daily_pnl = await self._get_daily_pnl()
        return {
            "is_quoting": self._is_quoting,
            "is_paused": self._paused,
            "pause_reason": self._pause_reason,
            "window_id": self._window_id,
            "fair_value": self._fair_value,
            "active_orders": len(self._active_orders),
            "daily_pnl_usd": daily_pnl,
            "btc_price_samples": len(self._btc_prices),
            "dry_run": self.dry_run,
        }
