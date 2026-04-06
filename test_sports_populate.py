#!/usr/bin/env python3
"""
Test script to populate sports data NOW.
Runs: Polymarket scanner → ESPN live scores → Correlation engine → Cross-odds engine
"""
import asyncio
import logging
from src.db_async import get_async_pool

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Run all sports data population tasks."""
    logger.info("🏀 Starting sports data population...")
    
    pool = get_async_pool()
    
    # 1. Polymarket Sports Scanner
    logger.info("=" * 80)
    logger.info("STEP 1: Scanning Polymarket for sports markets...")
    logger.info("=" * 80)
    from src.sports.polymarket_sports_scanner import PolymarketSportsScanner
    scanner = PolymarketSportsScanner(pool)
    markets_count = await scanner.scan_and_store()
    logger.info(f"✅ Stored {markets_count} sports markets in DB")
    
    # 2. ESPN Live Scores
    logger.info("=" * 80)
    logger.info("STEP 2: Fetching live scores from ESPN...")
    logger.info("=" * 80)
    from src.sports.espn_live import ESPNLiveScores
    espn = ESPNLiveScores(pool)
    events_count = await espn.update_live_events()
    logger.info(f"✅ Stored {events_count} live events in DB")
    
    # 3. Correlation Engine
    logger.info("=" * 80)
    logger.info("STEP 3: Running correlation engine...")
    logger.info("=" * 80)
    from src.sports.correlation_engine import CorrelationEngine
    correlation = CorrelationEngine(pool)
    correlation_signals = await correlation.run_all_checks()
    logger.info(f"✅ Found {len(correlation_signals)} correlation signals")
    
    # Store correlation signals
    if correlation_signals:
        async with pool.acquire() as conn:
            for signal in correlation_signals:
                try:
                    await conn.execute("""
                        INSERT INTO sports_signals (
                            edge_type, sport, market_id, market_title,
                            group_id, polymarket_price, fair_value, edge_pct,
                            confidence, signal, reasoning, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
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
                        signal.get('reasoning')
                    )
                except Exception as e:
                    logger.error(f"Failed to store signal: {e}")
        logger.info(f"✅ Stored {len(correlation_signals)} signals in DB")
    
    # 4. Cross-Odds Engine (group fair value only, sportsbook needs API key)
    logger.info("=" * 80)
    logger.info("STEP 4: Running cross-odds engine (group-based)...")
    logger.info("=" * 80)
    from src.sports.cross_odds_engine import CrossOddsEngine
    cross_odds = CrossOddsEngine(pool)
    cross_odds_signals = await cross_odds.run_analysis()
    logger.info(f"✅ Found {len(cross_odds_signals)} cross-odds signals")
    
    # Store cross-odds signals
    if cross_odds_signals:
        async with pool.acquire() as conn:
            for signal in cross_odds_signals:
                try:
                    await conn.execute("""
                        INSERT INTO sports_signals (
                            edge_type, sport, market_id, market_title,
                            group_id, polymarket_price, fair_value, edge_pct,
                            confidence, signal, reasoning, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
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
                        signal.get('reasoning')
                    )
                except Exception as e:
                    logger.error(f"Failed to store signal: {e}")
        logger.info(f"✅ Stored {len(cross_odds_signals)} cross-odds signals in DB")
    
    # 5. Verify Data
    logger.info("=" * 80)
    logger.info("VERIFICATION: Checking table row counts...")
    logger.info("=" * 80)
    async with pool.acquire() as conn:
        for table in ['sports_markets', 'sportsbook_odds', 'sports_signals', 'live_events']:
            row = await conn.fetchrow(f'SELECT COUNT(*) as count FROM {table}')
            count = row['count']
            logger.info(f"  {table}: {count} rows")
    
    logger.info("=" * 80)
    logger.info("✅ Sports data population complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
