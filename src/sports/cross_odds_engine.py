"""
Cross-Odds Engine
Compares Polymarket prices vs external sportsbook odds.
Phase 1: Group fair value from Polymarket's own grouped markets.
Phase 2: Sportsbook comparison via MarketMatcher links.
Phase 3: Line movement detection.
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
        If all teams in Stanley Cup are priced, normalize to get fair value.
        
        FILTERS:
        - Only BUY signals (we can't short on Polymarket)
        - Skip signals with edge > 100% (group overpricing artifacts)
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
                    
                    # Calculate total yes prices for normalization
                    total_yes = sum(float(m['yes_price'] or 0) for m in markets)
                    
                    if total_yes <= 0:
                        continue
                    
                    for market in markets:
                        yes_price = float(market['yes_price'] or 0)
                        
                        if yes_price <= 0:
                            continue
                        
                        # Fair value = normalized price
                        fair_value = yes_price / total_yes
                        
                        # Edge = fair_value - current_price
                        edge = fair_value - yes_price
                        edge_pct = (edge / yes_price) * 100
                        
                        # Fee-adjusted (Polymarket ~2% fee on winnings)
                        fee_adjusted_edge_pct = edge_pct - 2.0
                        
                        # FILTER: Only BUY signals (can't short on Polymarket)
                        if fee_adjusted_edge_pct <= 5:
                            continue
                        
                        # FILTER: Skip insane edges (>100% = group overpricing artifact)
                        if fee_adjusted_edge_pct > 100:
                            logger.debug(
                                f"Skipping garbage signal: {market['question'][:50]} "
                                f"edge={fee_adjusted_edge_pct:.0f}% (overpricing artifact)"
                            )
                            continue
                        
                        signals.append({
                            'edge_type': 'cross_odds',
                            'sport': sport,
                            'market_id': market['market_id'],
                            'market_title': market['question'],
                            'group_id': group_id,
                            'polymarket_price': yes_price,
                            'fair_value': fair_value,
                            'raw_edge_pct': edge_pct,
                            'edge_pct': fee_adjusted_edge_pct,
                            'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                            'signal': 'BUY',
                            'confidence': 'MEDIUM',
                            'reasoning': (
                                f"Group-normalized fair value is {fair_value:.2%}, "
                                f"current price is {yes_price:.2%}. "
                                f"Edge: {fee_adjusted_edge_pct:.1f}% after fees."
                            ),
                            'data_sources': {'polymarket_group': True},
                        })
        except Exception as e:
            logger.error(f"Failed to calculate group fair value: {e}")
        
        return signals
    
    async def fetch_sportsbook_odds(self, sport: str) -> List[Dict]:
        """
        Fetch odds from The Odds API via OddsFetcher.
        """
        if not self.odds_api_key:
            logger.debug("⚠️ ODDS_API_KEY not set — skipping sportsbook fetch")
            return []
        
        from src.sports.odds_fetcher import OddsFetcher
        fetcher = OddsFetcher(self.db_pool)
        await fetcher.fetch_all_sports()
        return []  # Data stored in DB
    
    async def compare_with_sportsbooks(self) -> List[Dict]:
        """
        Compare Polymarket prices with sportsbook consensus.
        Uses MarketMatcher to link daily match markets, then calculates edge.
        
        Only works for daily match markets (H2H), NOT futures.
        """
        if not self.odds_api_key:
            logger.debug("⚠️ Sportsbook comparison skipped (no API key)")
            return []
        
        signals = []
        
        try:
            from src.sports.market_matcher import MarketMatcher
            matcher = MarketMatcher(self.db_pool)
            
            # Link Polymarket markets to sportsbook events
            link_count = await matcher.link_markets_to_sportsbooks()
            logger.info(f"Linked {link_count} markets to sportsbook data")
            
            async with self.db_pool.acquire() as conn:
                # Get all linked markets with their sportsbook consensus
                # This query gets markets that have been linked
                rows = await conn.fetch("""
                    SELECT 
                        sm.market_id,
                        sm.question,
                        sm.sport,
                        sm.yes_price,
                        sm.volume_usd,
                        AVG(so.implied_probability) as sportsbook_prob,
                        COUNT(DISTINCT so.bookmaker) as num_bookmakers,
                        STRING_AGG(DISTINCT so.bookmaker, ', ') as bookmakers
                    FROM sports_markets sm
                    JOIN sportsbook_odds so ON so.polymarket_id = sm.market_id
                    WHERE sm.is_active = true
                    AND so.fetched_at > NOW() - INTERVAL '48 hours'
                    GROUP BY sm.market_id, sm.question, sm.sport, sm.yes_price, sm.volume_usd
                """)
                
                for row in rows:
                    polymarket_price = float(row['yes_price'] or 0.5)
                    sportsbook_prob = float(row['sportsbook_prob'])
                    num_bookmakers = int(row['num_bookmakers'])
                    
                    if polymarket_price <= 0:
                        continue
                    
                    # Edge: sportsbook says X%, Polymarket prices at Y%
                    edge = sportsbook_prob - polymarket_price
                    edge_pct = (edge / polymarket_price) * 100
                    
                    # Fee-adjusted (2% Polymarket fee)
                    fee_adjusted_edge_pct = edge_pct - 2.0
                    
                    # Determine signal direction
                    if fee_adjusted_edge_pct > 5:
                        signal_dir = 'BUY'  # Sportsbooks think it's more likely than PM price
                    elif fee_adjusted_edge_pct < -5:
                        signal_dir = 'SELL'  # Could sell NO shares (buy NO)
                    else:
                        continue  # Not enough edge
                    
                    # Skip insane edges
                    if abs(fee_adjusted_edge_pct) > 100:
                        continue
                    
                    confidence = 'HIGH' if num_bookmakers >= 3 and abs(fee_adjusted_edge_pct) > 10 else 'MEDIUM'
                    
                    signals.append({
                        'edge_type': 'cross_odds',
                        'sport': row['sport'],
                        'market_id': row['market_id'],
                        'market_title': row['question'],
                        'group_id': None,
                        'polymarket_price': polymarket_price,
                        'fair_value': sportsbook_prob,
                        'raw_edge_pct': edge_pct,
                        'edge_pct': fee_adjusted_edge_pct,
                        'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                        'signal': signal_dir,
                        'confidence': confidence,
                        'reasoning': (
                            f"Sportsbook consensus ({num_bookmakers} books: {row['bookmakers']}): "
                            f"{sportsbook_prob:.2%}, Polymarket: {polymarket_price:.2%}. "
                            f"Edge: {fee_adjusted_edge_pct:.1f}% after fees."
                        ),
                        'data_sources': {'polymarket_clob': True, 'sportsbook_odds': True},
                    })
            
            logger.info(f"✅ Found {len(signals)} cross-odds signals (sportsbook-based)")
        
        except Exception as e:
            logger.error(f"Failed to compare with sportsbooks: {e}", exc_info=True)
        
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
                    
                    if pm_price <= 0:
                        continue
                    
                    edge = current_prob - pm_price
                    edge_pct = (edge / pm_price) * 100
                    fee_adjusted_edge_pct = edge_pct - 2.0
                    
                    if abs(fee_adjusted_edge_pct) <= 5:
                        continue
                    
                    # Skip insane edges
                    if abs(fee_adjusted_edge_pct) > 100:
                        continue
                    
                    signal_dir = 'BUY' if fee_adjusted_edge_pct > 0 else 'SELL'
                    
                    signals.append({
                        'edge_type': 'line_movement',
                        'sport': row['sport'],
                        'market_id': polymarket_id,
                        'market_title': pm_row['question'],
                        'group_id': None,
                        'polymarket_price': pm_price,
                        'fair_value': current_prob,
                        'raw_edge_pct': edge_pct,
                        'edge_pct': fee_adjusted_edge_pct,
                        'fee_adjusted_edge_pct': fee_adjusted_edge_pct,
                        'signal': signal_dir,
                        'confidence': 'HIGH',
                        'reasoning': (
                            f"Sportsbook line moved from {old_prob:.2%} → {current_prob:.2%} "
                            f"({prob_change:+.1%}) but Polymarket still at {pm_price:.2%}. "
                            f"Edge: {fee_adjusted_edge_pct:.1f}% after fees."
                        ),
                        'data_sources': {'sportsbook_line_movement': True},
                    })
            
            logger.info(f"✅ Found {len(signals)} line movement signals")
        
        except Exception as e:
            logger.error(f"Failed to detect line movement: {e}")
        
        return signals
    
    async def run_analysis(self) -> List[Dict]:
        """Run cross-odds analysis."""
        logger.info("🔍 Running cross-odds analysis...")
        
        # Phase 1: Group fair value (internal Polymarket analysis)
        signals = await self.calculate_group_fair_value()
        logger.info(f"  ✅ Found {len(signals)} group-based signals")
        
        # Phase 2: Sportsbook comparison (external odds)
        sportsbook_signals = await self.compare_with_sportsbooks()
        signals.extend(sportsbook_signals)
        
        # Phase 3: Line movement detection
        movement_signals = await self.detect_line_movement()
        signals.extend(movement_signals)
        
        logger.info(f"  ✅ Total cross-odds signals: {len(signals)}")
        return signals
