# WeatherBot Deployment Guide

## 🚀 Deployed Components

### 1. FastAPI Backend (`src/main.py`)
- **Port:** 6010
- **Endpoints:** 12 API endpoints for dashboard
- **Health:** `curl http://localhost:6010/api/health`
- **Status:** Running via PM2

### 2. React Dashboard (`dashboard/`)
- **Framework:** React + Vite
- **Pages:** 5 (Overview, Signals, Trades, METAR, Settings)
- **Built:** `dashboard/dist/`
- **Served by:** nginx at `/`

### 3. Telegram Alert System (`src/alerts/`)
- **Bot:** `telegram_bot.py`
- **Functions:** 7 alert templates
- **Graceful degradation:** Works without token (console fallback)

### 4. Execution Engine (`src/execution/`)
- **Paper Trader:** `paper_trader.py` — Kelly Criterion sizing
- **Risk Manager:** `risk_manager.py` — Circuit breakers + limits

### 5. PM2 Process Manager
- **Config:** `ecosystem.config.cjs`
- **Process name:** `brobot`
- **Logs:** `logs/out.log`, `logs/error.log`
- **Auto-restart:** Yes

### 6. Nginx Configuration
- **Container:** `/home/linuxbrew/.linuxbrew/etc/nginx/servers/brobot.conf`
- **Host:** `/etc/nginx/conf.d/brobot.conf`
- **Features:** Static serving + API proxy

### 7. DNS & SSL
- **Domain:** brobot.1nnercircle.club
- **DNS:** 187.77.189.126 (Cloudflare proxied)
- **SSL:** Let's Encrypt (expires 2026-07-05)
- **Redirect:** HTTP → HTTPS

## 📊 Database Schema

Tables created in PostgreSQL `polyedge`:
- `signals` — Signal generation records
- `trades` — Trade execution history
- `markets` — Polymarket weather markets
- `bot_settings` — Bot configuration
- `metar_readings` — Weather observations (pre-existing)
- `temperature_trends` — Trend analysis (pre-existing)

## 🔐 Environment Variables

Create `.env` in project root:
```bash
DB_URL=postgresql://node@localhost:5432/polyedge
MODE=paper
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
KELLY_FRACTION=0.25
```

## 🏃 Quick Start

### Start Backend
```bash
cd /data/.openclaw/workspace/projects/brobot
pm2 start ecosystem.config.cjs
pm2 logs brobot
```

### Start Dashboard (Dev)
```bash
cd dashboard
npm run dev
# Open http://localhost:6011
```

### Build Dashboard (Production)
```bash
cd dashboard
npm run build
# Builds to dist/
```

## 🧪 Testing

### Backend Health
```bash
curl http://localhost:6010/api/health
curl http://localhost:6010/api/bot/status
curl http://localhost:6010/api/bankroll
```

### Frontend
```bash
curl https://brobot.1nnercircle.club/
curl https://brobot.1nnercircle.club/api/health
```

### PM2 Status
```bash
pm2 list
pm2 info brobot
pm2 logs brobot --lines 50
```

## 📡 API Endpoints

### Status
- `GET /api/health` — Health check
- `GET /api/bot/status` — Bot running status

### METAR
- `GET /api/metar/latest` — Latest reading per station
- `GET /api/metar/{icao}?hours=24` — History for station

### Markets
- `GET /api/markets` — Active weather markets

### Signals
- `GET /api/signals?limit=50` — Recent signals
- `GET /api/signals/pending` — High-confidence untrades

### Trades
- `GET /api/trades?limit=100` — Trade history
- `GET /api/trades/active` — Open positions

### Analytics
- `GET /api/pnl/daily?days=30` — Daily P&L
- `GET /api/bankroll` — Current bankroll
- `GET /api/analytics/win-rate?days=30` — Win rate stats

## 🎨 Dashboard Pages

### 1. Overview (`/`)
- Bot status (running/paused)
- Bankroll cards (total, available, in positions)
- Today's P&L
- Active positions count
- 7-day P&L chart

### 2. Signals (`/signals`)
- Signal history table
- Filters: confidence, min edge, city
- "Approve Trade" button for pending signals

### 3. Trades (`/trades`)
- Complete trade history
- Filters: status (all/open/won/lost)
- Summary stats: total trades, win rate, P&L, avg edge

### 4. METAR (`/metar`)
- Live station grid with temp + trend
- Click station → 24h temp chart
- Raw METAR display

### 5. Settings (`/settings`)
- Bot controls (start/pause/stop)
- Trading parameters (min edge, max position, Kelly fraction)
- Mode toggle (paper/live)
- API status indicators

## 🔧 Maintenance

### Update Code
```bash
git pull
cd dashboard && npm run build
pm2 restart brobot
```

### View Logs
```bash
pm2 logs brobot
tail -f logs/out.log
tail -f logs/error.log
```

### Database Backup
```bash
pg_dump -U node polyedge > backup-$(date +%Y%m%d).sql
```

### SSL Renewal (Auto)
Certbot auto-renews. Manual renewal:
```bash
ssh root@172.18.0.1 "certbot renew"
```

## 🐛 Troubleshooting

### API not responding
```bash
pm2 restart brobot
pm2 logs brobot --lines 100
```

### Dashboard not loading
```bash
# Check nginx config
nginx -t
nginx -s reload

# Rebuild dashboard
cd dashboard && npm run build
```

### Database connection issues
```bash
# Test DB connection
psql -U node -d polyedge -c "SELECT 1"

# Check environment
pm2 env brobot
```

### HTTPS not working
```bash
# Check SSL cert
ssh root@172.18.0.1 "certbot certificates | grep brobot"

# Test nginx
ssh root@172.18.0.1 "nginx -t"
```

## 📦 Dependencies

### Python
- FastAPI 0.115.0
- uvicorn 0.32.0
- psycopg2-binary 2.9.9
- apscheduler 3.10.4
- python-telegram-bot 21.5

### Node
- React 19.0.0
- react-router-dom 7.6.3
- recharts 3.0.3
- axios 2.0.0
- Vite 8.0.4

## 🎯 Next Steps

1. Wire data collection loop (Agent 1 deliverable)
2. Wire signal generation loop (Agent 2 deliverable)
3. Add scheduler triggers for data/signal loops
4. Implement settings save/load API
5. Add manual trade approval endpoint
6. Build real-time WebSocket updates (optional)

## 🏗️ Architecture

```
Internet (HTTPS)
    ↓
Host nginx (172.18.0.1:443) + SSL
    ↓
Container nginx (172.18.0.2:80)
    ├─ / → Static files (dashboard/dist)
    └─ /api → Proxy to localhost:6010
              ↓
          FastAPI (Python)
              ↓
          PostgreSQL (localhost:5432)
```

## ✅ Deployment Checklist

- [x] FastAPI server with 12 API endpoints
- [x] Telegram alert system (graceful degradation)
- [x] Paper trader with Kelly sizing
- [x] Risk manager with circuit breakers
- [x] React dashboard (5 pages, dark theme)
- [x] PM2 ecosystem config
- [x] Container nginx config (installed)
- [x] Host nginx config with SSL (installed)
- [x] DNS record (brobot.1nnercircle.club → VPS)
- [x] SSL certificate (Let's Encrypt)
- [x] Database schema initialized
- [x] Health check: `curl http://localhost:6010/api/health` ✅
- [x] HTTPS check: `curl https://brobot.1nnercircle.club/` ✅
- [x] API check: `curl https://brobot.1nnercircle.club/api/health` ✅

## 🌐 Live URLs

- **Dashboard:** https://brobot.1nnercircle.club/
- **API Health:** https://brobot.1nnercircle.club/api/health
- **API Docs:** https://brobot.1nnercircle.club/docs (FastAPI auto-docs)

---

**Powered by Claude + OpenClaw + Actual Intelligence**
