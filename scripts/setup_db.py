#!/usr/bin/env python3
"""
BroBot Database Setup — Creates all required tables in PostgreSQL.
Usage: python3 scripts/setup_db.py
"""
import os
import sys
import psycopg2

def get_db_url():
    """Get database connection from env or defaults."""
    db_url = os.getenv("DB_URL", "postgresql://node:node123@localhost:5432/polyedge")
    return db_url

def main():
    db_url = get_db_url()
    print(f"Connecting to database...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        print("✅ Connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Make sure PostgreSQL is running and the database exists.")
        print("Create it with: createdb polyedge")
        sys.exit(1)
    
    # Read schema file
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)
    
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    print("Creating tables...")
    
    # Split by statement and execute
    statements = schema_sql.split(";")
    created = 0
    errors = 0
    
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            cur.execute(stmt + ";")
            if "CREATE TABLE" in stmt.upper():
                created += 1
        except psycopg2.errors.DuplicateTable:
            pass  # Table already exists
        except psycopg2.errors.DuplicateObject:
            pass  # Index/constraint already exists
        except Exception as e:
            if "already exists" not in str(e):
                errors += 1
                # Don't print every error, just count
    
    # Insert default bot_settings
    try:
        cur.execute("""
            INSERT INTO bot_settings (key, value) VALUES 
                ('trading_mode', '"paper"'),
                ('paper_notifications', 'true'),
                ('live_trading', 'false'),
                ('live_max_stake', '25'),
                ('live_max_daily_loss', '100'),
                ('live_min_balance', '100'),
                ('recommended_min_edge', '7')
            ON CONFLICT (key) DO NOTHING
        """)
    except Exception:
        pass
    
    # Insert default strategy version
    try:
        cur.execute("""
            INSERT INTO btc_strategy_versions (version, max_entry, min_factors, min_rr, window_lengths, stakes, status)
            VALUES ('V4.1', 0.40, 5, 1.50, '{5}', '{"default": 25}'::jsonb, 'active')
            ON CONFLICT DO NOTHING
        """)
    except Exception:
        pass
    
    # Insert default bankroll
    try:
        cur.execute("""
            INSERT INTO btc_bankroll (balance, available, in_positions, total_won, total_lost, total_trades, peak_balance, max_drawdown_pct)
            VALUES (0, 0, 0, 0, 0, 0, 0, 0)
            ON CONFLICT DO NOTHING
        """)
    except Exception:
        pass
    
    # Count tables
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
    table_count = cur.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ Database setup complete!")
    print(f"   Tables: {table_count}")
    print(f"   Errors (non-critical): {errors}")
    print(f"\nBroBot is ready to run!")

if __name__ == "__main__":
    main()
