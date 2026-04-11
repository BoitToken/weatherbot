import React, { useState, useEffect, useCallback } from 'react'

const API = '/api/tradebook'

const BOT_TABS = [
  { key: 'All', label: 'All' },
  { key: 'BTC Paper', label: '🤖 BTC' },
  { key: 'BTC Live', label: '⚡ Live' },
  { key: 'JC Copy', label: '👻 JC' },
  { key: 'Sports', label: '🏏 Sports' },
  { key: 'Scalper', label: '⏱️ Scalper' },
  { key: 'Maker', label: '🏗️ Maker' },
]

const COLS = [
  { key: 'idx', label: '#', sortable: false, mobile: true },
  { key: 'bot', label: 'Bot', sortable: true, mobile: false },
  { key: 'timestamp', label: 'Time', sortable: true, mobile: true },
  { key: 'direction', label: 'Dir', sortable: false, mobile: true },
  { key: 'entry_price', label: 'Entry', sortable: true, mobile: false },
  { key: 'stake', label: 'Stake', sortable: true, mobile: false },
  { key: 'gross_pnl', label: 'Gross P&L', sortable: true, mobile: false },
  { key: 'fees', label: 'Fees', sortable: false, mobile: false },
  { key: 'net_pnl', label: 'Net P&L', sortable: true, mobile: true },
  { key: 'outcome', label: 'Result', sortable: false, mobile: true },
]

function fmt(val, prefix = '$') {
  if (val == null || val === '') return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return val
  return `${prefix}${n.toFixed(2)}`
}

function fmtPnl(val) {
  if (val == null) return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  const sign = n >= 0 ? '+' : ''
  return `${sign}$${n.toFixed(2)}`
}

function fmtTime(ts) {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    return d.toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
  } catch {
    return ts
  }
}

function OutcomeIcon({ outcome, pnl }) {
  if (!outcome) return <span style={{ color: '#94a3b8' }}>—</span>
  const o = outcome.toLowerCase()
  if (['won', 'win', 'correct', 'filled'].includes(o) || (pnl && pnl > 0)) return <span>✅</span>
  if (['lost', 'loss', 'wrong', 'liquidated'].includes(o) || (pnl && pnl < 0)) return <span>❌</span>
  if (['open', 'active', 'pending'].includes(o)) return <span style={{ fontSize: 12 }}>🔄</span>
  if (['failed'].includes(o)) return <span style={{ fontSize: 12 }}>⚠️</span>
  if (['closed'].includes(o) && pnl != null) return pnl >= 0 ? <span>✅</span> : <span>❌</span>
  return <span style={{ color: '#94a3b8', fontSize: 12 }}>{outcome}</span>
}

function SummaryCard({ label, value, sub, color }) {
  return (
    <div style={{
      background: '#111118',
      border: '1px solid #1e1e2e',
      borderRadius: 10,
      padding: '14px 18px',
      minWidth: 130,
      flex: '1 1 130px',
    }}>
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ color: color || '#e2e8f0', fontSize: 20, fontWeight: 700, fontFamily: 'monospace' }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function Tradebook() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeBot, setActiveBot] = useState('All')
  const [sortKey, setSortKey] = useState('timestamp')
  const [sortDir, setSortDir] = useState('desc')
  const [exporting, setExporting] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: 2000 })
      if (activeBot !== 'All') params.set('bot', activeBot)
      const res = await fetch(`${API}?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [activeBot])

  useEffect(() => {
    setLoading(true)
    fetchData()
  }, [fetchData])

  useEffect(() => {
    const iv = setInterval(fetchData, 30000)
    return () => clearInterval(iv)
  }, [fetchData])

  const handleSort = (key) => {
    if (!key) return
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetch('/api/tradebook/export')
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tradebook-${new Date().toISOString().slice(0, 10)}.xlsx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Export failed: ' + e.message)
    } finally {
      setExporting(false)
    }
  }

  const trades = data?.trades || []
  const summary = data?.summary || {}

  // Sort
  const sorted = [...trades].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey]
    if (av == null) av = ''
    if (bv == null) bv = ''
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDir === 'asc' ? av - bv : bv - av
    }
    return sortDir === 'asc'
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })

  // Running totals
  const runningPnl = summary.total_net_pnl || 0
  const totalW = summary.won || 0
  const totalL = summary.lost || 0

  const s = {
    page: { minHeight: '100vh', background: '#0a0a0f', padding: '24px 20px', fontFamily: 'system-ui, sans-serif' },
    header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 },
    title: { color: '#e2e8f0', fontSize: 22, fontWeight: 700 },
    exportBtn: {
      background: exporting ? '#4c1d95' : '#7c3aed',
      color: '#fff', border: 'none', borderRadius: 8,
      padding: '8px 18px', cursor: exporting ? 'not-allowed' : 'pointer',
      fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6
    },
    cards: { display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 24 },
    tabBar: { display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' },
    tableWrap: { overflowX: 'auto', borderRadius: 10, border: '1px solid #1e1e2e' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
    th: (active) => ({
      background: '#111118', color: active ? '#a78bfa' : '#94a3b8',
      padding: '10px 12px', textAlign: 'left', fontWeight: 600,
      borderBottom: '1px solid #1e1e2e', cursor: 'pointer', userSelect: 'none',
      whiteSpace: 'nowrap'
    }),
    td: { padding: '9px 12px', borderBottom: '1px solid #0f0f17', color: '#e2e8f0' },
    footer: {
      marginTop: 16, background: '#111118', border: '1px solid #1e1e2e',
      borderRadius: 10, padding: '12px 18px', display: 'flex', gap: 24,
      alignItems: 'center', flexWrap: 'wrap'
    }
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div style={s.title}>📒 TRADEBOOK</div>
        <button style={s.exportBtn} onClick={handleExport} disabled={exporting}>
          {exporting ? '⏳' : '⬇'} {exporting ? 'Exporting...' : 'Export XLSX'}
        </button>
      </div>

      {/* Summary Cards */}
      <div style={s.cards}>
        <SummaryCard label="Total Trades" value={summary.total_trades ?? '—'} />
        <SummaryCard label="Total Staked" value={summary.total_staked != null ? `$${summary.total_staked.toFixed(2)}` : '—'} />
        <SummaryCard
          label="Net P&L"
          value={runningPnl >= 0 ? `+$${runningPnl.toFixed(2)}` : `-$${Math.abs(runningPnl).toFixed(2)}`}
          color={runningPnl >= 0 ? '#22c55e' : '#ef4444'}
        />
        <SummaryCard
          label="Win Rate"
          value={summary.win_rate != null ? `${summary.win_rate}%` : '—'}
          color={summary.win_rate >= 50 ? '#22c55e' : '#ef4444'}
          sub={`${totalW}W — ${totalL}L`}
        />
        <SummaryCard
          label="Best Trade"
          value={summary.best_trade ? fmtPnl(summary.best_trade) : '—'}
          color="#22c55e"
          sub={summary.best_trade_bot}
        />
        <SummaryCard
          label="Worst Trade"
          value={summary.worst_trade ? fmtPnl(summary.worst_trade) : '—'}
          color="#ef4444"
          sub={summary.worst_trade_bot}
        />
      </div>

      {/* Bot Tabs */}
      <div style={s.tabBar}>
        {BOT_TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveBot(tab.key)}
            style={{
              background: activeBot === tab.key ? '#7c3aed' : '#111118',
              border: `1px solid ${activeBot === tab.key ? '#7c3aed' : '#1e1e2e'}`,
              color: activeBot === tab.key ? '#fff' : '#94a3b8',
              borderRadius: 8, padding: '6px 14px', cursor: 'pointer',
              fontWeight: activeBot === tab.key ? 600 : 400, fontSize: 13
            }}
          >
            {tab.label}
            {summary.by_bot?.[tab.key] && (
              <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.7 }}>
                {summary.by_bot[tab.key].trades}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ color: '#94a3b8', padding: 40, textAlign: 'center' }}>Loading trades...</div>
      ) : error ? (
        <div style={{ color: '#ef4444', padding: 40, textAlign: 'center' }}>Error: {error}</div>
      ) : (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr>
                {COLS.map(col => (
                  <th
                    key={col.key}
                    style={{
                      ...s.th(sortKey === col.key),
                      display: col.mobile ? '' : undefined,
                    }}
                    onClick={() => col.sortable && handleSort(col.key)}
                    className={col.mobile ? '' : 'hide-mobile'}
                  >
                    {col.label}
                    {col.sortable && sortKey === col.key && (
                      <span style={{ marginLeft: 4 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={COLS.length} style={{ ...s.td, textAlign: 'center', color: '#94a3b8', padding: 32 }}>
                    No trades found for this filter
                  </td>
                </tr>
              ) : sorted.map((t, i) => {
                const pnl = t.net_pnl || 0
                const isProfit = pnl >= 0
                return (
                  <tr key={`${t.bot}-${t.trade_id}-${i}`} style={{ background: i % 2 === 0 ? '#0d0d14' : '#0a0a0f' }}>
                    <td style={s.td}>{i + 1}</td>
                    <td style={{ ...s.td, color: '#a78bfa', fontWeight: 600 }} className="hide-mobile">{t.bot}</td>
                    <td style={{ ...s.td, color: '#94a3b8', fontSize: 12 }}>{fmtTime(t.timestamp)}</td>
                    <td style={{
                      ...s.td, fontWeight: 600, fontSize: 12,
                      color: (() => {
                        const d = (t.direction || '').toUpperCase()
                        if (d === 'UP' || d === 'LONG') return '#22c55e'
                        if (d === 'DOWN' || d === 'SHORT') return '#ef4444'
                        return '#a78bfa'  // Sports team names, etc.
                      })()
                    }}>
                      {t.direction || '—'}
                    </td>
                    <td style={{ ...s.td, fontFamily: 'monospace' }} className="hide-mobile">
                      {t.entry_price != null ? parseFloat(t.entry_price).toFixed(4) : '—'}
                    </td>
                    <td style={{ ...s.td, fontFamily: 'monospace' }} className="hide-mobile">{fmt(t.stake)}</td>
                    <td style={{ ...s.td, fontFamily: 'monospace', color: isProfit ? '#22c55e' : '#ef4444' }} className="hide-mobile">
                      {fmtPnl(t.gross_pnl)}
                    </td>
                    <td style={{ ...s.td, color: '#64748b', fontFamily: 'monospace' }} className="hide-mobile">
                      {fmt(t.fees)}
                    </td>
                    <td style={{ ...s.td, fontFamily: 'monospace', fontWeight: 700, color: isProfit ? '#22c55e' : '#ef4444' }}>
                      {fmtPnl(t.net_pnl)}
                    </td>
                    <td style={s.td}><OutcomeIcon outcome={t.outcome} pnl={t.net_pnl} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Running Total Footer */}
      {!loading && !error && (
        <div style={s.footer}>
          <span style={{ color: '#94a3b8', fontSize: 13 }}>Running Total:</span>
          <span style={{ color: runningPnl >= 0 ? '#22c55e' : '#ef4444', fontFamily: 'monospace', fontWeight: 700, fontSize: 16 }}>
            {runningPnl >= 0 ? '+' : ''}{runningPnl.toFixed(2)}
          </span>
          <span style={{ color: '#94a3b8', fontSize: 13 }}>|</span>
          <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: 13 }}>
            {totalW}W–{totalL}L
          </span>
          {summary.win_rate != null && (
            <span style={{ color: summary.win_rate >= 50 ? '#22c55e' : '#ef4444', fontSize: 13 }}>
              ({summary.win_rate}%)
            </span>
          )}
          <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: 11 }}>
            Auto-refreshes every 30s
          </span>
        </div>
      )}

      <style>{`
        @media (max-width: 640px) {
          .hide-mobile { display: none !important; }
        }
      `}</style>
    </div>
  )
}
