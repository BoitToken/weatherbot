import React, { useState, useEffect, useCallback, useRef } from 'react'

const API = ''
const BTC_ORANGE = '#F7931A'
const BTC_ORANGE_DIM = '#F7931A30'

// ─── Utility Components ───

function CountdownTimer({ closeTime }) {
  const [remaining, setRemaining] = useState('')
  useEffect(() => {
    const update = () => {
      if (!closeTime) { setRemaining('--:--'); return }
      const diff = new Date(closeTime) - new Date()
      if (diff <= 0) { setRemaining('CLOSED'); return }
      const m = Math.floor(diff / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setRemaining(`${m}:${s.toString().padStart(2, '0')}`)
    }
    update()
    const iv = setInterval(update, 1000)
    return () => clearInterval(iv)
  }, [closeTime])
  const isUrgent = remaining !== 'CLOSED' && remaining !== '--:--' && (() => {
    const parts = remaining.split(':')
    return parts.length === 2 && parseInt(parts[0]) < 2
  })()
  return (
    <span style={{
      fontFamily: 'monospace', fontWeight: 700, fontSize: 16,
      color: remaining === 'CLOSED' ? '#ef4444' : isUrgent ? '#f59e0b' : '#22c55e',
    }}>
      {remaining}
    </span>
  )
}

function PredictionBadge({ prediction, probUp, size = 'normal' }) {
  const map = {
    UP: { icon: '🟢', color: '#22c55e', bg: '#22c55e18' },
    DOWN: { icon: '🔴', color: '#ef4444', bg: '#ef444418' },
    SKIP: { icon: '⏭️', color: '#94a3b8', bg: '#94a3b818' },
  }
  const s = map[prediction] || map.SKIP
  const pct = probUp != null ? `${(probUp * 100).toFixed(0)}%` : ''
  const fs = size === 'large' ? 28 : 14
  return (
    <span style={{
      color: s.color, fontWeight: 700, fontSize: fs,
      background: s.bg, padding: size === 'large' ? '8px 20px' : '3px 12px',
      borderRadius: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
    }}>
      {s.icon} {prediction} {pct && <span style={{ fontWeight: 400, fontSize: fs * 0.7 }}>{pct}</span>}
    </span>
  )
}

function FactorBar({ name, weight, value, isVolatility = false, skipActive = false }) {
  const pct = Math.abs(value) * 100
  const isPositive = value > 0.05
  const isNegative = value < -0.05
  const barColor = isVolatility
    ? (skipActive ? '#ef4444' : value > 0.5 ? '#22c55e' : '#f59e0b')
    : (isPositive ? '#22c55e' : isNegative ? '#ef4444' : '#64748b')
  const direction = isVolatility ? '' : (isPositive ? '↑' : isNegative ? '↓' : '→')

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0',
      borderBottom: '1px solid #1e1e2e',
    }}>
      <div style={{ width: 140, flexShrink: 0 }}>
        <div style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 600 }}>
          {name} <span style={{ color: '#64748b', fontWeight: 400 }}>({(weight * 100).toFixed(0)}%)</span>
        </div>
      </div>
      <div style={{ flex: 1, position: 'relative', height: 20, background: '#0f0f17', borderRadius: 6, overflow: 'hidden' }}>
        {isVolatility ? (
          <div style={{
            position: 'absolute', left: 0, top: 0, height: '100%',
            width: `${Math.min(value * 100, 100)}%`,
            background: barColor, borderRadius: 6, transition: 'width 0.3s',
          }} />
        ) : (
          <>
            <div style={{
              position: 'absolute', left: '50%', top: 0, width: 1, height: '100%',
              background: '#334155',
            }} />
            <div style={{
              position: 'absolute',
              left: value >= 0 ? '50%' : `${50 - pct / 2}%`,
              top: 2, height: 16,
              width: `${pct / 2}%`,
              background: barColor, borderRadius: 4, transition: 'all 0.3s',
              maxWidth: '49%',
            }} />
          </>
        )}
      </div>
      <div style={{ width: 50, textAlign: 'right', fontFamily: 'monospace', fontSize: 13, color: barColor, fontWeight: 600 }}>
        {direction} {value.toFixed(2)}
      </div>
      {isVolatility && skipActive && (
        <span style={{
          background: '#ef444430', color: '#ef4444', fontSize: 10, fontWeight: 700,
          padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap',
        }}>
          HARD FILTER
        </span>
      )}
    </div>
  )
}

function ResultBadge({ wasCorrect }) {
  if (wasCorrect === true) return <span style={{ color: '#22c55e', fontSize: 13, fontWeight: 600 }}>✅</span>
  if (wasCorrect === false) return <span style={{ color: '#ef4444', fontSize: 13, fontWeight: 600 }}>❌</span>
  return <span style={{ color: '#94a3b8', fontSize: 13 }}>⏳</span>
}

function WindowTypeBadge({ length }) {
  return (
    <span style={{
      background: length === 15 ? BTC_ORANGE_DIM : '#3b82f620',
      color: length === 15 ? BTC_ORANGE : '#3b82f6',
      fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
    }}>
      {length}M
    </span>
  )
}

function StatCard({ icon, label, value, sub, color = BTC_ORANGE }) {
  return (
    <div style={{
      background: '#111118', borderRadius: 12, padding: '20px 24px',
      border: '1px solid #1e1e2e', flex: '1 1 180px', minWidth: 160,
    }}>
      <div style={{ fontSize: 28, marginBottom: 4 }}>{icon}</div>
      <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ color, fontSize: 24, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

// ─── Main Page ───

export default function BTC15M() {
  const [state, setState] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedSignal, setExpandedSignal] = useState(null)
  const refreshRef = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, signalsRes] = await Promise.all([
        fetch(`${API}/api/btc/state`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/btc/signals?limit=20`).then(r => r.json()).catch(() => ({ signals: [] })),
      ])
      if (stateRes) setState(stateRes)
      if (signalsRes?.signals) setSignals(signalsRes.signals)
    } catch (e) {
      console.error('BTC data fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    refreshRef.current = setInterval(fetchData, 10000)
    return () => clearInterval(refreshRef.current)
  }, [fetchData])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', color: '#94a3b8' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>₿</div>
          <div>Loading BTC Signal Engine...</div>
        </div>
      </div>
    )
  }

  const price = state?.btc_price || 0
  const change24h = state?.btc_change_24h || 0
  const accuracy = state?.accuracy || {}
  const weights = state?.weights || {}
  const windows = state?.active_windows || []
  
  // Find the most recent active window with a signal
  const activeWindow = windows.find(w => w.prediction && new Date(w.close_time) > new Date()) || windows[0]
  const factors = activeWindow?.factors || {}
  const volSkip = factors.volatility != null && factors.volatility === 0

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ color: '#fff', fontSize: 28, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: BTC_ORANGE }}>₿</span> BTC Signal Engine
            <span style={{ fontSize: 12, color: '#64748b', fontWeight: 400, background: '#1e1e2e', padding: '3px 10px', borderRadius: 8 }}>
              PAPER MODE
            </span>
          </h1>
          <div style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
            7-factor prediction model • 15-minute windows • Phase 0
          </div>
        </div>
        <div style={{ textAlign: 'right', color: '#64748b', fontSize: 12 }}>
          Auto-refresh: 10s<br />
          Last: {state?.timestamp ? new Date(state.timestamp).toLocaleTimeString() : '--'}
        </div>
      </div>

      {/* ── Hero Section ── */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 28, flexWrap: 'wrap' }}>
        {/* BTC Price */}
        <div style={{
          background: '#111118', borderRadius: 16, padding: 28,
          border: `1px solid ${BTC_ORANGE}40`, flex: '2 1 300px', minWidth: 280,
        }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
            BTC / USD
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span style={{ color: '#fff', fontSize: 42, fontWeight: 700, fontFamily: 'monospace' }}>
              ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span style={{
              color: change24h >= 0 ? '#22c55e' : '#ef4444',
              fontSize: 18, fontWeight: 600,
            }}>
              {change24h >= 0 ? '▲' : '▼'} {Math.abs(change24h).toFixed(2)}%
            </span>
          </div>
          <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>
            24h Range: ${state?.btc_low?.toLocaleString() || '--'} — ${state?.btc_high?.toLocaleString() || '--'}
          </div>
        </div>

        {/* Current Window + Prediction */}
        <div style={{
          background: '#111118', borderRadius: 16, padding: 28,
          border: '1px solid #1e1e2e', flex: '1 1 250px', minWidth: 220,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          {activeWindow ? (
            <>
              <div style={{ color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
                Active Window ({activeWindow.window_length}M)
              </div>
              <CountdownTimer closeTime={activeWindow.close_time} />
              <div style={{ marginTop: 12 }}>
                <PredictionBadge prediction={activeWindow.prediction || 'SKIP'} probUp={activeWindow.prob_up} size="large" />
              </div>
              {activeWindow.confidence != null && (
                <div style={{ color: '#64748b', fontSize: 12, marginTop: 8 }}>
                  Confidence: {(activeWindow.confidence * 100).toFixed(0)}%
                </div>
              )}
            </>
          ) : (
            <div style={{ color: '#64748b', textAlign: 'center' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>⏳</div>
              No active window
            </div>
          )}
        </div>
      </div>

      {/* ── Accuracy Stats Row ── */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 28, flexWrap: 'wrap' }}>
        <StatCard
          icon="🎯" label="Overall Accuracy"
          value={accuracy.total_predictions > 0 ? `${(accuracy.accuracy * 100).toFixed(1)}%` : '—'}
          sub={`${accuracy.correct || 0} / ${accuracy.total_predictions || 0} predictions`}
          color={accuracy.accuracy >= 0.55 ? '#22c55e' : accuracy.accuracy >= 0.50 ? '#f59e0b' : '#ef4444'}
        />
        <StatCard
          icon="📊" label="15M Accuracy"
          value={accuracy.accuracy_15m > 0 ? `${(accuracy.accuracy_15m * 100).toFixed(1)}%` : '—'}
          sub="15-minute windows"
        />
        <StatCard
          icon="🔥" label="High Conviction"
          value={accuracy.high_conviction_total > 0 ? `${(accuracy.high_conviction_accuracy * 100).toFixed(1)}%` : '—'}
          sub={`${accuracy.high_conviction_total || 0} high-prob trades`}
          color="#a855f7"
        />
        <StatCard
          icon="⏭️" label="Skip Rate"
          value={accuracy.total_signals > 0 ? `${(accuracy.skip_rate * 100).toFixed(1)}%` : '—'}
          sub={`${accuracy.total_signals || 0} total signals`}
          color="#94a3b8"
        />
        <StatCard
          icon="🏆" label="Streaks"
          value={`W${accuracy.win_streak || 0} / L${accuracy.loss_streak || 0}`}
          sub={`24h: ${accuracy.accuracy_24h > 0 ? (accuracy.accuracy_24h * 100).toFixed(0) + '%' : '—'} | 7d: ${accuracy.accuracy_7d > 0 ? (accuracy.accuracy_7d * 100).toFixed(0) + '%' : '—'}`}
        />
      </div>

      {/* ── Two-column: Factors + Windows ── */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 28, flexWrap: 'wrap' }}>
        {/* 7-Factor Signal Panel */}
        <div style={{
          background: '#111118', borderRadius: 14, padding: 24,
          border: '1px solid #1e1e2e', flex: '1 1 400px', minWidth: 360,
        }}>
          <h3 style={{ color: '#fff', fontSize: 16, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: BTC_ORANGE }}>⚡</span> Signal Factors
            {activeWindow && <WindowTypeBadge length={activeWindow.window_length} />}
          </h3>
          {factors.price_delta != null ? (
            <>
              <FactorBar name="Price Delta" weight={weights.price_delta || 0.38} value={factors.price_delta || 0} />
              <FactorBar name="Momentum" weight={weights.momentum || 0.22} value={factors.momentum || 0} />
              <FactorBar name="Volume Imbalance" weight={weights.volume_imbalance || 0.15} value={factors.volume_imbalance || 0} />
              <FactorBar name="Oracle Lead" weight={weights.oracle_lead || 0.08} value={factors.oracle_lead || 0} />
              <FactorBar name="Book Imbalance" weight={weights.book_imbalance || 0.10} value={factors.book_imbalance || 0} />
              <FactorBar name="Volatility" weight={weights.volatility || 0.05} value={factors.volatility || 0} isVolatility skipActive={volSkip} />
              <FactorBar name="Time Decay" weight={weights.time_decay || 0.02} value={factors.time_decay || 0} isVolatility />
            </>
          ) : (
            <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
              No active signals — waiting for next BTC window
            </div>
          )}
        </div>

        {/* Active Windows Table */}
        <div style={{
          background: '#111118', borderRadius: 14, padding: 24,
          border: '1px solid #1e1e2e', flex: '1 1 400px', minWidth: 360,
          overflowX: 'auto',
        }}>
          <h3 style={{ color: '#fff', fontSize: 16, margin: '0 0 16px 0' }}>
            <span style={{ color: BTC_ORANGE }}>📋</span> Active Windows
          </h3>
          {windows.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e1e2e' }}>
                  {['Type', 'Time Left', 'Open', 'Current', 'Δ', 'Signal', 'Result'].map(h => (
                    <th key={h} style={{ color: '#64748b', fontWeight: 600, padding: '8px 6px', textAlign: 'left', fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {windows.map((w, i) => {
                  const delta = w.btc_open && price ? ((price - w.btc_open) / w.btc_open * 100) : null
                  const isCorrect = w.resolution && w.prediction ? w.prediction === w.resolution : null
                  const rowBg = isCorrect === true ? '#22c55e08' : isCorrect === false ? '#ef444408' : 'transparent'
                  return (
                    <tr key={w.window_id || i} style={{ borderBottom: '1px solid #0f0f17', background: rowBg }}>
                      <td style={{ padding: '8px 6px' }}><WindowTypeBadge length={w.window_length} /></td>
                      <td style={{ padding: '8px 6px' }}><CountdownTimer closeTime={w.close_time} /></td>
                      <td style={{ padding: '8px 6px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                        {w.btc_open ? `$${w.btc_open.toLocaleString()}` : '—'}
                      </td>
                      <td style={{ padding: '8px 6px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                        ${price.toLocaleString()}
                      </td>
                      <td style={{
                        padding: '8px 6px', fontFamily: 'monospace', fontWeight: 600,
                        color: delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : '#94a3b8',
                      }}>
                        {delta != null ? `${delta >= 0 ? '+' : ''}${delta.toFixed(3)}%` : '—'}
                      </td>
                      <td style={{ padding: '8px 6px' }}>
                        <PredictionBadge prediction={w.prediction || 'SKIP'} probUp={w.prob_up} />
                      </td>
                      <td style={{ padding: '8px 6px' }}>
                        {w.resolution ? (
                          <span style={{
                            color: w.resolution === 'UP' ? '#22c55e' : '#ef4444',
                            fontWeight: 700, fontSize: 12,
                          }}>
                            {w.resolution}
                          </span>
                        ) : '⏳'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : (
            <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
              No windows tracked yet
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Signals Feed ── */}
      <div style={{
        background: '#111118', borderRadius: 14, padding: 24,
        border: '1px solid #1e1e2e',
      }}>
        <h3 style={{ color: '#fff', fontSize: 16, margin: '0 0 16px 0' }}>
          <span style={{ color: BTC_ORANGE }}>📡</span> Recent Signals
        </h3>
        {signals.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e1e2e' }}>
                  {['Time', 'Type', 'Secs Left', 'Prediction', 'Prob UP', 'Confidence', 'Result', ''].map(h => (
                    <th key={h} style={{ color: '#64748b', fontWeight: 600, padding: '8px 6px', textAlign: 'left', fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.map((sig, i) => {
                  const isExpanded = expandedSignal === sig.id
                  return (
                    <React.Fragment key={sig.id || i}>
                      <tr
                        style={{ borderBottom: '1px solid #0f0f17', cursor: 'pointer' }}
                        onClick={() => setExpandedSignal(isExpanded ? null : sig.id)}
                      >
                        <td style={{ padding: '8px 6px', color: '#94a3b8', fontFamily: 'monospace', fontSize: 12 }}>
                          {sig.signal_ts ? new Date(sig.signal_ts).toLocaleTimeString() : '--'}
                        </td>
                        <td style={{ padding: '8px 6px' }}><WindowTypeBadge length={sig.window_length} /></td>
                        <td style={{ padding: '8px 6px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                          {sig.seconds_remaining || '—'}s
                        </td>
                        <td style={{ padding: '8px 6px' }}>
                          <PredictionBadge prediction={sig.prediction} probUp={sig.prob_up} />
                        </td>
                        <td style={{ padding: '8px 6px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                          {(sig.prob_up * 100).toFixed(1)}%
                        </td>
                        <td style={{ padding: '8px 6px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                          {sig.confidence ? (sig.confidence * 100).toFixed(0) + '%' : '—'}
                        </td>
                        <td style={{ padding: '8px 6px' }}>
                          <ResultBadge wasCorrect={sig.was_correct} />
                          {sig.resolution && (
                            <span style={{ marginLeft: 6, color: '#64748b', fontSize: 11 }}>
                              ({sig.resolution})
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 6px', color: '#64748b', fontSize: 16 }}>
                          {isExpanded ? '▲' : '▼'}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={8} style={{ padding: '12px 24px', background: '#0a0a12' }}>
                            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                              {Object.entries(sig.factors || {}).map(([key, val]) => (
                                <div key={key} style={{ minWidth: 120 }}>
                                  <div style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase' }}>{key.replace('_', ' ')}</div>
                                  <div style={{
                                    color: val > 0.05 ? '#22c55e' : val < -0.05 ? '#ef4444' : '#94a3b8',
                                    fontFamily: 'monospace', fontWeight: 600, fontSize: 14,
                                  }}>
                                    {typeof val === 'number' ? val.toFixed(4) : val}
                                  </div>
                                </div>
                              ))}
                              {sig.skip_reason && (
                                <div style={{ minWidth: 200 }}>
                                  <div style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase' }}>Skip Reason</div>
                                  <div style={{ color: '#f59e0b', fontSize: 12 }}>{sig.skip_reason}</div>
                                </div>
                              )}
                              {sig.btc_open != null && sig.btc_close != null && (
                                <div style={{ minWidth: 200 }}>
                                  <div style={{ color: '#64748b', fontSize: 11, textTransform: 'uppercase' }}>BTC Open → Close</div>
                                  <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: 13 }}>
                                    ${sig.btc_open?.toLocaleString()} → ${sig.btc_close?.toLocaleString()}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
            No signals yet — engine will start generating predictions when BTC windows are active
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div style={{ textAlign: 'center', color: '#334155', fontSize: 11, marginTop: 32, paddingBottom: 16 }}>
        Powered by Claude + OpenClaw + Actual Intelligence
      </div>
    </div>
  )
}
