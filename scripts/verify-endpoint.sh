#!/bin/bash
# verify-endpoint.sh — Smoke test any API endpoint returns real data
# Usage: bash scripts/verify-endpoint.sh /api/tradebook

set -euo pipefail
ENDPOINT="${1:-/api/tradebook}"
PORT="${2:-6010}"
URL="http://localhost:${PORT}${ENDPOINT}"

echo "🔍 Verifying: $URL"

# 1. Check HTTP status
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
if [ "$STATUS" != "200" ]; then
    echo "❌ FAIL: HTTP $STATUS (expected 200)"
    exit 1
fi
echo "✅ HTTP 200"

# 2. Check response is valid JSON with data
BODY=$(curl -s "$URL")
python3 -c "
import json, sys

try:
    d = json.loads('''$BODY''')
except:
    # Handle large responses
    pass

# Quick checks
data = json.loads(sys.stdin.read())

# Check it's not empty
if isinstance(data, dict):
    if 'trades' in data and len(data['trades']) == 0:
        print('⚠️  WARNING: trades array is empty')
    if 'summary' in data:
        s = data['summary']
        if s.get('total_trades', 0) == 0:
            print('❌ FAIL: total_trades is 0')
            sys.exit(1)
        if s.get('total_net_pnl', 0) == 0 and s.get('total_trades', 0) > 5:
            print('❌ FAIL: net_pnl is 0 with', s['total_trades'], 'trades — queries likely broken')
            sys.exit(1)
        if s.get('win_rate', 0) == 0 and s.get('total_trades', 0) > 5:
            print('❌ FAIL: win_rate is 0% with', s['total_trades'], 'trades — outcome detection broken')
            sys.exit(1)
        print(f'✅ Data: {s[\"total_trades\"]} trades, \${s[\"total_net_pnl\"]:.2f} P&L, {s[\"win_rate\"]}% WR')
    else:
        # Generic check: response has content
        content_len = len(json.dumps(data))
        if content_len < 10:
            print('❌ FAIL: response too small:', content_len, 'bytes')
            sys.exit(1)
        print(f'✅ Data: {content_len} bytes')
elif isinstance(data, list):
    if len(data) == 0:
        print('⚠️  WARNING: empty array response')
    else:
        print(f'✅ Data: {len(data)} items')
else:
    print(f'✅ Response type: {type(data).__name__}')
" <<< "$BODY"

# 3. Check dashboard builds
if [ -d "dashboard" ]; then
    echo "🔨 Checking dashboard build..."
    cd dashboard
    BUILD_OUTPUT=$(npm run build 2>&1)
    if echo "$BUILD_OUTPUT" | grep -qi "error"; then
        echo "❌ FAIL: Dashboard build has errors"
        echo "$BUILD_OUTPUT" | grep -i "error" | head -5
        exit 1
    fi
    echo "✅ Dashboard builds clean"
fi

echo ""
echo "✅ ALL CHECKS PASSED"
