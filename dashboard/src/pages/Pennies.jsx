import React, { useState, useEffect, useCallback } from 'react'

const API = ''

function StatCard({ icon, label, value, sub, color = '#FFD700' }) {
  return (
    <div style={{
      background: '#111118', borderRadius: 12, padding: '20px 24px',
      border: '1px solid #1e1e2e', flex: '1 1 200px', minWidth: 180,
    }}>
      <div style={{ fontSize: 28, marginBottom: 4 }}>{icon}</div>
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ color, fontSize: 24, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function PriceTag({ price }) {
  const cents = (price * 100).toFixed(0)
  let color = '#EAB308'  // yellow for 3¢
  if (price <= 0.01) color = '#FFD700'      // bright gold for 1¢
  else if (price <= 0.02) color = '#F59E0B'  // amber for 2¢
  return (
    <span style={{
      color, fontWeight: 700, fontSize: 14,
      background: `${color}15`, padding: '2px 8px', borderRadius: 6,
    }}>
      {cents}¢
    </span>
  )
}

function StatusBadge({ status }) {
  const map = {
    open: { icon: '🟢', label: 'Open', color: '#22c55e' },
    won: { icon: '💰', label: 'Won', color: '#FFD700' },
    lost: { icon: '💀', label: 'Dead', color: '#ef4444' },
    bouncing: { icon: '📈', label: 'Bouncing', color: '#3b82f6' },
  }
  const s = map[status] || { icon: '⚪', label: status, color: '#94a3b8' }
  return (
    <span style={{
      color: s.color, fontSize: 12, fontWeight: 600,
      background: `${s.color}15`, padding: '2px 10px', borderRadius: 12,
    }}>
      {s.icon} {s.label}
    </span>
  )
}

function ScoreBar({ score }) {
  const pct = Math.min(score / 10 * 100, 100)
  const color = score >= 8 ? '#FFD700' : score >= 5 ? '#F59E0B' : '#EAB308'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 60, height: 6, background: '#1e1e2e', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ color, fontSize: 12, fontWeight: 600 }}>{score.toFixed(0)}</span>
    </div>
  )
}

export default function Pennies() {
  const [stats, setStats] = useState(null)
  const [positions, setPositions] = useState([])
  const [scanResults, setScanResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('positions')

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, posRes, scanRes] = await Promise.all([
        fetch(`${API}/api/penny/stats`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/penny/positions?limit=200`).then(r => r.json()).catch(() => ({ positions: [] })),
        fetch(`${API}/api/penny/scan`).then(r => r.json()).catch(() => null),
      ])
      if (statsRes) setStats(statsRes)
      if (posRes?.positions) setPositions(posRes.positions)
      if (scanRes) setScanResults(scanRes)
    } catch (e) {
      console.error('Penny fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [fetchData])

  const openPositions = positions.filter(p => p.status === 'open' || p.status === 'bouncing')
  const resolvedPositions = positions.filter(p => p.status === 'won' || p.status === 'lost')

  return (
    <div style={{ padding: '24px 32px', background: '#0a0a0f', minHeight: '100vh', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#FFD700' }}>
          🎰 Penny Hunter
        </h1>
        <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: 14 }}>
          1-3¢ contracts with asymmetric upside • Paper trading
          {stats?.last_scan && (
            <span style={{ marginLeft: 12, color: '#475569' }}>
              Last scan: {new Date(stats.last_scan).toLocaleTimeString()}
            </span>
          )}
        </p>
      </div>

      {/* Stats Bar */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 28 }}>
        <StatCard
          icon="🎰" label="Active Bets"
          value={stats ? stats.open_positions : '—'}
          sub={stats ? `$${stats.total_invested?.toFixed(2)} invested` : ''}
        />
        <StatCard
          icon="💰" label="Total P&L"
          value={stats ? `$${stats.total_pnl?.toFixed(2)}` : '—'}
          sub={stats ? `${stats.roi?.toFixed(1)}% ROI` : ''}
          color={stats && stats.total_pnl >= 0 ? '#22c55e' : '#ef4444'}
        />
        <StatCard
          icon="🎯" label="Hit Rate"
          value={stats ? `${stats.hit_rate?.toFixed(1)}%` : '—'}
          sub={stats ? `${stats.wins}W / ${stats.losses}L` : ''}
        />
        <StatCard
          icon="🏆" label="Best Win"
          value={stats && stats.best_win > 0 ? `$${stats.best_win?.toFixed(2)}` : '—'}
          sub={stats && stats.best_multiplier > 0 ? `${stats.best_multiplier}x return` : ''}
        />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid #1e1e2e' }}>
        {[
          { key: 'positions', label: `Active (${openPositions.length})`, icon: '🟢' },
          { key: 'scan', label: `Available (${scanResults?.total_found || 0})`, icon: '🔍' },
          { key: 'history', label: `History (${resolvedPositions.length})`, icon: '📜' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: 'none', border: 'none', color: activeTab === tab.key ? '#FFD700' : '#64748b',
              padding: '10px 20px', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              borderBottom: activeTab === tab.key ? '2px solid #FFD700' : '2px solid transparent',
              transition: 'all 0.2s',
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🎰</div>
          Loading penny positions...
        </div>
      ) : activeTab === 'positions' ? (
        <PositionsTable positions={openPositions} />
      ) : activeTab === 'scan' ? (
        <ScanResults data={scanResults} />
      ) : (
        <HistoryTable positions={resolvedPositions} />
      )}
    </div>
  )
}

function PositionsTable({ positions }) {
  if (positions.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>🎰</div>
        No active penny positions yet. Scanner runs every 30 minutes.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #1e1e2e' }}>
            {['Market', 'Price', 'Potential', 'Catalyst', 'Days Left', 'Size', 'Status'].map(h => (
              <th key={h} style={{
                padding: '10px 12px', textAlign: 'left', color: '#64748b',
                fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map(p => (
            <tr key={p.id} style={{ borderBottom: '1px solid #111118' }}>
              <td style={{ padding: '12px', maxWidth: 300 }}>
                <div style={{ fontWeight: 500, fontSize: 13, color: '#e2e8f0', lineHeight: 1.3 }}>
                  {p.question?.substring(0, 70)}{p.question?.length > 70 ? '...' : ''}
                </div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                  {p.category} • {p.outcome}
                </div>
              </td>
              <td style={{ padding: '12px' }}><PriceTag price={p.buy_price} /></td>
              <td style={{ padding: '12px', color: '#FFD700', fontWeight: 600, fontSize: 14 }}>
                {p.buy_price > 0 ? `${(1/p.buy_price).toFixed(0)}x` : '—'}
              </td>
              <td style={{ padding: '12px' }}>
                <ScoreBar score={p.catalyst_score} />
                <div style={{ fontSize: 10, color: '#475569', marginTop: 2, maxWidth: 160 }}>
                  {p.catalyst_reason?.substring(0, 50)}
                </div>
              </td>
              <td style={{ padding: '12px', color: '#94a3b8', fontSize: 13 }}>
                {p.days_to_resolution != null ? `${p.days_to_resolution}d` : '—'}
              </td>
              <td style={{ padding: '12px', color: '#94a3b8', fontSize: 13 }}>
                ${p.size_usd?.toFixed(2)}
              </td>
              <td style={{ padding: '12px' }}><StatusBadge status={p.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ScanResults({ data }) {
  if (!data || !data.contracts || data.contracts.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>🔍</div>
        No scan results yet. Trigger a scan or wait for the next scheduled run.
      </div>
    )
  }

  return (
    <div>
      <div style={{ marginBottom: 16, color: '#94a3b8', fontSize: 13 }}>
        Found <span style={{ color: '#FFD700', fontWeight: 700 }}>{data.total_found}</span> penny contracts •{' '}
        <span style={{ color: '#22c55e', fontWeight: 700 }}>{data.would_buy}</span> would buy (score ≥ 3)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
        {data.contracts.slice(0, 20).map((c, i) => (
          <div key={i} style={{
            background: '#111118', borderRadius: 10, padding: 16,
            border: c.would_buy ? '1px solid #FFD70040' : '1px solid #1e1e2e',
          }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#e2e8f0', marginBottom: 8, lineHeight: 1.3 }}>
              {c.question?.substring(0, 80)}{c.question?.length > 80 ? '...' : ''}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <PriceTag price={c.buy_price} />
              <span style={{ color: '#FFD700', fontWeight: 700, fontSize: 16 }}>{c.potential_return}</span>
            </div>
            <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#64748b' }}>
              <span>{c.category}</span>
              <span>•</span>
              <span>{c.outcome}</span>
              {c.days_to_resolution != null && <><span>•</span><span>{c.days_to_resolution}d</span></>}
              {c.volume_usd > 0 && <><span>•</span><span>${(c.volume_usd/1000).toFixed(0)}K vol</span></>}
            </div>
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <ScoreBar score={c.catalyst_score} />
              {c.would_buy && (
                <span style={{
                  fontSize: 10, fontWeight: 700, color: '#22c55e',
                  background: '#22c55e15', padding: '2px 8px', borderRadius: 8,
                }}>
                  ✅ WOULD BUY
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HistoryTable({ positions }) {
  if (positions.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 48, color: '#64748b' }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>📜</div>
        No resolved penny positions yet.
      </div>
    )
  }

  const totalInvested = positions.reduce((s, p) => s + (p.size_usd || 0), 0)
  const totalPnl = positions.reduce((s, p) => s + (p.pnl_usd || 0), 0)
  const totalReturned = totalInvested + totalPnl

  return (
    <div>
      {/* Summary */}
      <div style={{
        display: 'flex', gap: 24, marginBottom: 20, padding: '12px 16px',
        background: '#111118', borderRadius: 10, fontSize: 13,
      }}>
        <span style={{ color: '#94a3b8' }}>Invested: <b style={{ color: '#e2e8f0' }}>${totalInvested.toFixed(2)}</b></span>
        <span style={{ color: '#94a3b8' }}>Returned: <b style={{ color: '#e2e8f0' }}>${totalReturned.toFixed(2)}</b></span>
        <span style={{ color: '#94a3b8' }}>Net P&L:{' '}
          <b style={{ color: totalPnl >= 0 ? '#22c55e' : '#ef4444' }}>${totalPnl.toFixed(2)}</b>
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e1e2e' }}>
              {['Market', 'Price', 'Size', 'P&L', 'Result', 'Resolved'].map(h => (
                <th key={h} style={{
                  padding: '10px 12px', textAlign: 'left', color: '#64748b',
                  fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr key={p.id} style={{ borderBottom: '1px solid #111118' }}>
                <td style={{ padding: '10px 12px', maxWidth: 280 }}>
                  <div style={{ fontSize: 13, color: '#e2e8f0' }}>
                    {p.question?.substring(0, 60)}{p.question?.length > 60 ? '...' : ''}
                  </div>
                </td>
                <td style={{ padding: '10px 12px' }}><PriceTag price={p.buy_price} /></td>
                <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 13 }}>${p.size_usd?.toFixed(2)}</td>
                <td style={{
                  padding: '10px 12px', fontWeight: 700, fontSize: 14,
                  color: (p.pnl_usd || 0) >= 0 ? '#22c55e' : '#ef4444',
                }}>
                  ${(p.pnl_usd || 0).toFixed(2)}
                </td>
                <td style={{ padding: '10px 12px' }}><StatusBadge status={p.status} /></td>
                <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                  {p.resolved_at ? new Date(p.resolved_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
