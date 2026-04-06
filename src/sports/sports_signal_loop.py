"""
Sports Signal Loop
Main orchestrator for sports intelligence module.
Runs every 3 minutes to:
1. Scan Polymarket for sports markets
2. Update live scores from ESPN
3. Run correlation engine (logical arbitrage)
4. Run cross-odds engine (value plays)
5. Store signals in DB
"""
import logging
from datetime import datetime
from .polymarket_sports_scanner import PolymarketSportsScanner
from .espn_live import ESPNLiveScores
from .correlation_engine import CorrelationEngine
from .cross_odds_engine import CrossOddsEngine

logger = logging.getLogger(__name__)


class SportsSignalLoop:
    """Main sports scanning loop."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.scanner = PolymarketSportsScanner(db_pool)
        self.espn = ESPNLiveScores(db_pool)
        self.correlation = CorrelationEngine(db_pool)
        self.cross_odds = CrossOddsEngine(db_pool)
    
    async def run_once(self):
        """Run one complete sports intelligence cycle."""
        logger.info("🏀 Sports signal loop starting...")
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Scan Polymarket for sports markets
            markets_count = await self.scanner.scan_and_store()
            logger.info(f"  ✅ Scanned {markets_count} sports markets")
            
            # Step 2: Update live scores from ESPN
            events_count = await self.espn.update_live_events()
            logger.info(f"  ✅ Updated {events_count} live events")
            
            # Step 3: Run correlation engine (logical arbitrage)
            correlation_signals = await self.correlation.run_all_checks()
            logger.info(f"  ✅ Found {len(correlation_signals)} correlation signals")
            
            # Step 4: Run cross-odds engine
            cross_odds_signals = await self.cross_odds.run_analysis()
            logger.info(f"  ✅ Found {len(cross_odds_signals)} cross-odds signals")
            
            # Step 5: Store all signals in DB
            all_signals = correlation_signals + cross_odds_signals
            stored_count = await self.store_signals(all_signals)
            logger.info(f"  ✅ Stored {stored_count} signals")
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Sports signal loop complete ({elapsed:.1f}s)")
            
            return {
                'markets_scanned': markets_count,
                'live_events_updated': events_count,
                'signals_generated': len(all_signals),
                'signals_stored': stored_count,
                'elapsed_seconds': elapsed,
            }
        except Exception as e:
            logger.error(f"❌ Sports signal loop failed: {e}")
            raise
    
    async def store_signals(self, signals: list) -> int:
        """Store signals in sports_signals table."""
        if not signals:
            return 0
        
        stored = 0
        
        try:
            async with self.db_pool.acquire() as conn:
                for signal in signals:
                    try:
                        await conn.execute("""
                            INSERT INTO sports_signals (
                                edge_type, sport, market_id, market_title,
                                group_id, polymarket_price, fair_value, edge_pct,
                                confidence, signal, reasoning, data_sources, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                        """,
                            signal.get('edge_type'),
                            signal.get('sport'),
                            signal.get('market_id'),
                            signal.get('market_title'),
                            signal.get('group_id'),
                            signal.get('polymarket_price'),
                            signal.get('fair_value'),
                            signal.get('edge_pct'),
                            signal.get('confidence'),
                            signal.get('signal'),
                            signal.get('reasoning'),
                            None  # data_sources as JSON (convert dict to JSONB manually if needed)
                        )
                        stored += 1
                    except Exception as e:
                        logger.error(f"Failed to store signal: {e}")
        except Exception as e:
            logger.error(f"Failed to store signals: {e}")
        
        return stored
