import { useState, useEffect, useCallback } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

/* ── Position Drill-Down Modal ────────────────────────────── */
function PositionDrillDown({ positions, onClose }) {
  if (!positions || positions.length === 0) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(12px)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      overflowY: 'auto', padding: '24px 16px'
    }} onClick={onClose}>
      <div style={{ width: '100%', maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 20
        }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#fff' }}>
            📈 Active Positions ({positions.length})
          </h2>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 18, width: 36, height: 36, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>✕</button>
        </div>

        {positions.map((trade, idx) => {
          const entryPct = ((trade.entry_price || 0) * 100).toFixed(0)
          return (
            <div key={trade.id || idx} style={{
              background: 'linear-gradient(135deg, #1a1a2e 0%, #16162a 100%)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderLeft: '4px solid #10b981',
              borderRadius: 14, padding: 20, marginBottom: 14,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
                  📊 BTC 5M
                </span>
                <span style={{
                  padding: '5px 14px', borderRadius: 8, fontSize: 13, fontWeight: 800,
                  background: trade.side === 'UP' || trade.prediction === 'UP' ? 'rgba(16,185,129,0.18)' : 'rgba(239,68,68,0.18)',
                  color: trade.side === 'UP' || trade.prediction === 'UP' ? '#10B981' : '#EF4444'
                }}>
                  {trade.prediction || trade.side || 'UP'}
                </span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', marginBottom: 14, lineHeight: 1.4 }}>
                {trade.window_id || 'BTC 5-Minute Window'}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 20px' }}>
                <div>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Entry</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#fff' }}>{entryPct}¢</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Stake</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#fff' }}>${(trade.stake_usd || 0).toFixed(2)}</div>
                </div>
              </div>
              {trade.tx_hash && (
                <div style={{ marginTop: 10, fontSize: 11, color: '#475569' }}>
                  TX: {trade.tx_hash.substring(0, 16)}...
                </div>
              )}
            </div>
          )
        })}

        <div style={{
          background: 'linear-gradient(135deg, #1a1a2e 0%, #0f0f1e 100%)',
          border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: 14, padding: '16px 20px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Total Deployed</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>
              ${positions.reduce((s, t) => s + (t.stake_usd || 0), 0).toFixed(2)}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Positions</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#10b981' }}>{positions.length}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Bot List ────────────────────────────── */
const BOTS = [
  { name: "BTC 5M", status: "live", icon: "📊", description: "Polymarket BTC arbitrage" },
  { name: "JC Copy Trader", status: "paper", icon: "👻", description: "Jayson Casper levels" },
  { name: "Pennies", status: "paused", icon: "🎰", description: "Penny stock scanner" },
  { name: "Leader Copy", status: "paused", icon: "🎯", description: "Top trader copy system" },
  { name: "Weather Markets", status: "paused", icon: "🌤️", description: "Weather prediction markets" },
  { name: "Sports Markets", status: "paused", icon: "🏆", description: "Sports betting signals" },
]

const statusBadge = (status) => {
  const map = {
    live: { bg: 'rgba(16,185,129,0.15)', color: '#10b981', label: '🟢 LIVE' },
    paper: { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', label: '📝 Paper' },
    paused: { bg: 'rgba(100,116,139,0.15)', color: '#94a3b8', label: '⏸ Paused' },
  }
  const s = map[status] || map.paused
  return (
    <span style={{
      padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
      background: s.bg, color: s.color, whiteSpace: 'nowrap'
    }}>{s.label}</span>
  )
}

/* ── Styles ────────────────────────────── */
const styles = {
  card: {
    background: '#12121a',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: '18px 20px',
  },
  cardTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: 8,
  },
  cardValue: {
    fontSize: 28,
    fontWeight: 800,
    color: '#fff',
    lineHeight: 1.2,
  },
  cardLabel: {
    fontSize: 13,
    color: '#94a3b8',
    marginTop: 4,
  },
  green: { color: '#10b981' },
  red: { color: '#ef4444' },
}

function Overview() {
  const [health, setHealth] = useState(null)
  const [wallet, setWallet] = useState(null)
  const [todayPnl, setTodayPnl] = useState(null)
  const [positions, setPositions] = useState(null)
  const [weeklyPnl, setWeeklyPnl] = useState(null)
  const [trend, setTrend] = useState([])
  const [liveTrades, setLiveTrades] = useState([])
  const [showPositions, setShowPositions] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchFast = useCallback(async () => {
    try {
      const [healthRes, walletRes, posRes] = await Promise.all([
        fetch('/api/health').then(r => r.json()).catch(() => null),
        fetch('/api/wallet/balance').then(r => r.json()).catch(() => null),
        fetch('/api/live/positions').then(r => r.json()).catch(() => null),
      ])
      setHealth(healthRes)
      setWallet(walletRes)
      setPositions(posRes)
    } catch (e) { console.error('Fast fetch error:', e) }
  }, [])

  const fetchMedium = useCallback(async () => {
    try {
      const [todayRes, weeklyRes, tradesRes] = await Promise.all([
        fetch('/api/live/today').then(r => r.json()).catch(() => null),
        fetch('/api/live/weekly').then(r => r.json()).catch(() => null),
        fetch('/api/live/trades').then(r => r.json()).catch(() => null),
      ])
      setTodayPnl(todayRes)
      setWeeklyPnl(weeklyRes)
      if (tradesRes?.trades) {
        setLiveTrades(tradesRes.trades.filter(t => t.status === 'open'))
      }
    } catch (e) { console.error('Medium fetch error:', e) }
  }, [])

  const fetchSlow = useCallback(async () => {
    try {
      const trendRes = await fetch('/api/live/trend').then(r => r.json()).catch(() => [])
      setTrend(trendRes)
    } catch (e) { console.error('Slow fetch error:', e) }
  }, [])

  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchFast(), fetchMedium(), fetchSlow()])
      setLoading(false)
    }
    init()

    const fastInterval = setInterval(fetchFast, 30000)     // 30s
    const mediumInterval = setInterval(fetchMedium, 60000)  // 60s
    const slowInterval = setInterval(fetchSlow, 300000)     // 5min

    return () => {
      clearInterval(fastInterval)
      clearInterval(mediumInterval)
      clearInterval(slowInterval)
    }
  }, [fetchFast, fetchMedium, fetchSlow])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', color: '#94a3b8' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Loading command center...</div>
        </div>
      </div>
    )
  }

  const pnlToday = todayPnl?.pnl || 0
  const pnlWeekly = weeklyPnl?.pnl || 0
  const posCount = positions?.count || 0
  const deployed = positions?.deployed || 0
  const usdc = wallet?.usdc || 0
  const matic = wallet?.matic || 0
  const isRunning = health?.scheduler || health?.status === 'healthy'

  const chartData = (trend || []).map(d => ({
    date: new Date(d.day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    pnl: d.pnl,
    trades: d.trades,
  }))

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#fff', margin: '0 0 6px 0' }}>Overview</h1>
        <p style={{ fontSize: 14, color: '#64748b', margin: 0 }}>Real-time bot status and performance</p>
      </div>

      {/* Bot Status Card */}
      <div style={{ ...styles.card, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={styles.cardTitle}>Bot Status</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: isRunning ? '#10b981' : '#ef4444',
              boxShadow: isRunning ? '0 0 8px rgba(16,185,129,0.5)' : '0 0 8px rgba(239,68,68,0.5)',
            }} />
            <span style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
              {isRunning ? 'Running' : 'Paused'}
            </span>
          </div>
        </div>
        <div style={{ fontSize: 13, color: '#94a3b8', textAlign: 'right' }}>
          <div>Mode: <strong style={{ color: '#10b981' }}>live</strong></div>
          {health?.last_data_scan && (
            <div>Last scan: {new Date(health.last_data_scan).toLocaleTimeString()}</div>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 14,
        marginBottom: 20,
      }}>
        {/* Total Bankroll */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>Total Bankroll</div>
          <div style={styles.cardValue}>${usdc.toFixed(2)}</div>
          <div style={styles.cardLabel}>
            {matic > 0 && <span>{matic.toFixed(2)} MATIC</span>}
          </div>
        </div>

        {/* Today's P&L */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>Today's P&L</div>
          <div style={{ ...styles.cardValue, color: pnlToday >= 0 ? '#10b981' : '#ef4444' }}>
            {pnlToday >= 0 ? '+' : ''}${pnlToday.toFixed(2)}
          </div>
          <div style={styles.cardLabel}>
            {pnlToday >= 0 ? '📈 Profitable' : '📉 Loss'} • {todayPnl?.trades || 0} trades
          </div>
        </div>

        {/* Active Positions */}
        <div
          style={{ ...styles.card, cursor: posCount > 0 ? 'pointer' : 'default', transition: 'border-color 0.2s' }}
          onClick={() => posCount > 0 && liveTrades.length > 0 && setShowPositions(true)}
        >
          <div style={{ ...styles.cardTitle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Active Positions
            {posCount > 0 && <span style={{ fontSize: 11, color: '#10b981', fontWeight: 600 }}>TAP TO VIEW →</span>}
          </div>
          <div style={styles.cardValue}>{posCount}</div>
          <div style={styles.cardLabel}>${deployed.toFixed(2)} deployed</div>
        </div>

        {/* 7-Day P&L */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>7-Day P&L</div>
          <div style={{ ...styles.cardValue, color: pnlWeekly >= 0 ? '#10b981' : '#ef4444' }}>
            {pnlWeekly >= 0 ? '+' : ''}${pnlWeekly.toFixed(2)}
          </div>
          <div style={styles.cardLabel}>{weeklyPnl?.trades || 0} trades</div>
        </div>
      </div>

      {/* 7-Day P&L Trend */}
      {chartData.length > 0 && (
        <div style={{ ...styles.card, marginBottom: 20 }}>
          <div style={{ ...styles.cardTitle, marginBottom: 16 }}>7-Day P&L Trend</div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="#475569" style={{ fontSize: 11 }} />
              <YAxis stroke="#475569" style={{ fontSize: 11 }} tickFormatter={v => `$${v}`} />
              <Tooltip
                contentStyle={{
                  background: '#1a1a2e',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  color: '#fff',
                  fontSize: 13,
                }}
                formatter={(value) => [`$${value.toFixed(2)}`, 'P&L']}
              />
              <Area type="monotone" dataKey="pnl" stroke="#10b981" strokeWidth={2} fill="url(#pnlGradient)" dot={{ fill: '#10b981', r: 4, strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bot List */}
      <div style={{ ...styles.card, marginBottom: 20 }}>
        <div style={{ ...styles.cardTitle, marginBottom: 16 }}>Active Bots</div>
        {BOTS.map((bot, idx) => (
          <div key={idx} style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '14px 0',
            borderTop: idx > 0 ? '1px solid rgba(255,255,255,0.04)' : 'none',
          }}>
            <span style={{ fontSize: 28 }}>{bot.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>{bot.name}</div>
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{bot.description}</div>
            </div>
            {statusBadge(bot.status)}
          </div>
        ))}
      </div>

      {/* Live Trade Stats */}
      {(todayPnl?.trades > 0 || weeklyPnl?.trades > 0) && (
        <div style={{ ...styles.card, marginBottom: 20 }}>
          <div style={{ ...styles.cardTitle, marginBottom: 16 }}>Live Trading Summary</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Today Wins</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#10b981' }}>{todayPnl?.wins || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Today Trades</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>{todayPnl?.trades || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>7D Trades</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>{weeklyPnl?.trades || 0}</div>
            </div>
          </div>
        </div>
      )}

      {/* Position Drill-Down Modal */}
      {showPositions && (
        <PositionDrillDown positions={liveTrades} onClose={() => setShowPositions(false)} />
      )}
    </div>
  )
}

export default Overview
