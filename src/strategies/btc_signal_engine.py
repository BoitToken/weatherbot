"""
BTC Signal Engine — 7-Factor Prediction Model for Polymarket BTC/USD Windows
Phase 0: Paper trading only — predict, log, score accuracy.

Factors (15-minute calibration from v3.0 strategy):
  1. Price Delta (38%) — BTC price change from window open to now
  2. Momentum (22%) — 20-trade MA vs 100-trade MA
  3. Volume Imbalance (15%) — buy vs sell volume from recent trades
  4. Oracle Lead (8%) — Binance spot vs CoinGecko price divergence
  5. Book Imbalance (10%) — Polymarket UP vs DOWN outcome prices
  6. Volatility (5%) — realized vol; HARD FILTER if > 2σ
  7. Time Decay (2%) — confidence multiplier based on time remaining
"""

import httpx
import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BINANCE_API = "https://api.binance.com/api/v3"
GAMMA_API = "https://gamma-api.polymarket.com"
COINGECKO_API = "https://api.coingecko.com/api/v3"


class BTCSignalEngine:
    """7-factor signal engine for BTC/USD 15-minute Polymarket windows."""

    DEFAULT_WEIGHTS = {
        'price_delta': 0.38,
        'momentum': 0.22,
        'volume_imbalance': 0.15,
        'oracle_lead': 0.08,
        'book_imbalance': 0.10,
        'volatility': 0.05,
        'time_decay': 0.02,
    }

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._btc_price_cache = None
        self._btc_price_cache_ts = None
        self._btc_trades_cache = None
        self._btc_trades_cache_ts = None
        self._oracle_price_cache = None
        self._oracle_price_cache_ts = None

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------
    async def ensure_tables(self):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS btc_windows (
                    id SERIAL PRIMARY KEY,
                    window_id TEXT UNIQUE NOT NULL,
                    window_length INT NOT NULL,
                    open_time TIMESTAMPTZ NOT NULL,
                    close_time TIMESTAMPTZ NOT NULL,
                    btc_open NUMERIC(12,2),
                    btc_close NUMERIC(12,2),
                    up_price NUMERIC(6,4),
                    down_price NUMERIC(6,4),
                    resolution TEXT,
                    volume_usd NUMERIC(18,2),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS btc_signals (
                    id SERIAL PRIMARY KEY,
                    window_id TEXT REFERENCES btc_windows(window_id),
                    signal_ts TIMESTAMPTZ DEFAULT NOW(),
                    seconds_remaining INT,
                    f_price_delta NUMERIC(8,6),
                    f_momentum NUMERIC(8,6),
                    f_volume_imbalance NUMERIC(8,6),
                    f_oracle_lead NUMERIC(8,6),
                    f_book_imbalance NUMERIC(8,6),
                    f_volatility NUMERIC(8,6),
                    f_time_decay NUMERIC(8,6),
                    prob_up NUMERIC(6,4) NOT NULL,
                    prediction TEXT NOT NULL,
                    confidence NUMERIC(6,4),
                    skip_reason TEXT,
                    weights_used JSONB,
                    was_correct BOOLEAN,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS btc_calibration (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    window_length INT NOT NULL,
                    factor_weights JSONB NOT NULL,
                    accuracy_overall NUMERIC(6,4),
                    accuracy_high_conviction NUMERIC(6,4),
                    accuracy_by_bucket JSONB,
                    windows_analyzed INT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_btc_windows_close ON btc_windows(close_time)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_btc_signals_window ON btc_signals(window_id)
            """)
        logger.info("✅ BTC signal engine tables ready")

    # ------------------------------------------------------------------
    # Data fetchers (Binance REST — free, no auth)
    # ------------------------------------------------------------------
    async def get_btc_price(self) -> Dict:
        """Fetch current BTC/USD price + 24h stats + recent 1m klines from Binance."""
        now = datetime.now(timezone.utc)
        if self._btc_price_cache and self._btc_price_cache_ts and \
           (now - self._btc_price_cache_ts).total_seconds() < 5:
            return self._btc_price_cache

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 24h ticker
                ticker_resp = await client.get(f"{BINANCE_API}/ticker/24hr", params={"symbol": "BTCUSDT"})
                ticker = ticker_resp.json()

                # Recent 1-minute klines (last 15 candles)
                klines_resp = await client.get(f"{BINANCE_API}/klines", params={
                    "symbol": "BTCUSDT", "interval": "1m", "limit": 15
                })
                klines = klines_resp.json()

            result = {
                'price': float(ticker['lastPrice']),
                'volume_24h': float(ticker['volume']),
                'quote_volume_24h': float(ticker['quoteVolume']),
                'high': float(ticker['highPrice']),
                'low': float(ticker['lowPrice']),
                'change_pct': float(ticker['priceChangePercent']),
                'recent_klines': [
                    {
                        'open_time': k[0],
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5]),
                        'close_time': k[6],
                    }
                    for k in klines
                ],
            }
            self._btc_price_cache = result
            self._btc_price_cache_ts = now
            return result
        except Exception as e:
            logger.error(f"❌ Failed to fetch BTC price: {e}")
            if self._btc_price_cache:
                return self._btc_price_cache
            return {'price': 0, 'volume_24h': 0, 'quote_volume_24h': 0,
                    'high': 0, 'low': 0, 'change_pct': 0, 'recent_klines': []}

    async def get_btc_trades(self, limit: int = 200) -> List[Dict]:
        """Fetch recent BTC/USD trades from Binance for momentum/vol calculation."""
        now = datetime.now(timezone.utc)
        if self._btc_trades_cache and self._btc_trades_cache_ts and \
           (now - self._btc_trades_cache_ts).total_seconds() < 5:
            return self._btc_trades_cache

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{BINANCE_API}/trades", params={
                    "symbol": "BTCUSDT", "limit": limit
                })
                trades = resp.json()

            result = [
                {
                    'price': float(t['price']),
                    'qty': float(t['qty']),
                    'time': t['time'],
                    'isBuyerMaker': t['isBuyerMaker'],
                }
                for t in trades
            ]
            self._btc_trades_cache = result
            self._btc_trades_cache_ts = now
            return result
        except Exception as e:
            logger.error(f"❌ Failed to fetch BTC trades: {e}")
            return self._btc_trades_cache or []

    async def get_oracle_price(self) -> float:
        """Fetch BTC/USD from CoinGecko as oracle price proxy."""
        now = datetime.now(timezone.utc)
        if self._oracle_price_cache and self._oracle_price_cache_ts and \
           (now - self._oracle_price_cache_ts).total_seconds() < 30:
            return self._oracle_price_cache

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{COINGECKO_API}/simple/price", params={
                    "ids": "bitcoin", "vs_currencies": "usd"
                })
                data = resp.json()
            price = float(data['bitcoin']['usd'])
            self._oracle_price_cache = price
            self._oracle_price_cache_ts = now
            return price
        except Exception as e:
            logger.warning(f"⚠️ CoinGecko oracle fetch failed: {e}")
            return self._oracle_price_cache or 0.0

    # ------------------------------------------------------------------
    # Polymarket window discovery
    # ------------------------------------------------------------------
    async def find_active_btc_windows(self) -> List[Dict]:
        """Find active BTC 5m and 15m Up/Down markets using slug-based discovery.
        
        Polymarket BTC Up/Down markets use predictable slugs:
        - 5-minute: btc-updown-5m-{unix_timestamp} (timestamp = window start, rounded to 300s)
        - 15-minute: btc-updown-15m-{unix_timestamp} (rounded to 900s)
        
        We check the current window and next upcoming window for both timeframes.
        """
        windows = []
        now = datetime.now(timezone.utc)
        now_ts = int(now.timestamp())

        # Generate slugs for current + next windows
        slugs_to_check = []
        
        # 5-minute windows (300s boundaries)
        current_5m = (now_ts // 300) * 300
        for offset in [-300, 0, 300, 600]:  # prev, current, next, next+1
            slugs_to_check.append((f"btc-updown-5m-{current_5m + offset}", 5, current_5m + offset))
        
        # 15-minute windows (900s boundaries)
        current_15m = (now_ts // 900) * 900
        for offset in [-900, 0, 900]:
            slugs_to_check.append((f"btc-updown-15m-{current_15m + offset}", 15, current_15m + offset))

        async with httpx.AsyncClient(timeout=10) as client:
            for slug, window_length, start_ts in slugs_to_check:
                try:
                    resp = await client.get(f"{GAMMA_API}/events", params={"slug": slug})
                    events = resp.json()
                    if not events:
                        continue
                    
                    ev = events[0]
                    markets = ev.get('markets', [])
                    if not markets:
                        continue
                    
                    m = markets[0]
                    
                    # Parse times from the event
                    open_time = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                    close_time = open_time + timedelta(minutes=window_length)
                    
                    # Skip if already closed
                    if close_time <= now:
                        # Still useful for resolution checking
                        pass
                    
                    seconds_remaining = max(0, int((close_time - now).total_seconds()))

                    # Parse outcome prices
                    outcome_prices = []
                    try:
                        op_raw = m.get('outcomePrices') or '[]'
                        if isinstance(op_raw, str):
                            outcome_prices = json.loads(op_raw)
                        elif isinstance(op_raw, list):
                            outcome_prices = op_raw
                    except Exception:
                        outcome_prices = []

                    up_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
                    down_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5

                    condition_id = m.get('conditionId') or m.get('condition_id') or ''
                    window_id = slug  # Use the slug as window_id (unique, predictable)

                    volume = float(m.get('volume') or m.get('volumeNum') or 0)

                    # Extract token IDs for CLOB orderbook access
                    token_ids = m.get('clobTokenIds', [])
                    if isinstance(token_ids, str):
                        try:
                            token_ids = json.loads(token_ids)
                        except Exception:
                            token_ids = []

                    window_data = {
                        'window_id': window_id,
                        'window_length': window_length,
                        'open_time': open_time,
                        'close_time': close_time,
                        'seconds_remaining': seconds_remaining,
                        'up_price': up_price,
                        'down_price': down_price,
                        'volume_usd': volume,
                        'question': m.get('question') or ev.get('title', ''),
                        'condition_id': condition_id,
                        'token_id_up': token_ids[0] if len(token_ids) > 0 else '',
                        'token_id_down': token_ids[1] if len(token_ids) > 1 else '',
                        'slug': slug,
                    }
                    windows.append(window_data)

                    # Upsert into DB
                    try:
                        async with self.db_pool.acquire() as conn:
                            await conn.execute("""
                                INSERT INTO btc_windows (window_id, window_length, open_time, close_time,
                                                         up_price, down_price, volume_usd)
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                ON CONFLICT (window_id) DO UPDATE SET
                                    up_price = EXCLUDED.up_price,
                                    down_price = EXCLUDED.down_price,
                                    volume_usd = EXCLUDED.volume_usd
                            """, window_id, window_length, open_time, close_time,
                                 up_price, down_price, volume)
                    except Exception as e:
                        logger.error(f"DB upsert failed for {window_id}: {e}")
                
                except Exception as e:
                    logger.debug(f"Slug {slug} failed: {e}")
                    continue

        logger.info(f"📊 Found {len(windows)} active BTC windows")
        return windows

    # ------------------------------------------------------------------
    # Factor computation
    # ------------------------------------------------------------------
    async def compute_factors(self, window: Dict, btc_data: Dict, trades: List[Dict]) -> Dict:
        """Compute all 7 signal factors for a given window."""
        now = datetime.now(timezone.utc)
        result = {
            'f_price_delta': 0.0,
            'f_momentum': 0.0,
            'f_volume_imbalance': 0.0,
            'f_oracle_lead': 0.0,
            'f_book_imbalance': 0.0,
            'f_volatility': 1.0,
            'f_time_decay': 0.5,
            'volatility_skip': False,
        }

        current_price = btc_data.get('price', 0)
        if current_price == 0:
            return result

        # ---- Factor 1: Price Delta (38%) ----
        # BTC price change from window open to now, normalized by 30 bps
        klines = btc_data.get('recent_klines', [])
        open_time = window.get('open_time')
        btc_open = current_price  # fallback
        if klines and open_time:
            open_ts = int(open_time.timestamp() * 1000) if hasattr(open_time, 'timestamp') else 0
            for k in klines:
                if k['open_time'] <= open_ts:
                    btc_open = k['open']
            # If no kline before open_time, use first kline
            if btc_open == current_price and klines:
                btc_open = klines[0]['open']

        delta_bps = ((current_price - btc_open) / btc_open) * 10000 if btc_open > 0 else 0
        result['f_price_delta'] = max(-1.0, min(1.0, delta_bps / 30.0))

        # Store btc_open on window for DB
        window['btc_open'] = btc_open

        # ---- Factor 2: Momentum (22%) ----
        # 20-trade MA vs 100-trade MA
        if len(trades) >= 20:
            prices = [t['price'] for t in trades]
            ma20 = sum(prices[-20:]) / 20
            ma100 = sum(prices[-min(100, len(prices)):]) / min(100, len(prices))
            if ma100 > 0:
                mom = (ma20 - ma100) / ma100 * 10000  # in bps
                result['f_momentum'] = max(-1.0, min(1.0, mom / 20.0))

        # ---- Factor 3: Volume Imbalance (15%) ----
        # Buy vs sell volume from recent trades
        if trades:
            buy_vol = sum(t['qty'] for t in trades if not t['isBuyerMaker'])
            sell_vol = sum(t['qty'] for t in trades if t['isBuyerMaker'])
            total_vol = buy_vol + sell_vol
            if total_vol > 0:
                result['f_volume_imbalance'] = max(-1.0, min(1.0,
                    (buy_vol - sell_vol) / total_vol))

        # ---- Factor 4: Oracle Lead (8%) ----
        # Compare Binance spot vs CoinGecko (oracle proxy)
        oracle_price = await self.get_oracle_price()
        if oracle_price > 0 and current_price > 0:
            lead_bps = ((current_price - oracle_price) / oracle_price) * 10000
            result['f_oracle_lead'] = max(-1.0, min(1.0, lead_bps / 15.0))

        # ---- Factor 5: Book Imbalance (10%) ----
        # Use Polymarket outcome prices as proxy
        up_price = window.get('up_price', 0.5)
        down_price = window.get('down_price', 0.5)
        if up_price + down_price > 0:
            book_imb = (up_price - down_price) / (up_price + down_price)
            result['f_book_imbalance'] = max(-1.0, min(1.0, book_imb * 2.0))

        # ---- Factor 6: Volatility (5%) — HARD FILTER ----
        # Realized vol from recent trades — last ~60 seconds
        if len(trades) >= 10:
            now_ms = int(now.timestamp() * 1000)
            recent_60s = [t for t in trades if (now_ms - t['time']) < 60000]
            if len(recent_60s) >= 5:
                recent_prices = [t['price'] for t in recent_60s]
                returns = []
                for i in range(1, len(recent_prices)):
                    if recent_prices[i-1] > 0:
                        returns.append((recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1])
                if returns:
                    vol_60s = (sum(r**2 for r in returns) / len(returns)) ** 0.5

                    # 24h vol estimate from klines
                    if klines and len(klines) >= 5:
                        kline_returns = []
                        for i in range(1, len(klines)):
                            if klines[i-1]['close'] > 0:
                                kline_returns.append(
                                    (klines[i]['close'] - klines[i-1]['close']) / klines[i-1]['close']
                                )
                        if kline_returns:
                            mean_vol = (sum(r**2 for r in kline_returns) / len(kline_returns)) ** 0.5
                            std_vol = (sum((r**2 - mean_vol**2)**2 for r in kline_returns) / max(1, len(kline_returns))) ** 0.5
                            std_vol = max(std_vol ** 0.5, 1e-10)

                            # HARD FILTER: if vol > 2σ above mean
                            if vol_60s > mean_vol + 2 * std_vol:
                                result['volatility_skip'] = True
                                result['f_volatility'] = 0.0
                            else:
                                # Normalize: 1 = low vol (good), 0 = high vol
                                if mean_vol > 0:
                                    vol_ratio = vol_60s / mean_vol
                                    result['f_volatility'] = max(0.0, min(1.0, 1.0 - (vol_ratio - 1.0)))
                                else:
                                    result['f_volatility'] = 0.5

        # ---- Factor 7: Time Decay (2%) ----
        # Closer to close = higher confidence
        seconds_remaining = window.get('seconds_remaining', 0)
        window_seconds = window.get('window_length', 15) * 60
        if window_seconds > 0:
            elapsed_pct = 1.0 - (seconds_remaining / window_seconds)
            result['f_time_decay'] = max(0.0, min(1.0, elapsed_pct))

        return result

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, factors: Dict, weights: Dict = None) -> Tuple[str, float, float]:
        """
        Combine factors into final prediction.
        Returns: (prediction, prob_up, confidence)
        """
        w = weights or self.DEFAULT_WEIGHTS

        # Check volatility hard filter
        if factors.get('volatility_skip', False):
            return ('SKIP', 0.5, 0.0)

        # Weighted sum of directional factors
        directional_sum = (
            w['price_delta'] * factors['f_price_delta'] +
            w['momentum'] * factors['f_momentum'] +
            w['volume_imbalance'] * factors['f_volume_imbalance'] +
            w['oracle_lead'] * factors['f_oracle_lead'] +
            w['book_imbalance'] * factors['f_book_imbalance']
        )

        # Apply sigmoid-like transform
        prob_up = 0.5 + math.tanh(directional_sum * 5) * 0.45

        # Modulate with volatility and time decay
        vol_mult = factors['f_volatility']
        time_mult = factors['f_time_decay']

        # Confidence = factor agreement * volatility * time
        directional_factors = [
            factors['f_price_delta'],
            factors['f_momentum'],
            factors['f_volume_imbalance'],
            factors['f_oracle_lead'],
            factors['f_book_imbalance'],
        ]
        # Agreement ratio: how many factors agree on direction
        positive = sum(1 for f in directional_factors if f > 0.05)
        negative = sum(1 for f in directional_factors if f < -0.05)
        agreement = max(positive, negative) / max(len(directional_factors), 1)

        confidence = agreement * vol_mult * (0.5 + 0.5 * time_mult)
        confidence = max(0.0, min(1.0, confidence))

        # Decision
        if prob_up > 0.55:
            prediction = 'UP'
        elif prob_up < 0.45:
            prediction = 'DOWN'
        else:
            prediction = 'SKIP'

        return (prediction, round(prob_up, 4), round(confidence, 4))

    # ------------------------------------------------------------------
    # Full scan cycle
    # ------------------------------------------------------------------
    async def run_scan(self) -> List[Dict]:
        """Full scan cycle: find windows, compute factors, predict, store."""
        results = []

        windows = await self.find_active_btc_windows()
        if not windows:
            logger.info("📊 No active BTC windows found")
            return results

        btc_data = await self.get_btc_price()
        trades = await self.get_btc_trades(limit=200)
        current_price = btc_data.get('price', 0)

        for window in windows:
            try:
                factors = await self.compute_factors(window, btc_data, trades)
                prediction, prob_up, confidence = self.predict(factors)

                skip_reason = None
                if factors.get('volatility_skip'):
                    skip_reason = 'HARD_FILTER: Volatility > 2σ'
                elif prediction == 'SKIP':
                    skip_reason = 'Low conviction (prob_up between 0.45-0.55)'

                signal = {
                    'window_id': window['window_id'],
                    'window_length': window['window_length'],
                    'seconds_remaining': window.get('seconds_remaining', 0),
                    'close_time': window['close_time'],
                    'btc_price': current_price,
                    'btc_open': window.get('btc_open', current_price),
                    'up_price': window.get('up_price', 0.5),
                    'down_price': window.get('down_price', 0.5),
                    'factors': factors,
                    'prediction': prediction,
                    'prob_up': prob_up,
                    'confidence': confidence,
                    'skip_reason': skip_reason,
                    'question': window.get('question', ''),
                }

                # Store signal in DB
                try:
                    async with self.db_pool.acquire() as conn:
                        # Update window btc_open if not set
                        await conn.execute("""
                            UPDATE btc_windows SET btc_open = $1
                            WHERE window_id = $2 AND btc_open IS NULL
                        """, window.get('btc_open', current_price), window['window_id'])

                        await conn.execute("""
                            INSERT INTO btc_signals (
                                window_id, seconds_remaining,
                                f_price_delta, f_momentum, f_volume_imbalance,
                                f_oracle_lead, f_book_imbalance, f_volatility, f_time_decay,
                                prob_up, prediction, confidence, skip_reason, weights_used
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                            )
                        """,
                            window['window_id'],
                            window.get('seconds_remaining', 0),
                            factors['f_price_delta'],
                            factors['f_momentum'],
                            factors['f_volume_imbalance'],
                            factors['f_oracle_lead'],
                            factors['f_book_imbalance'],
                            factors['f_volatility'],
                            factors['f_time_decay'],
                            prob_up,
                            prediction,
                            confidence,
                            skip_reason,
                            self.DEFAULT_WEIGHTS,
                        )
                except Exception as e:
                    logger.error(f"❌ Failed to store signal for {window['window_id']}: {e}")

                results.append(signal)

            except Exception as e:
                logger.error(f"❌ Factor computation failed for {window['window_id']}: {e}")

        logger.info(f"📊 BTC scan complete: {len(results)} signals generated")
        return results

    # ------------------------------------------------------------------
    # Resolution checker
    # ------------------------------------------------------------------
    async def check_resolutions(self) -> List[Dict]:
        """Check closed windows, determine UP/DOWN, score predictions."""
        resolved = []
        now = datetime.now(timezone.utc)

        try:
            async with self.db_pool.acquire() as conn:
                # Find pending windows that should have closed
                pending = await conn.fetch("""
                    SELECT window_id, window_length, open_time, close_time, btc_open
                    FROM btc_windows
                    WHERE resolution IS NULL AND close_time < $1
                    ORDER BY close_time DESC
                    LIMIT 50
                """, now)

            if not pending:
                return resolved

            # Fetch current price for recent closes
            btc_data = await self.get_btc_price()
            current_price = btc_data.get('price', 0)

            for w in pending:
                window_id = w['window_id']
                btc_open = float(w['btc_open']) if w.get('btc_open') else None
                close_time = w['close_time']

                # For recently closed windows, use current price as approximation
                # (Within 5 minutes of close, current price ≈ close price)
                seconds_since_close = (now - close_time).total_seconds() if close_time else 9999

                if seconds_since_close > 300:
                    # Too old — try to get historical price from klines
                    try:
                        close_ts = int(close_time.timestamp() * 1000)
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.get(f"{BINANCE_API}/klines", params={
                                "symbol": "BTCUSDT",
                                "interval": "1m",
                                "startTime": close_ts - 60000,
                                "endTime": close_ts + 60000,
                                "limit": 3
                            })
                            klines = resp.json()
                        if klines:
                            btc_close = float(klines[-1][4])  # close price
                        else:
                            continue  # Can't determine close price
                    except Exception as e:
                        logger.error(f"❌ Failed to fetch historical price for {window_id}: {e}")
                        continue
                else:
                    btc_close = current_price

                if btc_open is None or btc_open == 0:
                    continue

                resolution = 'UP' if btc_close >= btc_open else 'DOWN'

                # Update window
                try:
                    async with self.db_pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE btc_windows SET btc_close = $1, resolution = $2
                            WHERE window_id = $3
                        """, btc_close, resolution, window_id)

                        # Score predictions
                        await conn.execute("""
                            UPDATE btc_signals SET was_correct = (prediction = $1)
                            WHERE window_id = $2 AND prediction != 'SKIP'
                        """, resolution, window_id)

                        # Also mark skips — was_correct stays NULL for skips
                except Exception as e:
                    logger.error(f"❌ Failed to resolve {window_id}: {e}")
                    continue

                resolved.append({
                    'window_id': window_id,
                    'btc_open': btc_open,
                    'btc_close': btc_close,
                    'resolution': resolution,
                    'delta_pct': ((btc_close - btc_open) / btc_open) * 100,
                })

            if resolved:
                logger.info(f"📊 Resolved {len(resolved)} BTC windows")

        except Exception as e:
            logger.error(f"❌ Resolution check failed: {e}")

        return resolved

    # ------------------------------------------------------------------
    # Accuracy stats
    # ------------------------------------------------------------------
    async def get_accuracy_stats(self) -> Dict:
        """Get rolling accuracy metrics."""
        stats = {
            'total_predictions': 0,
            'correct': 0,
            'accuracy': 0,
            'accuracy_15m': 0,
            'accuracy_5m': 0,
            'high_conviction_accuracy': 0,
            'high_conviction_total': 0,
            'skip_rate': 0,
            'total_signals': 0,
            'win_streak': 0,
            'loss_streak': 0,
            'accuracy_24h': 0,
            'accuracy_7d': 0,
        }

        try:
            async with self.db_pool.acquire() as conn:
                # Overall accuracy (non-skip predictions that have been resolved)
                overall = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE prediction != 'SKIP' AND was_correct IS NOT NULL) as total_pred,
                        COUNT(*) FILTER (WHERE was_correct = true) as correct,
                        COUNT(*) as total_signals,
                        COUNT(*) FILTER (WHERE prediction = 'SKIP') as skips
                    FROM btc_signals
                """)
                if overall:
                    total_pred = int(overall['total_pred'] or 0)
                    correct = int(overall['correct'] or 0)
                    total_signals = int(overall['total_signals'] or 0)
                    skips = int(overall['skips'] or 0)

                    stats['total_predictions'] = total_pred
                    stats['correct'] = correct
                    stats['accuracy'] = round(correct / total_pred, 4) if total_pred > 0 else 0
                    stats['total_signals'] = total_signals
                    stats['skip_rate'] = round(skips / total_signals, 4) if total_signals > 0 else 0

                # By window length
                by_length = await conn.fetch("""
                    SELECT w.window_length,
                           COUNT(*) FILTER (WHERE s.was_correct IS NOT NULL AND s.prediction != 'SKIP') as total,
                           COUNT(*) FILTER (WHERE s.was_correct = true) as correct
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    GROUP BY w.window_length
                """)
                for row in (by_length or []):
                    wl = int(row['window_length'])
                    total = int(row['total'] or 0)
                    corr = int(row['correct'] or 0)
                    acc = round(corr / total, 4) if total > 0 else 0
                    if wl == 15:
                        stats['accuracy_15m'] = acc
                    elif wl == 5:
                        stats['accuracy_5m'] = acc

                # High conviction (prob_up > 0.65 or < 0.35)
                hc = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE was_correct IS NOT NULL) as total,
                        COUNT(*) FILTER (WHERE was_correct = true) as correct
                    FROM btc_signals
                    WHERE prediction != 'SKIP'
                      AND (prob_up > 0.65 OR prob_up < 0.35)
                """)
                if hc:
                    hc_total = int(hc['total'] or 0)
                    hc_correct = int(hc['correct'] or 0)
                    stats['high_conviction_accuracy'] = round(hc_correct / hc_total, 4) if hc_total > 0 else 0
                    stats['high_conviction_total'] = hc_total

                # 24h accuracy
                acc_24h = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE was_correct IS NOT NULL AND prediction != 'SKIP') as total,
                        COUNT(*) FILTER (WHERE was_correct = true) as correct
                    FROM btc_signals
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)
                if acc_24h:
                    t = int(acc_24h['total'] or 0)
                    c = int(acc_24h['correct'] or 0)
                    stats['accuracy_24h'] = round(c / t, 4) if t > 0 else 0

                # 7d accuracy
                acc_7d = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE was_correct IS NOT NULL AND prediction != 'SKIP') as total,
                        COUNT(*) FILTER (WHERE was_correct = true) as correct
                    FROM btc_signals
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                """)
                if acc_7d:
                    t = int(acc_7d['total'] or 0)
                    c = int(acc_7d['correct'] or 0)
                    stats['accuracy_7d'] = round(c / t, 4) if t > 0 else 0

                # Streak calculation
                recent_results = await conn.fetch("""
                    SELECT was_correct FROM btc_signals
                    WHERE prediction != 'SKIP' AND was_correct IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                if recent_results:
                    win_streak = 0
                    loss_streak = 0
                    current_streak = 0
                    last_val = None
                    for r in recent_results:
                        if r['was_correct'] == last_val or last_val is None:
                            current_streak += 1
                        else:
                            if last_val is True:
                                win_streak = max(win_streak, current_streak)
                            else:
                                loss_streak = max(loss_streak, current_streak)
                            current_streak = 1
                        last_val = r['was_correct']
                    if last_val is True:
                        win_streak = max(win_streak, current_streak)
                    else:
                        loss_streak = max(loss_streak, current_streak)
                    stats['win_streak'] = win_streak
                    stats['loss_streak'] = loss_streak

        except Exception as e:
            logger.error(f"❌ Accuracy stats failed: {e}")

        return stats

    # ------------------------------------------------------------------
    # Dashboard state
    # ------------------------------------------------------------------
    async def get_current_state(self) -> Dict:
        """Get live engine state for dashboard."""
        btc_data = await self.get_btc_price()
        accuracy = await self.get_accuracy_stats()

        # Active windows with latest signals
        active_windows = []
        try:
            async with self.db_pool.acquire() as conn:
                windows = await conn.fetch("""
                    SELECT w.*, s.prediction, s.prob_up, s.confidence,
                           s.f_price_delta, s.f_momentum, s.f_volume_imbalance,
                           s.f_oracle_lead, s.f_book_imbalance, s.f_volatility, s.f_time_decay,
                           s.skip_reason
                    FROM btc_windows w
                    LEFT JOIN LATERAL (
                        SELECT * FROM btc_signals
                        WHERE window_id = w.window_id
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) s ON true
                    WHERE w.close_time > NOW() - INTERVAL '30 minutes'
                    ORDER BY w.close_time ASC
                    LIMIT 20
                """)
                for w in (windows or []):
                    active_windows.append({
                        'window_id': w['window_id'],
                        'window_length': w['window_length'],
                        'open_time': w['open_time'].isoformat() if w.get('open_time') else None,
                        'close_time': w['close_time'].isoformat() if w.get('close_time') else None,
                        'btc_open': float(w['btc_open']) if w.get('btc_open') else None,
                        'btc_close': float(w['btc_close']) if w.get('btc_close') else None,
                        'up_price': float(w['up_price']) if w.get('up_price') else None,
                        'down_price': float(w['down_price']) if w.get('down_price') else None,
                        'resolution': w.get('resolution'),
                        'volume_usd': float(w['volume_usd']) if w.get('volume_usd') else 0,
                        'prediction': w.get('prediction'),
                        'prob_up': float(w['prob_up']) if w.get('prob_up') else None,
                        'confidence': float(w['confidence']) if w.get('confidence') else None,
                        'skip_reason': w.get('skip_reason'),
                        'factors': {
                            'price_delta': float(w['f_price_delta']) if w.get('f_price_delta') is not None else None,
                            'momentum': float(w['f_momentum']) if w.get('f_momentum') is not None else None,
                            'volume_imbalance': float(w['f_volume_imbalance']) if w.get('f_volume_imbalance') is not None else None,
                            'oracle_lead': float(w['f_oracle_lead']) if w.get('f_oracle_lead') is not None else None,
                            'book_imbalance': float(w['f_book_imbalance']) if w.get('f_book_imbalance') is not None else None,
                            'volatility': float(w['f_volatility']) if w.get('f_volatility') is not None else None,
                            'time_decay': float(w['f_time_decay']) if w.get('f_time_decay') is not None else None,
                        } if w.get('f_price_delta') is not None else None,
                    })
        except Exception as e:
            logger.error(f"❌ Failed to fetch active windows: {e}")

        return {
            'btc_price': btc_data.get('price', 0),
            'btc_change_24h': btc_data.get('change_pct', 0),
            'btc_high': btc_data.get('high', 0),
            'btc_low': btc_data.get('low', 0),
            'btc_volume_24h': btc_data.get('quote_volume_24h', 0),
            'active_windows': active_windows,
            'accuracy': accuracy,
            'weights': self.DEFAULT_WEIGHTS,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    async def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        """Get recent signals for feed display."""
        signals = []
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT s.*, w.window_length, w.btc_open, w.btc_close, w.resolution
                    FROM btc_signals s
                    JOIN btc_windows w ON s.window_id = w.window_id
                    ORDER BY s.created_at DESC
                    LIMIT $1
                """, limit)
                for r in (rows or []):
                    signals.append({
                        'id': r['id'],
                        'window_id': r['window_id'],
                        'window_length': r['window_length'],
                        'signal_ts': r['signal_ts'].isoformat() if r.get('signal_ts') else None,
                        'seconds_remaining': r.get('seconds_remaining'),
                        'factors': {
                            'price_delta': float(r['f_price_delta']) if r.get('f_price_delta') is not None else 0,
                            'momentum': float(r['f_momentum']) if r.get('f_momentum') is not None else 0,
                            'volume_imbalance': float(r['f_volume_imbalance']) if r.get('f_volume_imbalance') is not None else 0,
                            'oracle_lead': float(r['f_oracle_lead']) if r.get('f_oracle_lead') is not None else 0,
                            'book_imbalance': float(r['f_book_imbalance']) if r.get('f_book_imbalance') is not None else 0,
                            'volatility': float(r['f_volatility']) if r.get('f_volatility') is not None else 0,
                            'time_decay': float(r['f_time_decay']) if r.get('f_time_decay') is not None else 0,
                        },
                        'prob_up': float(r['prob_up']) if r.get('prob_up') else 0,
                        'prediction': r.get('prediction'),
                        'confidence': float(r['confidence']) if r.get('confidence') else 0,
                        'skip_reason': r.get('skip_reason'),
                        'was_correct': r.get('was_correct'),
                        'btc_open': float(r['btc_open']) if r.get('btc_open') else None,
                        'btc_close': float(r['btc_close']) if r.get('btc_close') else None,
                        'resolution': r.get('resolution'),
                    })
        except Exception as e:
            logger.error(f"❌ Failed to fetch recent signals: {e}")
        return signals

    async def get_windows(self, limit: int = 50) -> List[Dict]:
        """Get active + recent windows."""
        windows = []
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM btc_windows
                    ORDER BY close_time DESC
                    LIMIT $1
                """, limit)
                for w in (rows or []):
                    windows.append({
                        'window_id': w['window_id'],
                        'window_length': w['window_length'],
                        'open_time': w['open_time'].isoformat() if w.get('open_time') else None,
                        'close_time': w['close_time'].isoformat() if w.get('close_time') else None,
                        'btc_open': float(w['btc_open']) if w.get('btc_open') else None,
                        'btc_close': float(w['btc_close']) if w.get('btc_close') else None,
                        'up_price': float(w['up_price']) if w.get('up_price') else None,
                        'down_price': float(w['down_price']) if w.get('down_price') else None,
                        'resolution': w.get('resolution'),
                        'volume_usd': float(w['volume_usd']) if w.get('volume_usd') else 0,
                    })
        except Exception as e:
            logger.error(f"❌ Failed to fetch windows: {e}")
        return windows

    async def get_calibration_history(self, limit: int = 30) -> List[Dict]:
        """Get weight calibration history."""
        calibrations = []
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM btc_calibration
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
                for c in (rows or []):
                    calibrations.append({
                        'id': c['id'],
                        'date': c['date'].isoformat() if c.get('date') else None,
                        'window_length': c['window_length'],
                        'factor_weights': c.get('factor_weights'),
                        'accuracy_overall': float(c['accuracy_overall']) if c.get('accuracy_overall') else None,
                        'accuracy_high_conviction': float(c['accuracy_high_conviction']) if c.get('accuracy_high_conviction') else None,
                        'accuracy_by_bucket': c.get('accuracy_by_bucket'),
                        'windows_analyzed': c.get('windows_analyzed'),
                    })
        except Exception as e:
            logger.error(f"❌ Failed to fetch calibration history: {e}")
        return calibrations
