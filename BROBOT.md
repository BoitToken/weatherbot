# BroBot — Fatman's Personal Bot Controller

## Overview
BroBot is Fatman's personal multi-strategy trading bot platform. Each tab controls a different trading strategy. The Home tab shows overall financial metrics across all bots.

## Architecture
- **URL:** brobot.1nnercircle.club
- **Backend:** FastAPI on port 6010, DB: polyedge
- **Wallet:** 0xb9BEa5FDe7957709D0f8d2064188B1603b74D5Ca (Polygon)
- **Funding:** $998.27 USDC + 50 MATIC

## Tabs / Strategies

### JC Desk (Jayson Casper Copy Trader)
- Copies BTC support/resistance levels from Jayson Casper's Discord
- Bybit futures (paper mode, ready for live)
- WWJD strategy system for stop-out response
- Manual override controls (TP/SL, kill, pause, add margin)

### ₿ BTC 5M (Bitcoin 5-Minute Arbitrage)
- Polymarket BTC UP/DOWN 5-minute windows
- V4 strategy: 7-factor signal analysis
- LIVE trading with real USDC on Polygon
- Safety: max $25/trade, 5/7 factors required, <50¢ entry

### Home (Command Center)
- Overall financial metrics across ALL bots
- Which bots are LIVE vs PAUSED
- Total bankroll (real wallet balance from blockchain)
- Today's P&L, 7-day P&L, active positions
- Bot status indicators (running/paused/error)

### Markets
- Sports betting signals
- Weather market predictions

### Performance
- Historical analytics
- Win rates, ROI, trade history

## Live Trading
- Mode: LIVE (paper notifications OFF)
- Wallet balance checked from Polygon blockchain every 30s
- Safety limits: $25 max/trade, $50 daily loss limit, $100 min balance
- All trades recorded in live_trades table with TX hashes

## Telegram Alerts
- @ArbitrageBihariBot — BTC 5M live trade alerts (green theme)
- @BTCJaysonCasperBot — JC copy trade alerts
- Paper notifications: DISABLED
