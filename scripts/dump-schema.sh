#!/bin/bash
# dump-schema.sh — Generates SCHEMA.md from live PostgreSQL
# Run before ANY agent touches DB queries
# Cron: daily at 6AM IST, or manually before agent spawn

set -euo pipefail
export PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/Cellar/postgresql@17/17.9/bin:$PATH"
DB_URL="${DB_URL:-postgresql://node@localhost:5432/polyedge}"
OUT="$(dirname "$0")/../SCHEMA.md"

echo "# SCHEMA.md — Live Database Schema" > "$OUT"
echo "**Auto-generated:** $(date '+%Y-%m-%d %H:%M IST')" >> "$OUT"
echo "**Database:** polyedge" >> "$OUT"
echo "" >> "$OUT"
echo "⚠️ **AGENTS: READ THIS BEFORE WRITING ANY SQL QUERY.**" >> "$OUT"
echo "Do NOT guess table/column names. Use ONLY what's listed here." >> "$OUT"
echo "" >> "$OUT"

# Get all tables
TABLES=$(psql "$DB_URL" -t -A -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")

for TABLE in $TABLES; do
    COUNT=$(psql "$DB_URL" -t -A -c "SELECT count(*) FROM \"$TABLE\"" 2>/dev/null || echo "?")
    echo "## $TABLE ($COUNT rows)" >> "$OUT"
    echo '```' >> "$OUT"
    psql "$DB_URL" -c "\d \"$TABLE\"" 2>/dev/null | grep -E '^\s' | head -40 >> "$OUT"
    echo '```' >> "$OUT"
    
    # Sample row (first row, key columns only)
    if [ "$COUNT" != "0" ] && [ "$COUNT" != "?" ]; then
        echo "<details><summary>Sample row</summary>" >> "$OUT"
        echo "" >> "$OUT"
        echo '```json' >> "$OUT"
        psql "$DB_URL" -t -A -c "SELECT row_to_json(t) FROM \"$TABLE\" t LIMIT 1" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -30 >> "$OUT"
        echo '```' >> "$OUT"
        echo "</details>" >> "$OUT"
    fi
    echo "" >> "$OUT"
done

echo "---" >> "$OUT"
echo "**Re-generate:** \`bash scripts/dump-schema.sh\`" >> "$OUT"

echo "✅ SCHEMA.md generated: $(wc -l < "$OUT") lines, $(echo "$TABLES" | wc -l) tables"
