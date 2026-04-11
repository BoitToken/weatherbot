import React, { useState, useEffect, useCallback, useRef } from 'react'

const API = ''

function StatCard({ icon, label, value, sub, color = '#7c3aed' }) {
  return (
    <div style={{
      background: '#111118', borderRadius: 12, padding: '20px 24px',
      border: '1px solid #1e1e2e', flex: '1 1 180px', minWidth: 160,
    }}>
      <div style={{ fontSize: 26, marginBottom: 4 }}>{icon}</div>
      <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ color, fontSize: 22, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function PnlBadge({ pnl }) {
  if (pnl == null) return <span style={{ color: '#64748b' }}>—</span>
  const pos = pnl >= 0
  return (
    <span style={{
      color: pos ? '#22c55e' : '#ef4444',
      fontWeight: 700,
      background: pos ? '#22c55e18' : '#ef444418',
      padding: '2px 8px', borderRadius: 6, fontSize: 13,
    }}>
      {pos ? '+' : ''}{Number(pnl).toFixed(2)}
    </span>
  )
}

function OutcomeBadge({ outcome }) {
  const map = {
    won: { label: '✅ Won', color: '#22c55e' },
    lost: { label: '❌ Lost', color: '#ef4444' },
    pending: { label: '⏳ Pending', color: '#f59e0b' },
  }
  const s = map[outcome] || { label: outcome, color: '#94a3b8' }
  return (
    <span style={{
      color: s.color, fontSize: 12, fontWeight: 600,
      background: `${s.color}18`, padding: '2px 10px', borderRadius: 10,
    }}>
      {s.label}
    </span>
  )
}

function DirectionBadge({ direction }) {
  const isUp = direction === 'UP'
  return (
    <span style={{
      color: isUp ? '#22c55e' : '#ef4444',
      fontWeight: 700, fontSize: 13,
      background: isUp ? '#22c55e18' : '#ef444418',
      padding: '2px 10px', borderRadius: 8,
    }}>
      {isUp ? '⬆️ UP' : '⬇️ DOWN'}
    </span>
  )
}

function CountdownRing({ seconds, max = 300 }) {
  const pct = Math.max(0, Math.min(1, seconds / max))
  const inScalpZone = seconds <= 20 && seconds > 5
  const veryClose = seconds <= 5
  const size = 120
  const r = 48
  const circ = 2 * Math.PI * r
  const stroke = circ * (1 - pct)
  const color = veryClose ? '#ef4444' : inScalpZone ? '#f59e0b' : '#7c3aed'

  return (
    <div style={{ textAlign: 'center', position: 'relative', display: 'inline-block' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e1e2e" strokeWidth={8} />
        <circle
          cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={8}
          strokeDasharray={circ}
          strokeDashoffset={stroke}
          style={{ transition: 'stroke-dashoffset 0.5s, stroke 0.3s' }}
        />
      </svg>
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        color: inScalpZone || veryClose ? color : '#e2e8f0',
        fontSize: 22, fontWeight: 800,
        animation: inScalpZone ? 'pulse 1s infinite' : 'none',
      }}>
        {seconds}s
      </div>
    </div>
  )
}

function fmt(val, decimals = 2) {
  if (val == null) return '—'
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function timeAgo(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  const diff = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function LastMinute() {
  const [status, setStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [countdown, setCountdown] = useState(null)
  const [toggling, setToggling] = useState(false)
  const intervalRef = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, statsRes, tradesRes] = await Promise.all([
        fetch(`${API}/api/late-window/status`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/late-window/stats`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/late-window/trades?limit=50`).then(r => r.json()).catch(() => ({ trades: [] })),
      ])
      if (statusRes) setStatus(statusRes)
      if (statsRes) setStats(statsRes)
      if (tradesRes?.trades) setTrades(tradesRes.trades)
    } catch (e) {
      console.error('LastMinute fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // Live countdown ticker
  useEffect(() => {
    const tick = () => {
      if (status?.next_window_epoch) {
        const now = Math.floor(Date.now() / 1000)
        const rem = Math.max(0, status.next_window_epoch - now)
        setCountdown(rem)
      }
    }
    tick()
    intervalRef.current = setInterval(tick, 500)
    return () => clearInterval(intervalRef.current)
  }, [status?.next_window_epoch])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 3000)
    return () => clearInterval(id)
  }, [fetchData])

  const handleToggle = async () => {
    setToggling(true)
    try {
      await fetch(`${API}/api/late-window/toggle`, { method: 'POST' })
      await fetchData()
    } catch (e) {
      console.error('Toggle error:', e)
    } finally {
      setToggling(false)
    }
  }

  const displayCountdown = countdown !== null ? countdown : (status?.seconds_to_next_window || 0)
  const inScalpZone = displayCountdown <= 20 && displayCountdown > 5
  const veryClose = displayCountdown <= 5

  return (
    <div style={{ padding: '24px', background: '#0a0a0f', minHeight: '100vh', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes scalp-alert {
          0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
          70% { box-shadow: 0 0 0 20px rgba(239,68,68,0); }
          100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
        }
      `}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: '#e2e8f0' }}>
            ⏱️ Last Minute Scalper
          </h1>
          <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 2 }}>
            Buys near-certain BTC contracts (85-99¢) in the final 15-20s of each 5M window
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Status dot */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: '#111118', borderRadius: 8, padding: '8px 16px',
            border: `1px solid ${status?.enabled ? '#22c55e' : '#ef4444'}30`,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: status?.enabled ? '#22c55e' : '#ef4444',
              boxShadow: `0 0 8px ${status?.enabled ? '#22c55e' : '#ef4444'}`,
              animation: status?.enabled ? 'pulse 2s infinite' : 'none',
            }} />
            <span style={{ fontSize: 13, color: status?.enabled ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
              {status?.enabled ? 'RUNNING' : 'PAUSED'}
            </span>
          </div>
          <button
            onClick={handleToggle}
            disabled={toggling}
            style={{
              padding: '8px 20px', borderRadius: 8, border: 'none',
              background: status?.enabled ? '#ef444420' : '#7c3aed',
              color: status?.enabled ? '#ef4444' : '#fff',
              fontWeight: 700, cursor: 'pointer', fontSize: 13,
              border: `1px solid ${status?.enabled ? '#ef444440' : '#7c3aed'}`,
            }}
          >
            {toggling ? '...' : status?.enabled ? '⏸️ Pause' : '▶️ Start'}
          </button>
        </div>
      </div>

      {/* Countdown + BTC comparison row */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        {/* Countdown card */}
        <div style={{
          background: '#111118', borderRadius: 16, padding: '24px',
          border: `2px solid ${inScalpZone || veryClose ? '#ef4444' : '#1e1e2e'}`,
          animation: inScalpZone ? 'scalp-alert 1s infinite' : 'none',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
          minWidth: 200, flex: '0 0 auto',
        }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
            Next Window
          </div>
          <CountdownRing seconds={displayCountdown} max={300} />
          <div style={{
            color: inScalpZone ? '#f59e0b' : veryClose ? '#ef4444' : '#94a3b8',
            fontSize: 12, fontWeight: 600,
            animation: inScalpZone ? 'pulse 1s infinite' : 'none',
          }}>
            {veryClose ? '🚨 TOO LATE' : inScalpZone ? '⚡ SCALP ZONE!' : 'Waiting...'}
          </div>
        </div>

        {/* BTC price comparison */}
        <div style={{
          background: '#111118', borderRadius: 16, padding: '24px',
          border: '1px solid #1e1e2e', flex: 1, minWidth: 260,
        }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 16 }}>
            BTC Price Context
          </div>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <div style={{ color: '#64748b', fontSize: 11 }}>CURRENT</div>
              <div style={{ color: '#e2e8f0', fontSize: 24, fontWeight: 800 }}>
                ${status?.current_btc_price ? Number(status.current_btc_price).toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}
              </div>
            </div>
            {status?.current_btc_price && (
              <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                <div style={{
                  fontSize: 13, fontWeight: 700, marginBottom: 4,
                  color: '#94a3b8',
                }}>
                  vs window open
                </div>
              </div>
            )}
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 16px' }}>
              <div style={{ color: '#64748b', fontSize: 11 }}>STAKE</div>
              <div style={{ color: '#7c3aed', fontWeight: 700 }}>${status?.stake_usd || 10}</div>
            </div>
            <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 16px' }}>
              <div style={{ color: '#64748b', fontSize: 11 }}>MIN ENTRY</div>
              <div style={{ color: '#7c3aed', fontWeight: 700 }}>{((status?.min_entry_price || 0.85) * 100).toFixed(0)}¢</div>
            </div>
            <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 16px' }}>
              <div style={{ color: '#64748b', fontSize: 11 }}>SCALP ZONE</div>
              <div style={{ color: '#7c3aed', fontWeight: 700 }}>{status?.scalp_zone || '5-20s'}</div>
            </div>
            <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 16px' }}>
              <div style={{ color: '#64748b', fontSize: 11 }}>PENDING</div>
              <div style={{ color: status?.pending_trades > 0 ? '#f59e0b' : '#94a3b8', fontWeight: 700 }}>
                {status?.pending_trades || 0}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <StatCard
          icon="🎯"
          label="Win Rate Today"
          value={stats ? `${stats.win_rate_today?.toFixed(1) || 0}%` : '—'}
          sub={`${stats?.won_today || 0}W / ${(stats?.trades_today || 0) - (stats?.won_today || 0)}L today`}
          color="#22c55e"
        />
        <StatCard
          icon="💰"
          label="P&L Today"
          value={stats ? `$${(stats.total_pnl_today >= 0 ? '+' : '')}${fmt(stats.total_pnl_today)}` : '—'}
          sub={`${stats?.trades_today || 0} trades today`}
          color={stats?.total_pnl_today >= 0 ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          icon="🏆"
          label="All-Time Win Rate"
          value={stats ? `${stats.win_rate?.toFixed(1) || 0}%` : '—'}
          sub={`${stats?.total_won || 0}W / ${stats?.total_lost || 0}L total`}
          color="#7c3aed"
        />
        <StatCard
          icon="📈"
          label="Total P&L"
          value={stats ? `$${stats.total_pnl >= 0 ? '+' : ''}${fmt(stats.total_pnl)}` : '—'}
          sub={`${stats?.total_trades || 0} total trades`}
          color={stats?.total_pnl >= 0 ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          icon="🎰"
          label="Avg Entry Price"
          value={stats?.avg_entry_price ? `${(stats.avg_entry_price * 100).toFixed(1)}¢` : '—'}
          sub="Target: 85-99¢"
          color="#f59e0b"
        />
        <StatCard
          icon="🔥"
          label="Win Streak"
          value={`${status?.win_streak || 0}`}
          sub="Current streak"
          color={status?.win_streak >= 3 ? '#f59e0b' : '#94a3b8'}
        />
      </div>

      {/* Trades table */}
      <div style={{ background: '#111118', borderRadius: 16, border: '1px solid #1e1e2e', overflow: 'hidden' }}>
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #1e1e2e', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontWeight: 700, fontSize: 16 }}>Recent Trades</div>
          <div style={{ color: '#64748b', fontSize: 12 }}>{trades.length} records</div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading trades...</div>
        ) : trades.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>⏳</div>
            <div>No trades yet. Waiting for scalp opportunities...</div>
            <div style={{ fontSize: 12, marginTop: 8, color: '#475569' }}>
              Scalper activates when BTC price moves &gt;$10 in the final 15-20s of a 5M window
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#0d1117' }}>
                  {['Direction', 'Entry', 'Outcome', 'P&L', 'BTC Open', 'BTC Close', 'Secs Left', 'Time'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', color: '#64748b', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={t.id} style={{
                    borderTop: '1px solid #1e1e2e',
                    background: i % 2 === 0 ? 'transparent' : '#0d111720',
                  }}>
                    <td style={{ padding: '12px 16px' }}>
                      <DirectionBadge direction={t.direction} />
                    </td>
                    <td style={{ padding: '12px 16px', color: '#e2e8f0', fontWeight: 600 }}>
                      {t.entry_price != null ? `${(t.entry_price * 100).toFixed(0)}¢` : '—'}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <OutcomeBadge outcome={t.outcome} />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <PnlBadge pnl={t.pnl_usd} />
                    </td>
                    <td style={{ padding: '12px 16px', color: '#94a3b8' }}>
                      {t.btc_open_price ? `$${Number(t.btc_open_price).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#94a3b8' }}>
                      {t.btc_close_price ? `$${Number(t.btc_close_price).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b' }}>
                      {t.seconds_remaining != null ? `${t.seconds_remaining}s` : '—'}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b' }}>
                      {timeAgo(t.traded_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
