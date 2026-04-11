#!/bin/bash
# WeatherBot Deployment Verification Script

echo "🔍 WeatherBot Deployment Verification"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

fail() {
    echo -e "${RED}❌ $1${NC}"
}

info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# 1. Check PM2 process
echo "1. Checking PM2 process..."
if pm2 list | grep -q brobot; then
    if pm2 list | grep brobot | grep -q online; then
        success "PM2 process 'brobot' is online"
    else
        fail "PM2 process 'brobot' is not online"
    fi
else
    fail "PM2 process 'brobot' not found"
fi
echo ""

# 2. Check local API
echo "2. Checking local API (localhost:6010)..."
if curl -sf http://localhost:6010/api/health > /dev/null; then
    HEALTH=$(curl -s http://localhost:6010/api/health | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    success "API health check: $HEALTH"
else
    fail "API not responding on localhost:6010"
fi
echo ""

# 3. Check container nginx
echo "3. Checking container nginx..."
if nginx -t 2>&1 | grep -q "syntax is ok"; then
    success "Container nginx config is valid"
else
    fail "Container nginx config has errors"
fi
echo ""

# 4. Check DNS
echo "4. Checking DNS resolution..."
DNS_IP=$(curl -s "https://dns.google/resolve?name=brobot.1nnercircle.club&type=A" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['Answer'][0]['data'] if 'Answer' in data else 'NXDOMAIN')")
if [ "$DNS_IP" == "187.77.189.126" ]; then
    success "DNS resolves to $DNS_IP"
else
    fail "DNS issue: got $DNS_IP, expected 187.77.189.126"
fi
echo ""

# 5. Check HTTPS
echo "5. Checking HTTPS..."
if curl -sI https://brobot.1nnercircle.club/ | head -1 | grep -q "200"; then
    success "HTTPS returns 200 OK"
else
    fail "HTTPS not working"
fi
echo ""

# 6. Check HTTPS API
echo "6. Checking HTTPS API endpoint..."
if curl -sf https://brobot.1nnercircle.club/api/health > /dev/null; then
    API_HEALTH=$(curl -s https://brobot.1nnercircle.club/api/health | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    success "HTTPS API health: $API_HEALTH"
else
    fail "HTTPS API not responding"
fi
echo ""

# 7. Check dashboard assets
echo "7. Checking dashboard build..."
if [ -d "dashboard/dist" ] && [ -f "dashboard/dist/index.html" ]; then
    ASSET_COUNT=$(find dashboard/dist -type f | wc -l)
    success "Dashboard built ($ASSET_COUNT files in dist/)"
else
    fail "Dashboard not built (dist/ missing)"
fi
echo ""

# 8. Check database tables
echo "8. Checking database tables..."
TABLE_COUNT=$(psql -U node -d polyedge -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | xargs)
if [ -n "$TABLE_COUNT" ] && [ "$TABLE_COUNT" -gt 0 ]; then
    success "Database has $TABLE_COUNT tables"
else
    info "Unable to verify database (psql not in PATH or connection failed)"
fi
echo ""

# 9. Check SSL certificate
echo "9. Checking SSL certificate..."
if ssh root@172.18.0.1 "certbot certificates 2>/dev/null | grep -q brobot"; then
    EXPIRY=$(ssh root@172.18.0.1 "certbot certificates 2>/dev/null" | grep -A 10 brobot | grep "Expiry Date" | head -1 | cut -d':' -f2- | xargs)
    success "SSL certificate installed (expires $EXPIRY)"
else
    fail "SSL certificate not found"
fi
echo ""

# Final summary
echo "======================================"
echo "📊 Deployment Summary"
echo "======================================"
echo ""
echo "Live URLs:"
echo "  Dashboard: https://brobot.1nnercircle.club/"
echo "  API Health: https://brobot.1nnercircle.club/api/health"
echo "  API Docs: https://brobot.1nnercircle.club/docs"
echo ""
echo "Local endpoints:"
echo "  API: http://localhost:6010/api/health"
echo "  Dashboard dev: http://localhost:6011 (when running npm run dev)"
echo ""
echo "Management:"
echo "  PM2 logs: pm2 logs brobot"
echo "  PM2 restart: pm2 restart brobot"
echo "  PM2 status: pm2 info brobot"
echo ""
