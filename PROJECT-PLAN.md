# WeatherBot — Project Plan (Master Document)
**Status:** In Development  
**Domain:** weatherbot.1nnercircle.club  
**Updated:** 2026-04-06 16:19 IST  

## Quick Links
- [PLAN.md](./PLAN.md) — Strategy & edge analysis
- [SPORTSBOT-PLAN.md](./SPORTSBOT-PLAN.md) — SportsBot plan (build after weather)
- [SHARED-BACKEND.md](./SHARED-BACKEND.md) — PolyEdge shared backend architecture

## Infrastructure
- **VPS:** 187.77.189.126 (existing Hostinger)
- **Database:** PostgreSQL localhost:5432, database: polyedge
- **Process:** PM2 `weatherbot` service
- **Dashboard:** weatherbot.1nnercircle.club (React + Vite)
- **Alerts:** Telegram bot
- **Mode:** Paper trading first → live after 2-week validation

## Build Agents (Sprint Allocation)
- **Agent 1:** Data Layer — METAR/TAF fetcher, parser, trend calculator, city mapping, DB schema
- **Agent 2:** Signal Engine — Polymarket scanner, market matcher, Gaussian model, Claude analyzer
- **Agent 3:** Dashboard + Alerts — React dashboard, Telegram bot, PM2 config, nginx setup

## Operating Costs
- Claude API: ~$21/month
- Everything else: $0 (free data, existing VPS)
- Trading capital: $500-2000 USDC on Polygon (Fatman to fund)
