"""
Cross-Odds Engine
Compares Polymarket prices vs external sportsbook odds.
For now, calculates fair value from Polymarket group dynamics.
Future: Integrate The Odds API for DraftKings/FanDuel/Pinnacle comparison.
"""
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CrossOddsEngine:
    """Compare Polymarket prices vs external odds."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.odds_api_key = os.environ.get('ODDS_API_KEY', '')
    
    async def calculate_group_fair_value(self) -> List[Dict]:
        """
        Calculate fair value from Polymarket's own grouped markets.
        If all teams in Stanley Cup are priced, use that as baseline.
        """
        signals = []
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get all groups
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
                    
                    # Get all markets in group
                    markets = await conn.fetch("""
                        SELECT market_id, question, yes_price, no_price, volume_usd
                        FROM sports_markets
                        WHERE group_id = $1 AND is_active = true
                    """, group_id)
                    
                    if len(markets) < 2:
                        continue
                    
                    # Calculate implied probabilities
                    total_yes = sum(float(m['yes_price'] or 0) for m in markets)
                    
                    # Normalize to get fair value
                    for market in markets:
                        yes_price = float(market['yes_price'] or 0)
                        
                        # Fair value = price / total (normalized)
                        fair_value = yes_price / total_yes if total_yes > 0 else 0.5
                        
                        # Edge = fair_value - current_price
                        edge = fair_value - yes_price
                        edge_pct = (edge / yes_price) * 100 if yes_price > 0 else 0
                        
                        # Only signal if >10% edge
                        if abs(edge_pct) > 10:
                            signals.append({
                                'edge_type': 'cross_odds',
                                'sport': sport,
                                'market_id': market['market_id'],
                                'market_title': market['question'],
                                'group_id': group_id,
                                'polymarket_price': yes_price,
                                'fair_value': fair_value,
                                'edge_pct': edge_pct,
                                'signal': 'BUY' if edge_pct > 0 else 'SELL',
                                'confidence': 'MEDIUM',
                                'reasoning': f"Group-normalized fair value is {fair_value:.2%}, current price is {yes_price:.2%}. Edge: {edge_pct:.1f}%.",
                                'data_sources': {'polymarket_group': True},
                            })
        except Exception as e:
            logger.error(f"Failed to calculate group fair value: {e}")
        
        return signals
    
    async def fetch_sportsbook_odds(self, sport: str) -> List[Dict]:
        """
        Fetch odds from The Odds API.
        PLACEHOLDER: Returns empty list until API key is configured.
        """
        if not self.odds_api_key:
            logger.info("⚠️ ODDS_API_KEY not set — skipping sportsbook comparison")
            return []
        
        # Future implementation:
        # import httpx
        # sport_key = {'NHL': 'icehockey_nhl', 'NBA': 'basketball_nba', ...}[sport]
        # async with httpx.AsyncClient() as client:
        #     resp = await client.get(
        #         f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
        #         params={'apiKey': self.odds_api_key, 'regions': 'us', 'markets': 'h2h'}
        #     )
        #     return resp.json()
        
        return []
    
    async def compare_with_sportsbooks(self) -> List[Dict]:
        """
        Compare Polymarket prices with DraftKings/FanDuel/Pinnacle.
        PLACEHOLDER: Returns empty list until The Odds API is integrated.
        """
        if not self.odds_api_key:
            logger.info("⚠️ Sportsbook comparison skipped (no API key)")
            return []
        
        # Future: Fetch odds, match markets, calculate edge
        # For now, return empty
        return []
    
    async def run_analysis(self) -> List[Dict]:
        """Run cross-odds analysis."""
        logger.info("🔍 Running cross-odds analysis...")
        
        # Phase 1: Use group fair value
        signals = await self.calculate_group_fair_value()
        logger.info(f"  ✅ Found {len(signals)} cross-odds signals (group-based)")
        
        # Phase 2: Sportsbook comparison (when API key available)
        sportsbook_signals = await self.compare_with_sportsbooks()
        signals.extend(sportsbook_signals)
        
        return signals
