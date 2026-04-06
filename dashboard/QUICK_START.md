# WeatherBot Dashboard — Quick Start Guide

## 🚀 What Changed?

**OLD:** 8 cramped tabs at the bottom  
**NEW:** 4 spacious tabs + industry sub-navigation

---

## 📱 New Navigation (Bottom Tabs)

```
┌─────────┬─────────┬─────────┬─────────┐
│ 🏠 Home │📊Markets│💰 Trades│⚙️Settings│
└─────────┴─────────┴─────────┴─────────┘
```

---

## 🏠 Home Tab
**What you see:** Bot status, bankroll, today's P&L, active trades  
**Use it for:** Quick health check

---

## 📊 Markets Tab
**What you see:** Industry tabs at the top

```
📊 All | 🌡️ Weather | 🏆 Sports | ₿ Crypto | 🏛️ Politics | 🎬 Entertainment | ⚙️ Custom
```

### 🌡️ Weather Intelligence
- **Live signals** with STRONG BUY / BUY / WATCH tags
- **8-Gate system** showing METAR + forecast + historical convergence
- **Execute Trade** button (paper trades)
- **Station detail:** Click any station to see 5-year historical data

### 🏆 Sports Intelligence
- **Market groups** with sum analysis (overpriced = arbitrage)
- **Live games** feed (ESPN integration)
- **Cross-odds** signals
- **Arbitrage opportunities** highlighted in red

### 📊 All / Other Industries
- Search & filter Polymarket markets
- View YES/NO prices, volume, liquidity
- Category-based filtering

---

## 💰 Trades Tab (NEW Performance Dashboard)

### Top Cards
```
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Total P&L│ Win Rate │ Active   │ Total    │ Best     │ Worst    │
│ +$245.67 │  67.2%   │ Positions│ Trades   │ Trade    │ Trade    │
│ +12.3%ROI│ 🟢●●●○○  │    3     │   45     │ +$89.23  │ -$23.45  │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### P&L Chart
- **Purple line:** Cumulative profit/loss over time
- **Green dots:** Winning trades
- **Red dots:** Losing trades
- **Toggle:** 7 days / 30 days / All time

### Strategy Comparison
See which strategies are winning:

| Strategy | Trades | Win Rate | P&L | Status |
|----------|--------|----------|-----|--------|
| Forecast Edge (A) | 12 | 75.0% | +$156.78 | ✓ Active |
| 8-Gate Intelligence (B) | 8 | 62.5% | +$89.34 | ✓ Active |
| Cross-Odds Sports | 5 | 80.0% | +$67.23 | ✓ Active |
| Correlation Arb | 0 | — | $0.00 | ✕ Disabled |

**Click the Status badge** to enable/disable any strategy.

### Recent Trades Feed
**Filters:** All | Open | Won | Lost | [Strategy Name]

**Mobile:** Card view (one per trade)  
**Desktop:** Full table with all columns

**Color Coding:**
- 🟢 Green background = Won
- 🔴 Red background = Lost
- ⚪ White background = Open

Each trade shows:
- Time & Date
- Market title
- Direction (YES/NO)
- Entry price
- Current/Exit price
- Edge %
- P&L in USD
- Strategy used

---

## ⚙️ Settings Tab
**What you see:** Bot config, API keys, risk settings  
**Use it for:** Adjusting parameters

---

## 📲 Mobile vs Desktop

### Mobile (<768px)
- **Bottom navigation** (4 big tabs)
- **Industry tabs scroll** horizontally
- **Cards stack** in single column
- **Tables become cards** for easy reading

### Desktop (>768px)
- **Left sidebar** (fixed)
- **Industry tabs** in a row
- **Multi-column grids**
- **Tables stay as tables**

---

## 🎯 Common Tasks

### Check if bot is running
1. Tap **Home** tab
2. Look at top card: "Bot Status"
3. Green dot = Running, Red dot = Paused

### See what markets look good
1. Tap **Markets** tab
2. Tap **🌡️ Weather** sub-tab
3. Filter by "Strong Buy" or "Buy"
4. Look for high **Edge %** (e.g., +15%)

### Execute a paper trade
1. Find a signal in Markets → Weather
2. Tap **Execute Trade** button
3. Bot will paper-trade $25 (default size)
4. Trade appears in **Trades** tab

### See which strategy is best
1. Tap **Trades** tab
2. Scroll to "Strategy Comparison"
3. Sort by **Win Rate** or **P&L**
4. Toggle strategies on/off

### View only winning trades
1. Tap **Trades** tab
2. Scroll to "Recent Trades"
3. Tap **Won** filter chip
4. See green-highlighted winning trades

### Check live sports games
1. Tap **Markets** tab
2. Tap **🏆 Sports** sub-tab
3. Tap **⚡ Live** button at top
4. See scores + status (LIVE/UPCOMING)

### Find arbitrage opportunities
**Weather:**
1. Markets → Weather → Filter: "Arbitrage"
2. Look for "💰 ARBITRAGE — FREE MONEY" badge

**Sports:**
1. Markets → Sports → Tab: "Arbitrage"
2. Red-highlighted groups = overpriced (sum > 100%)

---

## 🔄 Auto-Refresh

**Everything updates every 30 seconds:**
- Bot status
- Live signals
- P&L chart
- Recent trades
- Open positions
- Strategy performance

**No need to manually refresh!** Just leave the dashboard open.

---

## 🎨 Color Guide

| Color | Meaning |
|-------|---------|
| 🟢 Green | Profitable, Won, Active, Positive |
| 🔴 Red | Loss, Paused, Negative |
| 🟡 Amber | Warning, Watch signal, Medium priority |
| 🟣 Purple | Accent, Selected, Active tab |
| ⚪ White/Gray | Neutral, Open position, Inactive |

---

## 💡 Pro Tips

### For Strategy Tuning
- Disable losing strategies in **Trades → Strategy Comparison**
- Compare **Sharpe Ratio** (higher = better risk-adjusted returns)
- Watch **Avg Edge %** — strategies with <5% edge may not be profitable after fees

### For Signal Hunting
- **Weather:** Look for 8-gate convergence (all sources agree)
- **Sports:** Focus on groups with sum > 105% (overpriced)
- **Arbitrage:** Execute immediately (free money, no prediction needed)

### For Mobile Use
- Swipe horizontally on industry tabs
- Tap once to select, tap again to scroll
- Long-press trades for details (future feature)

---

## 🐛 Troubleshooting

### "Bot is scanning markets..."
- This is normal! Wait for signals to appear
- Weather signals appear every ~5-10 minutes
- Sports signals depend on live game schedules

### Charts show no data
- Normal if bot just started
- P&L builds up over time as trades close
- Try switching to "All time" view

### Strategy shows 0 trades
- That strategy may be disabled
- Check **Status** column in Strategy Comparison
- Click to enable it

### Bottom nav not showing
- You may be on desktop (check left sidebar)
- On mobile: scroll down to bottom edge

---

## 📞 Need Help?

**Check logs:**
```bash
cd /data/.openclaw/workspace/projects/weatherbot/dashboard
npm run dev
```

**Rebuild:**
```bash
npm run build
```

**Common fixes:**
- Hard refresh: Ctrl+Shift+R (desktop) or pull-to-refresh (mobile)
- Clear cache
- Check API is running (`curl http://localhost:8000/api/bot/status`)

---

## 🎉 You're Ready!

The new dashboard gives you:
- ✅ **Clean navigation** (no more cramped tabs)
- ✅ **All industries in one place** (Markets tab)
- ✅ **Full performance analytics** (Trades tab)
- ✅ **Mobile-optimized** (bigger touch targets)
- ✅ **Real-time updates** (auto-refresh)

**Happy trading!** 🚀

---

**Last Updated:** 2026-04-07  
**Version:** 2.0 (Redesigned Navigation + Performance Dashboard)
