# WeatherBot 🌦️⚡

> Polymarket weather arbitrage using aviation METAR data + Claude AI

**Status:** Planning → Build → Paper Trade → Live  
**Edge:** Aviation sensor data vs public forecast lag  
**Inspired by:** ColdMath ($101,042 profit, 5,252 trades)

## Quick Summary

Airport weather sensors (METAR) update every 30-60 minutes with real temperature readings accurate to 0.1°C. Public forecasts lag by hours. Polymarket prices weather outcomes based on public forecasts. When real data says one thing and market prices another — that's the trade.

$25 → $12,452. On the weather.

## Docs

- **[PLAN.md](./PLAN.md)** — Full strategy, architecture, build phases, risk management

## Stack
Python · FastAPI · Claude AI · Polymarket CLOB API · React · PostgreSQL · Polygon/USDC

---
*Status: Planning Phase — 2026-04-06*
