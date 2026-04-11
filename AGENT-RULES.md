# AGENT-RULES.md — Mandatory Rules for All BroBot Agents

## Rule #1: SCHEMA FIRST (No Guessing DB Columns)

**Before writing ANY SQL query, database migration, or API endpoint that touches the database:**

1. **Read `SCHEMA.md`** — it contains every table, every column, every type, and a sample row
2. **Use ONLY column names that exist in SCHEMA.md**
3. **If SCHEMA.md is missing or stale**, regenerate it: `bash scripts/dump-schema.sh`
4. **NEVER assume** column names from other projects, conventions, or "what makes sense"

**Why:** Agent built 6 SQL queries with guessed column names (`entry` instead of `entry_price`, `opened` instead of `opened_at`, `pnl` instead of `realized_pnl`). Every query broke. Whole feature shipped with $0 P&L everywhere.

### Examples of What Goes Wrong
| Guessed | Actual | Table |
|---------|--------|-------|
| `entry` | `entry_price` | jc_trades |
| `opened` | `opened_at` | jc_trades |
| `pnl` | `realized_pnl` | jc_trades |
| `stake` | `stake_usd` | jc_trades, late_window_trades |
| `prediction` | `direction` | late_window_trades |
| `created_at` | `traded_at` | late_window_trades |
| `btc_trades_detail` | `btc_pnl` | (whole table wrong) |

---

## Rule #2: Smoke Test Your Own Work

**Before reporting "done", hit the actual endpoint and verify real data:**

```bash
# Example: tradebook endpoint
curl -s http://localhost:6010/api/tradebook | python3 -c "
import json, sys; d=json.load(sys.stdin); s=d['summary']
assert s['total_trades'] > 0, 'No trades returned!'
assert s['total_net_pnl'] != 0, 'P&L is zero — queries are broken!'
print(f'✅ {s[\"total_trades\"]} trades, \${s[\"total_net_pnl\"]:.2f} P&L, {s[\"win_rate\"]}% WR')
"
```

**Checks:**
- [ ] API returns 200 (not 500/404)
- [ ] Data is non-empty (not `[]` or all nulls)
- [ ] Numbers are non-zero (P&L ≠ 0, win rate ≠ 0%)
- [ ] Build passes: `cd dashboard && npm run build` (0 errors)

---

## Rule #3: One File at a Time for Large Changes

When editing `src/main.py` (6000+ lines):
- Read the specific section you're modifying
- Make targeted edits (don't rewrite entire functions)
- Test after each change

---

## Rule #4: Check What Exists Before Creating

Before creating a new table, endpoint, or component:
```bash
# Tables
grep -c "table_name" SCHEMA.md

# Endpoints  
grep -n "@app\.\(get\|post\|put\|delete\)" src/main.py | grep "tradebook"

# Components
find dashboard/src -name "*.jsx" | head -20
```

---

## Rule #5: Environment Awareness

- **DB:** `postgresql://node@localhost:5432/polyedge`
- **API port:** 6010 (NOT 5002, NOT 3000)
- **Dashboard:** `dashboard/` dir, Vite + React
- **Python venv:** `.venv/` (use `.venv/bin/python3` or `.venv/bin/pip`)
- **PM2 name:** `brobot`
- **psql path:** `/home/linuxbrew/.linuxbrew/Cellar/postgresql@17/17.9/bin/psql`

---

## Rule #6: Post-Build Verification Script

Run this before reporting done for ANY endpoint work:

```bash
# Verify endpoint returns real data
bash scripts/verify-endpoint.sh /api/tradebook
```

---

**Last Updated:** 2026-04-11
**Lesson Source:** Tradebook shipped with 100% broken queries — all P&L showed $0, win rate 0%
