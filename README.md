# 🤖🛡️ BroBot — Multi-Strategy Crypto Trading Platform

BroBot is a personal trading bot controller that runs multiple strategies from a single dashboard. Live trading on Polymarket with real USDC, copy trading from Discord signals, and sports/weather market analysis.

## Features

- 🟢 **Live Trading** — Real USDC trades on Polymarket (Polygon)
- 📊 **BTC 5M Arbitrage** — 7-factor signal analysis on BTC UP/DOWN 5-minute windows
- 👻 **JC Copy Trader** — Copies Jayson Casper's BTC levels from Discord to Bybit futures
- 🏆 **Sports Markets** — Sports betting signal scanner
- 🌤️ **Weather Markets** — Weather prediction market analysis
- 💰 **Real Wallet Balance** — Live USDC/MATIC from Polygon blockchain
- 📱 **Mobile Dashboard** — Responsive command center at `brobot.1nnercircle.club`
- 📬 **Telegram Alerts** — Green-themed live trade notifications
- 🔒 **Encrypted Vault** — AES-256 + PBKDF2-SHA512 credential storage
- 🛡️ **Safety Checks** — Max stake, daily loss limit, min balance, factor gates

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Git

## Quick Start

```bash
# 1. Clone
git clone https://github.com/BoitToken/brobot.git
cd brobot

# 2. Python backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 3. Frontend dashboard
cd dashboard
npm install
npm run build
cd ..

# 4. Configure
cp .env.example .env
# Edit .env with your keys (see Configuration below)

# 5. Database
createdb polyedge
python3 scripts/setup_db.py

# 6. Run
uvicorn src.main:app --host 0.0.0.0 --port 6010

# Or with PM2:
pm2 start ecosystem.config.cjs
```

Open http://localhost:6010 in your browser.

## Configuration

Copy `.env.example` to `.env` and fill in your values:

### Required
| Variable | Description |
|----------|-------------|
| `DB_URL` | PostgreSQL connection string |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

### For Live Trading (Polymarket)
| Variable | Description |
|----------|-------------|
| `WALLET_ADDRESS` | Polygon wallet address |
| `POLYMARKET_PRIVATE_KEY` | Wallet private key (hex, with 0x prefix) |
| `POLYGON_RPC_HTTP` | Polygon RPC URL (QuikNode, Alchemy, etc.) |
| `CLOB_API_KEY` | Polymarket CLOB API key |
| `CLOB_API_SECRET` | Polymarket CLOB API secret |
| `CLOB_PASSPHRASE` | Polymarket CLOB API passphrase |

### For JC Copy Trader
| Variable | Description |
|----------|-------------|
| `BYBIT_API_KEY` | Bybit API key |
| `BYBIT_API_SECRET` | Bybit API secret |
| `DISCORD_TOKEN` | Discord user token (for watching JC's server) |

### Optional
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | For AI-powered research/chat |
| `BRAVE_SEARCH_API_KEY` | For web search in research |
| `ODDS_API_KEY` | For sports betting signals |

## Trading Modes

### Paper Mode (Default)
Signals are generated and logged to database. No real money is used. Good for testing and backtesting.

```env
TRADING_MODE=paper
```

### Live Mode
Real USDC trades are executed on Polymarket via CLOB API. Safety checks enforced.

```env
TRADING_MODE=live
```

**Safety limits (configurable in `bot_settings` table):**
- Max stake: $25 per trade
- Daily loss limit: $100
- Min wallet balance: $100
- Min factors: 5/7 must agree
- Max entry price: 40¢ (ensures R:R >1.5:1 after costs)

## Strategy: V4.1 (Live-Adjusted)

BroBot's primary strategy for BTC 5-minute Polymarket windows:

| Parameter | Value | Reason |
|-----------|-------|--------|
| Max entry | 40¢ | R:R >1.5:1 after 5% execution costs |
| Min factors | 5/7 | High conviction only |
| Execution cost | 5% | 2% Polymarket fee + 3% slippage |
| Stake | $25 fixed | Appropriate for 5M window liquidity |
| Windows | 5M only | 15M too efficient (entries always 85¢+) |

### 7 Signal Factors
1. **Price Delta** — BTC price momentum direction
2. **Momentum** — Rate of change acceleration
3. **Volume Imbalance** — Buy vs sell volume ratio
4. **Oracle Lead** — Smart money positioning
5. **Book Imbalance** — Order book depth asymmetry
6. **Volatility** — Recent price volatility level
7. **Time Decay** — Time remaining in window

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service health check |
| `GET /api/wallet/balance` | Real wallet USDC + MATIC from blockchain |
| `GET /api/live/trades` | Live trade history |
| `GET /api/live/stats` | Win rate, P&L, trade count |
| `GET /api/live/today` | Today's P&L |
| `GET /api/live/positions` | Active open positions |
| `GET /api/live/weekly` | 7-day P&L summary |
| `GET /api/live/trend` | Daily P&L trend (for charts) |
| `GET /api/ghost/jc-trades` | JC copy trader trades |
| `GET /api/ghost/jc-settings` | JC trader settings |
| `GET /api/ghost/jc-pause` | Pause JC trader |
| `GET /api/ghost/jc-kill` | Close JC position |

## Project Structure

```
brobot/
├── src/
│   ├── main.py                 # FastAPI app + all schedulers
│   ├── config.py               # Configuration loader
│   ├── vault.py                # Encrypted credential vault
│   ├── polymarket_live.py      # Live Polymarket trading client
│   ├── strategies/
│   │   ├── btc_signal_engine.py    # BTC 5M signal generation
│   │   └── internal_arb.py         # Internal arbitrage scanner
│   ├── signals/
│   │   └── signal_loop.py          # Weather signal processing
│   ├── sports/
│   │   ├── polymarket_sports_scanner.py
│   │   ├── sports_signal_loop.py
│   │   └── espn_live.py
│   └── data/
│       └── city_map.py
├── dashboard/                   # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx             # Main app with routing
│   │   └── pages/
│   │       ├── Overview.jsx    # Command center (home)
│   │       ├── BTC15M.jsx      # BTC 5M trading dashboard
│   │       ├── JC.jsx          # JC copy trader + chart
│   │       ├── Markets.jsx     # Sports/weather markets
│   │       └── Performance.jsx # Analytics
│   ├── public/
│   │   └── brobot-logo.png     # App logo
│   └── package.json
├── scripts/
│   ├── setup_db.py             # Database initialization
│   └── schema.sql              # Full database schema
├── ecosystem.config.cjs         # PM2 configuration
├── start.sh                     # Startup script (with PostgreSQL check)
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
├── BROBOT.md                    # Platform documentation
├── WWJD.md                      # JC strategy guide
└── README.md                    # This file
```

## Telegram Setup

1. Message @BotFather on Telegram
2. Create a new bot: `/newbot`
3. Copy the token to `TELEGRAM_BOT_TOKEN` in `.env`
4. Get your chat ID: message @userinfobot
5. Set `TELEGRAM_CHAT_ID` in `.env`

## Polymarket Setup (for Live Trading)

1. Create a wallet on MetaMask (Polygon network)
2. Fund with USDC.e (bridged USDC on Polygon)
3. Go to https://polymarket.com and connect wallet
4. Deposit USDC.e into Polymarket exchange
5. Generate CLOB API keys in Polymarket settings
6. Add all credentials to `.env`

## Security

- **Never commit `.env`** to git (it's in `.gitignore`)
- Private keys are stored with AES-256-CBC encryption in `.vault/`
- Set `.env` permissions: `chmod 600 .env`
- CLOB API keys have rate limits (500 req/min with key, 10 without)
- All live trades are logged to `live_trades` table for audit

## PM2 (Production)

```bash
# Start
pm2 start ecosystem.config.cjs

# Monitor
pm2 monit

# Logs
pm2 logs weatherbot

# Restart
pm2 restart weatherbot

# Save for auto-recovery
pm2 save
```

## Contributing

This is a personal trading platform. Feel free to fork and adapt for your own use.

## License

MIT

---

*Powered by Claude + OpenClaw + Actual Intelligence*
