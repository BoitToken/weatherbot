"""Initialize database schema."""
import psycopg2
from src import config

def init_schema():
    """Create all required tables."""
    conn = psycopg2.connect(config.DB_URL)
    cur = conn.cursor()
    
    with open('src/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Execute schema
    cur.execute(schema_sql)
    conn.commit()
    
    print("✅ Database schema initialized successfully")
    
    # Check tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    print(f"\n📋 Created {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    init_schema()
