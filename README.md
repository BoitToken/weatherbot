# PolyEdge — Polymarket Arbitrage Bot Suite 🎯

> Multiple bots exploiting data advantages across Polymarket categories

**Repo:** BoitToken/weatherbot  
**Status:** Planning → Build → Paper Trade → Live  

## Bots

| Bot | Category | Edge Source | Priority |
|-----|----------|-----------|----------|
| 🏀 **SportsBot** | Sports (0% fees!) | Sportsbook odds lag + injury news | #1 Build First |
| 🌦️ **WeatherBot** | Weather | Aviation METAR sensor data | #2 |
| 📈 CryptoBot | Crypto | Black-Scholes vs market price | #3 |
| 🏛️ MacroBot | Economics | Fed/CPI data release lag | #4 |
| 🎮 EsportsBot | Esports | Pinnacle odds lag | #5 |

## Docs

| Document | Description |
|----------|-------------|
| [SPORTSBOT-PLAN.md](./SPORTSBOT-PLAN.md) | SportsBot: odds arb, news alpha, de-vig engine |
| [PLAN.md](./PLAN.md) | WeatherBot: METAR/TAF aviation data strategy |
| [SHARED-BACKEND.md](./SHARED-BACKEND.md) | PolyEdge shared backend: risk manager, execution, learning engine, DB schema |

## The Thesis

Professional data sources (sportsbook odds, airport sensors, CME futures) are more accurate than Polymarket crowd pricing. When they diverge, the professional source is right. A bot that reads professional data and trades Polymarket before the crowd catches up prints money.

## Proven Results (Inspiration)
- **ColdMath** — $101K profit betting on weather using aviation data
- **Swisstony** — $3.7M profit on sports using sportsbook odds arbitrage

## Stack
Python · FastAPI · PostgreSQL · Claude AI · Polymarket CLOB · React · Polygon/USDC

---
*Status: Planning Phase — 2026-04-06*
