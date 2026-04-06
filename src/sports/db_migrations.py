"""
Database migrations for sports intelligence module.
Run once to create sports_markets, sports_signals, live_events, sportsbook_odds tables.
"""
import psycopg2
import logging

logger = logging.getLogger(__name__)

DB_CONFIG = {
    'dbname': 'polyedge',
    'user': 'node',
    'host': 'localhost',
    'port': 5432,
}


def run_migrations():
    """Create all sports tables."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        logger.info("🔧 Running sports DB migrations...")
        
        # Table 1: sports_markets
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_markets (
                id SERIAL PRIMARY KEY,
                market_id VARCHAR(255) UNIQUE,
                question TEXT,
                sport VARCHAR(50),
                league VARCHAR(100),
                event_type VARCHAR(50),
                team_a VARCHAR(200),
                team_b VARCHAR(200),
                yes_price NUMERIC,
                no_price NUMERIC,
                volume_usd NUMERIC,
                liquidity_usd NUMERIC,
                resolution_date TIMESTAMPTZ,
                group_id VARCHAR(255),
                metadata JSONB,
                last_updated TIMESTAMPTZ DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        logger.info("  ✅ Created sports_markets table")
        
        # Index for fast group queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_sports_markets_group_id 
            ON sports_markets(group_id) WHERE is_active = true
        """)
        
        # Table 2: sports_signals
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sports_signals (
                id SERIAL PRIMARY KEY,
                edge_type VARCHAR(50),
                sport VARCHAR(50),
                market_id VARCHAR(255),
                market_title TEXT,
                group_id VARCHAR(255),
                polymarket_price NUMERIC,
                fair_value NUMERIC,
                edge_pct NUMERIC,
                confidence VARCHAR(20),
                signal VARCHAR(20),
                reasoning TEXT,
                data_sources JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("  ✅ Created sports_signals table")
        
        # Index for signal queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_sports_signals_created 
            ON sports_signals(created_at DESC)
        """)
        
        # Table 3: live_events
        cur.execute("""
            CREATE TABLE IF NOT EXISTS live_events (
                id SERIAL PRIMARY KEY,
                sport VARCHAR(50),
                event_id VARCHAR(255) UNIQUE,
                home_team VARCHAR(200),
                away_team VARCHAR(200),
                home_score INTEGER DEFAULT 0,
                away_score INTEGER DEFAULT 0,
                status VARCHAR(50),
                minute VARCHAR(20),
                period VARCHAR(20),
                key_events JSONB,
                linked_market_ids TEXT[],
                last_updated TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("  ✅ Created live_events table")
        
        # Index for live event lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_live_events_status 
            ON live_events(status, sport)
        """)
        
        # Table 4: sportsbook_odds (placeholder for The Odds API data)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sportsbook_odds (
                id SERIAL PRIMARY KEY,
                sport VARCHAR(50),
                event_name TEXT,
                bookmaker VARCHAR(100),
                market_type VARCHAR(50),
                outcome VARCHAR(200),
                odds_decimal NUMERIC,
                implied_probability NUMERIC,
                polymarket_id VARCHAR(255),
                fetched_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("  ✅ Created sportsbook_odds table")
        
        conn.commit()
        logger.info("✅ All sports migrations complete")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_migrations()
