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
                        
                        # Fee-adjusted edge (Polymarket ~2% fee on winnings)
                        raw_edge_pct = edge_pct
                        fee_adjusted_edge_pct = raw_edge_pct - 2.0
                        
                        # Only signal if fee-adjusted edge > 5%
                        if abs(fee_adjusted_edge_pct) > 5:
                            logger.info(f"  📊 {market['question'][:50]}: Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%")
                            signals.append({
                                'edge_type': 'cross_odds',
                                'sport': sport,
                                'market_id': market['market_id'],
                                'market_title': market['question'],
                                'group_id': group_id,
                                'polymarket_price': yes_price,
                                'fair_value': fair_value,
                                'raw_edge_pct': raw_edge_pct,
                                'edge_pct': fee_adjusted_edge_pct,
                                'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                                'signal': 'BUY' if fee_adjusted_edge_pct > 0 else 'SELL',
                                'confidence': 'MEDIUM',
                                'reasoning': f"Group-normalized fair value is {fair_value:.2%}, current price is {yes_price:.2%}. Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%.",
                                'data_sources': {'polymarket_group': True},
                            })
        except Exception as e:
            logger.error(f"Failed to calculate group fair value: {e}")
        
        return signals
    
    async def fetch_sportsbook_odds(self, sport: str) -> List[Dict]:
        """
        Fetch odds from The Odds API.
        Now implemented via OddsFetcher.
        """
        if not self.odds_api_key:
            logger.debug("⚠️ ODDS_API_KEY not set — skipping sportsbook fetch")
            return []
        
        from src.sports.odds_fetcher import OddsFetcher
        fetcher = OddsFetcher(self.db_pool)
        
        # Fetch and store odds
        await fetcher.fetch_all_sports()
        
        return []  # Data is now in DB
    
    async def compare_with_sportsbooks(self) -> List[Dict]:
        """
        Compare Polymarket prices with DraftKings/FanDuel/Pinnacle.
        Uses MarketMatcher to link markets, then calculates edge.
        """
        if not self.odds_api_key:
            logger.debug("⚠️ Sportsbook comparison skipped (no API key)")
            return []
        
        signals = []
        
        try:
            from src.sports.market_matcher import MarketMatcher
            matcher = MarketMatcher(self.db_pool)
            
            # Link Polymarket markets to sportsbook events
            await matcher.link_markets_to_sportsbooks()
            
            async with self.db_pool.acquire() as conn:
                # Get all active Polymarket sports markets
                markets = await conn.fetch("""
                    SELECT market_id, question, sport, yes_price, volume_usd
                    FROM sports_markets
                    WHERE is_active = true
                """)
                
                for market in markets:
                    market_id = market['market_id']
                    polymarket_price = float(market['yes_price'] or 0.5)
                    
                    # Get sportsbook consensus price
                    sportsbook_prob = await matcher.get_sportsbook_price_for_market(market_id)
                    
                    if sportsbook_prob is None:
                        continue  # No sportsbook data for this market
                    
                    # Calculate edge: sportsbook_prob - polymarket_price
                    edge = sportsbook_prob - polymarket_price
                    edge_pct = (edge / polymarket_price) * 100 if polymarket_price > 0 else 0
                    
                    # Fee-adjusted edge (Polymarket ~2% fee on winnings)
                    raw_edge_pct = edge_pct
                    fee_adjusted_edge_pct = raw_edge_pct - 2.0
                    
                    # Signal if fee-adjusted edge > 5%
                    if abs(fee_adjusted_edge_pct) > 5:
                        logger.info(f"  📊 {market['question'][:50]}: Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%")
                        signals.append({
                            'edge_type': 'cross_odds',
                            'sport': market['sport'],
                            'market_id': market_id,
                            'market_title': market['question'],
                            'group_id': None,
                            'polymarket_price': polymarket_price,
                            'fair_value': sportsbook_prob,
                            'raw_edge_pct': raw_edge_pct,
                            'edge_pct': fee_adjusted_edge_pct,
                            'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                            'signal': 'BUY' if fee_adjusted_edge_pct > 0 else 'SELL',
                            'confidence': 'HIGH' if abs(fee_adjusted_edge_pct) > 10 else 'MEDIUM',
                            'reasoning': f"Sportsbook consensus: {sportsbook_prob:.2%}, Polymarket: {polymarket_price:.2%}. Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%.",
                            'data_sources': {'polymarket_clob': True, 'sportsbook_odds': True},
                        })
            
            logger.info(f"  ✅ Found {len(signals)} cross-odds signals (sportsbook-based)")
        
        except Exception as e:
            logger.error(f"Failed to compare with sportsbooks: {e}")
        
        return signals
    
    async def detect_line_movement(self) -> List[Dict]:
        """
        Track sportsbook odds changes over time.
        If odds move >3% but Polymarket hasn't adjusted, emit signal.
        """
        signals = []
        
        if not self.odds_api_key:
            return signals
        
        try:
            async with self.db_pool.acquire() as conn:
                # Find odds that have changed significantly
                # Compare current odds to odds from 1 hour ago
                rows = await conn.fetch("""
                    WITH current_odds AS (
                        SELECT DISTINCT ON (sport, outcome, bookmaker)
                            sport, event_name, outcome, bookmaker,
                            implied_probability as current_prob,
                            polymarket_id, fetched_at
                        FROM sportsbook_odds
                        WHERE fetched_at > NOW() - INTERVAL '10 minutes'
                        ORDER BY sport, outcome, bookmaker, fetched_at DESC
                    ),
                    old_odds AS (
                        SELECT DISTINCT ON (sport, outcome, bookmaker)
                            sport, outcome, bookmaker,
                            implied_probability as old_prob
                        FROM sportsbook_odds
                        WHERE fetched_at BETWEEN NOW() - INTERVAL '2 hours' AND NOW() - INTERVAL '50 minutes'
                        ORDER BY sport, outcome, bookmaker, fetched_at DESC
                    )
                    SELECT 
                        c.sport, c.event_name, c.outcome, c.polymarket_id,
                        c.current_prob, o.old_prob,
                        c.current_prob - o.old_prob as prob_change
                    FROM current_odds c
                    JOIN old_odds o ON 
                        c.sport = o.sport AND 
                        c.outcome = o.outcome AND 
                        c.bookmaker = o.bookmaker
                    WHERE c.polymarket_id IS NOT NULL
                    AND ABS(c.current_prob - o.old_prob) > 0.03
                """)
                
                for row in rows:
                    polymarket_id = row['polymarket_id']
                    current_prob = float(row['current_prob'])
                    old_prob = float(row['old_prob'])
                    prob_change = float(row['prob_change'])
                    
                    # Get Polymarket current price
                    pm_row = await conn.fetchrow("""
                        SELECT yes_price, question
                        FROM sports_markets
                        WHERE market_id = $1
                    """, polymarket_id)
                    
                    if not pm_row:
                        continue
                    
                    pm_price = float(pm_row['yes_price'] or 0.5)
                    
                    # Check if Polymarket has adjusted
                    # If sportsbook moved from 40% → 50% (+10%) but Polymarket still at 42%, that's a signal
                    edge = current_prob - pm_price
                    edge_pct = (edge / pm_price) * 100 if pm_price > 0 else 0
                    
                    # Fee-adjusted edge
                    raw_edge_pct = edge_pct
                    fee_adjusted_edge_pct = raw_edge_pct - 2.0
                    
                    if abs(fee_adjusted_edge_pct) > 5:
                        logger.info(f"  📊 Line movement {pm_row['question'][:50]}: Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%")
                        signals.append({
                            'edge_type': 'line_movement',
                            'sport': row['sport'],
                            'market_id': polymarket_id,
                            'market_title': pm_row['question'],
                            'group_id': None,
                            'polymarket_price': pm_price,
                            'fair_value': current_prob,
                            'raw_edge_pct': raw_edge_pct,
                            'edge_pct': fee_adjusted_edge_pct,
                            'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                            'signal': 'BUY' if fee_adjusted_edge_pct > 0 else 'SELL',
                            'confidence': 'HIGH',
                            'reasoning': f"Sportsbook odds moved from {old_prob:.2%} → {current_prob:.2%} ({prob_change:+.1%}) but Polymarket still at {pm_price:.2%}. Raw edge: {raw_edge_pct:.1f}%, Fee-adjusted: {fee_adjusted_edge_pct:.1f}%.",
                            'data_sources': {'sportsbook_line_movement': True},
                        })
            
            logger.info(f"  ✅ Found {len(signals)} line movement signals")
        
        except Exception as e:
            logger.error(f"Failed to detect line movement: {e}")
        
        return signals
    
    async def run_analysis(self) -> List[Dict]:
        """Run cross-odds analysis."""
        logger.info("🔍 Running cross-odds analysis...")
        
        # Phase 1: Use group fair value
        signals = await self.calculate_group_fair_value()
        logger.info(f"  ✅ Found {len(signals)} cross-odds signals (group-based)")
        
        # Phase 2: Sportsbook comparison (when API key available)
        sportsbook_signals = await self.compare_with_sportsbooks()
        signals.extend(sportsbook_signals)
        
        # Phase 3: Line movement detection
        movement_signals = await self.detect_line_movement()
        signals.extend(movement_signals)
        
        return signals
