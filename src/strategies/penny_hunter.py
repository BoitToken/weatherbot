"""
Penny Hunter Strategy
Scans ALL Polymarket markets for contracts priced 1-3¢ with asymmetric upside.
Paper trades only — no real execution.

The Math:
- Contracts at 1¢ have +$0.0336 EV per contract
- 2.66% resolve at 99¢ (99x return), 3.33% bounce to 50¢+, 94% die at $0
- One 99x win covers 98 losses. Spread thin, buy wide, let asymmetry work.
"""
import httpx
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PENNY_MAX_PRICE = 0.03   # 3¢ ceiling
PENNY_MIN_PRICE = 0.005  # below 0.5¢ is probably dead/glitched
GAMMA_API_URL = "https://gamma-api.polymarket.com"


class PennyHunter:
    """Scan Polymarket for 1-3¢ contracts with asymmetric upside."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------
    async def ensure_tables(self):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS penny_positions (
                    id SERIAL PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    condition_id TEXT,
                    question TEXT NOT NULL,
                    category TEXT,
                    outcome TEXT,
                    buy_price NUMERIC(6,4) NOT NULL,
                    quantity NUMERIC(10,2) DEFAULT 1,
                    size_usd NUMERIC(10,2),
                    potential_payout NUMERIC(10,2),
                    catalyst_score NUMERIC(4,2),
                    catalyst_reason TEXT,
                    days_to_resolution INT,
                    volume_usd NUMERIC(18,2),
                    status TEXT DEFAULT 'open',
                    resolution TEXT,
                    pnl_usd NUMERIC(10,2),
                    opened_at TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ,
                    metadata JSONB
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_penny_status ON penny_positions(status)
            """)
        logger.info("✅ penny_positions table ready")

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    async def scan_penny_contracts(self) -> List[Dict]:
        """
        Fetch active Polymarket markets from Gamma API.
        Filter for any outcome priced 1-3¢.
        Paginate through at least 500 markets.
        """
        penny_contracts: List[Dict] = []
        scanned = 0

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                for offset in range(0, 600, 100):
                    try:
                        resp = await client.get(f"{GAMMA_API_URL}/markets", params={
                            'active': 'true',
                            'closed': 'false',
                            'limit': 100,
                            'offset': offset,
                            'order': 'volume',
                            'ascending': 'false',
                        })
                        if resp.status_code != 200:
                            logger.warning(f"Gamma API {resp.status_code} at offset {offset}")
                            break

                        markets = resp.json()
                        if not isinstance(markets, list) or len(markets) == 0:
                            break

                        scanned += len(markets)

                        for m in markets:
                            pennies = self._extract_pennies(m)
                            penny_contracts.extend(pennies)

                    except httpx.TimeoutException:
                        logger.warning(f"Gamma API timeout at offset {offset}")
                        break
                    except Exception as e:
                        logger.error(f"Gamma API error at offset {offset}: {e}")
                        break

        except Exception as e:
            logger.error(f"Penny scan failed: {e}")

        logger.info(f"🎰 Penny scan: {len(penny_contracts)} penny contracts from {scanned} markets")
        return penny_contracts

    def _extract_pennies(self, market: Dict) -> List[Dict]:
        """Extract penny-priced outcomes from a market."""
        results = []
        prices_str = market.get('outcomePrices', '[]')
        outcomes_str = market.get('outcomes', '[]')

        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else (prices_str or [])
        except (json.JSONDecodeError, TypeError):
            prices = []

        try:
            outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else (outcomes_str or [])
        except (json.JSONDecodeError, TypeError):
            outcomes = []

        if not prices:
            return results

        # Calculate days to resolution
        end_date_str = market.get('endDate') or market.get('end_date_iso') or ''
        days_left = self._days_to_resolution(end_date_str)

        volume = float(market.get('volume', 0) or 0)
        question = market.get('question', '')
        market_id = market.get('id', '')
        condition_id = market.get('conditionId', market.get('condition_id', ''))
        description = market.get('description', '')
        category = self._detect_category(question)

        for i, price_val in enumerate(prices):
            try:
                price = float(price_val)
            except (ValueError, TypeError):
                continue

            if PENNY_MIN_PRICE <= price <= PENNY_MAX_PRICE:
                outcome_label = outcomes[i] if i < len(outcomes) else ('Yes' if i == 0 else 'No')
                results.append({
                    'market_id': market_id,
                    'condition_id': condition_id,
                    'question': question,
                    'category': category,
                    'outcome': outcome_label,
                    'buy_price': price,
                    'days_to_resolution': days_left,
                    'volume_usd': volume,
                    'description': description,
                    'end_date': end_date_str,
                })

        return results

    # ------------------------------------------------------------------
    # Catalyst scoring
    # ------------------------------------------------------------------
    def score_catalyst(self, market: Dict) -> Tuple[float, str]:
        """
        Score a penny contract 0-10 based on catalyst potential.
        Returns (score, reason_string).
        """
        score = 0.0
        reasons = []

        # Days to resolution
        days = market.get('days_to_resolution')
        if days is not None and days >= 0:
            if 7 <= days <= 30:
                score += 3
                reasons.append(f"{days}d left (sweet spot)")
            elif 1 <= days < 7:
                score += 2
                reasons.append(f"{days}d left (imminent)")
            elif 30 < days <= 90:
                score += 1
                reasons.append(f"{days}d left")
            # >90 days = +0
        else:
            # Unknown resolution = slight penalty
            score += 0.5

        # Volume
        vol = market.get('volume_usd', 0) or 0
        if vol > 100_000:
            score += 2
            reasons.append(f"${vol/1000:.0f}K vol")
        elif vol > 10_000:
            score += 1
            reasons.append(f"${vol/1000:.0f}K vol")
        # <$1K = +0

        # Category boost
        cat = (market.get('category') or '').lower()
        if cat in ('politics', 'crypto', 'sports'):
            score += 1
            reasons.append(f"{cat} catalyst")

        # Price asymmetry
        price = market.get('buy_price', 0.03)
        if price <= 0.01:
            score += 2
            reasons.append("1¢ max asymmetry")
        elif price <= 0.02:
            score += 1
            reasons.append("2¢ good asymmetry")
        else:
            score += 0.5
            reasons.append("3¢ moderate")

        reason_str = ' | '.join(reasons) if reasons else 'Asymmetric value'
        return (min(score, 10.0), reason_str)

    # ------------------------------------------------------------------
    # Execute paper bet
    # ------------------------------------------------------------------
    async def execute_penny_bet(self, contract: Dict) -> Optional[int]:
        """
        Create a paper trade for a penny contract.
        Position sizing by catalyst score. Dedup by market_id + outcome.
        """
        catalyst_score = contract.get('catalyst_score', 0)
        if catalyst_score < 3:
            return None

        # Position sizing
        if catalyst_score >= 8:
            size_usd = 5.0
        elif catalyst_score >= 5:
            size_usd = 2.50
        else:
            size_usd = 1.0

        buy_price = contract['buy_price']
        quantity = size_usd / buy_price if buy_price > 0 else 0
        potential_payout = quantity * 1.0  # each share pays $1 if wins

        market_id = contract['market_id']
        outcome = contract.get('outcome', 'Yes')

        try:
            async with self.db_pool.acquire() as conn:
                # Dedup: check for existing open position on same market+outcome
                existing = await conn.fetchrow("""
                    SELECT id FROM penny_positions
                    WHERE market_id = $1 AND outcome = $2 AND status = 'open'
                """, market_id, outcome)

                if existing:
                    logger.debug(f"Penny position already open for {market_id}/{outcome}")
                    return None

                row = await conn.fetchrow("""
                    INSERT INTO penny_positions (
                        market_id, condition_id, question, category, outcome,
                        buy_price, quantity, size_usd, potential_payout,
                        catalyst_score, catalyst_reason,
                        days_to_resolution, volume_usd, status, metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9,
                        $10, $11,
                        $12, $13, 'open', $14
                    ) RETURNING id
                """,
                    market_id,
                    contract.get('condition_id', ''),
                    contract['question'],
                    contract.get('category', ''),
                    outcome,
                    buy_price,
                    round(quantity, 2),
                    size_usd,
                    round(potential_payout, 2),
                    contract.get('catalyst_score', 0),
                    contract.get('catalyst_reason', ''),
                    contract.get('days_to_resolution'),
                    contract.get('volume_usd', 0),
                    json.dumps({
                        'description': (contract.get('description', '') or '')[:500],
                        'end_date': contract.get('end_date', ''),
                        'scanned_at': datetime.now(timezone.utc).isoformat(),
                    }),
                )

                pos_id = row['id'] if row else None
                if pos_id:
                    logger.info(
                        f"🎰 PENNY BET #{pos_id}: {contract['question'][:50]} | "
                        f"{buy_price*100:.0f}¢ | ${size_usd} → potential ${potential_payout:.0f} | "
                        f"Score: {catalyst_score:.0f}/10"
                    )
                return pos_id

        except Exception as e:
            logger.error(f"Failed to execute penny bet for {market_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Check resolutions
    # ------------------------------------------------------------------
    async def check_resolutions(self) -> List[Dict]:
        """
        Check all open penny positions for resolution or price bounces.
        """
        resolved = []

        try:
            async with self.db_pool.acquire() as conn:
                open_positions = await conn.fetch("""
                    SELECT id, market_id, condition_id, question, outcome,
                           buy_price, quantity, size_usd, potential_payout
                    FROM penny_positions
                    WHERE status = 'open'
                    ORDER BY opened_at ASC
                """)

            if not open_positions:
                return resolved

            # Batch fetch current market data
            market_ids = list(set(str(p['market_id']) for p in open_positions))
            market_data = await self._fetch_markets_by_ids(market_ids)

            async with self.db_pool.acquire() as conn:
                for pos in open_positions:
                    mid = str(pos['market_id'])
                    mdata = market_data.get(mid)
                    if not mdata:
                        continue

                    is_closed = mdata.get('closed', False)
                    is_active = mdata.get('active', True)

                    # Parse current prices
                    prices_str = mdata.get('outcomePrices', '[]')
                    try:
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else (prices_str or [])
                    except (json.JSONDecodeError, TypeError):
                        prices = []

                    outcomes_str = mdata.get('outcomes', '[]')
                    try:
                        outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else (outcomes_str or [])
                    except (json.JSONDecodeError, TypeError):
                        outcomes = []

                    # Find current price for our outcome
                    current_price = None
                    outcome_label = pos['outcome']
                    for i, olabel in enumerate(outcomes):
                        if olabel == outcome_label and i < len(prices):
                            try:
                                current_price = float(prices[i])
                            except (ValueError, TypeError):
                                pass
                            break

                    if current_price is None and len(prices) > 0:
                        # Fallback: use first price for Yes, second for No
                        idx = 0 if outcome_label in ('Yes', 'yes', 'YES') else (1 if len(prices) > 1 else 0)
                        try:
                            current_price = float(prices[idx])
                        except (ValueError, TypeError):
                            continue

                    if current_price is None:
                        continue

                    buy_price = float(pos['buy_price'])
                    quantity = float(pos['quantity'])
                    size_usd = float(pos['size_usd'])

                    if is_closed or not is_active:
                        # Market resolved
                        if current_price >= 0.95:
                            # Won: outcome resolved YES
                            pnl = (1.0 - buy_price) * quantity * 0.98  # 2% fee
                            status = 'won'
                            resolution = 'resolved_win'
                        else:
                            # Lost
                            pnl = -size_usd
                            status = 'lost'
                            resolution = 'resolved_loss'

                        await conn.execute("""
                            UPDATE penny_positions
                            SET status = $1, resolution = $2, pnl_usd = $3,
                                resolved_at = NOW()
                            WHERE id = $4
                        """, status, resolution, round(pnl, 2), pos['id'])

                        resolved.append({
                            'id': pos['id'],
                            'market_id': mid,
                            'question': pos['question'],
                            'outcome': outcome_label,
                            'buy_price': buy_price,
                            'current_price': current_price,
                            'pnl_usd': round(pnl, 2),
                            'status': status,
                            'resolution': resolution,
                        })
                        logger.info(
                            f"{'💰' if status == 'won' else '💀'} Penny #{pos['id']} "
                            f"{status.upper()}: {pos['question'][:40]} | "
                            f"P&L: ${pnl:+.2f}"
                        )

                    elif current_price >= 0.50:
                        # Price bounced significantly — flag it
                        await conn.execute("""
                            UPDATE penny_positions
                            SET status = 'bouncing',
                                metadata = metadata || $1::jsonb
                            WHERE id = $2
                        """, json.dumps({'bounce_price': current_price, 'bounce_at': datetime.now(timezone.utc).isoformat()}), pos['id'])

                        resolved.append({
                            'id': pos['id'],
                            'market_id': mid,
                            'question': pos['question'],
                            'outcome': outcome_label,
                            'buy_price': buy_price,
                            'current_price': current_price,
                            'pnl_usd': round((current_price - buy_price) * quantity, 2),
                            'status': 'bouncing',
                            'resolution': f'bounced to {current_price*100:.0f}¢',
                        })

        except Exception as e:
            logger.error(f"Resolution check failed: {e}")

        return resolved

    # ------------------------------------------------------------------
    # Portfolio stats
    # ------------------------------------------------------------------
    async def get_portfolio_stats(self) -> Dict:
        """Get penny portfolio statistics."""
        try:
            async with self.db_pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_positions,
                        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                        COUNT(CASE WHEN status = 'bouncing' THEN 1 END) as bouncing_positions,
                        COALESCE(SUM(size_usd), 0) as total_invested,
                        COALESCE(SUM(CASE WHEN status IN ('won', 'lost', 'bouncing') THEN pnl_usd ELSE 0 END), 0) as total_pnl,
                        COUNT(CASE WHEN status = 'won' THEN 1 END) as wins,
                        COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses,
                        MAX(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) as best_win,
                        COALESCE(AVG(
                            CASE WHEN resolved_at IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (resolved_at - opened_at)) / 86400.0
                            END
                        ), 0) as avg_days_held
                    FROM penny_positions
                """)

                if not stats:
                    return self._empty_stats()

                total = int(stats['total_positions'] or 0)
                wins = int(stats['wins'] or 0)
                losses = int(stats['losses'] or 0)
                resolved = wins + losses
                total_invested = float(stats['total_invested'] or 0)
                total_pnl = float(stats['total_pnl'] or 0)
                best_win = float(stats['best_win'] or 0)
                best_buy = None

                if best_win > 0:
                    best_row = await conn.fetchrow("""
                        SELECT buy_price, pnl_usd FROM penny_positions
                        WHERE pnl_usd = $1 LIMIT 1
                    """, round(best_win, 2))
                    if best_row and float(best_row['buy_price']) > 0:
                        best_buy = float(best_row['buy_price'])

                return {
                    'total_positions': total,
                    'open_positions': int(stats['open_positions'] or 0),
                    'bouncing_positions': int(stats['bouncing_positions'] or 0),
                    'total_invested': round(total_invested, 2),
                    'total_pnl': round(total_pnl, 2),
                    'wins': wins,
                    'losses': losses,
                    'hit_rate': round(wins / resolved * 100, 1) if resolved > 0 else 0,
                    'best_win': round(best_win, 2),
                    'best_multiplier': round(1.0 / best_buy, 0) if best_buy and best_buy > 0 else 0,
                    'avg_days_held': round(float(stats['avg_days_held'] or 0), 1),
                    'roi': round(total_pnl / total_invested * 100, 1) if total_invested > 0 else 0,
                }

        except Exception as e:
            logger.error(f"Portfolio stats failed: {e}")
            return self._empty_stats()

    def _empty_stats(self) -> Dict:
        return {
            'total_positions': 0, 'open_positions': 0, 'bouncing_positions': 0,
            'total_invested': 0, 'total_pnl': 0,
            'wins': 0, 'losses': 0, 'hit_rate': 0,
            'best_win': 0, 'best_multiplier': 0,
            'avg_days_held': 0, 'roi': 0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _fetch_markets_by_ids(self, market_ids: List[str]) -> Dict[str, Dict]:
        """Fetch market data for a list of IDs from Gamma API."""
        result = {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Gamma API supports fetching by ID
                for mid in market_ids:
                    try:
                        resp = await client.get(f"{GAMMA_API_URL}/markets/{mid}")
                        if resp.status_code == 200:
                            data = resp.json()
                            if isinstance(data, dict):
                                result[mid] = data
                            elif isinstance(data, list) and len(data) > 0:
                                result[mid] = data[0]
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Batch market fetch failed: {e}")
        return result

    def _days_to_resolution(self, end_date_str: str) -> Optional[int]:
        """Calculate days until market resolution."""
        if not end_date_str:
            return None
        try:
            # Handle ISO format with or without timezone
            end_date_str = end_date_str.replace('Z', '+00:00')
            end_date = datetime.fromisoformat(end_date_str)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (end_date - now).days
            return max(delta, 0)
        except (ValueError, TypeError):
            return None

    def _detect_category(self, question: str) -> str:
        """Detect market category from question text."""
        q = question.lower()
        if any(kw in q for kw in ['president', 'election', 'vote', 'congress', 'senate', 'trump', 'biden', 'democrat', 'republican']):
            return 'politics'
        if any(kw in q for kw in ['bitcoin', 'ethereum', 'btc', 'eth', 'crypto', 'solana', 'token']):
            return 'crypto'
        if any(kw in q for kw in ['nba', 'nfl', 'mlb', 'nhl', 'ncaa', 'game', 'match', 'win', 'championship', 'series', 'playoffs']):
            return 'sports'
        if any(kw in q for kw in ['temperature', 'weather', 'rain', 'snow', 'celsius', 'fahrenheit']):
            return 'weather'
        if any(kw in q for kw in ['gdp', 'inflation', 'fed', 'interest rate', 'stock', 'nasdaq']):
            return 'economics'
        if any(kw in q for kw in ['ai', 'artificial intelligence', 'spacex', 'nasa']):
            return 'science'
        return 'other'
