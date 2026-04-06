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
            
            # Step 4: Run cross-odds engine (includes sportsbook comparison + line movement)
            cross_odds_signals = await self.cross_odds.run_analysis()
            logger.info(f"  ✅ Found {len(cross_odds_signals)} cross-odds signals")
            
            # Step 5: Detect momentum signals from live scores
            momentum_signals = await self.espn.detect_momentum_signals()
            logger.info(f"  ✅ Found {len(momentum_signals)} momentum signals")
            
            # Step 6: Store all signals in DB
            all_signals = correlation_signals + cross_odds_signals + momentum_signals
            stored_count = await self.store_signals(all_signals)
            logger.info(f"  ✅ Stored {stored_count} signals")
            
            # Step 7: Create paper trades for high-confidence signals
            trades_created = await self.create_paper_trades(all_signals)
            logger.info(f"  ✅ Created {trades_created} paper trades")
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Sports signal loop complete ({elapsed:.1f}s)")
            
            return {
                'markets_scanned': markets_count,
                'live_events_updated': events_count,
                'signals_generated': len(all_signals),
                'signals_stored': stored_count,
                'paper_trades_created': trades_created,
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
    
    async def create_paper_trades(self, signals: list) -> int:
        """
        Create paper trades for high-confidence sports signals.
        Uses shared src/execution/paper_trader.py.
        """
        trades_created = 0
        
        try:
            # Import paper trader
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from execution.paper_trader import PaperTrader
            
            trader = PaperTrader(self.db_pool)
            
            for signal in signals:
                # Only trade high-confidence signals
                if signal.get('confidence') != 'HIGH':
                    continue
                
                # Skip if no clear edge
                edge_pct = signal.get('edge_pct')
                if edge_pct is None or abs(edge_pct) < 5:
                    continue
                
                # Determine position size based on edge and confidence
                position_size = 100  # Base size in USD
                if abs(edge_pct) > 10:
                    position_size = 200  # Larger for bigger edges
                
                # Create paper trade
                trade_signal = signal.get('signal', 'BUY')
                
                if trade_signal in ['BUY', 'SELL']:
                    side = 'BUY' if trade_signal == 'BUY' else 'SELL'
                    
                    await trader.create_trade(
                        market_id=signal.get('market_id'),
                        side=side,
                        amount_usd=position_size,
                        price=signal.get('polymarket_price', 0.5),
                        source='sports',
                        strategy=signal.get('edge_type', 'unknown'),
                        metadata={
                            'signal': signal.get('signal'),
                            'confidence': signal.get('confidence'),
                            'edge_pct': edge_pct,
                            'reasoning': signal.get('reasoning'),
                        }
                    )
                    
                    trades_created += 1
                
                elif trade_signal == 'BUY_BOTH':
                    # Binary arbitrage: buy both YES and NO
                    await trader.create_trade(
                        market_id=signal.get('market_id'),
                        side='BUY',
                        amount_usd=position_size / 2,
                        price=signal.get('polymarket_price', 0.5),
                        source='sports',
                        strategy='binary_arb',
                        metadata={'reasoning': signal.get('reasoning')}
                    )
                    
                    # Buy NO side too (would need NO price)
                    # For now, just log
                    logger.info(f"  Binary arb opportunity: {signal.get('market_title')}")
                    trades_created += 1
        
        except ImportError:
            logger.warning("⚠️ PaperTrader not found - skipping paper trade creation")
        except Exception as e:
            logger.error(f"Failed to create paper trades: {e}")
        
        return trades_created
