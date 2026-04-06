# WeatherBot Dashboard — Component Hierarchy

## Navigation Structure (4 Tabs)

```
┌─────────────────────────────────────────────────────────────┐
│  WeatherBot Dashboard                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 🏠 Home  │  │ 📊 Markets│  │ 💰 Trades│  │ ⚙️ Settings│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│      (1)           (2)            (3)           (4)        │
└─────────────────────────────────────────────────────────────┘
```

---

## Tab 1: 🏠 Home
**Route:** `/`  
**Component:** `Overview.jsx`

```
Overview
├── Bot Status Card
│   └── Running/Paused indicator
├── Bankroll Metrics (3 cards)
│   ├── Total Bankroll
│   ├── Today's P&L
│   └── Active Positions
├── P&L Chart (7 days)
│   └── LineChart (recharts)
└── Active Trades Table
```

---

## Tab 2: 📊 Markets
**Route:** `/markets` or `/markets/:industry`  
**Component:** `Markets.jsx`

### Industry Sub-Tabs (Horizontal Scroll)
```
Markets
├── Sub-Tab: 📊 All
│   └── <Explorer />
│       ├── Search & Category Filters
│       ├── Market Cards Grid
│       │   ├── YES/NO price bars
│       │   ├── Volume & End Date
│       │   └── View Detail button
│       └── Load More button
│
├── Sub-Tab: 🌡️ Weather
│   ├── <Intelligence />
│   │   ├── Summary Bar (Total/Actionable/Arbitrage)
│   │   ├── Filter Chips (All/Strong Buy/Buy/Watch/Arbitrage)
│   │   ├── Signal Cards Grid
│   │   │   ├── Signal badge (Strong Buy/Buy/Watch/Skip)
│   │   │   ├── METAR data (temp, trend, forecast)
│   │   │   ├── Probability analysis
│   │   │   ├── Edge calculation
│   │   │   └── Execute Trade button
│   │   ├── Station Data Convergence Table
│   │   │   └── Click → Station Detail Modal
│   │   └── 8-Gate Intelligence System overview
│   │
│   └── <METAR />
│       ├── Live METAR readings
│       └── Raw observation data
│
├── Sub-Tab: 🏆 Sports
│   └── <SportsIntelligence />
│       ├── Tabs: Overview/Arbitrage/Live/Signals
│       ├── Sport Filter Chips (NHL/NBA/Soccer/etc.)
│       ├── Sport Summary Cards
│       ├── Market Groups — Sum Analysis
│       ├── Arbitrage Opportunities
│       ├── Live Games Feed
│       └── Sports Trading Signals
│
├── Sub-Tab: ₿ Crypto
│   └── <FilteredExplorer category="crypto" />
│       ├── Search input
│       └── Crypto-filtered market cards
│
├── Sub-Tab: 🏛️ Politics
│   └── <FilteredExplorer category="politics" />
│
├── Sub-Tab: 🎬 Entertainment
│   └── <FilteredExplorer category="entertainment" />
│
└── Sub-Tab: ⚙️ Custom
    └── <FilteredExplorer category="custom" />
```

---

## Tab 3: 💰 Trades (Performance Dashboard)
**Route:** `/trades`  
**Component:** `Trades.jsx`

```
Trades Dashboard
├── Section 1: Performance Summary (6 cards)
│   ├── Total P&L (with ROI %)
│   ├── Win Rate (with circular progress)
│   ├── Active Positions
│   ├── Total Trades
│   ├── Best Trade
│   └── Worst Trade
│
├── Section 2: Cumulative P&L Chart
│   ├── Time Range Toggle (7d/30d/all)
│   ├── LineChart (recharts)
│   │   ├── Purple cumulative P&L line
│   │   └── Trade markers (green=win, red=loss)
│   └── Empty State (if 0 trades)
│
├── Section 3: Strategy Comparison Table
│   ├── Columns: Name | Trades | Win Rate | Avg Edge | P&L | Sharpe | Status
│   ├── Rows:
│   │   ├── Forecast Edge (A)
│   │   ├── 8-Gate Intelligence (B)
│   │   ├── Cross-Odds Sports
│   │   ├── Correlation Arb
│   │   └── Live Momentum
│   └── Toggle Enable/Disable button
│
└── Section 4: Recent Trades Feed
    ├── Filter Chips: All/Open/Won/Lost + Strategy buttons
    ├── Desktop View: Table
    │   └── Columns: Time | Market | Direction | Entry | Current | Edge | P&L | Strategy
    ├── Mobile View: Cards
    │   ├── Trade Card
    │   │   ├── Timestamp + Status badge
    │   │   ├── Market title
    │   │   ├── Direction/Entry/Current/Edge (2x2 grid)
    │   │   └── Strategy + P&L
    │   └── Color-coded background (green/red tint)
    └── Auto-refresh every 30s
```

---

## Tab 4: ⚙️ Settings
**Route:** `/settings`  
**Component:** `Settings.jsx`

```
Settings
├── Bot Configuration
├── API Keys
├── Strategy Parameters
└── Risk Management
```

---

## Responsive Behavior

### Desktop (>768px)
```
┌────────────────────────────────────────────────────┐
│ Sidebar (left, fixed)                              │
│ ┌──────────────┐                                   │
│ │ WeatherBot   │  Main Content Area                │
│ ├──────────────┤  (max-width: 1600px, padded)      │
│ │ 🏠 Home      │                                    │
│ │ 📊 Markets   │  [Page content here]              │
│ │ 💰 Trades    │                                    │
│ │ ⚙️ Settings  │                                    │
│ └──────────────┘                                   │
└────────────────────────────────────────────────────┘
```

### Mobile (<768px)
```
┌────────────────────────────────────────────────────┐
│ Main Content (full-width, padding-bottom: 80px)   │
│                                                    │
│  [Page content here]                               │
│  [Stacked cards, full-width charts]               │
│  [Tables → Cards]                                  │
│                                                    │
├────────────────────────────────────────────────────┤
│ Bottom Navigation (fixed, 70px height)            │
│  ┌────────┬────────┬────────┬────────┐           │
│  │ 🏠     │ 📊     │ 💰     │ ⚙️     │           │
│  │ Home   │Markets │ Trades │Settings│           │
│  └────────┴────────┴────────┴────────┘           │
└────────────────────────────────────────────────────┘
```

---

## Component Reuse Strategy

### Old Pages → Embedded Components
- `Explorer.jsx` → Used in Markets → All tab
- `Intelligence.jsx` → Used in Markets → Weather tab
- `SportsIntelligence.jsx` → Used in Markets → Sports tab
- `METAR.jsx` → Used in Markets → Weather tab

### New Wrapper Components
- `Markets.jsx` → Orchestrates industry tabs + embeds old components
- `Trades.jsx` → Completely new performance dashboard

### Unchanged
- `Overview.jsx` → Standalone Home page
- `Settings.jsx` → Standalone Settings page

---

## Data Flow

### Auto-Refresh Pattern
```
Component Mount
    ↓
fetchData()  ← setInterval(fetchData, 30000)
    ↓
API Calls (parallel with Promise.all)
    ├→ /api/bot/status
    ├→ /api/trades
    ├→ /api/analytics/win-rate
    ├→ /api/pnl/daily
    └→ /api/strategy/comparison
    ↓
setState()
    ↓
Re-render UI
```

### User Actions
```
User clicks filter/toggle
    ↓
onClick handler
    ↓
setState() or API call
    ↓
Re-render or fetchData()
```

---

## Style Inheritance

### Global Styles (`App.css`)
- `.card`, `.card-grid`, `.card-value`, `.card-title`
- `.btn`, `.btn-primary`, `.btn-secondary`
- `.table-container`, `table`, `th`, `td`
- `.badge`, `.status-indicator`
- `.empty-state`, `.loading`
- Mobile media queries

### Page-Specific Styles
- `Explorer.css` → Markets page, industry tabs, market cards
- `Intelligence.css` → Signal cards, filters, station tables
- `Settings.css` → Form elements, config sections

---

## Accessibility

### Mobile Touch Targets
- Bottom nav tabs: **70px height** (44px minimum)
- Buttons: **44px+ min-height** on mobile
- Filter chips: **32px+ height**

### Color Contrast
- Text on dark: WCAG AA compliant
- Success/Error colors: High contrast
- Focus states: Purple accent border

### Keyboard Navigation
- All interactive elements focusable
- Tab order: logical left-to-right, top-to-bottom
- Enter/Space triggers buttons

---

## Performance

### Bundle Size
- Total JS: **679 KB** (205 KB gzipped)
- Total CSS: **24 KB** (5 KB gzipped)
- HTML: **0.5 KB**

### Optimization Opportunities (future)
- Code splitting by route
- Lazy load charts library
- Image optimization (if added)
- Service worker caching

### API Call Efficiency
- Parallel fetching with `Promise.all`
- 30s refresh interval (not real-time)
- Debounced search inputs
- Pagination for large lists

---

**Last Updated:** 2026-04-07  
**Build Status:** ✅ Production Ready
