"""
Correlation Engine — Logical Arbitrage Detector
Finds mathematical impossibilities in Polymarket sports markets:
- Type A: Sum >100% on grouped markets
- Type B: Subset violations (team price > conference price)
- Type C: Binary mispricing (YES + NO != $1)
"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Detect logical arbitrage opportunities in sports markets."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def find_group_overpricing(self) -> List[Dict]:
        """
        Type A: Find market groups where sum of YES prices > 100%.
        Example: All Stanley Cup team prices should sum to ~$1.00
        """
        signals = []
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get all unique groups with >1 market
                groups = await conn.fetch("""
                    SELECT group_id, sport, COUNT(*) as market_count
                    FROM sports_markets
                    WHERE is_active = true
                    AND group_id IS NOT NULL
                    GROUP BY group_id, sport
                    HAVING COUNT(*) > 1
                """)
                
                for group_row in groups:
                    group_id = group_row['group_id']
                    sport = group_row['sport']
                    
                    # Get all markets in this group
                    markets = await conn.fetch("""
                        SELECT market_id, question, yes_price, no_price, volume_usd
                        FROM sports_markets
                        WHERE group_id = $1 AND is_active = true
                    """, group_id)
                    
                    if len(markets) < 2:
                        continue
                    
                    # Calculate sum of YES prices
                    total_yes = sum(float(m['yes_price'] or 0) for m in markets)
                    
                    # If sum > 1.05 (allowing 5% overround), there's arbitrage
                    if total_yes > 1.05:
                        # Find most overpriced (highest deviation from fair share)
                        fair_share = 1.0 / len(markets)
                        
                        for market in markets:
                            yes_price = float(market['yes_price'] or 0)
                            deviation = yes_price - fair_share
                            
                            if deviation > 0.02:  # At least 2% overpriced
                                edge_pct = (total_yes - 1.0) * 100  # Total edge in group
                                
                                signals.append({
                                    'edge_type': 'logical_arb',
                                    'arb_type': 'group_overpricing',
                                    'sport': sport,
                                    'market_id': market['market_id'],
                                    'market_title': market['question'],
                                    'group_id': group_id,
                                    'polymarket_price': yes_price,
                                    'fair_value': fair_share,
                                    'edge_pct': edge_pct,
                                    'total_sum': total_yes,
                                    'signal': 'SELL',  # Sell overpriced YES
                                    'confidence': 'HIGH' if edge_pct > 10 else 'MEDIUM',
                                    'reasoning': f"Group sum is {total_yes:.2%} (>100%). This market is {deviation:.2%} above fair share.",
                                    'data_sources': {'polymarket_clob': True},
                                })
        except Exception as e:
            logger.error(f"Failed to find group overpricing: {e}")
        
        return signals
    
    async def find_subset_violations(self) -> List[Dict]:
        """
        Type B: Subset violations.
        Example: "Avalanche win Cup" (8¢) > "Western Conference wins Cup" (6¢)
        This is mathematically impossible.
        """
        signals = []
        
        # Common subset relationships
        SUBSET_RULES = [
            # NHL
            {
                'superset_keywords': ['western conference', 'west'],
                'subset_keywords': ['avalanche', 'oilers', 'stars', 'golden knights'],
                'sport': 'NHL',
                'event': 'stanley cup'
            },
            {
                'superset_keywords': ['eastern conference', 'east'],
                'subset_keywords': ['bruins', 'rangers', 'panthers', 'lightning'],
                'sport': 'NHL',
                'event': 'stanley cup'
            },
            # NBA
            {
                'superset_keywords': ['western conference', 'west'],
                'subset_keywords': ['lakers', 'warriors', 'nuggets', 'suns'],
                'sport': 'NBA',
                'event': 'nba finals'
            },
            {
                'superset_keywords': ['eastern conference', 'east'],
                'subset_keywords': ['celtics', 'bucks', 'heat', '76ers'],
                'sport': 'NBA',
                'event': 'nba finals'
            },
        ]
        
        try:
            async with self.db_pool.acquire() as conn:
                for rule in SUBSET_RULES:
                    sport = rule['sport']
                    event = rule['event']
                    
                    # Find superset market (conference)
                    superset_markets = await conn.fetch("""
                        SELECT market_id, question, yes_price, no_price
                        FROM sports_markets
                        WHERE sport = $1
                        AND is_active = true
                        AND (
                            question ILIKE ANY($2)
                        )
                    """, sport, [f'%{kw}%' for kw in rule['superset_keywords']])
                    
                    if not superset_markets:
                        continue
                    
                    superset = superset_markets[0]
                    superset_price = float(superset['yes_price'] or 0)
                    
                    # Find subset markets (individual teams)
                    for team_kw in rule['subset_keywords']:
                        subset_markets = await conn.fetch("""
                            SELECT market_id, question, yes_price, no_price
                            FROM sports_markets
                            WHERE sport = $1
                            AND is_active = true
                            AND question ILIKE $2
                        """, sport, f'%{team_kw}%')
                        
                        for subset in subset_markets:
                            subset_price = float(subset['yes_price'] or 0)
                            
                            # Check violation: subset > superset
                            if subset_price > superset_price + 0.01:  # Allow 1¢ tolerance
                                edge_pct = ((subset_price - superset_price) / superset_price) * 100
                                
                                signals.append({
                                    'edge_type': 'logical_arb',
                                    'arb_type': 'subset_violation',
                                    'sport': sport,
                                    'market_id': superset['market_id'],
                                    'market_title': superset['question'],
                                    'group_id': None,
                                    'polymarket_price': superset_price,
                                    'fair_value': subset_price,  # Must be at least this
                                    'edge_pct': edge_pct,
                                    'signal': 'BUY',  # Buy underpriced superset
                                    'confidence': 'HIGH',
                                    'reasoning': f"Subset '{subset['question']}' is priced at {subset_price:.2f} but superset is only {superset_price:.2f}. Guaranteed mispricing.",
                                    'data_sources': {'polymarket_clob': True},
                                })
        except Exception as e:
            logger.error(f"Failed to find subset violations: {e}")
        
        return signals
    
    async def find_binary_mispricing(self) -> List[Dict]:
        """
        Type C: Binary mispricing.
        YES + NO should = ~$1.00
        If YES(25¢) + NO(70¢) = 95¢ → BUY BOTH → guaranteed 5¢ profit
        """
        signals = []
        
        try:
            async with self.db_pool.acquire() as conn:
                markets = await conn.fetch("""
                    SELECT market_id, question, sport, yes_price, no_price, volume_usd
                    FROM sports_markets
                    WHERE is_active = true
                """)
                
                for market in markets:
                    yes_price = float(market['yes_price'] or 0.5)
                    no_price = float(market['no_price'] or 0.5)
                    total = yes_price + no_price
                    
                    # If total < 0.98 (allowing 2¢ spread), there's arb
                    if total < 0.98:
                        edge_pct = ((1.0 - total) / total) * 100
                        
                        signals.append({
                            'edge_type': 'logical_arb',
                            'arb_type': 'binary_mispricing',
                            'sport': market['sport'],
                            'market_id': market['market_id'],
                            'market_title': market['question'],
                            'group_id': None,
                            'polymarket_price': yes_price,
                            'fair_value': 0.5,  # Doesn't matter, buy both
                            'edge_pct': edge_pct,
                            'signal': 'BUY_BOTH',
                            'confidence': 'HIGH',
                            'reasoning': f"YES({yes_price:.2f}) + NO({no_price:.2f}) = {total:.2f} < $1.00. Buy both sides for guaranteed profit.",
                            'data_sources': {'polymarket_clob': True},
                        })
        except Exception as e:
            logger.error(f"Failed to find binary mispricing: {e}")
        
        return signals
    
    async def run_all_checks(self) -> List[Dict]:
        """Run all correlation checks and return combined signals."""
        all_signals = []
        
        logger.info("🔍 Running correlation checks...")
        
        group_signals = await self.find_group_overpricing()
        all_signals.extend(group_signals)
        logger.info(f"  ✅ Found {len(group_signals)} group overpricing opportunities")
        
        subset_signals = await self.find_subset_violations()
        all_signals.extend(subset_signals)
        logger.info(f"  ✅ Found {len(subset_signals)} subset violations")
        
        binary_signals = await self.find_binary_mispricing()
        all_signals.extend(binary_signals)
        logger.info(f"  ✅ Found {len(binary_signals)} binary mispricings")
        
        logger.info(f"✅ Total correlation signals: {len(all_signals)}")
        return all_signals
