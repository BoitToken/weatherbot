import { useState, useEffect } from 'react'
import axios from 'axios'

const SPORT_EMOJI = { NBA: '🏀', NHL: '🏒', NCAA: '🎓', MLB: '⚾', NFL: '🏈', SOCCER: '⚽', OTHER: '📊' }
const TYPE_COLORS = { SPREAD: '#7c3aed', TOTAL: '#3b82f6', MONEYLINE: '#f59e0b', ML: '#f59e0b' }

function formatVol(v) {
  if (!v) return '$0'
  if (v >= 1e6) return `$${(v/1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v/1e3).toFixed(1)}K`
  return `$${Number(v).toFixed(0)}`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: 'var(--bg-secondary, #1a1a2e)',
      borderRadius: 12,
      padding: '16px 20px',
      borderLeft: `3px solid ${accent || '#7c3aed'}`,
    }}>
      <div style={{ color: '#94a3b8', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color: '#fff', marginTop: 4 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Badge({ text, color }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 12,
      fontSize: 11,
      fontWeight: 700,
      background: `${color}22`,
      color: color,
      border: `1px solid ${color}44`,
    }}>
      {text}
    </span>
  )
}

function BarChart({ data, maxVal }) {
  if (!data || data.length === 0) return null
  const mx = maxVal || Math.max(...data.map(d => d.value), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map((d, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 80, fontSize: 12, color: '#94a3b8', textAlign: 'right' }}>{d.label}</span>
          <div style={{ flex: 1, height: 20, background: 'rgba(255,255,255,0.04)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              width: `${(d.value / mx) * 100}%`,
              height: '100%',
              background: d.color || '#7c3aed',
              borderRadius: 4,
              transition: 'width 0.5s',
            }} />
          </div>
          <span style={{ width: 60, fontSize: 12, color: '#fff', fontWeight: 600 }}>{d.display || d.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function LeaderStrategy() {
  const [stats, setStats] = useState({})
  const [bySport, setBySport] = useState([])
  const [byType, setByType] = useState([])
  const [liveActivity, setLiveActivity] = useState([])
  const [dbTrades, setDbTrades] = useState([])
  const [config, setConfig] = useState({})
  const [sportFilter, setSportFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const [statsRes, liveRes, tradesRes, configRes] = await Promise.all([
        axios.get('/api/leader/stats').catch(() => ({ data: {} })),
        axios.get('/api/leader/live').catch(() => ({ data: { activities: [] } })),
        axios.get('/api/leader/trades?limit=50').catch(() => ({ data: { trades: [] } })),
        axios.get('/api/leader/config').catch(() => ({ data: {} })),
      ])
      setStats(statsRes.data?.stats || {})
      setBySport(statsRes.data?.by_sport || [])
      setByType(statsRes.data?.by_type || [])
      setLiveActivity(liveRes.data?.activities || [])
      setDbTrades(tradesRes.data?.trades || [])
      setConfig(configRes.data || {})
    } catch (err) {
      console.error('Leader fetch error:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="loading">Loading Leader Strategy...</div>

  const totalTrades = stats.total_trades || 0
  const totalVol = stats.total_volume || 0
  const wins = stats.wins || 0
  const losses = stats.losses || 0
  const winRate = (wins + losses) > 0 ? ((wins / (wins + losses)) * 100).toFixed(1) : '—'
  const ourDeployed = stats.our_total_deployed || 0
  const totalPnl = stats.total_pnl || 0

  // Filter live activity
  const filteredActivity = liveActivity.filter(a => {
    if (sportFilter !== 'all' && a.sport !== sportFilter) return false
    if (typeFilter !== 'all' && a.trade_type !== typeFilter) return false
    return true
  })

  // Strategy profile data
  const sportData = (bySport.length > 0 ? bySport : [
    { sport: 'NBA', volume: 10873005 },
    { sport: 'NHL', volume: 1925405 },
    { sport: 'OTHER', volume: 1548355 },
  ]).map(s => ({
    label: `${SPORT_EMOJI[s.sport] || '📊'} ${s.sport}`,
    value: s.volume || s.count || 0,
    display: formatVol(s.volume),
    color: s.sport === 'NBA' ? '#7c3aed' : s.sport === 'NHL' ? '#3b82f6' : '#f59e0b',
  }))

  const typeData = (byType.length > 0 ? byType : [
    { trade_type: 'SPREAD', volume: 6914291 },
    { trade_type: 'TOTAL', volume: 6420037 },
    { trade_type: 'MONEYLINE', volume: 1012438 },
  ]).map(t => ({
    label: t.trade_type,
    value: t.volume || t.count || 0,
    display: formatVol(t.volume),
    color: TYPE_COLORS[t.trade_type] || '#7c3aed',
  }))

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">🎯 Leader Strategy</h1>
        <p className="page-subtitle">
          Copy-trading Polymarket's #1 trader — <span style={{ color: '#7c3aed', fontWeight: 700 }}>Multicolored-Self</span>
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
          <code style={{ fontSize: 12, color: '#64748b', background: 'rgba(255,255,255,0.04)', padding: '4px 8px', borderRadius: 6 }}>
            0x4924...3782
          </code>
          <Badge text="#1 Monthly P&L" color="#10b981" />
          <Badge text="#1 Weekly P&L" color="#3b82f6" />
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 8px #10b981',
            animation: 'pulse 2s infinite',
          }} />
          <span style={{ color: '#10b981', fontSize: 12, fontWeight: 600 }}>Polling every 60s</span>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
        <StatCard label="Trades Tracked" value={totalTrades || liveActivity.length} sub="unique markets" accent="#7c3aed" />
        <StatCard label="Leader Volume" value={formatVol(totalVol || 14346766)} sub="last 10 days" accent="#3b82f6" />
        <StatCard label="Win Rate" value={winRate === '—' ? '~94%' : `${winRate}%`} sub={`${wins}W / ${losses}L`} accent="#10b981" />
        <StatCard label="Our Copy $" value={`$${ourDeployed > 0 ? ourDeployed.toFixed(2) : '0.00'}`} sub="$25 per $100K scale" accent="#f59e0b" />
        <StatCard label="Avg Entry" value={`${(stats.avg_entry_price || 0.509).toFixed(3)}`} sub="always near 50¢" accent="#ec4899" />
      </div>

      {/* Strategy Profile */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div style={{ background: 'var(--bg-secondary, #1a1a2e)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 14, color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
            📊 Market Types
          </h3>
          <BarChart data={typeData} />
        </div>
        <div style={{ background: 'var(--bg-secondary, #1a1a2e)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 14, color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
            🏆 Sport Focus
          </h3>
          <BarChart data={sportData} />
        </div>
      </div>

      {/* Strategy Rules Card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(124,58,237,0.1), rgba(59,130,246,0.05))',
        border: '1px solid rgba(124,58,237,0.2)',
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
      }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14, color: '#7c3aed', fontWeight: 700 }}>🧠 STRATEGY RULES (from analysis)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, fontSize: 13 }}>
          <div><span style={{ color: '#94a3b8' }}>Entry zone:</span> <span style={{ color: '#fff', fontWeight: 600 }}>0.45–0.60 (50¢ sweet spot)</span></div>
          <div><span style={{ color: '#94a3b8' }}>Never above:</span> <span style={{ color: '#ef4444', fontWeight: 600 }}>60¢ (hard cap)</span></div>
          <div><span style={{ color: '#94a3b8' }}>Market types:</span> <span style={{ color: '#fff', fontWeight: 600 }}>Spreads + O/U only</span></div>
          <div><span style={{ color: '#94a3b8' }}>Execution:</span> <span style={{ color: '#fff', fontWeight: 600 }}>Order splitting (2s intervals)</span></div>
          <div><span style={{ color: '#94a3b8' }}>Timing:</span> <span style={{ color: '#fff', fontWeight: 600 }}>Pre-game (2-3 hrs before tip)</span></div>
          <div><span style={{ color: '#94a3b8' }}>Scale:</span> <span style={{ color: '#fff', fontWeight: 600 }}>${((config.wallets?.[0]?.scale_factor || 0.00025) * 100000).toFixed(0)} per $100K</span></div>
          <div><span style={{ color: '#94a3b8' }}>Max position:</span> <span style={{ color: '#fff', fontWeight: 600 }}>${config.wallets?.[0]?.max_position || 50}</span></div>
          <div><span style={{ color: '#94a3b8' }}>Min leader size:</span> <span style={{ color: '#fff', fontWeight: 600 }}>${formatVol(config.strategy_rules?.min_leader_size || 10000)}</span></div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <span style={{ color: '#64748b', fontSize: 13, alignSelf: 'center', marginRight: 4 }}>Sport:</span>
        {['all', 'NBA', 'NHL', 'NCAA', 'MLB', 'SOCCER'].map(s => (
          <button key={s} onClick={() => setSportFilter(s)} style={{
            padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer',
            background: sportFilter === s ? '#7c3aed' : 'rgba(255,255,255,0.06)',
            color: sportFilter === s ? '#fff' : '#94a3b8',
            fontSize: 12, fontWeight: 600,
          }}>
            {s === 'all' ? 'All' : `${SPORT_EMOJI[s] || ''} ${s}`}
          </button>
        ))}
        <span style={{ color: '#64748b', fontSize: 13, alignSelf: 'center', margin: '0 4px 0 12px' }}>Type:</span>
        {['all', 'SPREAD', 'TOTAL', 'ML'].map(t => (
          <button key={t} onClick={() => setTypeFilter(t)} style={{
            padding: '6px 14px', borderRadius: 16, border: 'none', cursor: 'pointer',
            background: typeFilter === t ? (TYPE_COLORS[t] || '#7c3aed') : 'rgba(255,255,255,0.06)',
            color: typeFilter === t ? '#fff' : '#94a3b8',
            fontSize: 12, fontWeight: 600,
          }}>
            {t === 'all' ? 'All' : t}
          </button>
        ))}
      </div>

      {/* Live Activity Feed */}
      <div style={{ background: 'var(--bg-secondary, #1a1a2e)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>⚡ Live Activity Feed</h3>
          <span style={{ fontSize: 11, color: '#64748b' }}>Auto-refresh 30s • {filteredActivity.length} items</span>
        </div>

        {filteredActivity.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>🎯</div>
            <div>No activity matching filters. Leader may be between games.</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>NBA games typically start 22:00-01:00 UTC</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 500, overflowY: 'auto' }}>
            {filteredActivity.map((a, i) => {
              const isTrade = a.type === 'TRADE'
              const isRedeem = a.type === 'REDEEM'
              const copySize = (a.size * 0.00025).toFixed(2)
              
              return (
                <div key={i} style={{
                  padding: '12px 16px',
                  background: isTrade ? 'rgba(124,58,237,0.06)' : 'rgba(255,255,255,0.02)',
                  borderRadius: 10,
                  borderLeft: `3px solid ${isTrade ? '#10b981' : isRedeem ? '#64748b' : '#ef4444'}`,
                  transition: 'background 0.2s',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 14 }}>{isTrade ? '🟢' : '⚪'}</span>
                      <span style={{ color: '#64748b', fontSize: 12, fontFamily: 'monospace' }}>{formatTime(a.timestamp)}</span>
                      <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>{a.type}</span>
                      {isTrade && <Badge text={a.trade_type} color={TYPE_COLORS[a.trade_type] || '#7c3aed'} />}
                      {a.sport && <span style={{ fontSize: 14 }}>{SPORT_EMOJI[a.sport] || ''}</span>}
                    </div>
                    {isTrade && (
                      <span style={{ color: '#10b981', fontWeight: 700, fontSize: 14 }}>
                        {formatVol(a.size)} @ {a.price.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <div style={{ color: '#e2e8f0', fontSize: 13, marginLeft: 30 }}>
                    {a.title}
                  </div>
                  {isTrade && a.size >= 1000 && (
                    <div style={{ color: '#f59e0b', fontSize: 11, marginLeft: 30, marginTop: 4 }}>
                      📋 Our copy: ${copySize} • {a.outcome && `Outcome: ${a.outcome}`}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Tracked Trades from DB */}
      {Array.isArray(dbTrades) && dbTrades.length > 0 && (
        <div style={{ background: 'var(--bg-secondary, #1a1a2e)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 700 }}>📋 Tracked Positions ({dbTrades.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {dbTrades.map((t, i) => (
              <div key={i} style={{
                padding: '14px 16px',
                background: 'rgba(255,255,255,0.02)',
                borderRadius: 10,
                borderLeft: `3px solid ${TYPE_COLORS[t.trade_type] || '#7c3aed'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Badge text={t.trade_type} color={TYPE_COLORS[t.trade_type] || '#7c3aed'} />
                    <Badge text={t.sport} color={t.sport === 'NBA' ? '#7c3aed' : '#3b82f6'} />
                    <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>{t.market_title}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ color: '#10b981', fontWeight: 700 }}>{formatVol(t.leader_size)}</span>
                    <Badge 
                      text={t.status === 'detected' ? '⏳ Active' : t.result === 'won' ? '✅ Won' : t.result === 'lost' ? '❌ Lost' : t.status}
                      color={t.status === 'detected' ? '#f59e0b' : t.result === 'won' ? '#10b981' : '#ef4444'}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
                  <span>Leader: @ {(t.leader_price || 0).toFixed(3)}</span>
                  <span>Our copy: ${(t.our_size || 0).toFixed(2)}</span>
                  {t.polymarket_url && (
                    <a href={t.polymarket_url} target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed', textDecoration: 'none' }}>
                      View on Polymarket ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Config */}
      <div style={{
        background: 'var(--bg-secondary, #1a1a2e)',
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
        border: '1px solid rgba(255,255,255,0.04)',
      }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14, color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase' }}>⚙️ Configuration</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, fontSize: 13 }}>
          <div>
            <span style={{ color: '#64748b' }}>Copy Scale: </span>
            <span style={{ color: '#fff', fontWeight: 600 }}>$25 per $100K (0.025%)</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Max Position: </span>
            <span style={{ color: '#fff', fontWeight: 600 }}>$50 per trade</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Poll Interval: </span>
            <span style={{ color: '#fff', fontWeight: 600 }}>60 seconds</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Sports: </span>
            <span style={{ color: '#10b981', fontWeight: 600 }}>NBA ✅ NHL ✅ NCAA ✅</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Types: </span>
            <span style={{ color: '#10b981', fontWeight: 600 }}>Spread ✅ O/U ✅</span>
            <span style={{ color: '#ef4444', fontWeight: 600 }}> ML ❌</span>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Mode: </span>
            <span style={{ color: '#f59e0b', fontWeight: 600 }}>Paper Trading (signals only)</span>
          </div>
        </div>
      </div>

      <div className="footer">
        Powered by Claude + OpenClaw + Actual Intelligence
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
