"""
Polymarket LIVE Execution Client for BTC 5M Bot.
REAL MONEY — conservative safety checks enforced.

Safety constraints:
  - Max $25 per trade
  - Min 5/7 factors must agree
  - Entry price < 50¢ only
  - Balance checks before every trade
  - All trades recorded in live_trades table
  - Green-themed 🟢 LIVE TRADE alerts to Telegram
"""
import asyncio
import json
import logging
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — do NOT increase without CEO approval
# ═══════════════════════════════════════════════════════════════
MAX_STAKE_USD = 25.0        # Hard cap per trade
MIN_FACTORS = 5             # Minimum factor agreement (out of 7)
MAX_ENTRY_PRICE = 0.50      # Entry must be below 50¢
MIN_BALANCE_USD = 5.0       # Don't trade if wallet balance < $5
MAX_OPEN_TRADES = 5         # Max concurrent live positions
MAX_DAILY_LOSS_USD = 50.0   # Daily loss circuit breaker


class PolymarketLiveTrader:
    """
    Live execution client for Polymarket CLOB.
    Places real orders using py-clob-client.
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._client = None
        self._initialized = False
        self._last_balance_check = 0
        self._cached_balance = None

        # Load config from env
        from dotenv import load_dotenv
        load_dotenv(override=True)

        self.clob_api_key = os.getenv("CLOB_API_KEY", "")
        self.clob_api_secret = os.getenv("CLOB_API_SECRET", "")
        self.clob_passphrase = os.getenv("CLOB_PASSPHRASE", "")
        self.clob_host = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
        self.wallet_address = os.getenv("WALLET_ADDRESS", "")
        self.rpc_url = os.getenv("POLYGON_RPC_HTTP", "")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_client(self) -> bool:
        """Initialize the CLOB client. Returns True if successful."""
        if self._initialized and self._client:
            return True

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds

            # Get private key for order signing
            private_key = self._get_private_key()

            creds = ApiCreds(
                api_key=self.clob_api_key,
                api_secret=self.clob_api_secret,
                api_passphrase=self.clob_passphrase,
            )

            if private_key:
                # Full L2 client — can sign and post orders
                self._client = ClobClient(
                    host=self.clob_host,
                    chain_id=137,
                    key=private_key,
                    creds=creds,
                )
                self._has_private_key = True
                logger.info(f"✅ CLOB client initialized (L2) — wallet: {self.wallet_address}")
            else:
                # L0 client — can read market data but not sign orders
                self._client = ClobClient(
                    host=self.clob_host,
                    chain_id=137,
                    creds=creds,
                )
                self._has_private_key = False
                logger.warning("⚠️ CLOB client initialized WITHOUT private key — orders will fail")
                logger.warning("   Set POLYMARKET_PRIVATE_KEY in .env to enable live trading")

            # Verify connectivity
            ok = self._client.get_ok()
            if ok != "OK":
                logger.error(f"❌ CLOB server check failed: {ok}")
                return False

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"❌ CLOB client init failed: {e}\n{traceback.format_exc()}")
            return False

    def _get_private_key(self) -> Optional[str]:
        """Get wallet private key from vault or env."""
        try:
            from src.vault import get_polymarket_private_key
            pk = get_polymarket_private_key()
            if pk:
                logger.info("🔐 Private key loaded from vault")
                return pk
        except Exception as e:
            logger.warning(f"Vault load failed: {e}")

        pk = os.getenv("POLYMARKET_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
        if pk:
            logger.info("🔐 Private key loaded from environment")
        return pk

    # ------------------------------------------------------------------
    # Balance & Safety Checks
    # ------------------------------------------------------------------

    async def get_usdc_balance(self) -> Optional[float]:
        """Get USDC balance on Polygon for the trading wallet."""
        now = time.time()
        # Cache for 30 seconds
        if self._cached_balance is not None and (now - self._last_balance_check) < 30:
            return self._cached_balance

        try:
            from web3 import Web3

            w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not w3.is_connected():
                logger.error("❌ Cannot connect to Polygon RPC")
                return None

            # USDC on Polygon (PoS) — 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174 (USDC.e)
            # Also check 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359 (native USDC)
            USDC_CONTRACTS = [
                "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC.e (bridged)
                "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",  # Native USDC
            ]
            ERC20_ABI = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function",
                },
            ]

            total_balance = 0.0
            wallet = Web3.to_checksum_address(self.wallet_address)

            for contract_addr in USDC_CONTRACTS:
                try:
                    contract = w3.eth.contract(
                        address=Web3.to_checksum_address(contract_addr),
                        abi=ERC20_ABI,
                    )
                    decimals = contract.functions.decimals().call()
                    raw_balance = contract.functions.balanceOf(wallet).call()
                    balance = raw_balance / (10 ** decimals)
                    if balance > 0:
                        logger.info(f"💰 USDC balance ({contract_addr[:10]}...): ${balance:.4f}")
                    total_balance += balance
                except Exception as e:
                    logger.debug(f"Balance check failed for {contract_addr[:10]}...: {e}")

            # Also check Polymarket CTF allowance if client is initialized
            if self._client and self._initialized:
                try:
                    ba = self._client.get_balance_allowance()
                    if ba:
                        logger.info(f"📊 CLOB balance/allowance: {ba}")
                except Exception:
                    pass

            self._cached_balance = total_balance
            self._last_balance_check = now
            return total_balance

        except Exception as e:
            logger.error(f"❌ Balance check failed: {e}")
            return None

    async def _check_daily_loss(self) -> float:
        """Check today's realized loss from live_trades table."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(pnl_usd), 0) as daily_pnl
                    FROM live_trades
                    WHERE created_at::date = CURRENT_DATE
                      AND status IN ('resolved_win', 'resolved_loss')
                """)
                return float(row["daily_pnl"]) if row else 0.0
        except Exception as e:
            logger.error(f"Daily loss check failed: {e}")
            return 0.0

    async def _get_open_trade_count(self) -> int:
        """Count open live trades."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM live_trades WHERE status = 'open'"
                )
                return int(row["cnt"]) if row else 0
        except Exception as e:
            logger.error(f"Open trade count failed: {e}")
            return 999  # Fail safe — prevent new trades

    async def _check_duplicate(self, window_id: str) -> bool:
        """Check if we already have an open trade for this window."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM live_trades WHERE window_id = $1 AND status = 'open'",
                    window_id,
                )
                return row is not None
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return True  # Fail safe

    # ------------------------------------------------------------------
    # Order Execution
    # ------------------------------------------------------------------

    async def execute_live_trade(
        self,
        window_id: str,
        prediction: str,  # 'UP' or 'DOWN'
        token_id: str,    # Polymarket token ID for the outcome
        entry_price: float,
        stake_usd: float,
        factors_agreeing: int,
        signal_metadata: Optional[Dict] = None,
    ) -> Optional[int]:
        """
        Execute a LIVE trade on Polymarket.

        Returns: trade_id from live_trades table, or None if failed/blocked.
        """
        # ═══════════════════════════════════════════════════════════
        # SAFETY GATE — every check must pass
        # ═══════════════════════════════════════════════════════════

        # 1. Stake cap
        if stake_usd > MAX_STAKE_USD:
            logger.warning(f"🛑 Stake ${stake_usd} exceeds max ${MAX_STAKE_USD} — capping")
            stake_usd = MAX_STAKE_USD

        # 2. Factor agreement
        if factors_agreeing < MIN_FACTORS:
            logger.warning(f"🛑 Only {factors_agreeing}/7 factors — need {MIN_FACTORS}. Skipping.")
            return None

        # 3. Entry price
        if entry_price >= MAX_ENTRY_PRICE:
            logger.warning(f"🛑 Entry {entry_price*100:.1f}¢ >= {MAX_ENTRY_PRICE*100:.0f}¢ cap. Skipping.")
            return None
        if entry_price <= 0.01:
            logger.warning(f"🛑 Entry {entry_price*100:.1f}¢ too low — suspicious. Skipping.")
            return None

        # 4. Duplicate check
        if await self._check_duplicate(window_id):
            logger.info(f"⏭️ Already have open trade for {window_id}")
            return None

        # 5. Open trade limit
        open_count = await self._get_open_trade_count()
        if open_count >= MAX_OPEN_TRADES:
            logger.warning(f"🛑 {open_count} open trades — max {MAX_OPEN_TRADES}. Skipping.")
            return None

        # 6. Daily loss circuit breaker
        daily_pnl = await self._check_daily_loss()
        if daily_pnl <= -MAX_DAILY_LOSS_USD:
            logger.warning(f"🛑 Daily loss ${daily_pnl:.2f} hit circuit breaker (${MAX_DAILY_LOSS_USD}). HALTED.")
            return None

        # 7. Balance check
        balance = await self.get_usdc_balance()
        if balance is None:
            logger.error("🛑 Cannot verify balance — skipping trade")
            return None
        if balance < MIN_BALANCE_USD:
            logger.warning(f"🛑 Balance ${balance:.2f} < ${MIN_BALANCE_USD} minimum. Skipping.")
            return None
        if stake_usd > balance * 0.8:  # Don't use more than 80% of balance
            logger.warning(f"🛑 Stake ${stake_usd} > 80% of balance ${balance:.2f}. Capping.")
            stake_usd = min(stake_usd, balance * 0.5)  # Use max 50% if balance is low

        # ═══════════════════════════════════════════════════════════
        # EXECUTE ORDER
        # ═══════════════════════════════════════════════════════════

        if not self._init_client():
            logger.error("🛑 CLOB client not initialized — cannot trade")
            return None

        if not self._has_private_key:
            logger.error("🛑 No private key — cannot sign orders. Set POLYMARKET_PRIVATE_KEY in .env")
            await self._send_trade_alert(
                prediction=prediction,
                entry_price=entry_price,
                stake_usd=stake_usd,
                factors=factors_agreeing,
                status="FAILED",
                error="No private key. Set POLYMARKET_PRIVATE_KEY in .env to enable live trading.",
                balance=balance,
            )
            return None

        tx_hash = None
        order_id = None
        balance_before = balance

        try:
            from py_clob_client.order_builder.constants import BUY
            from py_clob_client.clob_types import OrderArgs, OrderType

            # Calculate shares
            shares = stake_usd / entry_price

            order_args = OrderArgs(
                price=round(entry_price, 2),
                size=round(shares, 2),
                side=BUY,
                token_id=token_id,
            )

            logger.info(
                f"🟢 PLACING LIVE ORDER: {prediction} | "
                f"token={token_id[:20]}... | price={entry_price:.2f} | "
                f"size={shares:.2f} shares | stake=${stake_usd:.2f}"
            )

            # Create and post order
            result = self._client.create_and_post_order(order_args)
            logger.info(f"📋 Order result: {result}")

            if result:
                if isinstance(result, dict):
                    order_id = result.get("orderID") or result.get("id")
                    tx_hash = result.get("transactHash") or result.get("txHash") or str(order_id)
                else:
                    tx_hash = str(result)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Order placement failed: {error_msg}\n{traceback.format_exc()}")

            # Record failed trade
            trade_id = await self._record_trade(
                window_id=window_id,
                prediction=prediction,
                token_id=token_id,
                side="BUY",
                entry_price=entry_price,
                stake_usd=stake_usd,
                tx_hash=f"FAILED: {error_msg[:100]}",
                status="failed",
                balance_before=balance_before,
            )

            # Send failure alert
            await self._send_trade_alert(
                prediction=prediction,
                entry_price=entry_price,
                stake_usd=stake_usd,
                factors=factors_agreeing,
                status="FAILED",
                error=error_msg[:200],
                balance=balance_before,
            )
            return None

        # ═══════════════════════════════════════════════════════════
        # RECORD SUCCESS
        # ═══════════════════════════════════════════════════════════

        trade_id = await self._record_trade(
            window_id=window_id,
            prediction=prediction,
            token_id=token_id,
            side="BUY",
            entry_price=entry_price,
            stake_usd=stake_usd,
            tx_hash=tx_hash or "pending",
            status="open",
            balance_before=balance_before,
        )

        # Send success alert 🟢
        await self._send_trade_alert(
            prediction=prediction,
            entry_price=entry_price,
            stake_usd=stake_usd,
            factors=factors_agreeing,
            status="EXECUTED",
            trade_id=trade_id,
            balance=balance_before,
            order_id=order_id,
            window_id=window_id,
        )

        logger.info(f"🟢 LIVE TRADE #{trade_id} EXECUTED: {prediction} @ {entry_price*100:.1f}¢ ${stake_usd}")
        return trade_id

    # ------------------------------------------------------------------
    # Database Recording
    # ------------------------------------------------------------------

    async def _record_trade(
        self,
        window_id: str,
        prediction: str,
        token_id: str,
        side: str,
        entry_price: float,
        stake_usd: float,
        tx_hash: str,
        status: str,
        balance_before: float,
    ) -> Optional[int]:
        """Insert trade into live_trades table."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO live_trades (
                        window_id, prediction, token_id, side,
                        entry_price, stake_usd, tx_hash, status,
                        wallet_balance_before, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    RETURNING id
                    """,
                    window_id,
                    prediction,
                    token_id,
                    side,
                    entry_price,
                    stake_usd,
                    tx_hash,
                    status,
                    balance_before,
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"❌ Failed to record live trade: {e}")
            return None

    # ------------------------------------------------------------------
    # Telegram Alerts (green theme)
    # ------------------------------------------------------------------

    async def _send_trade_alert(
        self,
        prediction: str,
        entry_price: float,
        stake_usd: float,
        factors: int,
        status: str,
        trade_id: Optional[int] = None,
        error: Optional[str] = None,
        balance: Optional[float] = None,
        order_id: Optional[str] = None,
        window_id: Optional[str] = None,
    ):
        """Send green-themed 🟢 LIVE TRADE alert to Telegram."""
        try:
            if not self.telegram_token or not self.telegram_chat_id:
                return

            reward_risk = (1.0 / entry_price - 1.0) * 0.98 if entry_price > 0 else 0
            potential = (stake_usd / entry_price - stake_usd) * 0.98 if entry_price > 0 else 0
            now_ist = datetime.now().strftime("%H:%M IST")

            if status == "EXECUTED":
                msg = (
                    f"🟢💰 LIVE TRADE EXECUTED\n"
                    f"\n"
                    f"━━━ ORDER ━━━\n"
                    f"Direction: {prediction}\n"
                    f"Entry: {entry_price*100:.1f}¢ | Stake: ${stake_usd:.0f}\n"
                    f"R:R {reward_risk:.1f}:1 | Potential: +${potential:.0f}\n"
                    f"Factors: {factors}/7 agreed\n"
                    f"\n"
                    f"━━━ WALLET ━━━\n"
                    f"Balance: ${balance:.2f}" if balance else ""
                )
                if trade_id:
                    msg += f"\nTrade #{trade_id}"
                if window_id:
                    msg += f" | {window_id}"
                msg += f"\n⏰ {now_ist}"
            elif status == "FAILED":
                msg = (
                    f"🔴 LIVE TRADE FAILED\n"
                    f"\n"
                    f"Direction: {prediction} @ {entry_price*100:.1f}¢\n"
                    f"Stake: ${stake_usd:.0f} | Factors: {factors}/7\n"
                    f"Error: {error}\n"
                    f"⏰ {now_ist}"
                )
            else:
                msg = f"📊 Trade update: {status} — {prediction} @ {entry_price*100:.1f}¢"

            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={"chat_id": self.telegram_chat_id, "text": msg},
                )
        except Exception as e:
            logger.error(f"❌ Telegram alert failed: {e}")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve_trade(self, trade_id: int, won: bool, exit_price: float = None):
        """Resolve a live trade as win or loss."""
        try:
            status = "resolved_win" if won else "resolved_loss"
            async with self.db_pool.acquire() as conn:
                # Get trade details
                trade = await conn.fetchrow(
                    "SELECT * FROM live_trades WHERE id = $1", trade_id
                )
                if not trade:
                    return

                entry = float(trade["entry_price"])
                stake = float(trade["stake_usd"])

                if won:
                    pnl = (stake / entry - stake) * 0.98  # 2% fee
                else:
                    pnl = -stake

                balance_after = await self.get_usdc_balance()

                await conn.execute(
                    """
                    UPDATE live_trades
                    SET status = $1, pnl_usd = $2, exit_price = $3,
                        wallet_balance_after = $4, resolved_at = NOW()
                    WHERE id = $5
                    """,
                    status,
                    pnl,
                    exit_price or (1.0 if won else 0.0),
                    balance_after,
                    trade_id,
                )

                # Send resolution alert
                emoji = "🟢💰" if won else "🔴💸"
                msg = (
                    f"{emoji} LIVE TRADE {'WON' if won else 'LOST'}\n"
                    f"\n"
                    f"Trade #{trade_id} | {trade['prediction']}\n"
                    f"Entry: {entry*100:.1f}¢ | Stake: ${stake:.0f}\n"
                    f"P&L: {'+'if pnl>=0 else ''}${pnl:.2f}\n"
                    f"Balance: ${balance_after:.2f}" if balance_after else ""
                )

                if self.telegram_token and self.telegram_chat_id:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(
                            f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                            json={"chat_id": self.telegram_chat_id, "text": msg},
                        )

                logger.info(f"{'✅' if won else '❌'} Live trade #{trade_id} resolved: P&L ${pnl:+.2f}")

        except Exception as e:
            logger.error(f"❌ Trade resolution failed: {e}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> Dict:
        """Get live trading status summary."""
        try:
            balance = await self.get_usdc_balance()
            open_count = await self._get_open_trade_count()
            daily_pnl = await self._check_daily_loss()

            async with self.db_pool.acquire() as conn:
                total = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE status = 'resolved_win') as wins,
                        COUNT(*) FILTER (WHERE status = 'resolved_loss') as losses,
                        COALESCE(SUM(pnl_usd), 0) as total_pnl,
                        COALESCE(SUM(stake_usd), 0) as total_staked
                    FROM live_trades
                    """
                )

            return {
                "initialized": self._initialized,
                "has_private_key": getattr(self, '_has_private_key', False),
                "wallet": self.wallet_address,
                "usdc_balance": balance,
                "open_positions": open_count,
                "daily_pnl": daily_pnl,
                "total_trades": int(total["total_trades"]) if total else 0,
                "wins": int(total["wins"]) if total else 0,
                "losses": int(total["losses"]) if total else 0,
                "total_pnl": float(total["total_pnl"]) if total else 0.0,
                "total_staked": float(total["total_staked"]) if total else 0.0,
                "safety": {
                    "max_stake": MAX_STAKE_USD,
                    "min_factors": MIN_FACTORS,
                    "max_entry": MAX_ENTRY_PRICE,
                    "max_daily_loss": MAX_DAILY_LOSS_USD,
                    "max_open_trades": MAX_OPEN_TRADES,
                },
            }
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {"error": str(e)}
