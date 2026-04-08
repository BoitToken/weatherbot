"""
Internal Arbitrage Scanner
Finds YES + NO < $1.00 opportunities on Polymarket for guaranteed profit.
This is the PRIMARY strategy — risk-free when both sides are purchased.

Fee model: Polymarket charges ~2% on winnings.
Profit = (1.0 - combined_cost) / combined_cost * 100
Net profit = profit - (profit * 0.02)  [2% fee on the profit portion]
"""
import httpx
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

POLYMARKET_FEE_RATE = 0.02  # 2% fee on winnings
MIN_NET_PROFIT_PCT = 0.5    # Minimum 0.5% after fees
GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"


class InternalArbScanner:
    """Scan Polymarket for YES+NO < $1.00 opportunities."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    def _calculate_arb(self, yes_price: float, no_price: float) -> Optional[Dict]:
        """
        Calculate arb opportunity from YES and NO prices.
        Returns dict with profit metrics or None if not profitable.
        """
        if yes_price <= 0 or no_price <= 0:
            return None
        if yes_price >= 1.0 or no_price >= 1.0:
            return None

        combined_cost = yes_price + no_price
        if combined_cost >= 1.0:
            return None  # No arb — costs $1 or more

        # Raw profit: buy both for combined_cost, payout is always $1.00
        raw_profit = 1.0 - combined_cost
        raw_profit_pct = (raw_profit / combined_cost) * 100

        # Fee is 2% on winnings (the profit portion)
        fee = raw_profit * POLYMARKET_FEE_RATE
        net_profit = raw_profit - fee
        fee_adjusted_profit_pct = (net_profit / combined_cost) * 100

        if fee_adjusted_profit_pct < MIN_NET_PROFIT_PCT:
            return None

        # Recommended stake based on profit %
        if fee_adjusted_profit_pct > 5.0:
            recommended_stake = 100
        elif fee_adjusted_profit_pct > 3.0:
            recommended_stake = 75
        elif fee_adjusted_profit_pct > 1.5:
            recommended_stake = 50
        else:
            recommended_stake = 25

        return {
            'combined_cost': round(combined_cost, 4),
            'raw_profit_pct': round(raw_profit_pct, 2),
            'fee_adjusted_profit_pct': round(fee_adjusted_profit_pct, 2),
            'fee_pct': round(POLYMARKET_FEE_RATE * 100, 1),
            'recommended_stake': recommended_stake,
        }

    async def scan_all_markets(self) -> List[Dict]:
        """
        Query sports_markets table for all active markets.
        Check if yes_price + no_price < 1.00 after fees.
        """
        opportunities = []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT market_id, question, yes_price, no_price,
                           volume_usd, sport, group_id
                    FROM sports_markets
                    WHERE is_active = true
                      AND yes_price IS NOT NULL
                      AND no_price IS NOT NULL
                      AND yes_price > 0
                      AND no_price > 0
                """)

                for row in rows:
                    yes_price = float(row['yes_price'])
                    no_price = float(row['no_price'])
                    arb = self._calculate_arb(yes_price, no_price)

                    if arb:
                        opportunities.append({
                            'market_id': row['market_id'],
                            'question': row['question'],
                            'yes_price': yes_price,
                            'no_price': no_price,
                            'volume_usd': float(row['volume_usd'] or 0),
                            'sport': row['sport'],
                            'group_id': row['group_id'],
                            'source': 'database',
                            **arb,
                        })

            logger.info(f"💰 DB scan: {len(opportunities)} internal arb opportunities from {len(rows)} markets")

        except Exception as e:
            logger.error(f"Internal arb DB scan failed: {e}")

        return opportunities

    async def scan_clob_live(self) -> List[Dict]:
        """
        Hit Polymarket Gamma API directly for real-time prices.
        Catches opportunities our DB might miss due to scan delay.
        """
        opportunities = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Fetch active markets in batches
                for offset in range(0, 500, 100):
                    resp = await client.get(GAMMA_API_URL, params={
                        'active': 'true',
                        'closed': 'false',
                        'limit': 100,
                        'offset': offset,
                        'order': 'volume',
                        'ascending': 'false',
                    })
                    if resp.status_code != 200:
                        logger.warning(f"Gamma API returned {resp.status_code} at offset {offset}")
                        break

                    markets = resp.json()
                    if not isinstance(markets, list) or len(markets) == 0:
                        break

                    for m in markets:
                        # Parse outcome prices
                        prices_str = m.get('outcomePrices', '[]')
                        try:
                            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        except (json.JSONDecodeError, TypeError):
                            prices = []

                        if len(prices) < 2:
                            continue

                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                        arb = self._calculate_arb(yes_price, no_price)

                        if arb:
                            opportunities.append({
                                'market_id': m.get('id', ''),
                                'question': m.get('question', ''),
                                'yes_price': yes_price,
                                'no_price': no_price,
                                'volume_usd': float(m.get('volume', 0) or 0),
                                'sport': None,  # Not categorized in CLOB
                                'group_id': None,
                                'source': 'gamma_api',
                                **arb,
                            })

            logger.info(f"💰 CLOB scan: {len(opportunities)} internal arb opportunities from live API")

        except Exception as e:
            logger.error(f"Internal arb CLOB scan failed: {e}")

        return opportunities

    async def scan_combined(self) -> List[Dict]:
        """
        Run both DB and CLOB scans, deduplicate by market_id.
        CLOB prices take priority (fresher).
        """
        db_opps = await self.scan_all_markets()
        clob_opps = await self.scan_clob_live()

        # Merge: CLOB wins on duplicates
        seen = {}
        for opp in clob_opps:
            seen[opp['market_id']] = opp
        for opp in db_opps:
            if opp['market_id'] not in seen:
                seen[opp['market_id']] = opp

        combined = sorted(seen.values(), key=lambda x: x['fee_adjusted_profit_pct'], reverse=True)
        logger.info(f"💰 Combined: {len(combined)} unique internal arb opportunities")
        return combined

    async def execute_internal_arb(self, market_id: str, yes_price: float, no_price: float, stake_usd: float):
        """
        Create a paper trade record for internal arb.
        Buy both YES and NO sides. PnL is guaranteed at entry.
        Auto-resolves immediately (no need to wait for market outcome).
        """
        combined_cost = yes_price + no_price
        if combined_cost >= 1.0:
            logger.warning(f"Arb no longer valid for {market_id}: combined={combined_cost}")
            return None

        # Calculate guaranteed PnL
        raw_profit_per_dollar = (1.0 - combined_cost) / combined_cost
        raw_profit = stake_usd * raw_profit_per_dollar
        fee = raw_profit * POLYMARKET_FEE_RATE
        net_profit = raw_profit - fee
        net_profit_pct = (net_profit / stake_usd) * 100

        try:
            async with self.db_pool.acquire() as conn:
                # Check if we already have an open arb on this market
                existing = await conn.fetchrow("""
                    SELECT id FROM trades
                    WHERE market_id = $1
                      AND strategy = 'internal_arb'
                      AND status IN ('open', 'won')
                      AND entry_at > NOW() - INTERVAL '1 hour'
                """, market_id)

                if existing:
                    logger.debug(f"Arb already executed for {market_id} recently, skipping")
                    return None

                # Get question for market_title
                market_row = await conn.fetchrow("""
                    SELECT question FROM sports_markets WHERE market_id = $1
                """, market_id)
                market_title = market_row['question'] if market_row else f"Market {market_id}"

                # Insert trade — auto-resolve as won immediately
                await conn.execute("""
                    INSERT INTO trades (
                        market_id, market_title, side, entry_price, shares,
                        size_usd, edge_at_entry, status, exit_price,
                        pnl_usd, pnl_pct, resolved_at, entry_at,
                        strategy, metadata
                    ) VALUES (
                        $1, $2, 'BOTH', $3, $4,
                        $5, $6, 'won', 1.0,
                        $7, $8, NOW(), NOW(),
                        'internal_arb', $9
                    )
                """,
                    market_id,
                    market_title,
                    combined_cost,       # entry_price = combined cost
                    stake_usd / combined_cost,  # shares = how many pairs we can buy
                    stake_usd,
                    round(1.0 - combined_cost, 4),  # edge_at_entry = spread
                    round(net_profit, 2),
                    round(net_profit_pct, 4),
                    json.dumps({
                        'strategy': 'internal_arb',
                        'yes_price': yes_price,
                        'no_price': no_price,
                        'combined_cost': combined_cost,
                        'raw_profit_pct': round(raw_profit_per_dollar * 100, 2),
                        'fee_pct': POLYMARKET_FEE_RATE * 100,
                        'net_profit_usd': round(net_profit, 2),
                        'net_profit_pct': round(net_profit_pct, 2),
                        'auto_resolved': True,
                        'timestamp': datetime.utcnow().isoformat(),
                    }),
                )

            logger.info(
                f"💰 INTERNAL ARB EXECUTED: {market_title[:50]} | "
                f"YES={yes_price:.2f} NO={no_price:.2f} | "
                f"Stake=${stake_usd:.0f} → Net +${net_profit:.2f} ({net_profit_pct:.1f}%)"
            )

            return {
                'market_id': market_id,
                'market_title': market_title,
                'stake_usd': stake_usd,
                'net_profit': round(net_profit, 2),
                'net_profit_pct': round(net_profit_pct, 2),
            }

        except Exception as e:
            logger.error(f"Failed to execute internal arb for {market_id}: {e}")
            return None
